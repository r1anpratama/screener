# 📊 IDX QUANT — Pipeline Screening Saham ML & Dashboard Interaktif (Institutional Grade)

Pipeline kuantitatif tingkat lanjut untuk *screening* saham harian IHSG (T+1 trading) berdasarkan probabilitas machine learning, volatilitas dinamis, manajemen risiko Kelly Criterion, dan visualisasi dashboard modern.

Sistem ini mengombinasikan **Data Historis (Yahoo Finance)** dengan **Data Riil Bursa (IDX API)** untuk mendeteksi emiten berpotensi lonjakan tinggi (>5%) dengan pembobotan alokasi portofolio dinamis untuk meminimalkan risiko drawdown.

---

## 🌟 Fitur Utama (v4.0 Quant Suite)

### 1. Core Machine Learning Architecture
* **Unsupervised Clustering (K-Means)**: AI secara otomatis menghitung *Profil Historis* (volatilitas dan likuiditas jangka panjang) untuk membagi ratusan emiten IHSG ke dalam klaster spesifik (Blue-chip, Mid-cap, Gorengan).
* **Supervised Multi-XGBoost**: Melatih model spesialis terpisah untuk setiap klaster. Saham gorengan dievaluasi secara terpisah dari saham lapis 1.
* **Auto-Tuning Hyperparameter (Optuna)**: Optuna melakukan pencarian otomatis dinamis untuk mencari konfigurasi *learning_rate* dan *depth* terbaik untuk memaksimalkan AUC-ROC (rata-rata gabungan **~0.78+**).

### 2. High-Profit & Risk Management Upgrades (Baru!)
* **Optimasi Portofolio Kelly Criterion**: Menghitung porsi alokasi modal optimal ($f^*$) per saham secara matematis untuk memaksimalkan pertumbuhan portofolio geometris jangka panjang:
  $$f^* = \text{Half-Kelly} \times \frac{p \cdot R - (1 - p)}{R}$$
  *Diversifikasi Teruji: Alokasi tunggal otomatis dibatasi maksimal 25% per saham.*
* **Dynamic Volatility SL/TP (ATR)**: Stop Loss diset dinamis pada $1.5 \times \text{ATR}$ dan Take Profit pada $3 \times \text{ATR}$, menyesuaikan jarak pelindung dengan volatilitas unik emiten.
* **Trailing Stop-Loss**: Sistem secara otomatis melacak posisi keluar mengikuti harga puncak tertinggi ($2 \times \text{ATR}$) guna memaksimalkan keuntungan dari tren naik panjang.

### 3. Historical Strategy Backtester (`backtester.py`)
Mesin backtest harian berkemampuan tinggi untuk menyimulasikan kinerja screening historis 6-12 bulan terakhir. Backtest melacak modal, biaya komisi (0.3% round-trip), dan menyajikan visualisasi data komprehensif (Sharpe Ratio, Win Rate, Max Drawdown) dibandingkan dengan indeks benchmark IHSG.

### 4. Interactive Web Dashboard Website (Baru!)
Aplikasi web modern berbasis **FastAPI** dengan desain antarmuka **Premium Midnight Tech CSS** (FFFFFF, FCA311, 14213D) yang menyajikan:
* **Market Dashboard**: Rangkuman saham ter-screen, *Skor Profit* komposit, dan visualisasi interaktif alokasi Kelly (Chart.js).
* **Profit Backtester Visualizer**: Kolom kustomisasi modal, rasio Kelly, dan stop ATR yang langsung memplot kurva ekuitas secara interaktif.
* **Report Hub Explorer**: Penjelajah laporan riset broker harian `.md` dan grafik candlestick `mplfinance` langsung di browser.
* **Interactive Charting Studio**: Visualisasi teknikal multi-indikator (Bollinger Bands, SMA-20, RSI-14) per emiten menggunakan Chart.js.
* **Live Developer Terminal**: Log visualisasi pelatihan XGBoost dan Optuna yang dialirkan secara *real-time* via Server-Sent Events (SSE).

---

## ⚙️ Setup Environment

 virtual environment sangat disarankan agar dependensi tidak bentrok dengan sistem global Windows Anda.

