from app.db.session import engine
from app.db.base import Base
import os

def init_db():
    print("Checking database path...")
    if not os.path.exists("data"):
        os.makedirs("data")
    
    print("Building tables...")
    Base.metadata.create_all(bind=engine)
    print("Success! Database initialized at ./data/findmynyumba.db")

if __name__ == "__main__":
    init_db()
