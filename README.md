FindMyNyumba 🏠
FindMyNyumba is a modern student housing and rental marketplace application designed to connect students with verified landlords and property listings.

🚀 Features
Secure Authentication: JWT-based login system with Argon2 password hashing.

Role-Based Access Control: Separate permissions for Admin, Landlord, and Regular Users.

Property Management: Landlords can list properties and upload multiple images.

Review System: Verified users can rate properties (1-5 stars) and leave comments.

Rating Analytics: Automatic calculation of average ratings and review summaries.

🛠️ Tech Stack
Backend: FastAPI (Python)

Database: SQLAlchemy with SQLite

Security: JWT (Jose) & Passlib (Argon2)

File Handling: Multipart form-data for image uploads

📥 Installation & Setup
Clone the repository:

Bash
git clone https://github.com/[your-username]/FindMyNyumba.git
cd FindMyNyumba/backend
Create a Virtual Environment:

Bash
python -m venv venv
.\venv\Scripts\activate  # On Windows
Install Dependencies:

Bash
pip install -r requirements.txt
Run the Server:

Bash
uvicorn app.main:app --reload
🔒 API Security & Roles
The API uses a custom role-checker to protect sensitive routes:

Admin: Full access to all data and user management.

Landlord: Can create and edit their own property listings.

User: Can browse listings and leave reviews.

📂 Project Structure
Plaintext
backend/

backend/
├── app/
│   ├── api/v1/         # Route handlers (auth, properties, reviews)
│   ├── models/         # Database schemas
│   └── db/             # Database connection & sessions
├── static/             # Uploaded property images
└── main.py             # Application entry point
