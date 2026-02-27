from fastapi import APIRouter, BackgroundTasks, Depends
from app.utils.notifications import NotificationService
from app.core.responses import success_response

router = APIRouter()

@router.post("/register-test")
async def register_student(email: str, name: str, background_tasks: BackgroundTasks):
    # 1. Logic to save student to DB goes here...
    
    # 2. Add the notification to background tasks
    # The response is sent to the user IMMEDIATELY, 
    # and the server runs the function after.
    background_tasks.add_task(NotificationService.send_welcome_notification, email, name)
    
    return success_response(
        data={"email": email}, 
        message="Registration started! You will receive a notification shortly."
    )
