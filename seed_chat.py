import sys, os
sys.path.append(os.getcwd())
from app.core.database import SessionLocal
from app.models.user import User
from app.models.message import Message

def seed_chat():
    db = SessionLocal()
    student = db.query(User).filter(User.role == "student").first()
    
    if student:
        # Create a mock Landlord
        landlord = db.query(User).filter(User.email == "landlord@test.com").first()
        if not landlord:
            landlord = User(full_name="Mr. Phiri (Landlord)", email="landlord@test.com", role="landlord")
            db.add(landlord)
            db.commit()
            db.refresh(landlord)
        
        # Send a welcome message from the Landlord to the Student
        msg = db.query(Message).filter(Message.sender_id == landlord.id).first()
        if not msg:
            welcome = Message(sender_id=landlord.id, receiver_id=student.id, content="Hello! Are you still interested in the Luxury En-suite in Kabulonga? I can arrange a viewing tomorrow.")
            db.add(welcome)
            db.commit()
            print("💬 SUCCESS: Mr. Phiri just sent you a message!")
    else:
        print("❌ No student found. Register first!")

if __name__ == "__main__": seed_chat()