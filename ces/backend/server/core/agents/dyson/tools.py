import logging
import os
import uuid
from datetime import datetime, timedelta

from .mygmail import GmailClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID", "hello-world-418507")
logger.info(f"PROJECT_ID: {PROJECT_ID}")

gmail = gmail = GmailClient(token_path=f"secret:gmail-token:{PROJECT_ID}")


def send_email(to: str, subject: str, message_text: str) -> dict:
    """Send an email using Gmail API.

    Args:
        to (str): Email address of the recipient
        subject (str): Subject line of the email
        message_text (str): Body text of the email

    Returns:
        dict: Dictionary containing:
            - status (str): "success" or "error"
            - message (str): Success message or error details
    """
    logger.info(
        f"Sending email - To: {to}, Subject: {subject}, Message: {message_text}"
    )

    try:
        gmail.send_email(to, subject, message_text)
        logger.info("Email sent successfully")
        return {"status": "success", "message": "Email sent successfully"}

    except Exception as e:
        error_msg = f"Error sending email: {e}"
        logger.info(error_msg)
        return {"status": "error", "message": error_msg}


def schedule_appointment(customer_id: str, start_time: str, showroom: str) -> dict:
    """
    Schedules a mock appointment at a Dyson showroom for a fixed one-hour slot.

    Args:
        customer_id (str): Unique identifier for the customer.
        start_time (str): Desired appointment start time in 'YYYY-MM-DD HH:MM' format.
        showroom (str): Name of the Dyson showroom where the appointment will be held.

    Returns:
        dict: Appointment confirmation or error message. On success, returns a detailed appointment object
              containing appointment_id, scheduled_slot, venue, and status information.
    """
    logger.info(
        f"Scheduling technician appointment for customer {customer_id} at start time: {start_time} at {showroom}"
    )
    # Validate and parse start_time
    try:
        dt_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
    except ValueError:
        logger.error(f"Invalid start_time format: {start_time}")
        return {
            "status": "error",
            "message": "Invalid start_time format. Use 'YYYY-MM-DD HH:MM'.",
            "customer_id": customer_id,
            "requested_start_time": start_time,
            "venue": showroom,
        }

    # Calculate end time (1 hour later)
    dt_end = dt_start.replace(second=0, microsecond=0) + timedelta(hours=1)
    slot_str = f"{dt_start.strftime('%Y-%m-%d %H:%M')}-{dt_end.strftime('%H:%M')}"
    appointment_id = f"APT-{uuid.uuid4().hex[:3].upper()}"
    logger.info(
        f"Successfully scheduled appointment {appointment_id} for {customer_id} at {slot_str}"
    )
    return {
        "status": "success",
        "appointment_id": appointment_id,
        "customer_id": customer_id,
        "scheduled_slot": slot_str,
        "venue": showroom,
        "message": f"Appointment successfully scheduled for {slot_str}. Your appointment ID is {appointment_id}.",
    }


def show_hair_dryer_models():
    """
    Dummy tool that returns three Dyson hair dryer models with descriptions.
    """
    return {
        "status": "success",
        "models": [
            {
                "model": "supersonic r",
                "description": "Our most powerful, yet lightest hair dryer.",
            },
            {
                "model": "supersonic nural",
                "description": "Fast, intelligent drying. Scalp health protection.",
            },
            {
                "model": "supersonic",
                "description": "Fast drying with no extreme heat",
            },
        ],
    }


def show_youtube_video(product_name: str):
    """
    Tool that returns a YouTube video URL based on the product name.
    Supports multiple Dyson products with specific video IDs.
    Never read out the youtube video url.
    
    Args:
        product_name (str): The name of the Dyson product (e.g., "airwrap", "supersonic r", "supersonic")

    """
    video_map = {
        "airwrap": "3uCWL0EoDm0",
        "supersonic r": "nRaQDFgB_6c"
    }
    
    video_id = video_map.get(product_name.lower())
    if video_id:
        return {
            "status": "success",
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
        }
    else:
        return {
            "status": "error", 
            "message": f"No YouTube video found for {product_name}",
        }