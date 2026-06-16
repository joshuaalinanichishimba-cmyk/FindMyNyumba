import os
import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql.expression import func
from typing import List

import google.generativeai as genai

# Import our custom modules (You must have these files: database.py, models.py, security.py)
from database import engine, Base, get_db
from models import (
    User, Customer, Expense, Feedback, ServiceCredential,
    UserCreate, Token, RegistrationRequest, FeedbackCreate,
    CustomerResponse, CustomerUpdate, ExpenseCreate, ExpenseResponse,
    CredentialsUpdate, DashboardStats, AIPlanAdvisorRequest,
    AIReminderRequest, AIBusinessInsightsRequest,
    ConfirmPaymentResponse
)
from security import (
    authenticate_user, create_access_token, get_password_hash,
    get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
)

# Load .env variables
load_dotenv()

# Configure Gemini AI
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_API_KEY not set. AI features will be disabled.")
    genai.configure(api_key="DUMMY_KEY")
else:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- FastAPI App Initialization ---
app = FastAPI(title="Ali Subscription Express API")

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Setup ---
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Use this line ONLY if you need to force drop tables
        await conn.run_sync(Base.metadata.create_all)

# =A_P_I_T_A_G_S=
tags_auth = "1. Authentication"
tags_public = "2. Public"
tags_customers = "3. Admin: Customers"
tags_dashboard = "4. Admin: Dashboard"
tags_ai = "5. Admin: AI Tools"

# ==================================================
# 1. AUTHENTICATION ENDPOINTS
# ==================================================

@app.post("/api/v1/auth/token", response_model=Token, tags=[tags_auth])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/v1/auth/create-admin", status_code=status.HTTP_201_CREATED, tags=[tags_auth])
async def create_admin_user(
    user: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    # Optional: Check if admin already exists
    existing_user = await db.execute(select(User).filter(User.username == user.username))
    if existing_user.scalars().first():
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return {"username": db_user.username, "message": "Admin user created successfully."}

@app.get("/api/v1/auth/me", tags=[tags_auth])
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return {"username": current_user.username}

# ==================================================
# 2. PUBLIC ENDPOINTS
# ==================================================

# --- *** UPDATED submit_registration *** ---
@app.post("/api/v1/public/registrations", status_code=status.HTTP_201_CREATED, tags=[tags_public])
async def submit_registration(
    req: RegistrationRequest,
    db: AsyncSession = Depends(get_db)
):
    due_date = datetime.datetime.utcnow() + datetime.timedelta(days=30 * req.months)

    new_customer = Customer(
        name=req.name,
        email=req.email,
        number=req.number,
        # location=req.location, # <-- REMOVED
        plan=req.plan,
        due_date=due_date,
        paid=0,
        renewal_count=0,
        renewal_history=[],
        notes="Payment submitted by user, pending admin confirmation.",
        has_discount=False,
        payment_confirmed=False
    )
    db.add(new_customer)
    await db.commit()
    return {"message": "Registration submitted. Awaiting payment confirmation."}

@app.post("/api/v1/public/feedback", status_code=status.HTTP_201_CREATED, tags=[tags_public])
async def submit_feedback(
    req: FeedbackCreate,
    db: AsyncSession = Depends(get_db)
):
    new_feedback = Feedback(message=req.message)
    db.add(new_feedback)
    await db.commit()
    return {"message": "Feedback received. Thank you!"}

# ==================================================
# 3. ADMIN: CUSTOMER ENDPOINTS
# ==================================================

@app.get("/api/v1/admin/customers", response_model=List[CustomerResponse], tags=[tags_customers])
async def get_all_customers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Customer).order_by(Customer.due_date))
    return result.scalars().all()

