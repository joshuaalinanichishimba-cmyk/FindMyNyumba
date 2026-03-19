
# --- FORCED RESET ENDPOINT ---
@router.post('/request-reset')
def request_reset_forced(email: str):
    reset_link = f"http://localhost:3000/reset-password.html?token=magic_token_123"
    print(f"\n{'='*60}\n🚨 DEBUG: PASSWORD RESET LINK GENERATED 🚨\n👉 COPY THIS LINK: {reset_link}\n{'='*60}\n")
    return {"msg": "Success"}
