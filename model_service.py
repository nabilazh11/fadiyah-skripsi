"""Pemuat model dua tahap dan fungsi deteksi. Model hanya dimuat, tidak dilatih ulang."""
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
MODEL_PATH = BASE / "model" / "ddos_two_stage_model.pkl"
METRICS_PATH = BASE / "model" / "metrics.json"


def signed_log1p(X):
    """Meredam ekor distribusi, aman untuk nilai negatif (mis. Init Fwd Win Bytes = -1)."""
    X = np.asarray(X, dtype=np.float64)
    return np.sign(X) * np.log1p(np.abs(X))


def apply_stage1(data, st):
    """Aturan Tahap 1. True = ditandai serangan."""
    if st["type"] == "rate":
        mask = np.zeros(len(data), dtype=bool)
        for f, t in st["thresholds"].items():
            mask |= data[f].values > t
        return mask
    X = data[st["features"]].values
    return ((X < st["lo"]) | (X > st["hi"])).sum(axis=1) >= st["k"]


# Pipeline model menyimpan acuan ke signed_log1p pada modul __main__ saat pelatihan.
sys.modules["__main__"].signed_log1p = signed_log1p
sys.modules["__main__"].apply_stage1 = apply_stage1

if not MODEL_PATH.exists():
    raise SystemExit(
        f"Berkas model tidak ditemukan di {MODEL_PATH}.\n"
        "Jalankan notebook/model_ddos_two_stage.ipynb sampai selesai lebih dulu, "
        "atau salin ddos_two_stage_model.pkl ke folder model/."
    )

BUNDLE = joblib.load(MODEL_PATH)
FEATURES = BUNDLE["features"]
STAGE1 = BUNDLE["stage1"]
PREPROC = BUNDLE["preprocessor"]
OCSVM = BUNDLE["ocsvm"]
DEFAULT_THRESHOLD = float(BUNDLE["stage2_threshold"])
CONFIG = BUNDLE.get("config", {})


def info_model():
    """Ringkasan konfigurasi untuk halaman Model dan status di bilah atas."""
    st = STAGE1
    if st["type"] == "rate":
        rancangan, rincian = "Ambang atas fitur laju", list(st["thresholds"])
    else:
        rancangan, rincian = "Pita persentil seluruh fitur", [f"Ambang suara K = {st['k']}"]
    return {
        "fitur": FEATURES,
        "jumlah_fitur": len(FEATURES),
        "stage1_rancangan": rancangan,
        "stage1_rincian": rincian,
        "stage1_nama": st.get("name", rancangan),
        "kernel": OCSVM.kernel.upper(),
        "nu": CONFIG.get("nu", OCSVM.nu),
        "gamma": CONFIG.get("gamma", OCSVM.gamma),
        "support_vector": int(len(OCSVM.support_)),
        "ambang": DEFAULT_THRESHOLD,
        "anggaran_fpr": CONFIG.get("system_max_fpr", 0.05),
        "berkas_model": MODEL_PATH.name,
        "ukuran_model_mb": round(MODEL_PATH.stat().st_size / 1e6, 2),
    }


def metrik_penelitian():
    if METRICS_PATH.exists():
        return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    return {"komposisi": [], "ablation": [], "per_serangan": [], "catatan": ""}


