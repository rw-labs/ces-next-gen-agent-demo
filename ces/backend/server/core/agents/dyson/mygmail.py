from __future__ import print_function

import base64
import json
import logging
import mimetypes
import os.path
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request  # type: ignore
from google.cloud import secretmanager
from google.oauth2.credentials import Credentials  # type: ignore
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
from googleapiclient.discovery import build  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore

logger = logging.getLogger(__name__)



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
                    try:
                        creds.refresh(Request())
                    except Exception as e:
                        logger.info(f"Error refreshing token: {e}")
                        if os.path.exists(token_path_to_use):
                            os.remove(token_path_to_use)
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self.credentials_path, self.SCOPES
                        )
                        creds = flow.run_local_server(port=0)
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.SCOPES
                    )
                    # Set token expiry to 24 hours
                    flow.oauth2session.token_expires_in = (
                        24 * 60 * 60
                    )  # 24 hours in seconds
                    creds = flow.run_local_server(port=0)

                # Save credentials for future use
                with open(token_path_to_use, "w") as token:
                    token.write(creds.to_json())

        logger.info(f"Credentials: {creds}")
        return build("gmail", "v1", credentials=creds)

    def create_message(self, to, subject, message_text, file_dir=None, filename=None):
        """Create a message for an email.

        Args:
            to: Email address of the receiver.
            subject: The subject of the email message.
            message_text: The text of the email message.
            file_dir: The directory containing the file to attach.
            filename: The name of the file to attach.

        Returns:
            An object containing a base64url encoded email object.
        """
        if file_dir and filename:
            message = MIMEMultipart()
            message["to"] = to
            message["subject"] = subject

            msg = MIMEText(message_text)
            message.attach(msg)

            filepath = os.path.join(file_dir, filename)
            content_type, encoding = mimetypes.guess_type(filepath)

            if content_type is None or encoding is not None:
                content_type = "application/octet-stream"

            main_type, sub_type = content_type.split("/", 1)
            with open(filepath, "rb") as fp:
                file_content = fp.read()
            attachment = MIMEBase(main_type, sub_type)
            attachment.set_payload(file_content)

            import email.encoders

            email.encoders.encode_base64(attachment)

            attachment.add_header(
                "Content-Disposition", "attachment", filename=filename
            )
            message.attach(attachment)

        else:
            message = MIMEText(message_text)
            message["to"] = to
            message["subject"] = subject

        logger.info(f"Message content: {message}")
        raw_message = base64.urlsafe_b64encode(
            message.as_string().encode("utf-8")
        ).decode("utf-8")
        return {"raw": raw_message}

    def send_message(self, message, user_id="me"):
        """Send an email message.

        Args:
            message: Message to be sent.
            user_id: User's email address. The special value "me"
                    can be used to indicate the authenticated user.

        Returns:
            Sent Message.
        """
        try:
            message = (
                self.service.users()
                .messages()
                .send(userId=user_id, body=message)
                .execute()
            )
            logger.info("Message Id: %s" % message["id"])
            return message
        except HttpError as error:
            logger.info("An error occurred: %s" % error)

    def send_email(self, to, subject, message_text, file_dir=None, filename=None):
        """Convenience method to create and send an email in one step."""
        try:
            message = self.create_message(to, subject, message_text, file_dir, filename)
            return self.send_message(message)
        except Exception as error:
            logger.info(f"An error occurred: {error}")

    def get_important_emails(self, max_results=5, user_id="me"):
        """Get the latest important emails.

        Args:
            max_results: Maximum number of emails to return (default 5)
            user_id: User's email address. The special value "me"
                    can be used to indicate the authenticated user.

        Returns:
            List of dictionaries containing email details
        """
        try:
            # Search for messages marked as important
            query = "is:important subject:URGENT"
            results = (
                self.service.users()
                .messages()
                .list(userId=user_id, q=query, maxResults=max_results)
                .execute()
            )

            messages = results.get("messages", [])
            email_list = []

            for message in messages:
                msg = (
                    self.service.users()
                    .messages()
                    .get(userId=user_id, id=message["id"])
                    .execute()
                )

                headers = msg["payload"]["headers"]
                subject = next(
                    (h["value"] for h in headers if h["name"] == "Subject"), ""
                )
                sender = next((h["value"] for h in headers if h["name"] == "From"), "")
                date = next((h["value"] for h in headers if h["name"] == "Date"), "")

                email_dict = {
                    "id": msg["id"],
                    "subject": subject,
                    "sender": sender,
                    "date": date,
                    "snippet": msg["snippet"],
                }
                email_list.append(email_dict)

            return email_list

        except HttpError as error:
            logger.info(f"An error occurred: {error}")
            return []


if __name__ == "__main__":
    gmail = GmailClient(credentials_path="secret:gmail-credentials:your-gcp-project-id")

    to = "weiyih@google.com"  # replace with recipient email
    subject = "Hurray, it is working!!"
    message_text = "This is a test email sent from the Gmail API."

    # Optional: Test with attachment
    attachment_path = "test_attachment.txt"
    with open(attachment_path, "w") as f:
        f.write("Test attachment content")

    try:
        # Send test email without attachment
        gmail.send_email(to, subject, message_text)
        logger.info("Test email sent successfully without attachment")

    except Exception as e:
        logger.info(f"Error sending test email: {e}")
    finally:
        # Clean up test attachment
        if os.path.exists(attachment_path):
            os.remove(attachment_path)
