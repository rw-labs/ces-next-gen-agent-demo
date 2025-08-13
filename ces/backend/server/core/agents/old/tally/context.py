import json
import logging
import os
from datetime import datetime
from config.config import PROMPT_LANGUAGE, FIRST_NAME, LAST_NAME

logger = logging.getLogger(__name__)

# Use configured names or provide Tally-specific defaults
TALLY_CUSTOMER_FIRST_NAME = FIRST_NAME # Or "Paul"
TALLY_CUSTOMER_LAST_NAME = LAST_NAME   # Or "Barnes"

DEFAULT_LANGUAGE = PROMPT_LANGUAGE or "en-AU"

# Mock data for the use case
class TallyContext:
    CUSTOMER_PROFILE = {
        "customer_profile": {
            "customer_id": "paul_barnes_123",
            "first_name": TALLY_CUSTOMER_FIRST_NAME,
            "last_name": TALLY_CUSTOMER_LAST_NAME,
            "address": "42 Wallaby Way, Sydney",
            "email": "paul.barnes@example.com",
            "baseline_monthly_kwh": 450,
            "cost_per_kwh": 0.28,
            "account_type": "Energy Australia",
            "account_id": "778923"
        },
        "language": DEFAULT_LANGUAGE,
        "brand_name": "Tally",
        "assistant_name": "Adora",
        "current_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": None, # Will be populated at runtime
    }

    ENERGY_USAGE_DATA = {
        "paul_barnes_123": {
            "fridge": {
                "current_monthly_percentage": 32.0,
                "baseline_monthly_percentage": 18.0
            },
            "hvac": {
                "current_monthly_percentage": 45.0,
            },
            "lighting": {
                "current_monthly_percentage": 10.0,
            },
            "other": {
                "current_monthly_percentage": 13.0,
            }
        }
    }

    PRODUCT_CATALOG = [
        {
            "id": "FR-LG-700S",
            "brand": "LG",
            "model": "700L French Door Fridge",
            "price": 2800.00,
            "energy_rating_stars": 4.5,
            "annual_kwh": 420, # translates to 35 kWh/month
            "features": ["InstaView Door-in-Door", "Pure N Fresh Air Filtration", "SmartThinQ enabled"],
            "product_url": "https://www.lg.com/au/fridges/lg-gf-v700psl",
        },
        {
            "id": "FR-SS-640L",
            "brand": "Samsung",
            "model": "640L Family Hub Refrigerator",
            "price": 3200.00,
            "energy_rating_stars": 4.0,
            "annual_kwh": 480, # translates to 40 kWh/month
            "features": ["Family Hub Touchscreen", "Beverage Centre", "Dual Ice Maker"],
            "product_url": "https://www.samsung.com/au/refrigerators/french-door/srf7300sa-640l-silver-rf65a9770sg-sa/",
        }
    ]

    INSTALLATION_INFO = {
        "default_quote": {
            "installation_cost": 100.00,
            "old_appliance_removal_cost": 50.00,
            "total_cost": 150.00
        },
        "available_slots": [
            "Tomorrow, 9am - 11am",
            "Tomorrow, 2pm - 4pm",
            "The day after tomorrow, 10am - 12pm"
        ]
    }