import sqlite3
con = sqlite3.connect(r'G:\My Drive\Colab Notebooks\optionalpha-monitor\gex.db')
rows = con.execute("SELECT COUNT(*), COUNT(flip) FROM gex_strike_window WHERE symbol='SPX' AND source='gex'").fetchone()
print('total', rows[0], 'non_null', rows[1])
sample = con.execute("SELECT ndate, ntime, flip FROM gex_strike_window WHERE symbol='SPX' AND source='gex' AND flip IS NOT NULL ORDER BY ndate DESC, ntime DESC LIMIT 10").fetchall()
for r in sample:
    print(r)
