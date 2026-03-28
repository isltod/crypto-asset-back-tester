import pandas as pd
df_cache = pd.read_csv('btc_usdt_1m_cache.csv')

# 2026-03-21 20:29:00 KST
start_ms = 1774092540000 
end_ms = 1774178940000

display_df = df_cache[(df_cache['timestamp'] >= start_ms) & (df_cache['timestamp'] <= end_ms)].copy()
print("display_df shape:", display_df.shape)
