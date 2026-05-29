"""
web_app.py — FastAPI Web Server Backend
=======================================
Server web FastAPI untuk menyajikan Dashboard Interaktif Saham IHSG.
Menyediakan API untuk hasil screening, backtesting kustom, penjelajah
laporan analisis harian, data historis untuk chart, dan log streaming (SSE).
"""

import os
import sys
import json
import queue
import asyncio
import threading
import contextlib
import pandas as pd
import numpy as np
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from screener import StockScreener
from backtester import DailyBacktester
from portfolio_optimizer import PortfolioOptimizer
from ml_model import SelfLearningMetaFilter, generate_hindsight_diagnoses
from config import WEB_HOST, WEB_PORT

# Inisialisasi Direktori
os.makedirs("analisa", exist_ok=True)
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app = FastAPI(
    title="IHSG Institutional Stock Screener Dashboard",
    description="Dashboard Kuantitatif Tingkat Lanjut berbasis Machine Learning & Kelly Criterion.",
    version="4.0"
)

# Global State
is_screening_running = False
latest_run_time = None
screener_instance = None
features_cache_path = os.path.join("analisa", "features_cache.csv")
latest_picks_json_path = os.path.join("analisa", "latest_picks.json")

# Queue untuk Log Streaming
class LogStreamer:
    def __init__(self):
        self.listeners = []

    def register(self):
        q = asyncio.Queue()
        self.listeners.append(q)
        return q

    def deregister(self, q):
        if q in self.listeners:
            self.listeners.remove(q)

    def write(self, buf):
        sys.__stdout__.write(buf)
        sys.__stdout__.flush()
        # Bersihkan log line
        cleaned = buf.rstrip()
        if cleaned:
            # Kirim ke semua listener async
            for q in self.listeners:
                asyncio.run_coroutine_threadsafe(q.put(cleaned), loop)

    def flush(self):
        sys.__stdout__.flush()

# Set up global event loop reference for logging
loop = asyncio.get_event_loop()
log_streamer = LogStreamer()

class RedirectStdout:
    def __init__(self, streamer):
        self.streamer = streamer
        self.old_stdout = sys.stdout

    def __enter__(self):
        sys.stdout = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.old_stdout

    def write(self, buf):
        self.streamer.write(buf)

    def flush(self):
        self.streamer.flush()

# Model untuk Request Backtest Kustom
class BacktestRequest(BaseModel):
    initial_capital: float = 100000000.0
    kelly_fraction: float = 0.5
    sl_multiplier: float = 1.5
    tp_multiplier: float = 3.0
    trailing_multiplier: float = 2.0

# =====================================================================
# BACKGROUND RUNNER PIPELINE
# =====================================================================

