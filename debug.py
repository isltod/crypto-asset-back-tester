import ccxt
from datetime import datetime, timezone
import pandas as pd

# Use naive datetime and assume KST -> convert to UTC ms
dt_start = pd.to_datetime('2026-03-21 20:29:00').tz_localize('Asia/Seoul')
start_ms = int(dt_start.timestamp() * 1000)

exchange = ccxt.binance({'options': {'defaultType': 'future'}})
ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1m', since=start_ms, limit=10)
print(f"start_ms: {start_ms}")
print(f"fetched: {len(ohlcv)}")
if ohlcv:
    print(f"first candle ts: {ohlcv[0][0]}")

