"""Quick DB inspector. Useful when debugging a fresh setup.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\db_status.py [path/to/sqlite.db]
"""
import sqlite3
import sys
from pathlib import Path

db_path = Path(sys.argv[1] if len(sys.argv) > 1 else "oncoboard.db")
if not db_path.exists():
    print(f"DB not found at {db_path}")
    sys.exit(1)

con = sqlite3.connect(db_path)
con.row_factory = sqlite3.Row

print(f"DB: {db_path.resolve()}  ({db_path.stat().st_size:,} bytes)\n")

tables = [r["name"] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()]
print(f"Tables ({len(tables)}): {', '.join(tables)}\n")

print("Row counts:")
for t in tables:
    n = con.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
    print(f"  {t:<20} {n}")

print("\nFirst 5 cases:")
for row in con.execute(
    "SELECT case_id, ajcc_stage, er_status, pr_status, her2_status, molecular_subtype "
    "FROM cases ORDER BY case_id LIMIT 5"
):
    print(f"  {row['case_id']:<18} stage={row['ajcc_stage'] or '-':<10} "
          f"ER={row['er_status'] or '-':<10} PR={row['pr_status'] or '-':<10} "
          f"HER2={row['her2_status'] or '-':<10} subtype={row['molecular_subtype'] or '-'}")

print("\nSubtype distribution:")
for row in con.execute(
    "SELECT COALESCE(molecular_subtype, 'Unknown') AS subtype, COUNT(*) AS n "
    "FROM cases GROUP BY molecular_subtype ORDER BY n DESC"
):
    print(f"  {row['subtype']:<20} {row['n']}")

con.close()
