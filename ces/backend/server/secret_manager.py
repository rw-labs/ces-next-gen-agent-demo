import json
import logging
import os

from google.auth.transport.requests import Request  # type: ignore
from google.cloud import secretmanager
from google.oauth2.credentials import Credentials  # type: ignore
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
from googleapiclient.discovery import build  # type: ignore

logger = logging.getLogger(__name__)

PROJECT_ID = "cx-demo-312101"
LOCATION = "us-central1"

def get_secret(secret_id, project_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode("UTF-8")

class GmailClient:
    # If modifying these scopes, delete the file token.json.
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",  # Read-only access
        "https://www.googleapis.com/auth/gmail.modify",  # Read and modify but not delete
        "https://www.googleapis.com/auth/gmail.compose",  # Create/send emails
        "https://www.googleapis.com/auth/gmail.labels",  # Manage labels
    ]

    def __init__(
        self, credentials_path="credentials.json", token_path="gmail_token.json"
    ):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth 2.0"""
        creds = None

        # Fetch credentials from Secret Manager if specified
        if self.credentials_path.startswith("secret:"):
            # Format: secret:SECRET_ID:PROJECT_ID
            _, secret_id, project_id = self.credentials_path.split(":")
            credentials_json = get_secret(secret_id, project_id)
            credentials_info = json.loads(credentials_json)
            flow = InstalledAppFlow.from_client_config(credentials_info, self.SCOPES)
            creds = flow.run_local_server(port=0)
        else:
            # If token_path is a secret, fetch and write to file
            if self.token_path.startswith("secret:"):
                _, token_secret_id, token_project_id = self.token_path.split(":")
                token_json = get_secret(token_secret_id, token_project_id)
                # Write the token to a file for use by Credentials
                with open("gmail_token.json", "w") as token_file:
                    token_file.write(token_json)
                token_path_to_use = "gmail_token.json"
            else:
                token_path_to_use = self.token_path

            # Load existing credentials if available
            if os.path.exists(token_path_to_use):
                creds = Credentials.from_authorized_user_file(token_path_to_use, self.SCOPES)

            # If no valid credentials, authenticate user
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.SCOPES
                    )
                    # Set token expiry to 1 year
                    flow.oauth2session.expires_in = (
                        24 * 60 * 60 * 365
                    )  # 365 days in seconds
                    creds = flow.run_local_server(port=0)

                # Save credentials for future use
                with open(token_path_to_use, "w") as token:
                    token.write(creds.to_json())

        logger.info(f"Credentials: {creds}")
        return build("gmail", "v1", credentials=creds)
    
if __name__ == "__main__":

    # data = get_secret("gmail-token", PROJECT_ID)
    # print(data)

    gmail = GmailClient(credentials_path="credentials.json")
