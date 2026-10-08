"""Sistem web deteksi anomali DDoS — arsitektur dua tahap Threshold + One-Class SVM."""
import json
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import (Flask, abort, flash, redirect, render_template,
                   request, send_file, url_for)
from werkzeug.utils import secure_filename

import model_service as ms

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
RESULTS = BASE / "storage" / "results"
HISTORY = BASE / "storage" / "history.json"
CONTOH = BASE / "data"
IZIN = {".csv", ".parquet", ".xlsx", ".xls"}
MAKS_RIWAYAT = 30

app = Flask(__name__)
app.secret_key = "ddos-two-stage"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024   # 50 MB

INFO = ms.info_model()


# ------------------------------------------------------------------ riwayat
def baca_riwayat():
    if HISTORY.exists():
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    return []


def simpan_riwayat(catatan):
    data = [catatan] + baca_riwayat()
    for usang in data[MAKS_RIWAYAT:]:
        (RESULTS / f"{usang['id']}.csv").unlink(missing_ok=True)
    data = data[:MAKS_RIWAYAT]
    HISTORY.write_text(json.dumps(data, indent=2), encoding="utf-8")


def ambil_catatan(run_id):
    return next((c for c in baca_riwayat() if c["id"] == run_id), None)


@app.context_processor
def bekal_template():
    return {"info": INFO, "now": datetime.now()}


# ------------------------------------------------------------------ halaman
@app.route("/")
def dasbor():
    m = ms.metrik_penelitian()
    utama = next((a for a in m["ablation"] if "usulan" in a["nama"].lower()),
                 m["ablation"][-1] if m["ablation"] else None)
    return render_template("dasbor.html", m=m, utama=utama)


@app.route("/deteksi", methods=["GET", "POST"])
def deteksi():
    contoh = sorted(p.name for p in CONTOH.glob("*") if p.suffix.lower() in IZIN)

    if request.method == "POST":
        # Ambang selalu menggunakan nilai kalibrasi dari model — tidak diambil dari form.
        pilihan = request.form.get("contoh")

        if pilihan:
            path, nama = CONTOH / pilihan, pilihan
        else:
            berkas = request.files.get("berkas")
            if not berkas or not berkas.filename:
                flash("Pilih berkas rekaman flow lebih dulu.")
                return redirect(url_for("deteksi"))
            nama = secure_filename(berkas.filename)
            if Path(nama).suffix.lower() not in IZIN:
                flash("Format berkas belum didukung. Pakai .csv, .parquet, atau .xlsx.")
                return redirect(url_for("deteksi"))
            path = UPLOADS / nama
            berkas.save(path)

        try:
            df = ms.baca_berkas(path)
            hasil, ringkas = ms.deteksi(df)
        except Exception as e:                      # berkas tidak sesuai bentuk model
            flash(str(e))
            return redirect(url_for("deteksi"))

        run_id = uuid.uuid4().hex[:10]
        hasil.to_csv(RESULTS / f"{run_id}.csv", index=False)
        simpan_riwayat({
            "id": run_id, "berkas": nama,
            "waktu": datetime.now().strftime("%d %b %Y, %H:%M"),
            "ringkas": ringkas,
        })
        return redirect(url_for("hasil", run_id=run_id))

    return render_template("deteksi.html", contoh=contoh)


@app.route("/hasil/<run_id>")
def hasil(run_id):
    catatan = ambil_catatan(run_id) or abort(404)
    saring = request.args.get("saring", "semua")
    tabel = pd.read_csv(RESULTS / f"{run_id}.csv", low_memory=False)
    kolom, baris, jumlah = ms.baris_tampil(tabel, saring=saring)
    return render_template("hasil.html", c=catatan, r=catatan["ringkas"],
                           kolom=kolom, baris=baris, jumlah=jumlah, saring=saring)


@app.route("/hasil/<run_id>/unduh")
def unduh(run_id):
    catatan = ambil_catatan(run_id) or abort(404)
    return send_file(RESULTS / f"{run_id}.csv", as_attachment=True,
                     download_name=f"hasil_deteksi_{catatan['berkas']}")


@app.route("/riwayat")
def riwayat():
    data = baca_riwayat()
    berlabel = [c["ringkas"]["accuracy"] for c in data if c["ringkas"].get("punya_label")]
    ikhtisar = {
        "jumlah": len(data),
        "flow": sum(c["ringkas"]["total"] for c in data),
        "accuracy": sum(berlabel) / len(berlabel) if berlabel else None,
        "maks": MAKS_RIWAYAT,
    }
    return render_template("riwayat.html", data=data, ikhtisar=ikhtisar)


@app.route("/riwayat/kosongkan", methods=["POST"])
def kosongkan():
    for c in baca_riwayat():
        (RESULTS / f"{c['id']}.csv").unlink(missing_ok=True)
    HISTORY.write_text("[]", encoding="utf-8")
    return redirect(url_for("riwayat"))


@app.route("/model")
def model():
    return render_template("model.html")


@app.template_filter("persen")
def persen(v, desimal=2):
    return "—" if v is None else f"{v * 100:.{desimal}f}%".replace(".", ",")


@app.template_filter("angka")
def angka(v):
    return "—" if v is None else f"{v:,.0f}".replace(",", ".")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)