def run_screener_pipeline_thread():
    global is_screening_running, latest_run_time, screener_instance
    is_screening_running = True
    print("[SERVER] Memulai pipeline screening di latar belakang...")
    
    try:
        with RedirectStdout(log_streamer):
            # Inisialisasi dan jalankan pipeline
            screener_instance = StockScreener()
            df_screened = screener_instance.run()
            
            # Simpan cache data features & picks
            if screener_instance.df_features is not None:
                screener_instance.df_features.to_csv(features_cache_path, index=False)
                print(f"   [CACHE] Berhasil menyimpan fitur historis ke: {features_cache_path}")
            
            if not df_screened.empty:
                # Simpan picks ke file JSON untuk pemuatan instan
                # Ubah DataFrame ke format dict yang serialize-able
                df_display = screener_instance.format_output(df_screened)
                
                # --- GENERASI REPORT & GRAFIK TRADINGVIEW OTOMATIS (BARU) ---
                try:
                    from report_generator import generate_reports
                    generate_reports(df_display, screener_instance.df_ohlcv)
                    print("   [CACHE] Berhasil men-generate laporan riset & chart TradingView di folder analisa/")
                except Exception as e_rep:
                    print(f"   [ERROR] Gagal men-generate laporan riset: {e_rep}")

                records = df_display.to_dict(orient="records")
                
                # Format rupiah dan numeric asli untuk grafik/backtest
                raw_records = df_screened.to_dict(orient="records")
                # Gabungkan data untuk response frontend lengkap
                picks_data = {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "picks": records,
                    "raw_picks": raw_records,
                    "market_regime": getattr(screener_instance, "market_regime", "BULLISH"),
                    "ihsg_close": getattr(screener_instance, "ihsg_close", 0.0),
                    "ihsg_sma_50": getattr(screener_instance, "ihsg_sma_50", 0.0)
                }
                
                with open(latest_picks_json_path, "w", encoding="utf-8") as f:
                    json.dump(picks_data, f, indent=4, default=str)
                print(f"   [CACHE] Hasil screening terbaru disimpan ke: {latest_picks_json_path}")
            else:
                print("   [!] Tidak ada saham yang lolos kriteria hari ini.")
                
            print("=" * 60)
            print("[SUCCESS] PIPELINE SCREENING BERHASIL DISELESAIKAN!")
            print("=" * 60)
            
    except Exception as e:
        import traceback
        print(f"\n[ERROR] Kegagalan Pipeline: {e}")
        traceback.print_exc(file=sys.stdout)
    finally:
        is_screening_running = False
        latest_run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# =====================================================================
# API ENDPOINTS
# =====================================================================

