from app.core.database import engine
from app.models import models
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("DROP SCHEMA public CASCADE;"))
    conn.execute(text("CREATE SCHEMA public;"))
    conn.commit()

models.Base.metadata.create_all(bind=engine)
print('✅ Database rebuilt with new location column!')
