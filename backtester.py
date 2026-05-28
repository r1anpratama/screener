"""
backtester.py — Engine Backtesting Historis
===========================================
Modul ini mensimulasikan kinerja historis dari strategi screening saham
IHSG yang telah ditingkatkan. Mendukung parameter kustom seperti capital awal,
dynamic Kelly sizing, dan trailing stop-loss berbasis ATR.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from portfolio_optimizer import PortfolioOptimizer

class DailyBacktester:
    """
    Simulasi backtesting harian untuk portfolio saham pilihan.
    """

    def __init__(
        self,
        df_features: pd.DataFrame,
        initial_capital: float = 100000000.0,  # default Rp 100 Juta
        kelly_fraction: float = 0.5,
        sl_multiplier: float = 1.5,
        tp_multiplier: float = 3.0,
        trailing_multiplier: float = 2.0,
        max_single_alloc: float = 0.25,
        transaction_cost: float = 0.003,       # 0.3% roundtrip cost (fee beli + jual)
    ):
        self.df_features = df_features.copy()
        self.initial_capital = initial_capital
        self.kelly_fraction = kelly_fraction
        self.sl_multiplier = sl_multiplier
        self.tp_multiplier = tp_multiplier
        self.trailing_multiplier = trailing_multiplier
        self.max_single_alloc = max_single_alloc
        self.transaction_cost = transaction_cost
        
        # Inisialisasi optimizer
        self.optimizer = PortfolioOptimizer(kelly_fraction=self.kelly_fraction)

    def run_backtest(self) -> dict:
        """
        Menjalankan simulasi backtesting harian secara kronologis.
        
        Logika Backtest:
        1. Urutkan data berdasarkan Tanggal.
        2. Pada hari T, kumpulkan semua saham yang ter-screen (ada sinyal aktif & model predict_proba).
        3. Gunakan PortfolioOptimizer untuk menghitung target SL/TP dan alokasi Kelly %.
        4. Masukkan transaksi beli pada hari T+1 (Entry di harga Open).
        5. Lacak posisi terbuka setiap hari:
           - Update harga tertinggi sejak entry untuk trailing stop.
           - Periksa apakah Low menyentuh Stop Loss atau Trailing Stop.
           - Periksa apakah High menyentuh Take Profit.
           - Close posisi jika exit terpicu, kurangi transaction cost.
        6. Hitung nilai ekuitas portfolio harian (Cash + Value Posisi Terbuka).
        """
        # 1. Persiapan data prediksi historis
        df = self.df_features.copy()
        
        # Isi default columns jika tidak ada
        if "win_probability" not in df.columns:
            # fallback jika model belum dijalankan: hitung win prob acak terdistribusi positif
            df["win_probability"] = 52.0
            
        # Dapatkan daftar tanggal trading unik secara kronologis
        trading_dates = sorted(df["date"].unique())
        if len(trading_dates) < 20:
            return {"error": "Data historis terlalu pendek untuk backtesting."}

        # Status Portofolio
        cash = self.initial_capital
        open_positions = []  # List of dict: {ticker, entry_date, entry_price, shares, sl, tp, highest_price, weight}
        
        daily_equity = []
        trade_logs = []  # Laporan transaksi individual
        
        # Rincian pergerakan harga per hari untuk lookup cepat
        # group_by date dan buat dict of ticker -> price_row
        print(f"[>] Memulai Backtest Historis ({len(trading_dates)} hari trading)...")
        
        for i in range(len(trading_dates) - 1):
            current_date = trading_dates[i]
            next_date = trading_dates[i + 1]
            
            # --- TAHAP A: UPDATE POSISI TERBUKA & VALUASI ---
            # Ambil data harga pada hari ini (current_date) untuk melacak open positions
            df_today = df[df["date"] == current_date]
            today_prices = {row["ticker"]: row for _, row in df_today.iterrows()}
            
            closed_positions_today = []
            current_positions_value = 0.0
            
            for pos in open_positions:
                ticker = pos["ticker"]
                
                if ticker in today_prices:
                    price_info = today_prices[ticker]
                    low_p = price_info["low"]
                    high_p = price_info["high"]
                    close_p = price_info["close"]
                    atr_val = price_info.get("atr", close_p * 0.02)
                    
                    # Update harga tertinggi untuk trailing stop
                    if high_p > pos["highest_price"]:
                        pos["highest_price"] = high_p
                    
                    # Hitung level Trailing Stop dinamis saat ini
                    current_trailing_stop = pos["highest_price"] - (atr_val * self.trailing_multiplier)
                    
                    # 1. Cek Stop Loss
                    if low_p <= pos["sl"]:
                        # Terkena Stop Loss (exit pada harga SL atau Open jika gap down)
                        exit_price = min(pos["sl"], price_info["open"])
                        closed_positions_today.append((pos, exit_price, "Stop Loss", current_date))
                    
                    # 2. Cek Trailing Stop
                    elif low_p <= current_trailing_stop:
                        exit_price = min(current_trailing_stop, price_info["open"])
                        closed_positions_today.append((pos, exit_price, "Trailing Stop", current_date))
                        
                    # 3. Cek Take Profit
                    elif high_p >= pos["tp"]:
                        exit_price = max(pos["tp"], price_info["open"])
                        closed_positions_today.append((pos, exit_price, "Take Profit", current_date))
                        
                    else:
                        # Posisi tetap terbuka, valuasi menggunakan harga Close hari ini
                        current_positions_value += pos["shares"] * close_p
                else:
                    # Saham delisted / tidak ada data hari ini, valuasi konstan
                    current_positions_value += pos["shares"] * pos["entry_price"]

            # Keluarkan posisi yang sudah closed
            for pos, exit_p, exit_reason, exit_date in closed_positions_today:
                open_positions.remove(pos)
                gross_return = pos["shares"] * exit_p
                net_return = gross_return * (1.0 - self.transaction_cost)
                cash += net_return
                
                pnl = net_return - (pos["shares"] * pos["entry_price"] * (1.0 + self.transaction_cost))
                pnl_pct = (exit_p / pos["entry_price"] - 1.0) * 100
                
                trade_logs.append({
                    "ticker": pos["ticker"],
                    "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                    "exit_date": exit_date.strftime("%Y-%m-%d"),
                    "entry_price": pos["entry_price"],
                    "exit_price": exit_p,
                    "reason": exit_reason,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct
                })

            # Total Ekuitas Hari Ini
            total_equity = cash + current_positions_value
            daily_equity.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "equity": total_equity,
                "cash": cash,
                "pos_value": current_positions_value
            })

            # --- TAHAP B: CARI PREDIKSI BARU HARI INI & EKSEKUSI BESOK (T+1) ---
            # Saham hasil screening pada hari current_date
            df_screened_today = df_today[
                (df_today["signal_volatility_contraction"] | 
                 df_today["signal_momentum_extreme"] | 
                 df_today["signal_bandarmology"] | 
                 df_today["signal_foreign_inflow"] | 
                 df_today["signal_strong_bid"])
            ].copy()
            
            if not df_screened_today.empty:
                # Ambil top pick diurutkan berdasarkan win_probability
                df_screened_today.sort_values("win_probability", ascending=False, inplace=True)
                df_picks = df_screened_today.head(5)
                
                # Optimasi menggunakan Kelly
                df_optimized = self.optimizer.optimize_allocations(
                    df_picks, max_single_allocation=self.max_single_alloc
                )
                
                # Saring hanya yang memiliki alokasi modal > 0%
                df_allocs = df_optimized[df_optimized["portfolio_weight"] > 0]
                
                # Dapatkan data harga hari esok (next_date) untuk eksekusi beli di harga Open
                df_tomorrow = df[df["date"] == next_date]
                tomorrow_prices = {row["ticker"]: row for _, row in df_tomorrow.iterrows()}
                
                # Alokasikan modal yang tersedia pada hari esok
                # Untuk keamanan, kita batasi total alokasi baru tidak melampaui sisa cash saat ini
                available_cash_for_new = cash
                
                # Cek ticker yang sudah dimiliki agar tidak double buy
                active_tickers = [p["ticker"] for p in open_positions]
                
                for _, row in df_allocs.iterrows():
                    ticker = row["ticker"]
                    weight = row["portfolio_weight"]
                    
                    if ticker in active_tickers:
                        continue # sudah ada posisi
                        
                    if ticker in tomorrow_prices:
                        tomorrow_data = tomorrow_prices[ticker]
                        entry_p = tomorrow_data["open"]
                        atr_val = tomorrow_data.get("atr", entry_p * 0.02)
                        
                        # Tentukan modal untuk saham ini berdasarkan bobot Kelly
                        alloc_capital = self.initial_capital * weight
                        
                        # Pastikan tidak overspend cash yang ada
                        if alloc_capital > available_cash_for_new:
                            alloc_capital = available_cash_for_new
                            
                        if alloc_capital < 100000:  # minimal Rp 100 Ribu per posisi
                            continue
                            
                        # Hitung jumlah lembar saham (lot = 100 lembar)
                        shares = int(alloc_capital / (entry_p * (1.0 + self.transaction_cost)))
                        if shares == 0:
                            continue
                            
                        buy_value = shares * entry_p * (1.0 + self.transaction_cost)
                        cash -= buy_value
                        available_cash_for_new -= buy_value
                        
                        # SL dan TP berbasis ATR
                        sl = entry_p - (atr_val * self.sl_multiplier)
                        tp = entry_p + (atr_val * self.tp_multiplier)
                        
                        open_positions.append({
                            "ticker": ticker,
                            "entry_date": next_date,
                            "entry_price": entry_p,
                            "shares": shares,
                            "sl": sl,
                            "tp": tp,
                            "highest_price": entry_p,
                            "weight": weight
                        })

        # Hari terakhir: Liquidate semua posisi terbuka untuk menutup buku
        last_date = trading_dates[-1]
        df_last = df[df["date"] == last_date]
        last_prices = {row["ticker"]: row for _, row in df_last.iterrows()}
        
        for pos in open_positions:
            ticker = pos["ticker"]
            exit_p = pos["entry_price"]
            if ticker in last_prices:
                exit_p = last_prices[ticker]["close"]
                
            gross_return = pos["shares"] * exit_p
            net_return = gross_return * (1.0 - self.transaction_cost)
            cash += net_return
            
            pnl = net_return - (pos["shares"] * pos["entry_price"] * (1.0 + self.transaction_cost))
            pnl_pct = (exit_p / pos["entry_price"] - 1.0) * 100
            
            trade_logs.append({
                "ticker": pos["ticker"],
                "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                "exit_date": last_date.strftime("%Y-%m-%d"),
                "entry_price": pos["entry_price"],
                "exit_price": exit_p,
                "reason": "End of Backtest",
                "pnl": pnl,
                "pnl_pct": pnl_pct
            })
            
        daily_equity.append({
            "date": last_date.strftime("%Y-%m-%d"),
            "equity": cash,
            "cash": cash,
            "pos_value": 0.0
        })

        # --- TAHAP C: EVALUASI PERFORMA & METRIK ---
        df_equity = pd.DataFrame(daily_equity)
        
        # Hitung return harian
        df_equity["daily_return"] = df_equity["equity"].pct_change()
        
        total_return_pct = ((df_equity["equity"].iloc[-1] / self.initial_capital) - 1.0) * 100
        
        # Sharpe Ratio (disetahunkan, risk-free rate diasumsikan 5% / 250 hari trading)
        rf_daily = 0.05 / 250
        excess_returns = df_equity["daily_return"].dropna() - rf_daily
        if len(excess_returns) > 1 and excess_returns.std() > 0:
            sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(250)
        else:
            sharpe = 0.0
            
        # Maximum Drawdown
        df_equity["peak"] = df_equity["equity"].cummax()
        df_equity["dd"] = (df_equity["equity"] - df_equity["peak"]) / df_equity["peak"]
        max_dd_pct = df_equity["dd"].min() * 100
        
        # Statistik Trades
        df_trades = pd.DataFrame(trade_logs)
        if not df_trades.empty:
            total_trades = len(df_trades)
            winning_trades = len(df_trades[df_trades["pnl"] > 0])
            losing_trades = len(df_trades[df_trades["pnl"] <= 0])
            win_rate = (winning_trades / total_trades) * 100
            
            total_profit = df_trades[df_trades["pnl"] > 0]["pnl"].sum()
            total_loss = abs(df_trades[df_trades["pnl"] <= 0]["pnl"].sum())
            
            profit_factor = total_profit / total_loss if total_loss > 0 else total_profit
            avg_pnl_pct = df_trades["pnl_pct"].mean()
        else:
            total_trades = 0
            win_rate = 0.0
            profit_factor = 0.0
            avg_pnl_pct = 0.0
            
        # Simulasikan Benchmark IHSG Buy & Hold (Menggunakan rata-rata harga saham semesta)
        # Untuk kesederhanaan, kita hitung indeks rata-rata closing price seluruh emiten di semesta
        market_index = df.groupby("date")["close"].mean().reset_index()
        market_index.sort_values("date", inplace=True)
        market_initial = market_index["close"].iloc[0]
        market_index["benchmark_equity"] = (market_index["close"] / market_initial) * self.initial_capital
        market_index["date_str"] = market_index["date"].dt.strftime("%Y-%m-%d")
        
        # Merge benchmark ke equity curve
        df_equity = df_equity.merge(
            market_index[["date_str", "benchmark_equity"]],
            left_on="date",
            right_on="date_str",
            how="left"
        ).drop(columns=["date_str"])
        
        df_equity["benchmark_equity"] = df_equity["benchmark_equity"].ffill()
        benchmark_return_pct = ((df_equity["benchmark_equity"].iloc[-1] / self.initial_capital) - 1.0) * 100

        # Rinci hasil dalam dict
        results = {
            "initial_capital": self.initial_capital,
            "final_equity": df_equity["equity"].iloc[-1],
            "total_return_pct": round(total_return_pct, 2),
            "benchmark_return_pct": round(benchmark_return_pct, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "total_trades": total_trades,
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_pnl_pct": round(avg_pnl_pct, 2),
            "equity_curve": df_equity[["date", "equity", "cash", "pos_value", "benchmark_equity"]].to_dict(orient="records"),
            "trade_logs": df_trades.head(100).to_dict(orient="records") if not df_trades.empty else []
        }
        
        print(f"[OK] Backtest selesai. Return: {results['total_return_pct']}% vs Benchmark: {results['benchmark_return_pct']}%")
        return results