def baca_berkas(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    raise ValueError("Format berkas belum didukung. Pakai .csv, .parquet, atau .xlsx.")


def siapkan(df):
    """Menyamakan nama kolom dan memastikan seluruh fitur model tersedia."""
    df = df.copy()
    df.columns = df.columns.str.strip()
    kurang = [f for f in FEATURES if f not in df.columns]
    if kurang:
        raise ValueError(f"{len(kurang)} kolom fitur tidak ada pada berkas, antara lain: {kurang[:5]}")
    df[FEATURES] = (df[FEATURES].replace([np.inf, -np.inf], np.nan)
                    .fillna(0).astype("float64"))
    return df


def evaluasi(y, pred, skor=None):
    y, pred = np.asarray(y), np.asarray(pred)
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    bagi = lambda a, b: a / b if b else 0.0
    precision, recall = bagi(tp, tp + fp), bagi(tp, tp + fn)
    hasil = {
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": bagi(tp + tn, tp + tn + fp + fn),
        "precision": precision,
        "recall": recall,
        "f1": bagi(2 * precision * recall, precision + recall),
        "fpr": bagi(fp, fp + tn),
        "roc_auc": None,
    }
    if skor is not None and len(np.unique(y)) == 2:
        try:
            from sklearn.metrics import roc_auc_score
            hasil["roc_auc"] = round(float(roc_auc_score(y, skor)), 4)
        except Exception:
            pass
    return hasil


def deteksi(df):
    """Menjalankan deteksi dua tahap. Ambang selalu dari nilai kalibrasi model."""
    ambang = DEFAULT_THRESHOLD
    data = siapkan(df)

    mulai = time.perf_counter()
    s1 = apply_stage1(data, STAGE1)

    skor = np.full(len(data), np.nan)
    lolos = ~s1
    if lolos.any():
        X = PREPROC.transform(data.loc[lolos, FEATURES])
        skor[lolos] = -OCSVM.decision_function(X)

    s2 = np.zeros(len(data), dtype=bool)
    s2[lolos] = skor[lolos] >= ambang
    pred = s1 | s2
    durasi = time.perf_counter() - mulai

    hasil = data.copy()
    hasil["skor_ocsvm"] = skor
    hasil["prediksi"] = pred.astype(int)
    hasil["hasil_deteksi"] = np.where(pred, "Serangan", "Normal")
    hasil["diputus_oleh"] = np.where(s1, "Tahap 1", np.where(s2, "Tahap 2", "—"))

    ringkas = {
        "total": int(len(data)),
        "serangan": int(pred.sum()),
        "normal": int((~pred).sum()),
        "tahap1": int(s1.sum()),
        "tahap2": int(s2.sum()),
        "diperiksa_ocsvm": int(lolos.sum()),
        "durasi": round(durasi, 3),
        "ms_per_flow": round(durasi / max(len(data), 1) * 1000, 4),
        "ambang": ambang,
        "punya_label": False,
    }

    kolom_label = next((c for c in ("Label", "label", "LABEL") if c in df.columns), None)
    if kolom_label:
        label = df[kolom_label].astype(str).str.strip()
        y = (~label.str.lower().eq("benign")).astype(int).values
        hasil["label_asli"] = label.values
        skor_lengkap = np.where(s1, ambang + 1, skor)   # Tahap-1 flow pasti di atas ambang
        ringkas.update(evaluasi(y, pred, skor=skor_lengkap), punya_label=True)
        ringkas["per_serangan"] = rincian_per_serangan(label.values, y, pred, s1)
    return hasil, ringkas


def rincian_per_serangan(label, y, pred, s1):
    tabel = pd.DataFrame({"label": label, "y": y, "pred": pred, "s1": s1})
    baris = []
    for nama, sub in tabel[tabel["y"] == 1].groupby("label"):
        t1, total = int(sub["s1"].sum()), int(sub["pred"].sum())
        baris.append({"label": nama, "sampel": len(sub), "tahap1": t1,
                      "tahap2": total - t1, "recall": total / len(sub)})
    return sorted(baris, key=lambda r: r["recall"], reverse=True)


KOLOM_TAMPIL = ["Flow Packets/s", "Flow Bytes/s", "Packet Length Mean", "Total Fwd Packets"]


def baris_tampil(hasil, batas=300, saring="semua"):
    """Sebagian baris untuk ditampilkan di tabel halaman hasil."""
    sub = hasil
    if saring == "serangan":
        sub = sub[sub["prediksi"] == 1]
    elif saring == "normal":
        sub = sub[sub["prediksi"] == 0]
    kolom = [c for c in KOLOM_TAMPIL if c in sub.columns]
    baris = []
    for i, (_, r) in enumerate(sub.head(batas).iterrows(), start=1):
        baris.append({
            "no": i,
            "nilai": [f"{r[c]:,.2f}" for c in kolom],
            "skor": "—" if pd.isna(r["skor_ocsvm"]) else f"{r['skor_ocsvm']:.4f}",
            "hasil": r["hasil_deteksi"],
            "tahap": r["diputus_oleh"],
            "label": r.get("label_asli", "—"),
        })
    return kolom, baris, int(len(sub))