@app.get("/api/latest-picks")
def get_latest_picks():
    """Mengembalikan hasil screening saham harian terbaru diperkaya dengan hasil T+1 jika tersedia."""
    if not os.path.exists(latest_picks_json_path):
        return {"status": "no_data", "message": "Belum ada screening yang dijalankan."}
        
    try:
        with open(latest_picks_json_path, "r", encoding="utf-8") as f:
            picks_data = json.load(f)
            
        # Perkaya dengan realized return jika df_features cache tersedia
        if os.path.exists(features_cache_path) and "picks" in picks_data:
            try:
                df = pd.read_csv(features_cache_path)
                df["date_str"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                
                # Urutkan berdasarkan emiten dan tanggal secara kronologis
                df_sorted = df.sort_values(["ticker", "date"]).reset_index(drop=True)
                
                for pick in picks_data["picks"]:
                    ticker = pick["Saham"]
                    date_str = picks_data.get("date")
                    
                    # Cari baris hari ini
                    idx_list = df_sorted[(df_sorted["ticker"] == ticker) & (df_sorted["date_str"] == date_str)].index
                    if len(idx_list) > 0:
                        idx = idx_list[0]
                        # Cari baris setelahnya untuk ticker yang sama
                        next_idx = idx + 1
                        if next_idx < len(df_sorted) and df_sorted.loc[next_idx, "ticker"] == ticker:
                            row_next = df_sorted.loc[next_idx]
                            
                            # Realized T+1 prices
                            close_t = df_sorted.loc[idx, "close"]
                            close_t1 = row_next["close"]
                            high_t1 = row_next["high"]
                            
                            # Hitung return
                            ret_close_close = ((close_t1 - close_t) / close_t) * 100
                            max_ret = ((high_t1 - close_t) / close_t) * 100
                            target_met = high_t1 >= (close_t * 1.05) # Target > 5%
                            
                            # Tambahkan field ke display picks
                            pick["Harga T+1"] = f"Rp {close_t1:,.0f}"
                            pick["Return T+1"] = f"{ret_close_close:+.2f}%"
                            pick["Max Return T+1"] = f"{max_ret:+.2f}%"
                            pick["Realized Status"] = "🟢 Success" if target_met else "🔴 Failed"
                        else:
                            pick["Harga T+1"] = "Pending T+1"
                            pick["Return T+1"] = "Pending T+1"
                            pick["Max Return T+1"] = "Pending T+1"
                            pick["Realized Status"] = "🟡 Active"
                    else:
                        pick["Harga T+1"] = "-"
                        pick["Return T+1"] = "-"
                        pick["Max Return T+1"] = "-"
                        pick["Realized Status"] = "🟡 Active"
            except Exception as e:
                print(f"[ERROR] Gagal memperkaya T+1: {e}")
                
        return picks_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memuat cache picks: {e}")

@app.get("/api/prediction-performance")
def get_prediction_performance():
    """Mengembalikan performa prediksi historis berdasarkan hasil riil hari berikutnya (T+1)."""
    if not os.path.exists(features_cache_path):
        return {"status": "no_data", "message": "Cache data belum tersedia."}
        
    try:
        df = pd.read_csv(features_cache_path)
        df["date_str"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df_sorted = df.sort_values(["ticker", "date"]).reset_index(drop=True)
        
        # Saring baris yang memiliki minimal 1 sinyal aktif
        signal_columns = [
            "signal_volatility_contraction",
            "signal_momentum_extreme",
            "signal_bandarmology",
            "signal_foreign_inflow",
            "signal_strong_bid",
        ]
        df_sorted["total_signals"] = df_sorted[signal_columns].sum(axis=1)
        df_signals = df_sorted[df_sorted["total_signals"] >= 1].copy()
        
        if df_signals.empty:
            return {"status": "empty", "message": "Belum ada sinyal historis."}
            
        # Ambil tanggal-tanggal unik terakhir
        all_dates = sorted(df_sorted["date_str"].unique())
        if len(all_dates) < 2:
            return {"status": "empty", "message": "Data historis tidak mencukupi."}
            
        # Evaluasi beberapa hari trading terakhir (menyisakan hari terakhr sebagai pending)
        dates_to_eval = all_dates[-15:-1]
        
        performance_records = []
        total_predictions = 0
        successful_predictions = 0
        
        for eval_date in dates_to_eval:
            df_date_signals = df_signals[df_signals["date_str"] == eval_date].copy()
            if df_date_signals.empty:
                continue
                
            # Ambil picks teratas berdasarkan win_probability jika ada, atau skor volume/vwap
            # Urutkan berdasarkan total sinyal dan vwap ratio
            df_date_signals["score"] = (df_date_signals["vwap_ratio"] * 0.5) + (df_date_signals["volume_spike_ratio"] * 0.5)
            df_picks = df_date_signals.sort_values("score", ascending=False).head(3)
            
            for _, row in df_picks.iterrows():
                ticker = row["ticker"]
                close_t = row["close"]
                
                # Cari baris T+1 di df_sorted
                idx_list = df_sorted[(df_sorted["ticker"] == ticker) & (df_sorted["date_str"] == eval_date)].index
                if len(idx_list) > 0:
                    idx = idx_list[0]
                    next_idx = idx + 1
                    if next_idx < len(df_sorted) and df_sorted.loc[next_idx, "ticker"] == ticker:
                        row_next = df_sorted.loc[next_idx]
                        close_t1 = row_next["close"]
                        high_t1 = row_next["high"]
                        
                        ret = ((close_t1 - close_t) / close_t) * 100
                        max_ret = ((high_t1 - close_t) / close_t) * 100
                        success = high_t1 >= (close_t * 1.05) # Target > 5%
                        
                        total_predictions += 1
                        if success:
                            successful_predictions += 1
                            
                        performance_records.append({
                            "date": eval_date,
                            "ticker": ticker,
                            "close_t": f"Rp {close_t:,.0f}",
                            "date_t1": row_next["date_str"],
                            "close_t1": f"Rp {close_t1:,.0f}",
                            "return_pct": f"{ret:+.2f}%",
                            "max_return_pct": f"{max_ret:+.2f}%",
                            "status": "🟢 Success" if success else "🔴 Failed"
                        })
                        
        realized_win_rate = (successful_predictions / total_predictions * 100) if total_predictions > 0 else 0.0
        
        return {
            "status": "success",
            "realized_win_rate": f"{realized_win_rate:.1f}%",
            "total_predictions": total_predictions,
            "successful_predictions": successful_predictions,
            "history": performance_records[::-1] # Urutan terbaru di atas
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_bearish_regime():
    try:
        import yfinance as yf
        df_ihsg = yf.download("^JKSE", period="1y", interval="1d", progress=False)
        if isinstance(df_ihsg.columns, pd.MultiIndex):
            df_ihsg.columns = df_ihsg.columns.get_level_values(0)
        df_ihsg = df_ihsg.dropna(subset=["Close"])
        df_ihsg['sma_50'] = df_ihsg['Close'].rolling(50).mean()
        latest_close = float(df_ihsg['Close'].iloc[-1])
        latest_sma_50 = float(df_ihsg['sma_50'].iloc[-1])
        return latest_close < latest_sma_50
    except:
        return False


@app.post("/api/run-self-learning")
def run_self_learning():
    """Menjalankan proses hindsight error diagnosis dan melatih Neural Network Meta-Filter."""
    if not os.path.exists(features_cache_path):
        raise HTTPException(status_code=400, detail="Cache data features_cache.csv belum tersedia. Silakan jalankan screener terlebih dahulu.")
        
    try:
        df = pd.read_csv(features_cache_path)
        df["date_str"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df_sorted = df.sort_values(["ticker", "date"]).reset_index(drop=True)
        
        signal_columns = [
            "signal_volatility_contraction",
            "signal_momentum_extreme",
            "signal_bandarmology",
            "signal_foreign_inflow",
            "signal_strong_bid",
        ]
        df_sorted["total_signals"] = df_sorted[signal_columns].sum(axis=1)
        df_signals = df_sorted[df_sorted["total_signals"] >= 1].copy()
        
        all_dates = sorted(df_sorted["date_str"].unique())
        if len(all_dates) < 2:
            return {"status": "error", "message": "Data historis tidak mencukupi untuk proses belajar mandiri."}
            
        # Analisis 15 hari terakhir untuk melatih model
        dates_to_eval = all_dates[-15:-1]
        
        hindsight_records = []
        feature_vectors = []
        labels = []
        
        for eval_date in dates_to_eval:
            df_date_signals = df_signals[df_signals["date_str"] == eval_date].copy()
            if df_date_signals.empty:
                continue
                
            # Identifikasi top picks menggunakan metode scoring vwap & volume
            df_date_signals["score"] = (df_date_signals["vwap_ratio"] * 0.5) + (df_date_signals["volume_spike_ratio"] * 0.5)
            df_picks = df_date_signals.sort_values("score", ascending=False).head(3)
            
            for _, row in df_picks.iterrows():
                ticker = row["ticker"]
                close_t = row["close"]
                
                idx_list = df_sorted[(df_sorted["ticker"] == ticker) & (df_sorted["date_str"] == eval_date)].index
                if len(idx_list) > 0:
                    idx = idx_list[0]
                    next_idx = idx + 1
                    if next_idx < len(df_sorted) and df_sorted.loc[next_idx, "ticker"] == ticker:
                        row_next = df_sorted.loc[next_idx]
                        close_t1 = row_next["close"]
                        high_t1 = row_next["high"]
                        
                        max_ret = ((high_t1 - close_t) / close_t) * 100
                        success = high_t1 >= (close_t * 1.05)
                        
                        hindsight_records.append({
                            "date": eval_date,
                            "ticker": ticker,
                            "close_t": close_t,
                            "high_t1": high_t1,
                            "max_return_pct": max_ret,
                            "success": success,
                            "rsi_14": row.get("rsi_14", 50.0),
                            "volume_spike_ratio": row.get("volume_spike_ratio", 1.0),
                            "bid_offer_ratio": row.get("bid_offer_ratio", 1.0),
                            "vwap_ratio": row.get("vwap_ratio", 1.0),
                            "bb_bandwidth": row.get("bb_bandwidth", 30.0),
                            "close_to_high_ratio": row.get("close_to_high_ratio", 0.5),
                            "foreign_net": row.get("foreign_net", 0.0),
                            "hist_volatility": row.get("hist_volatility", 0.03),
                            "avg_volume": row.get("avg_volume", 15.0)
                        })
                        
                        # Simpan ke dataset training meta-filter
                        feat_vals = [
                            row.get("bb_bandwidth", 30.0),
                            row.get("rsi_14", 50.0),
                            row.get("vwap_ratio", 1.0),
                            row.get("volume_spike_ratio", 1.0),
                            row.get("close_to_high_ratio", 0.5),
                            row.get("foreign_net", 0.0),
                            row.get("bid_offer_ratio", 1.0),
                            row.get("hist_volatility", 0.03),
                            row.get("avg_volume", 15.0)
                        ]
                        # Isi NaN dengan 0.0
                        feat_vals = [0.0 if pd.isna(v) else v for v in feat_vals]
                        
                        feature_vectors.append(feat_vals)
                        labels.append(1 if success else 0)
                        
        if not hindsight_records:
            return {"status": "error", "message": "Tidak ditemukan data rekomendasi historis untuk dievaluasi."}
            
        # Inisialisasi Meta Filter
        meta_filter = SelfLearningMetaFilter()
        
        # Training Neural Network & capture logs
        logs = []
        def log_callback(line):
            print(f"[SELF-LEARNING] {line}")
            logs.append(line)
            
        log_callback("=" * 60)
        log_callback("[START] MEMULAI SIKLUS PEMBELAJARAN MANDIRI (SELF-CORRECTION)")
        log_callback("=" * 60)
        log_callback(f"   [DATA] Teridentifikasi {len(hindsight_records)} picks historis selama 15 hari terakhir.")
        log_callback(f"   [STATS] Sukses: {sum(labels)} picks | Gagal: {len(labels) - sum(labels)} picks.")
        
        X_train = np.array(feature_vectors)
        y_train = np.array(labels)
        
        # Latih model selama 10 epoch
        history_logs = meta_filter.train_epochs(X_train, y_train, epochs=10, print_callback=log_callback)
        
        # Diagnosis
        failed_picks_df = pd.DataFrame([r for r in hindsight_records if not r["success"]])
        diagnoses = []
        if not failed_picks_df.empty:
            diagnoses = generate_hindsight_diagnoses(failed_picks_df)
        
        # Simpan diagnoses ke model
        meta_filter.diagnoses = diagnoses
        
        # Susun Model Adaptation Policies kustom
        active_policies = [
            {
                "title": "RSI Overbought Constraint",
                "desc": "Menurunkan toleransi entry pada saham overbought dari RSI > 70 ke RSI > 68.",
                "status": "AKTIF & TERKALIBRASI" if any(r.get("rsi_14", 50.0) > 68 for r in hindsight_records if not r["success"]) else "TERPANTAU"
            },
            {
                "title": "Volume Spike Confirmation Threshold",
                "desc": "Meningkatkan syarat konfirmasi volume spike breakout dari 1.3x ke 1.5x VMA20.",
                "status": "AKTIF & TERKALIBRASI" if any(r.get("volume_spike_ratio", 1.0) < 1.3 for r in hindsight_records if not r["success"]) else "TERPANTAU"
            },
            {
                "title": "Bid/Offer Resistance Guard",
                "desc": "Memeriksa ketebalan offer untuk menolak pump-and-dump ritel.",
                "status": "AKTIF & TERKALIBRASI" if any(r.get("bid_offer_ratio", 1.0) < 1.1 for r in hindsight_records if not r["success"]) else "TERPANTAU"
            },
            {
                "title": "Regime Capital Preservation Discount",
                "desc": "Memotong ukuran alokasi Kelly sebesar 50% di bawah regime IHSG Bearish.",
                "status": "AKTIF & TERKALIBRASI" if check_bearish_regime() else "TERPANTAU"
            }
        ]
        meta_filter.policies = active_policies
        meta_filter.save()
        
        # Sinkronisasi instance screener aktif agar langsung sadar model ter-update
        global screener_instance
        if screener_instance is not None:
            screener_instance.meta_filter = meta_filter
            
        log_callback("=" * 60)
        log_callback("[SUCCESS] SIKLUS PEMBELAJARAN MANDIRI BERHASIL DISELESAIKAN!")
        log_callback("   -> Deep learning meta-filter di-save ke meta_filter_model.pkl")
        log_callback("   -> Seluruh rekomendasi hari esok akan disaring oleh meta-filter ini.")
        log_callback("=" * 60)
        
        return {
            "status": "success",
            "logs": "\n".join(logs),
            "diagnoses": diagnoses,
            "policies": active_policies
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Kegagalan eksekusi belajar mandiri: {str(e)}"}


@app.get("/api/self-learning-status")
def get_self_learning_status():
    """Mengambil status dan diagnosis terakhir yang disimpan dari model self-learning."""
    meta_filter = SelfLearningMetaFilter()
    return {
        "is_trained": meta_filter.is_trained,
        "diagnoses": meta_filter.diagnoses,
        "policies": meta_filter.policies
    }


@app.get("/api/screener-status")
def get_screener_status():
    """Mengecek status eksekusi pipeline screening."""
    return {
        "is_running": is_screening_running,
        "latest_run_time": latest_run_time or "Belum pernah"
    }

@app.post("/api/run-screener")
def trigger_screener(background_tasks: BackgroundTasks):
    """Memicu eksekusi pipeline screening saham di latar belakang."""
    global is_screening_running
    if is_screening_running:
        return {"status": "already_running", "message": "Screener sedang berjalan."}
    
    # Jalankan thread background
    t = threading.Thread(target=run_screener_pipeline_thread)
    t.daemon = True
    t.start()
    
    return {"status": "started", "message": "Pipeline screening berhasil dimulai."}

@app.get("/api/logs")
async def get_logs_stream():
    """SSE (Server-Sent Events) endpoint untuk mengalirkan log secara real-time."""
    q = log_streamer.register()
    
    async def log_generator():
        # Kirim salam pembuka
        yield f"data: 🚀 Koneksi terminal web aktif. Menunggu output...\n\n"
        try:
            while True:
                # Tunggu log baru masuk
                line = await q.get()
                yield f"data: {line}\n\n"
                q.task_done()
        except asyncio.CancelledError:
            pass
        finally:
            log_streamer.deregister(q)

    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.post("/api/backtest")
def run_custom_backtest(req: BacktestRequest):
    """Menjalankan engine backtester kuantitatif kustom."""
    # Gunakan cache features jika tersedia
    if not os.path.exists(features_cache_path):
        # Jika cache kosong, coba download dan hitung di tempat
        print("[SERVER] Cache fitur kosong. Mengunduh data baru untuk backtest...")
        try:
            screener = StockScreener()
            screener.ingest_data()
            screener.engineer_features()
            # Latih model untuk generate win_probability historis
            screener.train_model()
            
            # Simpan cache
            screener.df_features.to_csv(features_cache_path, index=False)
            df_features = screener.df_features
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Gagal menyiapkan data historis untuk backtest: {e}. Selesaikan pipeline run terlebih dahulu."
            )
    else:
        df_features = pd.read_csv(features_cache_path)
        # Parse date col
        df_features["date"] = pd.to_datetime(df_features["date"])

    # Jalankan Backtesting
    backtester = DailyBacktester(
        df_features=df_features,
        initial_capital=req.initial_capital,
        kelly_fraction=req.kelly_fraction,
        sl_multiplier=req.sl_multiplier,
        tp_multiplier=req.tp_multiplier,
        trailing_multiplier=req.trailing_multiplier
    )
    
    try:
        results = backtester.run_backtest()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengeksekusi backtest: {e}")

@app.get("/api/reports")
def list_reports():
    """Daftar seluruh direktori analisa harian dan laporan saham didalamnya."""
    base_dir = "analisa"
    if not os.path.exists(base_dir):
        return []
        
    dates = []
    # Loop folder tanggal analisa/YYYY-MM-DD/
    for entry in sorted(os.listdir(base_dir), reverse=True):
        entry_path = os.path.join(base_dir, entry)
        if os.path.isdir(entry_path) and not entry.startswith("."):
            tickers = []
            for file in os.listdir(entry_path):
                if file.endswith("_analisa.md"):
                    ticker = file.replace("_analisa.md", "")
                    tickers.append(ticker)
            if tickers:
                dates.append({
                    "date": entry,
                    "tickers": sorted(tickers)
                })
    return dates

@app.get("/api/reports/{date}/{ticker}")
def get_report_content(date: str, ticker: str):
    """Mengembalikan konten Markdown dari analis report."""
    file_path = os.path.join("analisa", date, f"{ticker}_analisa.md")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Laporan analisis tidak ditemukan.")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membaca file: {e}")

@app.get("/api/reports/{date}/{ticker}/chart")
def get_report_chart(date: str, ticker: str):
    """Mengembalikan gambar grafik Candlestick harian."""
    file_path = os.path.join("analisa", date, f"{ticker}_chart.png")
    if not os.path.exists(file_path):
        # Fallback to a placeholder or 404
        raise HTTPException(status_code=404, detail="Gambar grafik tidak ditemukan.")
    return FileResponse(file_path)

@app.get("/api/stock-history/{ticker}")
def get_stock_history(ticker: str):
    """Mengembalikan data teknikal historis saham untuk interaktif chart."""
    if not os.path.exists(features_cache_path):
        raise HTTPException(status_code=400, detail="Data cache belum tersedia. Jalankan pipeline screening dahulu.")
    
    try:
        df = pd.read_csv(features_cache_path)
        df_stock = df[df["ticker"] == ticker.upper()].copy()
        if df_stock.empty:
            raise HTTPException(status_code=404, detail=f"Saham {ticker} tidak ditemukan.")
            
        df_stock = df_stock.sort_values("date").tail(100) # Ambil 100 hari terakhir
        
        # Hitung Bollinger Bands sederhana jika kolom bb_bandwidth tidak cukup
        # untuk render, kita kembalikan close, volume, rsi, dan price bounds
        df_stock["sma_20"] = df_stock["close"].rolling(window=20).mean()
        df_stock["bb_upper"] = df_stock["sma_20"] + 2 * df_stock["close"].rolling(window=20).std()
        df_stock["bb_lower"] = df_stock["sma_20"] - 2 * df_stock["close"].rolling(window=20).std()
        
        # Bersihkan NaN
        df_stock = df_stock.bfill().fillna(0)
        
        # Pastikan kolom vwap_ratio & bid_offer_ratio ada sebelum diekstrak
        for col in ["vwap_ratio", "bid_offer_ratio"]:
            if col not in df_stock.columns:
                df_stock[col] = 1.0
                
        records = df_stock[[
            "date", "open", "high", "low", "close", "volume", "rsi_14", "sma_20", "bb_upper", "bb_lower",
            "vwap_ratio", "bid_offer_ratio"
        ]].to_dict(orient="records")
        
        return records
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses data chart: {e}")

# =====================================================================
# FRONTEND MOUNTING & STATIC FILES
# =====================================================================

# Sajikan index.html pada root
@app.get("/", response_class=HTMLResponse)
def get_index():
    index_path = os.path.join("templates", "index.html")
    if not os.path.exists(index_path):
        return HTMLResponse("<h2>Error: templates/index.html tidak ditemukan.</h2>", status_code=404)
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

# Mount folder static untuk CSS & JS
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    # Jalankan server
    uvicorn.run(app, host=WEB_HOST, port=WEB_PORT)
