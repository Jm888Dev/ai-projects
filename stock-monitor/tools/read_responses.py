import sqlite3

c = sqlite3.connect('prices.db')
c.row_factory = sqlite3.Row

rows = c.execute("""
    SELECT model, prompt_size, decode_mode, json_valid,
           direction_valid, ticker_mismatch, raw_response
    FROM slm_benchmarks
    ORDER BY id DESC LIMIT 38
""").fetchall()

for r in rows:
    print(f"--- {r['model']} | {r['prompt_size']} | {r['decode_mode']} | "
          f"json={r['json_valid']} dir={r['direction_valid']} mismatch={r['ticker_mismatch']} ---")
    print(r['raw_response'][:3600] if r['raw_response'] else 'NO RESPONSE')
    print()

c.close()