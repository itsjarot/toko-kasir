-- Jalankan di Supabase: SQL Editor > New query > Run
create extension if not exists "pgcrypto";

create table if not exists produk (
  id uuid primary key default gen_random_uuid(),
  nama text not null,
  kategori text,
  harga numeric(12,0) not null check (harga >= 0),
  stok integer not null default 0 check (stok >= 0),
  created_at timestamptz not null default now()
);

create table if not exists transaksi (
  id uuid primary key default gen_random_uuid(),
  total numeric(12,0) not null default 0,
  metode_bayar text not null default 'tunai',
  created_at timestamptz not null default now()
);

create table if not exists transaksi_item (
  id uuid primary key default gen_random_uuid(),
  transaksi_id uuid not null references transaksi(id) on delete cascade,
  produk_id uuid references produk(id) on delete set null,
  nama_produk text not null,
  harga numeric(12,0) not null,
  qty integer not null check (qty > 0),
  subtotal numeric(12,0) not null
);

create index if not exists idx_transaksi_created on transaksi(created_at desc);

-- Fungsi checkout atomik: semua berhasil atau semua dibatalkan.
-- Harga diambil dari database, bukan dari browser, jadi tidak bisa dimanipulasi.
create or replace function buat_transaksi(p_items jsonb, p_metode text)
returns uuid
language plpgsql
as $$
declare
  v_id uuid;
  v_total numeric := 0;
  it jsonb;
  p produk%rowtype;
  v_qty int;
begin
  if p_items is null or jsonb_array_length(p_items) = 0 then
    raise exception 'Keranjang kosong';
  end if;

  insert into transaksi(total, metode_bayar) values (0, p_metode) returning id into v_id;

  for it in select * from jsonb_array_elements(p_items) loop
    v_qty := (it->>'qty')::int;
    select * into p from produk where id = (it->>'id')::uuid for update;
    if not found then raise exception 'Produk tidak ditemukan'; end if;
    if v_qty <= 0 then raise exception 'Jumlah tidak valid'; end if;
    if p.stok < v_qty then raise exception 'Stok % tidak cukup (sisa %)', p.nama, p.stok; end if;

    update produk set stok = stok - v_qty where id = p.id;
    insert into transaksi_item(transaksi_id, produk_id, nama_produk, harga, qty, subtotal)
    values (v_id, p.id, p.nama, p.harga, v_qty, p.harga * v_qty);
    v_total := v_total + p.harga * v_qty;
  end loop;

  update transaksi set total = v_total where id = v_id;
  return v_id;
end;
$$;

-- Keamanan: aktifkan RLS tanpa policy. Hanya server Python (service_role) yang bisa akses.
alter table produk enable row level security;
alter table transaksi enable row level security;
alter table transaksi_item enable row level security;
