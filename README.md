# Kasir Toko (Flask + Supabase)

## Demo tampilan lokal (tanpa Supabase)
Untuk melihat seluruh halaman dengan data contoh, jalankan dari folder proyek:

```bash
python3 demo.py
```

Lalu buka http://127.0.0.1:5001. Mode ini memakai data contoh di memori; perubahan stok/produk/transaksi hanya untuk sesi demo dan akan kembali seperti semula setelah server dimatikan. Tidak perlu mengisi `.env` atau menyiapkan Supabase.

## Struktur
```
kasir/
├── app.py                    # versi aplikasi yang terhubung ke Supabase
├── demo.py                   # server demo lokal dengan data contoh
├── schema.sql
├── requirements.txt
├── .env                      # buat dari .env.example untuk aplikasi Supabase
├── static/css/style.css
└── templates/ (base, dashboard, kasir, produk, riwayat)
```

## Menjalankan aplikasi dengan Supabase
1. Buat project Supabase, buka SQL Editor, lalu jalankan isi `schema.sql`.
2. Salin `.env.example` menjadi `.env`; isi URL dan service role key dari Project Settings > API. Jangan bagikan atau commit file `.env`.
3. Siapkan CSS di `static/css/style.css`.
4. Pasang dependensi dan jalankan:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

5. Buka http://127.0.0.1:5000.
