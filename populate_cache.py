import os
import json
import pandas as pd
from datetime import datetime
from screener import StockScreener

print("[CACHE_POPULATOR] Memulai screening untuk membuat file cache awal...")
screener = StockScreener()
df_screened = screener.run()

# Buat folder analisa jika belum ada
os.makedirs("analisa", exist_ok=True)

# Simpan features cache
if screener.df_features is not None:
    screener.df_features.to_csv("analisa/features_cache.csv", index=False)
    print("[CACHE_POPULATOR] Berhasil menyimpan analisa/features_cache.csv")

# Simpan picks json
if not df_screened.empty:
    df_display = screener.format_output(df_screened)
    
    # JALANKAN GENERASI REPORT OTOMATIS (BARU)
    from report_generator import generate_reports
    generate_reports(df_display, screener.df_ohlcv)
    
    records = df_display.to_dict(orient="records")
    raw_records = df_screened.to_dict(orient="records")
    picks_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "picks": records,
        "raw_picks": raw_records,
        "market_regime": getattr(screener, "market_regime", "BULLISH"),
        "ihsg_close": getattr(screener, "ihsg_close", 0.0),
        "ihsg_sma_50": getattr(screener, "ihsg_sma_50", 0.0)
    }
    with open("analisa/latest_picks.json", "w", encoding="utf-8") as f:
        json.dump(picks_data, f, indent=4, default=str)
    print("[CACHE_POPULATOR] Berhasil menyimpan analisa/latest_picks.json & broker briefs")
    print("[CACHE_POPULATOR] Selesai!")
else:
    print("[CACHE_POPULATOR] Selesai. Sinyal kosong hari ini.")
