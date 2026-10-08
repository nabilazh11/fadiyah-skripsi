# Sistem Deteksi Anomali DDoS — Threshold + One-Class SVM

Antarmuka web untuk menjalankan model deteksi anomali dua tahap: penyaringan **threshold statistik**
pada tahap pertama, lalu klasifikasi **One-Class SVM** pada tahap kedua. Aplikasi hanya memuat model
yang sudah dilatih — tidak ada pelatihan ulang saat deteksi berjalan.

Skripsi Fadiyah Sri Muthiah, Teknik Informatika, UIN Alauddin Makassar.

## Menjalankan (3 langkah)

**1. Letakkan model.** Salin `ddos_two_stage_model.pkl` hasil notebook ke folder `model/`:

    model/ddos_two_stage_model.pkl

Bila notebook juga menghasilkan `metrics.json`, salin ke folder yang sama agar halaman Dasbor
menampilkan angka hasil penelitian. Tanpa berkas itu sistem tetap berjalan.

**2. Pasang pustaka.**

    pip install -r requirements.txt

**3. Nyalakan.**

    python app.py

Buka `http://127.0.0.1:5000` di peramban. Hentikan dengan `Ctrl+C`.
Bila port 5000 sudah terpakai, ubah angka port pada baris terakhir `app.py`.

## Mencoba sistem

Masuk ke menu **Deteksi**, lalu tekan **Pakai berkas** pada `contoh_flow.csv` yang sudah disertakan.
Untuk berkas sendiri, unggah `.csv`, `.parquet`, atau `.xlsx` berisi fitur hasil ekstraksi CICFlowMeter,
maksimal 50 MB. Nama kolom harus sama dengan yang dipakai model — daftar lengkapnya ada di halaman
**Model**, dan bila ada yang kurang aplikasi menyebutkan kolom mana saja yang hilang.

Kolom `Label` bersifat opsional. Bila ada, sistem sekaligus menghitung accuracy, precision, recall,
F1-score, false positive rate, confusion matrix, dan recall per jenis serangan.

## Menu

| Menu | Isi |
|---|---|
| Dasbor | Ringkasan hasil model: metrik data uji, skema dua tahap, perbandingan komponen, komposisi data, recall per jenis serangan |
| Deteksi | Unggah berkas rekaman flow, atur ambang Tahap 2, jalankan model |
| Hasil deteksi | Keputusan tiap tahap, evaluasi, confusion matrix, dan rincian per flow |
| Riwayat | 30 pemeriksaan terakhir, dapat dibuka dan diunduh kembali |
| Model | Konfigurasi model dan daftar fitur yang diperiksa |

## Isi folder

```
ddos_detection_system/
├── app.py                  rute web (Flask)
├── model_service.py        pemuat model + fungsi deteksi dua tahap
├── requirements.txt
├── model/                  <- letakkan ddos_two_stage_model.pkl di sini
├── data/contoh_flow.csv    berkas contoh untuk mencoba sistem
├── notebook/
│   └── model_ddos_two_stage.ipynb   pelatihan model (opsional, bila ingin melatih ulang)
├── dataset/                tempat berkas .parquet CSE-CIC-IDS2018 bila notebook dijalankan
├── artefak/                tabel dan grafik evaluasi keluaran notebook
├── storage/                riwayat pemeriksaan dan berkas hasil
├── uploads/                berkas yang diunggah lewat halaman Deteksi
├── templates/              halaman web
└── static/                 style.css dan app.js
```

## Melatih ulang model (opsional)

Bila model perlu dibuat ulang, salin berkas `.parquet` CSE-CIC-IDS2018 ke folder `dataset/`,
lalu jalankan `notebook/model_ddos_two_stage.ipynb` dari atas ke bawah. Notebook menulis sendiri
`model/ddos_two_stage_model.pkl`, `model/metrics.json`, berkas contoh di `data/`, serta tabel
dan grafik evaluasi di `artefak/`.

## Catatan teknis

- Ambang skor Tahap 2 pada halaman Deteksi dapat diubah tanpa melatih ulang model.
  Nilai bawaan adalah hasil kalibrasi pada data validasi dengan anggaran FPR 5%.
- Riwayat menyimpan 30 pemeriksaan terakhir pada `storage/history.json`,
  tabel hasilnya disimpan sebagai CSV di `storage/results/`.
- Fungsi `signed_log1p` didaftarkan ke `__main__` sebelum `joblib.load`,
  karena fungsi itu ikut tersimpan di dalam `Pipeline` saat model dilatih.
