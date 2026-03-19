from sqlalchemy import create_engine, text
import os

# Get DB URL from your .env
env_dict = {}
with open('.env') as f:
    for line in f:
        if '=' in line:
            k, v = line.strip().split('=', 1)
            env_dict[k] = v

engine = create_engine(env_dict.get('DATABASE_URL'))
with engine.connect() as conn:
    result = conn.execute(text("SELECT id, email, full_name, role FROM users"))
    print("\n--- USERS IN DATABASE ---")
    for row in result:
        print(f"ID: {row[0]} | Email: {row[1]} | Name: {row[2]} | Role: {row[3]}")
    print("-------------------------\n")