```bash
# 1. Clone atau masuk ke direktori project
cd d:\code\screener

# 2. Buat virtual environment
python -m venv screener

# 3. Aktifkan Virtual Environment (PowerShell Windows)
.\screener\Scripts\Activate.ps1

# 4. Install seluruh dependensi utama
pip install -r requirements.txt
```

---

## 🚀 Cara Menjalankan (2 Cara Mudah)

### Cara 1: Jalankan Dashboard Interaktif Web (Sangat Direkomendasikan)
Cukup jalankan satu skrip launcher pintar. Skrip ini akan otomatis memeriksa virtual environment, menginstal FastAPI/Uvicorn jika belum ada, dan mem-boot server web:

```bash
python run_web.py
```

*   **Akses Browser**: Buka browser Anda dan masuk ke **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.
*   **Memulai**: Klik tombol **⚡ Run Screener** di bilah sisi. Pipeline machine learning akan berjalan di latar belakang, dan log tuning XGBoost akan dialirkan langsung ke terminal web Anda secara real-time. Setelah selesai, dashboard akan otomatis menampilkan sinyal dan alokasi Kelly terbaru!

### Cara 2: Jalankan Pipeline via Console CLI (Traditional Mode)
Jika Anda hanya ingin menjalankan pencetakan laporan riset harian di folder `analisa/` tanpa membuka web:

```bash
python main.py
```

Skrip CLI akan melatih model, menyajikan tabel ringkasan kuantitatif di konsol, dan men-generate 10 laporan riset serta grafik candlestick di direktori `analisa/[TANGGAL_HARI_INI]/`.

---

## 📁 Struktur Project Terbaru

| File / Folder | Deskripsi |
|---|---|
| **`run_web.py`** | *Launcher* utama server web yang mengotomatisasi pengecekan sistem. |
| **`web_app.py`** | Backend server web FastAPI, penanganan logs SSE, dan perutean API data. |
| **`static/app.js`** | Logika frontend SPA, penangan fetch JSON, dan penggambaran Chart.js. |
| **`static/style.css`** | Tema visual *Midnight Tech* custom premium (Navy, Amber Orange, Crisp White). |
| **`templates/index.html`** | Halaman dashboard HTML5 dengan layout modular multi-tab. |
| **`portfolio_optimizer.py`** | Modul perhitungan Kelly alokasi portofolio, ATR stops, dan Skor Profit. |
| **`backtester.py`** | *Engine* simulasi trading historis lengkap dengan komisi transaksi. |
| `config.py` | Konvensi global, universe emiten, parameter ATR, dan host port web. |
| `idx_client.py` | Modul bypass Cloudflare IDX menggunakan impersonasi TLS Chrome (`curl_cffi`). |
| `data_ingestion.py` | Pengumpul data terpadu Yahoo Finance dan IDX Stock Summary. |
| `feature_engineering.py` | Pembangun fitur indikator teknikal harian dan kalkulasi ATR. |
| `ml_model.py` | Inti kecerdasan buatan: K-Means Clustering + Tuning Optuna + model XGBoost. |
| `report_generator.py` | Penulis otomatis Broker Report bergaya institusi (`.md` & `mplfinance` chart). |
| `screener.py` | Orchestrator utama pengumpul alur pipeline ML dan kalkulasi alokasi. |
| `main.py` | Entry point CLI konsol tradisional. |

---

## 🛡️ Analisis Risiko & Disclaimer

*   **Pencegahan Overfitting**: Model menggunakan *learning_rate* dinamis rendah (~0.05) dan Optuna validasi silang (Stratified Validation Split) untuk meredam kebisingan sinyal/jebakan manipulasi orderbook (*spoofing*) di pasar IHSG.
*   **Disclaimer Penting**: Seluruh keluaran probabilitas model, trading plan, stop-loss, dan porsi alokasi Kelly dari sistem ini bersifat **analitis kuantitatif probabilistik**, dan **bukan merupakan rekomendasi investasi atau saran keuangan**. Keputusan transaksi sepenuhnya tanggung jawab pribadi Anda. Selalu terapkan money management ketat. *Past performance does not guarantee future results.*
