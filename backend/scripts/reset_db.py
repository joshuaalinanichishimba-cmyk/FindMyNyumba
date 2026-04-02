from app.core.database import engine
from app.main import PropertyDB, Base

print('🗑️ Dropping old properties table...')
PropertyDB.__table__.drop(engine, checkfirst=True)

print('🏗️ Recreating properties table with the new rooms column...')
Base.metadata.create_all(bind=engine)

print('✅ Database schema updated successfully!')
