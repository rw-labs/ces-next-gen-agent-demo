from datetime import datetime

from config.config import PROMPT_LANGUAGE

DEFAULT_LANGUAGE = PROMPT_LANGUAGE or "en-US"  # Default to Canadian English


class DysonContext:
    CUSTOMER_PROFILE = {
        "customer_profile": {
            "customer_first_name": "George",  # As requested
            "customer_last_name": "Liao",  # As requested
            "email": "weiyih@google.com",
        },
        "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": None,  # Will be populated at runtime
        "language": DEFAULT_LANGUAGE,
    }
