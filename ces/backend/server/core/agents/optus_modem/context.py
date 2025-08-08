# ./server/core/agents/ollie/context.py
import json
import logging
import os
from datetime import datetime
from config.config import PROMPT_LANGUAGE, FIRST_NAME, LAST_NAME

logger = logging.getLogger(__name__)

# Use configured names or provide Ollie-specific defaults
USER_CUSTOMER_FIRST_NAME = FIRST_NAME # Or "Alex"
USER_CUSTOMER_LAST_NAME = LAST_NAME   # Or "Consumer"

DEFAULT_LANGUAGE = PROMPT_LANGUAGE or "en-AU"

# Path to the product catalog JSON file
# Assuming product_v3.json is in the same directory as this context.py file,
# or an appropriate path is provided.
PRODUCT_CATALOG_FILE = os.path.join(os.path.dirname(__file__), 'product_v4.json')

def load_catalog_data(file_path: str) -> list:
    """Loads product catalog data from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                logger.error(f"Product catalog JSON at {file_path} is not a list.")
                return []
    except FileNotFoundError:
        logger.error(f"Product catalog file not found: {file_path}")
        return []
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from product catalog file: {file_path}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading product catalog {file_path}: {e}")
        return []

class OptusModemContext:
    # Load the live catalog data from the JSON file
    # LIVE_OPTUS_CATALOG_DATA = load_catalog_data(PRODUCT_CATALOG_FILE)
    # if not LIVE_OPTUS_CATALOG_DATA:
    #     logger.warning("LIVE_OPTUS_CATALOG_DATA is empty. Search functionality will be affected.")

    CUSTOMER_PROFILE = {
        "customer_profile": {
            "first_name": USER_CUSTOMER_FIRST_NAME,
            "last_name": USER_CUSTOMER_LAST_NAME,
            "is_optus_customer": True, # Can be updated based on interaction
            "modem_type": "Optus Ultra 5G modem", # Can be identified during conversation
            "upgrade_interest": None, # e.g., "Looking for new phone"
            "preferred_contact_method": "chat",
        },
        "brand_name": "Optus",
        "assistant_name": "Modem Setup Assistant",
        "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": None, # Will be populated at runtime
        "language": DEFAULT_LANGUAGE
    }

    # Note: The static OPTUS_ANDROID_CATALOG from R1 is no longer used by the primary catalog search tool.
    # If it was present in R2 context, it's superseded by LIVE_OPTUS_CATALOG_DATA for the search_live_optus_catalog tool.