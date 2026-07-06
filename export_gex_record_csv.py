import sqlite3
import json
import csv

conn = sqlite3.connect('gex.db')

# Get the specific record
row = conn.execute(
    "SELECT ndate, ntime, price, data FROM gex_strike_window "
    "WHERE ndate=20260706 AND ntime=701 AND symbol='SPX' "
    "ORDER BY source LIMIT 1",
).fetchone()

if not row:
    print("No record found for 20260706 701")
    conn.close()
    exit()

ndate, ntime, price, data_json = row
strikes = json.loads(data_json)

print(f"Record: {ndate} {ntime}, Price: {price}, Strikes: {len(strikes)}")

# Write to CSV
output_file = 'gex_record_20260706_701.csv'
fieldnames = ['strike', 'cg', 'pg', 'net', 'abs', 'total', 'coi', 'poi', 'cvol', 'pvol', 'pcmag', 'cotm', 'potm']

with open(output_file, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for s in strikes:
        writer.writerow({
            'strike': s.get('strike'),
            'cg': s.get('cg', 0),
            'pg': s.get('pg', 0),
            'net': s.get('net', 0),
            'abs': s.get('abs', 0),
            'total': s.get('total', 0),
            'coi': s.get('coi', 0),
            'poi': s.get('poi', 0),
            'cvol': s.get('cvol', 0),
            'pvol': s.get('pvol', 0),
            'pcmag': s.get('pcmag', 0),
            'cotm': s.get('cotm', 0),
            'potm': s.get('potm', 0),
        })

print(f"CSV exported to: {output_file}")
conn.close()