@app.post("/api/v1/admin/customers/{customer_id}/confirm-payment", response_model=ConfirmPaymentResponse, tags=[tags_customers])
async def confirm_payment(
    customer_id: int,
    plan_price: float,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Customer).filter(Customer.id == customer_id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer.payment_confirmed = True
    customer.paid = (customer.paid or 0) + plan_price
    customer.renewal_count = (customer.renewal_count or 0) + 1

    new_history = {
        "date": datetime.datetime.utcnow().isoformat(),
        "amount": plan_price
    }
    customer.renewal_history = (customer.renewal_history or []) + [new_history]

    customer.notes = (customer.notes or "").replace(
        'pending admin confirmation', 'Payment Confirmed.'
    )

    creds = {}
    keys = ["netflixEmail", "netflixPassword", "spotifyInfo", "appleMusicInfo"]
    for key in keys:
        cred_result = await db.execute(select(ServiceCredential).filter(ServiceCredential.key == key))
        cred = cred_result.scalars().first()
        creds[key] = cred.value if cred else ""

    message_lines = [
        f"Payment confirmed for {customer.name}!",
        "--- SIMULATING CREDENTIAL SEND ---",
        f"Sending details to {customer.number}:"
    ]

    plan_name = customer.plan.lower()
    sent_details = False
    if "netflix" in plan_name:
        message_lines.append(f"Netflix Email: {creds.get('netflixEmail', 'N/A')}")
        message_lines.append(f"Netflix Pass: ********")
        sent_details = True

    if "spotify" in plan_name:
        message_lines.append(f"Spotify Info: {creds.get('spotifyInfo', 'N/A')}")
        sent_details = True

    if "apple" in plan_name or "all-in-one" in plan_name:
        message_lines.append(f"Apple Music Info: {creds.get('appleMusicInfo', 'N/A')}")
        sent_details = True

    if not sent_details:
        message_lines.append("Plan name not recognized. Sending all details as a fallback:")
        message_lines.append(f"Netflix Email: {creds.get('netflixEmail', 'N/A')}")
        message_lines.append(f"Netflix Pass: ********")
        message_lines.append(f"Spotify Info: {creds.get('spotifyInfo', 'N/A')}")
        message_lines.append(f"Apple Music Info: {creds.get('appleMusicInfo', 'N/A')}")

    message_lines.append("---------------------------------")

    simulation_message = "\n".join(message_lines)

    db.add(customer)
    await db.commit()
    await db.refresh(customer)

    return ConfirmPaymentResponse(customer=customer, simulation_message=simulation_message)

@app.post("/api/v1/admin/customers/{customer_id}/renew", response_model=CustomerResponse, tags=[tags_customers])
async def renew_subscription(
    customer_id: int,
    months: int,
    price: float,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Customer).filter(Customer.id == customer_id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    current_due_date = customer.due_date or datetime.datetime.utcnow()
    new_due_date = current_due_date + datetime.timedelta(days=30 * months)

    customer.due_date = new_due_date
    customer.paid = (customer.paid or 0) + price
    customer.renewal_count = (customer.renewal_count or 0) + 1

    new_history = {
        "date": datetime.datetime.utcnow().isoformat(),
        "amount": price
    }
    customer.renewal_history = (customer.renewal_history or []) + [new_history]
    customer.notes = (customer.notes or "") + f" | Renewed on {datetime.date.today()}"

    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer

# --- *** UPDATED update_customer_details *** ---
@app.put("/api/v1/admin/customers/{customer_id}", response_model=CustomerResponse, tags=[tags_customers])
async def update_customer_details(
    customer_id: int,
    req: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Customer).filter(Customer.id == customer_id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer.name = req.name
    customer.email = req.email
    customer.number = req.number
    # customer.location = req.location # <-- REMOVED
    customer.plan = req.plan
    customer.notes = req.notes
    customer.has_discount = req.has_discount

    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer

# ==================================================
# 4. ADMIN: DASHBOARD ENDPOINTS
# ==================================================

@app.get("/api/v1/admin/dashboard/stats", response_model=DashboardStats, tags=[tags_dashboard])
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    now = datetime.datetime.utcnow()
    one_week_from_now = now + datetime.timedelta(days=7)

    total_revenue_result = await db.execute(select(func.sum(Customer.paid)).filter(Customer.payment_confirmed == True))
    total_revenue = total_revenue_result.scalar() or 0.0

    total_expense_result = await db.execute(select(func.sum(Expense.amount)))
    total_expense = total_expense_result.scalar() or 0.0

    true_profit = total_revenue - total_expense

    customer_count_result = await db.execute(select(func.count(Customer.id)))
    customer_count = customer_count_result.scalar() or 0

    due_soon_count_result = await db.execute(
        select(func.count(Customer.id)).filter(Customer.due_date > now, Customer.due_date <= one_week_from_now)
    )
    due_soon_count = due_soon_count_result.scalar() or 0

    overdue_count_result = await db.execute(
        select(func.count(Customer.id)).filter(Customer.due_date <= now)
    )
    overdue_count = overdue_count_result.scalar() or 0

    loyal_customer_count_result = await db.execute(
        select(func.count(Customer.id)).filter(Customer.renewal_count >= 3)
    )
    loyal_customer_count = loyal_customer_count_result.scalar() or 0

    return DashboardStats(
        totalRevenue=total_revenue,
        trueProfit=true_profit,
        customerCount=customer_count,
        dueSoonCount=due_soon_count,
        overdueCount=overdue_count,
        loyalCustomerCount=loyal_customer_count
    )

@app.post("/api/v1/admin/expenses", response_model=ExpenseResponse, tags=[tags_dashboard])
async def log_expense(
    req: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    new_expense = Expense(month_year=req.month_year, amount=req.amount)
    db.add(new_expense)
    await db.commit()
    await db.refresh(new_expense)
    return new_expense

@app.get("/api/v1/admin/expenses", response_model=List[ExpenseResponse], tags=[tags_dashboard])
async def get_expenses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    result = await db.execute(select(Expense).order_by(Expense.timestamp.desc()))
    return result.scalars().all()

@app.get("/api/v1/admin/credentials", response_model=CredentialsUpdate, tags=[tags_dashboard])
async def get_credentials(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    keys = ["netflixEmail", "netflixPassword", "spotifyInfo", "appleMusicInfo"]
    creds = {}
    for key in keys:
        result = await db.execute(select(ServiceCredential).filter(ServiceCredential.key == key))
        cred = result.scalars().first()
        creds[key] = cred.value if cred else ""
    return CredentialsUpdate(**creds)

@app.post("/api/v1/admin/credentials", tags=[tags_dashboard])
async def save_credentials(
    req: CredentialsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    for key, value in req.dict().items():
        result = await db.execute(select(ServiceCredential).filter(ServiceCredential.key == key))
        cred = result.scalars().first()
        if cred:
            cred.value = value
            db.add(cred)
        else:
            new_cred = ServiceCredential(key=key, value=value)
            db.add(new_cred)
    await db.commit()
    return {"message": "Credentials saved successfully."}

# ==================================================
# 5. ADMIN: AI ENDPOINTS
# ==================================================

def get_gemini_model():
    if GOOGLE_API_KEY == "DUMMY_KEY" or not GOOGLE_API_KEY:
          raise HTTPException(
              status_code=503,
              detail="AI Service not configured. Please set GOOGLE_API_KEY in .env"
          )
    return genai.GenerativeModel('gemini-pro')

@app.post("/api/v1/ai/recommendation", tags=[tags_ai])
async def get_ai_recommendation(
    req: AIPlanAdvisorRequest,
    current_user: User = Depends(get_current_active_user)
):
    model = get_gemini_model()
    prompt = f"""
    A customer provided the following preferences for a streaming subscription service:
    - Watches movies/shows: {req.q1}
    - Importance of new music: {req.q2}
    - Looking for long-term savings: {req.q3}

    Our plans are:
    - Netflix (Shared): K50/mo
    - Netflix (Private): K100/mo
    - Spotify: K50/mo
    - Apple Music: K50/mo
    - We offer 2 and 3 month discounts.

    Based on their answers, recommend the best plan for them and briefly explain why. Be friendly and concise.
    """
    try:
        response = await model.generate_content_async(prompt)
        return {"recommendation": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

@app.post("/api/v1/ai/reminder", tags=[tags_ai])
async def generate_ai_reminder(
    req: AIReminderRequest,
    current_user: User = Depends(get_current_active_user)
):
    model = get_gemini_model()
    prompt = f"""
    Generate a friendly and professional WhatsApp reminder message for a customer.
    - Customer Name: {req.name}
    - Plan: {req.plan}
    - Due Date: {req.dueDate}

    The message should:
    1. Greet the customer by name.
    2. Remind them their subscription is due.
    3. Mention the payment details (Airtel: 0973404727, MTN: 0765158426).
    4. Be polite and include a "thank you".
    """
    try:
        response = await model.generate_content_async(prompt)
        return {"message": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

@app.post("/api/v1/ai/insights", tags=[tags_ai])
async def generate_business_insights(
    req: AIBusinessInsightsRequest,
    current_user: User = Depends(get_current_active_user)
):
    model = get_gemini_model()
    prompt = f"""
    I am the admin for 'Ali Subscription Express'. Here are my current business stats:
    - Total Revenue: K{req.stats.totalRevenue}
    - True Profit: K{req.stats.trueProfit}
    - Total Customers: {req.stats.customerCount}
    - Customers Due Soon: {req.stats.dueSoonCount}
    - Customers Overdue: {req.stats.overdueCount}
    - Loyal Customers (3+ renewals): {req.stats.loyalCustomerCount}

    Here is the popularity of my plans:
    {str(req.plans)}

    Based ONLY on this data, provide 3 short, actionable business insights or suggestions.
    Focus on growth, retention, or profitability.
    """
    try:
        response = await model.generate_content_async(prompt)
        return {"insights": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

# --- Run the App ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)