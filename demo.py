"""Local visual demo for the Kasir Toko UI; uses in-memory sample data only."""
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = "local-demo-only"


@app.context_processor
def inject_demo_mode():
    return {"demo_mode": True}


WIB = ZoneInfo("Asia/Jakarta")

products = [
    {"id": "p01", "nama": "Kopi Susu Gula Aren", "kategori": "Minuman", "harga": 18000, "stok": 14},
    {"id": "p02", "nama": "Es Teh Nusantara", "kategori": "Minuman", "harga": 7000, "stok": 23},
    {"id": "p03", "nama": "Roti Bakar Cokelat", "kategori": "Makanan", "harga": 16000, "stok": 8},
    {"id": "p04", "nama": "Nasi Ayam Sambal Matah", "kategori": "Makanan", "harga": 28000, "stok": 6},
    {"id": "p05", "nama": "Kentang Goreng", "kategori": "Snack", "harga": 15000, "stok": 12},
    {"id": "p06", "nama": "Air Mineral 600 ml", "kategori": "Minuman", "harga": 5000, "stok": 18},
    {"id": "p07", "nama": "Pisang Goreng", "kategori": "Snack", "harga": 12000, "stok": 3},
    {"id": "p08", "nama": "Americano", "kategori": "Minuman", "harga": 15000, "stok": 9},
]


def make_transaction(tx_id, when, method, lines):
    by_id = {p["id"]: p for p in products}
    items = []
    total = 0
    for product_id, qty in lines:
        product = by_id[product_id]
        subtotal = product["harga"] * qty
        total += subtotal
        items.append({"produk_id": product_id, "nama_produk": product["nama"], "harga": product["harga"], "qty": qty, "subtotal": subtotal})
    return {"id": tx_id, "total": total, "metode_bayar": method, "created_at": when.isoformat(), "transaksi_item": items}


_now = datetime.now(WIB)
transactions = [
    make_transaction("TRX-1048", _now - timedelta(minutes=18), "qris", [("p01", 2), ("p03", 1)]),
    make_transaction("TRX-1047", _now - timedelta(hours=1, minutes=12), "tunai", [("p04", 1), ("p06", 1)]),
    make_transaction("TRX-1046", _now - timedelta(hours=2, minutes=35), "tunai", [("p02", 2), ("p07", 1)]),
    make_transaction("TRX-1045", _now - timedelta(hours=5), "transfer", [("p01", 1), ("p05", 1)]),
    make_transaction("TRX-1044", _now - timedelta(days=1, hours=2), "qris", [("p04", 1), ("p02", 1)]),
    make_transaction("TRX-1043", _now - timedelta(days=2, hours=4), "tunai", [("p01", 2), ("p08", 1)]),
    make_transaction("TRX-1042", _now - timedelta(days=3, hours=1), "qris", [("p03", 2), ("p06", 2)]),
    make_transaction("TRX-1041", _now - timedelta(days=5, hours=3), "transfer", [("p04", 1), ("p05", 1)]),
]


@app.template_filter("rupiah")
def rupiah(value):
    return "Rp " + f"{int(value or 0):,}".replace(",", ".")


@app.template_filter("tgl")
def tgl(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(WIB)
    return dt.strftime("%d/%m/%Y %H:%M")


def next_product_id():
    return f"p{max(int(p['id'][1:]) for p in products) + 1:02d}"


@app.route("/")
def dashboard():
    now = datetime.now(WIB)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def as_datetime(row):
        return datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")).astimezone(WIB)

    today_rows = [row for row in transactions if as_datetime(row) >= today_start]
    month_rows = [row for row in transactions if as_datetime(row) >= month_start]
    per_day = defaultdict(int)
    sold = defaultdict(int)
    for row in transactions:
        dt = as_datetime(row)
        per_day[dt.date()] += row["total"]
        for item in row["transaksi_item"]:
            sold[item["nama_produk"]] += item["qty"]

    grafik = []
    for days_ago in range(6, -1, -1):
        date = (now - timedelta(days=days_ago)).date()
        grafik.append({"label": date.strftime("%d/%m"), "total": per_day[date]})
    maks = max((day["total"] for day in grafik), default=1) or 1

    return render_template(
        "dashboard.html", halaman="dashboard",
        pendapatan_hari=sum(row["total"] for row in today_rows),
        transaksi_hari=len(today_rows),
        pendapatan_bulan=sum(row["total"] for row in month_rows),
        transaksi_bulan=len(month_rows), grafik=grafik, maks=maks,
        terlaris=sorted(sold.items(), key=lambda pair: pair[1], reverse=True)[:5],
    )


@app.route("/kasir")
def kasir():
    return render_template("kasir.html", halaman="kasir", produk=sorted(products, key=lambda p: p["nama"]))


@app.post("/api/checkout")
def checkout():
    data = request.get_json(silent=True) or {}
    method = data.get("metode", "tunai")
    items = data.get("items", [])
    if method not in ("tunai", "qris", "transfer"):
        return jsonify(error="Metode pembayaran tidak valid"), 400
    if not items:
        return jsonify(error="Keranjang masih kosong"), 400

    lines = []
    for item in items:
        product = next((p for p in products if p["id"] == str(item.get("id"))), None)
        qty = int(item.get("qty", 0))
        if product is None or qty <= 0:
            return jsonify(error="Produk atau jumlah tidak valid"), 400
        if product["stok"] < qty:
            return jsonify(error=f"Stok {product['nama']} tidak cukup"), 400
        lines.append((product["id"], qty))

    for product_id, qty in lines:
        next(p for p in products if p["id"] == product_id)["stok"] -= qty
    tx_id = f"TRX-{1049 + len(transactions) - 8:04d}"
    transaction = make_transaction(tx_id, datetime.now(WIB), method, lines)
    transactions.insert(0, transaction)
    return jsonify(ok=True, id=tx_id)


@app.route("/produk", methods=["GET", "POST"])
def produk():
    if request.method == "POST":
        try:
            products.append({
                "id": next_product_id(),
                "nama": request.form["nama"].strip(),
                "kategori": request.form.get("kategori", "").strip() or None,
                "harga": int(request.form["harga"]),
                "stok": int(request.form["stok"]),
            })
            flash("Produk demo ditambahkan.", "success")
        except (KeyError, ValueError):
            flash("Periksa kembali data produk.", "error")
        return redirect(url_for("produk"))
    return render_template("produk.html", halaman="produk", produk=sorted(products, key=lambda p: p["nama"]))


@app.post("/produk/<pid>/stok")
def tambah_stok(pid):
    product = next((p for p in products if p["id"] == pid), None)
    if product is None:
        flash("Produk tidak ditemukan.", "error")
    else:
        try:
            amount = int(request.form["tambah"])
            product["stok"] = max(0, product["stok"] + amount)
            flash("Stok demo diperbarui.", "success")
        except (KeyError, ValueError):
            flash("Jumlah stok tidak valid.", "error")
    return redirect(url_for("produk"))


@app.post("/produk/<pid>/hapus")
def hapus_produk(pid):
    product = next((p for p in products if p["id"] == pid), None)
    if product:
        products.remove(product)
        flash("Produk dihapus dari data demo.", "success")
    return redirect(url_for("produk"))


@app.route("/riwayat")
def riwayat():
    ordered = sorted(transactions, key=lambda row: row["created_at"], reverse=True)[:100]
    return render_template("riwayat.html", halaman="riwayat", transaksi=ordered)


if __name__ == "__main__":
    print("Kasir Toko — DEMO lokal (data contoh hanya tersimpan di memori)")
    app.run(host="127.0.0.1", port=5001, debug=False)
