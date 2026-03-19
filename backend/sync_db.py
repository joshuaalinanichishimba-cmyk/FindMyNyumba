from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("Checking for photo_url column...")
    try:
        conn.execute(text("ALTER TABLE properties ADD COLUMN photo_url VARCHAR;"))
        conn.commit()
        print("✅ photo_url column added successfully!")
    except Exception as e:
        print("ℹ️ Column might already exist or: ", e)
