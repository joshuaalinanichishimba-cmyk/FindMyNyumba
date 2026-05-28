from app.main import engine
from sqlalchemy import text

def run_upgrade():
    queries = [
        "ALTER TABLE properties ADD COLUMN owner_id INTEGER DEFAULT 1;",
        "ALTER TABLE properties ADD COLUMN image_urls TEXT DEFAULT '';",
        "ALTER TABLE properties ADD COLUMN is_featured BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE properties ADD COLUMN is_boosted BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE properties ADD COLUMN subscription_tier VARCHAR(50) DEFAULT 'basic';"
    ]
    
    with engine.begin() as conn:
        for q in queries:
            try:
                conn.execute(text(q))
                print(f"✅ Success: {q}")
            except Exception as e:
                # If column already exists, safely ignore
                print(f"⏩ Skipped (Already exists): {q.split('ADD COLUMN ')[1].split(' ')[0]}")

if __name__ == "__main__":
    run_upgrade()
