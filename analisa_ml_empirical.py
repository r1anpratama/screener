import pandas as pd
import numpy as np

def analyze():
    # Load features cache
    cache_path = "analisa/features_cache.csv"
    try:
        df = pd.read_csv(cache_path)
        print(f"Loaded cache successfully: {len(df)} rows")
    except Exception as e:
        print(f"Error loading cache: {e}")
        return

    # Ensure dates and tickers are sorted
    df["date"] = pd.to_datetime(df["date"])
    df_sorted = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    # Shift columns to get next-day's high and close
    df_sorted["next_high"] = df_sorted.groupby("ticker")["high"].shift(-1)
    df_sorted["next_close"] = df_sorted.groupby("ticker")["close"].shift(-1)

    # Calculate metrics
    df_sorted["next_max_gain"] = (df_sorted["next_high"] - df_sorted["close"]) / df_sorted["close"]
    df_sorted["next_close_return"] = (df_sorted["next_close"] - df_sorted["close"]) / df_sorted["close"]

    # Filter rows that have at least 1 signal and valid T+1 target data
    signal_columns = [
        "signal_volatility_contraction",
        "signal_momentum_extreme",
        "signal_bandarmology",
        "signal_foreign_inflow",
        "signal_strong_bid"
    ]
    
    # Ensure they exist
    for col in signal_columns:
        if col not in df_sorted.columns:
            df_sorted[col] = False

    df_sorted["total_signals"] = df_sorted[signal_columns].sum(axis=1)
    
    # Filter valid rows where signals >= 1 and next_max_gain is not null
    df_signals = df_sorted[(df_sorted["total_signals"] >= 1) & (df_sorted["next_max_gain"].notna())].copy()
    
    if len(df_signals) == 0:
        print("No signal rows with valid T+1 outcomes found.")
        return

    # Define success (max gain >= 5%)
    df_signals["success"] = (df_signals["next_max_gain"] >= 0.05).astype(int)

    success_count = df_signals["success"].sum()
    total_count = len(df_signals)
    win_rate = success_count / total_count * 100
    print(f"\nEmpirical Signal Baseline: {success_count} / {total_count} ({win_rate:.2f}% Win Rate for >= 5% Next Day High)")

    # Compare features
    features = [
        "bb_bandwidth",
        "rsi_14",
        "vwap_ratio",
        "volume_spike_ratio",
        "close_to_high_ratio",
        "foreign_net",
        "bid_offer_ratio",
        "hist_volatility",
        "avg_volume"
    ]

    print("\n" + "="*80)
    print("FEATURE ANALYSIS: SUCCESSFUL VS FAILED SIGNALS (Target: Next Day Max Gain >= 5%)")
    print("="*80)
    
    for f in features:
        if f not in df_signals.columns:
            continue
        
        # Fill NA with 0 to prevent statistics errors
        df_signals[f] = df_signals[f].fillna(0)
        
        success_mean = df_signals[df_signals["success"] == 1][f].mean()
        fail_mean = df_signals[df_signals["success"] == 0][f].mean()
        success_median = df_signals[df_signals["success"] == 1][f].median()
        fail_median = df_signals[df_signals["success"] == 0][f].median()
        
        print(f"Feature: {f}")
        print(f"  [SUCCESS] Mean: {success_mean:12.4f} | Median: {success_median:12.4f}")
        print(f"  [FAILED]  Mean: {fail_mean:12.4f} | Median: {fail_median:12.4f}")
        ratio = success_mean / fail_mean if fail_mean != 0 else 0
        print(f"  Ratio (Success/Fail Mean): {ratio:.4f}")
        print("-" * 60)

    # Let's inspect signal accuracy per signal type
    print("\n" + "="*80)
    print("WIN RATE BY INDIVIDUAL SIGNAL TYPE")
    print("="*80)
    for col in signal_columns:
        sub = df_signals[df_signals[col] == True]
        if len(sub) == 0:
            print(f"Signal: {col:35s} | No samples")
            continue
        sub_success = sub["success"].sum()
        sub_total = len(sub)
        sub_win_rate = sub_success / sub_total * 100
        print(f"Signal: {col:35s} | Success: {sub_success:4d} / {sub_total:4d} ({sub_win_rate:.2f}%)")

if __name__ == "__main__":
    analyze()
