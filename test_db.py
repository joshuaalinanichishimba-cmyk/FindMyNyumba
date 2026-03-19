import os
from sqlalchemy import create_engine

env_dict = {}
try:
    with open('.env', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Only process lines that have data, are not comments, and contain an '=' sign
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                env_dict[key.strip()] = val.strip()
except Exception as e:
    print(f'❌ Could not read .env file: {e}')
    exit()

db_url = env_dict.get('DATABASE_URL')
print('Attempting to connect to the PostgreSQL database...')

try:
    if not db_url:
        print('❌ DATABASE CONNECTION FAILED: No DATABASE_URL found in .env file.')
        exit()
        
    # Attempt to open the connection
    engine = create_engine(db_url)
    with engine.connect() as connection:
        print('✅ DATABASE CONNECTION SUCCESSFUL! The backend is talking to PostgreSQL.')
except Exception as e:
    print('❌ DATABASE CONNECTION FAILED!')
    print(f'Details: {e}')
