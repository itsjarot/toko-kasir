import os
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from supabase import create_client

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only")
db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
WIB = ZoneInfo("Asia/Jakarta")


@app.template_filter("rupiah")
def rupiah(n):
    return "Rp " + f"{int(n or 0):,}".replace(",", ".")


@app.template_filter("tgl")
def tgl(iso):
    d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(WIB)
    return d.strftime("%d/%m/%Y %H:%M")


def awal_hari(offset_hari=0):
    now = datetime.now(WIB)
    return (now - timedelta(days=offset_hari)).replace(hour=0, minute=0, second=0, microsecond=0)


def jumlah(rows):
    return sum(int(r["total"]) for r in rows)


# ---------- Dashboard ----------
@app.route("/")
def dashboard():
    now = datetime.now(WIB)
    awal_bulan = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start7 = awal_hari(6)

    rows = (
        db.table("transaksi")
        .select("total,created_at")
        .gte("created_at", min(awal_bulan, start7).isoformat())
        .execute()
        .data
    )

    def dt(r):
        return datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).astimezone(WIB)

    hari_ini = [r for r in rows if dt(r) >= awal_hari()]
    bulan_ini = [r for r in rows if dt(r) >= awal_bulan]

    per_hari = defaultdict(int)
    for r in rows:
        per_hari[dt(r).date()] += int(r["total"])
    grafik = []
    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).date()
        grafik.append({"label": d.strftime("%d/%m"), "total": per_hari.get(d, 0)})
    maks = max([g["total"] for g in grafik] + [1])

    terlaris = {}
    items = db.table("transaksi_item").select("nama_produk,qty").limit(2000).execute().data
    for it in items:
        terlaris[it["nama_produk"]] = terlaris.get(it["nama_produk"], 0) + it["qty"]
    terlaris = sorted(terlaris.items(), key=lambda x: x[1], reverse=True)[:5]

    return render_template(
        "dashboard.html",
        halaman="dashboard",
        pendapatan_hari=jumlah(hari_ini),
        transaksi_hari=len(hari_ini),
        pendapatan_bulan=jumlah(bulan_ini),
        transaksi_bulan=len(bulan_ini),
        grafik=grafik,
        maks=maks,
        terlaris=terlaris,
    )


# ---------- Kasir ----------
@app.route("/kasir")
def kasir():
    produk = db.table("produk").select("*").order("nama").execute().data
    return render_template("kasir.html", halaman="kasir", produk=produk)


@app.post("/api/checkout")
def checkout():
    data = request.get_json(silent=True) or {}
    items = [
        {"id": i["id"], "qty": int(i["qty"])}
        for i in data.get("items", [])
        if int(i.get("qty", 0)) > 0
    ]
    metode = data.get("metode", "tunai")
    if metode not in ("tunai", "qris", "transfer"):
        return jsonify(error="Metode bayar tidak valid"), 400
    try:
        res = db.rpc("buat_transaksi", {"p_items": items, "p_metode": metode}).execute()
        return jsonify(ok=True, id=res.data)
    except Exception as e:
        return jsonify(error=getattr(e, "message", str(e))), 400


# ---------- Produk ----------
@app.route("/produk", methods=["GET", "POST"])
def produk():
    if request.method == "POST":
        try:
            db.table("produk").insert(
                {
                    "nama": request.form["nama"].strip(),
                    "kategori": request.form.get("kategori", "").strip() or None,
                    "harga": int(request.form["harga"]),
                    "stok": int(request.form["stok"]),
                }
            ).execute()
            flash("Produk ditambahkan.", "success")
        except Exception as e:
            flash(f"Gagal menambah produk: {e}", "error")
        return redirect(url_for("produk"))
    rows = db.table("produk").select("*").order("nama").execute().data
    return render_template("produk.html", halaman="produk", produk=rows)


@app.post("/produk/<pid>/stok")
def tambah_stok(pid):
    try:
        p = db.table("produk").select("stok").eq("id", pid).single().execute().data
        db.table("produk").update({"stok": p["stok"] + int(request.form["tambah"])}).eq("id", pid).execute()
        flash("Stok diperbarui.", "success")
    except Exception as e:
        flash(f"Gagal memperbarui stok: {e}", "error")
    return redirect(url_for("produk"))


@app.post("/produk/<pid>/hapus")
def hapus_produk(pid):
    db.table("produk").delete().eq("id", pid).execute()
    flash("Produk dihapus. Riwayat transaksi tetap tersimpan.", "success")
    return redirect(url_for("produk"))


# ---------- Riwayat ----------
@app.route("/riwayat")
def riwayat():
    rows = (
        db.table("transaksi")
        .select("id,total,metode_bayar,created_at,transaksi_item(nama_produk,qty)")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
        .data
    )
    return render_template("riwayat.html", halaman="riwayat", transaksi=rows)


if __name__ == "__main__":
    app.run(debug=True)
