"""
fix_messages_table.py
Run from your backend folder:
    python fix_messages_table.py
"""
import re
import psycopg2

# Read DATABASE_URL from .env
db_url = ""
try:
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL"):
                db_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
except FileNotFoundError:
    print("ERROR: .env file not found. Make sure you run this from the backend folder.")
    exit(1)

print(f"DATABASE_URL: {db_url}")

if not db_url:
    print("ERROR: DATABASE_URL not found in .env")
    exit(1)

# Parse the connection URL
m = re.match(
    r"postgresql(?:\+psycopg2)?://([^:]+):([^@]+)@([^/:]+)(?::(\d+))?/(.+)",
    db_url,
)
if not m:
    print("ERROR: Cannot parse DATABASE_URL. Expected format:")
    print("  postgresql://user:password@host:port/dbname")
    exit(1)

user, pwd, host, port, dbname = m.groups()
port = int(port) if port else 5432

print(f"Connecting to: dbname={dbname}  user={user}  host={host}  port={port}")

try:
    conn = psycopg2.connect(
        dbname=dbname, user=user, password=pwd, host=host, port=port
    )
    cur = conn.cursor()

    # Add the 3 missing columns
    cur.execute("""
        ALTER TABLE messages
            ADD COLUMN IF NOT EXISTS attachment_url  VARCHAR,
            ADD COLUMN IF NOT EXISTS attachment_name VARCHAR,
            ADD COLUMN IF NOT EXISTS attachment_type VARCHAR;
    """)
    conn.commit()

    # Confirm
    cur.execute("""
        SELECT column_name
        FROM   information_schema.columns
        WHERE  table_name = 'messages'
        ORDER  BY ordinal_position
    """)
    cols = [r[0] for r in cur.fetchall()]
    print(f"messages columns now: {cols}")

    cur.close()
    conn.close()
    print("\n[SUCCESS] Migration complete. Now restart uvicorn.")

except psycopg2.OperationalError as e:
    print(f"ERROR connecting to database: {e}")
    exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
