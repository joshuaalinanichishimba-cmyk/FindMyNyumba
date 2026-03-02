import time
from app.core.logger import logger

class NotificationService:
    @staticmethod
    def send_welcome_notification(email: str, name: str):
        # Simulate a slow network call (like sending an email/SMS)
        logger.info(f"Starting background notification for {email}")
        time.sleep(5)  # Simulate a 5-second delay
        logger.info(f"Notification successfully sent to {name} at {email}")
