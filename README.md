# 📊 Pipeline Screening Saham Harian IHSG (Institutional Grade)

Pipeline Python tingkat lanjut untuk *screening* saham harian (T+1 trading) berdasarkan probabilitas matematis, volatilitas, bandarmologi, aliran dana asing, dan sentimen orderbook.

Sistem ini menggunakan **Machine Learning (Multi-Cluster XGBoost)** dan mengombinasikan **Data Historis (Yahoo Finance)** dengan **Data Riil Bursa (IDX API)** untuk mencari saham dengan potensi kenaikan tertinggi di hari berikutnya. Tidak ada lagi data simulasi (mock), 100% menggunakan data pasar riil.

---

## 🌟 Fitur Utama (v3.5 Advanced)

- **100% Real Data Integration:**
  - Historis 3 tahun dari **Yahoo Finance** (`yfinance`).
  - Data sentimen riil dari **API Resmi BEI (IDX)**.
- **Bypass Cloudflare IDX:** Terintegrasi dengan `curl_cffi` (teknik impersonasi Chrome) yang memungkinkan skrip ini mengambil data langsung dari `idx.co.id` dari jaringan mana pun di dunia tanpa terkena blokir 403 Forbidden.
- **Machine Learning: Cluster-then-Predict Architecture:**
  - **Unsupervised Learning (K-Means):** AI secara otomatis menghitung *Profil Historis* (volatilitas dan rata-rata likuiditas log-transformed) tiap saham, lalu membagi ratusan saham ke dalam klaster yang berbeda (Blue-chip, Gorengan, Medium).
  - **Supervised Learning (Multi-XGBoost):** AI melatih model spesialis terpisah untuk setiap klaster. Saham gorengan dievaluasi dengan cara yang berbeda dari saham blue-chip.
- **Auto-Tuning Hyperparameter (Optuna):** Tidak lagi bergantung pada *setting* manual. Optuna otomatis melakukan komputasi *trial and error* untuk mencari kombinasi *learning_rate* dan batas kedalaman terbaik spesifik untuk setiap klaster.
- **Institutional Auto-Reporting:** Pipeline secara otomatis membuat folder harian (`analisa/YYYY-MM-DD/`), menggambar **Grafik Candlestick**, dan membuat file `.md` bergaya laporan riset pialang sekuritas yang merinci *Trading Plan* (Entry, Stop Loss, Target Profit) untuk tiap saham rekomendasi. Sistem cerdas juga membersihkan sisa laporan usang di hari yang sama.

---

## ⚙️ Setup Environment

Sangat direkomendasikan menggunakan Virtual Environment agar dependensi (seperti `curl_cffi` dan `optuna`) tidak bentrok dengan sistem Windows bawaan.

```bash
# 1. Buat virtual environment
python -m venv screener

# 2. Aktifkan (Windows PowerShell)
.\screener\Scripts\Activate.ps1

# 3. Install dependensi
pip install -r requirements.txt
```

---

## 🚀 Cara Menjalankan

Setelah environment aktif, cukup jalankan:

```bash
python main.py
```

Pipeline akan secara otomatis:
1. Mendownload data OHLCV historis (3 Tahun terakhir).
2. Mengambil Stock Summary & Broker Summary riil dari IDX API.
3. Melakukan Feature Engineering, Log-transform, dan Data Enrichment.
4. Melakukan Clustering K-Means & Training Auto-Tune Optuna pada Multi-Model XGBoost.
5. Menampilkan tabel 10 saham dengan probabilitas T+1 tertinggi di konsol Anda.
6. Memproduksi Laporan Analisis beserta grafik candlestick ke dalam folder `analisa/[TANGGAL_HARI_INI]/`.

---

## 📁 Struktur Project

| File | Deskripsi |
|---|---|
| `config.py` | Konstanta global, daftar 128+ ticker IHSG. |
| `idx_client.py` | Modul klien IDX API canggih dengan bypass Cloudflare (`curl_cffi`). |
| `data_ingestion.py` | Pengumpulan data dari Yahoo Finance (3 Tahun) dan IDX. |
| `feature_engineering.py` | Kalkulasi indikator teknikal, Profil Saham, dan log-transform. |
| `ml_model.py` | Arsitektur inti: K-Means Clustering + Optuna + XGBoost Multi-Model. |
| `report_generator.py` | Modul pencetak otomatis laporan pialang `.md` dan grafik `mplfinance`. |
| `screener.py` | Orchestrator utama yang menyambungkan seluruh alur pipeline. |
| `main.py` | Entry point aplikasi (menangani format CLI output). |

---

## 📌 Catatan Penting

- **Durasi Eksekusi:** Karena pipeline ini menggunakan auto-tuning (Optuna) secara dinamis, waktu tunggu komputasi pada *Tahap 3* dapat memakan waktu 1 hingga 3 menit tergantung kecepatan prosesor.
- **Disclaimer:** Laporan riset dan hasil *screening* yang ditampilkan **bukan merupakan rekomendasi investasi atau saran keuangan**. Model Machine Learning ini menggunakan pendekatan probabilistik. Selalu lakukan analisis fundamental & teknikal mandiri (DYOR) serta terapkan manajemen risiko (Stop Loss ketat) sebelum mengambil keputusan trading. *Past performance does not guarantee future results.*
