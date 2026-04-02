
import os

from pathlib import Path

from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker, declarative_base

from dotenv import load_dotenv



# Find the exact path to the .env file

env_path = Path(__file__).resolve().parent.parent.parent / ".env"

load_dotenv(dotenv_path=env_path)



SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")



if not SQLALCHEMY_DATABASE_URL:

    raise ValueError("🚨 DATABASE_URL is missing! Check your .env file.")



# Create the database engine

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()



def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()
