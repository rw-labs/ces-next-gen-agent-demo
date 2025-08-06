import os
import logging

from dotenv import load_dotenv
load_dotenv()

LOG_LEVEL=os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_TO_FILE= True if (os.getenv('LOG_TO_FILE', False) == "true") else False
LOG_FILE_NAME=os.getenv('LOG_FILE_NAME', "debug_messages.log")

print(f"LOG_LEVEL: {os.getenv('LOG_LEVEL')}")

if LOG_TO_FILE:
    logging.basicConfig(
        filename=LOG_FILE_NAME,
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s",
        force=True
    )
else:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s",
        force=True
    )

logger = logging.getLogger(__name__)
