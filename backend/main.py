from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from db.session import engine, Base
from models.property import Property
from routes import property_routes
from db.session import get_db

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.include_router(property_routes.router)

@app.get("/")
def root():
    return {"message": "FindMyNyumba backend is running"}

# Temporary endpoint for testing
@app.post("/test-create-property")
def test_create_property(db: Session = Depends(get_db)):
    prop = Property(
        title="Test House",
        description="A property for testing",
        location="Lusaka",
        property_type="House",
        price=1000,
        owner_id=1  # matches stubbed current_user
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return {"status": "success", "data": prop}