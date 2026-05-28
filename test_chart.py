import os
import pandas as pd
import numpy as np
import mplfinance as mpf

def test_chart():
    # Load features cache to get some stock data
    cache_path = "analisa/features_cache.csv"
    if not os.path.exists(cache_path):
        print("Features cache not found. Please run the screener first.")
        return

    df = pd.read_csv(cache_path)
    df["date"] = pd.to_datetime(df["date"])
    
    # Let's take 'DEWA' or another active stock
    ticker = "DEWA"
    if ticker not in df["ticker"].unique():
        ticker = df["ticker"].unique()[0]
        
    df_stock = df[df["ticker"] == ticker].copy()
    print(f"Selected stock: {ticker} with {len(df_stock)} rows")
    
    # Set index
    df_stock.set_index("date", inplace=True)
    df_stock.sort_index(inplace=True)
    df_stock = df_stock.tail(100)
    
    df_stock.rename(columns={
        "open": "Open", "high": "High", "low": "Low", 
        "close": "Close", "volume": "Volume"
    }, inplace=True)
    
    # Calculate Bollinger Bands
    df_stock['SMA20'] = df_stock['Close'].rolling(window=20).mean()
    df_stock['BB_Upper'] = df_stock['SMA20'] + 2 * df_stock['Close'].rolling(window=20).std()
    df_stock['BB_Lower'] = df_stock['SMA20'] - 2 * df_stock['Close'].rolling(window=20).std()
    
    # TradingView Dark Theme Market Colors
    # Up candle: Teal Green (#089981), Down candle: Cherry Red (#f23645)
    mc = mpf.make_marketcolors(
        up='#089981', down='#f23645',
        edge='inherit',
        wick='inherit',
        volume='inherit',
        ohlc='inherit'
    )
    
    # TradingView Dark Theme MPF Style
    # Background: #131722, Grid: #2a2e39
    tv_style = mpf.make_mpf_style(
        base_mpf_style='charles',
        marketcolors=mc,
        facecolor='#131722',
        figcolor='#131722',
        gridcolor='#2a2e39',
        gridstyle='-',
        rc={
            'axes.labelcolor': '#848e9c',
            'axes.edgecolor': '#2a2e39',
            'xtick.color': '#848e9c',
            'ytick.color': '#848e9c',
            'text.color': '#ffffff',
            'grid.color': '#2a2e39',
            'grid.linestyle': '-',
            'grid.linewidth': 0.5,
            'font.family': 'sans-serif'
        }
    )
    
    # Addplots for Bollinger Bands styled like TradingView
    # Upper/Lower Bands are light blue (#2962ff), SMA20 is orange (#ff9800)
    apds = [
        mpf.make_addplot(df_stock['BB_Upper'], color='#2962ff', width=1.0, alpha=0.8),
        mpf.make_addplot(df_stock['SMA20'], color='#ff9800', width=1.2, alpha=0.8),
        mpf.make_addplot(df_stock['BB_Lower'], color='#2962ff', width=1.0, alpha=0.8),
    ]
    
    # Save chart
    save_path = "test_tv_chart.png"
    mpf.plot(
        df_stock, type='candle', volume=True, addplot=apds,
        title=f"Analisis Teknikal: {ticker} (TradingView Theme)",
        style=tv_style,
        savefig=dict(fname=save_path, dpi=120, bbox_inches='tight')
    )
    print(f"Chart successfully saved to {save_path}")

if __name__ == "__main__":
    test_chart()
