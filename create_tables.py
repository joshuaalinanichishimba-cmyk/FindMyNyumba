from app.core.database import engine, Base
from app.models.user import User
from app.models.listing import Listing

print("Creating database tables...")
# This command looks at all classes inheriting from Base and creates them in SQLite
Base.metadata.create_all(bind=engine)
print("Tables 'users' and 'listings' created successfully!")
