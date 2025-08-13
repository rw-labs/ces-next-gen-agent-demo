import logging
import os
import json
import requests
import re # For parsing prices

from google.adk.tools.tool_context import ToolContext
from .context import TallyContext

# For Google Cloud authentication and ID token generation (retained for other tools)
import google.auth
import google.auth.transport.requests
from google.oauth2 import id_token as google_id_token
import google.auth.exceptions

logger = logging.getLogger(__name__)

# --- Configuration for your Cloud Run Endpoints ---
CUSTOM_SEARCH_CLOUD_RUN_URL = os.environ.get("CUSTOM_SEARCH_CLOUD_RUN_URL")
WEB_SUMMARIZER_CLOUD_RUN_URL = os.environ.get("WEB_SUMMARIZER_CLOUD_RUN_URL")
# LIVE_CATALOG_CLOUD_RUN_URL is no longer used by search_live_teg_catalog

# --- Helper function to get an ID token for invoking Cloud Run (retained for other tools) ---
def get_id_token(target_audience_url: str) -> str:
    print(f"Attempting to get ID token for audience: {target_audience_url}")
    credentials = None 
    project_id = None
    auth_req = None
    try:
        print("Calling google.auth.default()...")
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            try:
                adc_path = "Unknown"
                if os.name == 'nt':
                    adc_path = os.path.join(os.getenv('APPDATA', ''), 'gcloud', 'application_default_credentials.json')
                else:
                    adc_path = os.path.join(os.path.expanduser('~'), '.config', 'gcloud', 'application_default_credentials.json')
                print(f"Expecting ADC file at: {adc_path}. Exists: {os.path.exists(adc_path)}")
            except Exception as path_e:
                logger.warning(f"Could not determine or check ADC path: {path_e}")

        credentials, project_id = google.auth.default(
            scopes=["openid", "email", "profile", "https://www.googleapis.com/auth/cloud-platform"]
        )

        if not credentials:
            logger.error("google.auth.default() returned no credentials.")
            raise google.auth.exceptions.DefaultCredentialsError("ADC: No credentials found.")
        
        print(f"ADC: Successfully obtained credentials. Type: {type(credentials)}. Project ID: {project_id or 'Not determined'}")

        auth_req = google.auth.transport.requests.Request()

        print("ADC: Attempting to refresh credentials if necessary...")
        try:
            credentials.refresh(auth_req)
            print("ADC: Credentials refresh attempt completed.")
        except google.auth.exceptions.RefreshError as re:
            logger.error(f"ADC: Failed to refresh credentials: {re}. ADC might be stale or revoked.")
            raise
        except AttributeError:
            logger.warning(f"ADC: Credentials of type {type(credentials)} do not have a refresh method. Proceeding.")

        print(f"ADC: Fetching ID token for audience: {target_audience_url} using obtained credentials.")
        token = google_id_token.fetch_id_token(auth_req, target_audience_url)
        
        if not token:
            logger.error("fetch_id_token returned None or empty token.")
            raise ValueError("Failed to fetch a valid ID token (token was None/empty).")
            
        print("Successfully fetched ID token.")
        return token

    except google.auth.exceptions.RefreshError as re:
        logger.error(f"ID Token Generation Failed due to RefreshError: {re}")
        raise
    except google.auth.exceptions.DefaultCredentialsError as dce:
        logger.error(f"ID Token Generation Failed due to DefaultCredentialsError: {dce}")
        logger.error("This error during fetch_id_token might indicate issues with the refresh token or network access to token servers.")
        raise
    except Exception as e:
        logger.exception(f"An unexpected error occurred during ID token generation for {target_audience_url}: {e}")
        if credentials:
            logger.error(f"Credentials state at time of error: valid={credentials.valid}, expired={credentials.expired}, token={credentials.token is not None}")
        raise


def update_crm(customer_id: str, details: str, tool_context: ToolContext) -> dict:
    """Add customer interaction record to CRM.

    Args:
        customer_id: The ID of the customer.
        details: A brief summary of the interaction to be recorded in the CRM.

    Returns:
        A dictionary representing the cart contents.  Example:
        {'status': 'success', 'message': 'CRM record for paul_barnes_123 updated.'}
    """
    logger.info(f"Tool: update_crm called for customer '{customer_id}' with details: '{details}'")
    # In a real scenario, this would interact with a CRM system.
    return {"status": "success", "message": f"CRM record for '{customer_id}' updated."}

def custom_web_search(search_query: str, tool_context: ToolContext, num_results: int = 5) -> dict:
    """Search internet to find answers to customer's queries

    Args:
        search_query: query to search for in the internet.
        tool_context: The context of the tool invocation.
        num_results: number of results to return. Defaults to 5 if not specified.

    Returns:
        A dictionary representing the cart contents.  Example:
        {'status': 'success', 'search_results': ["result1", "result2", "result3"]}'}
    """
    logger.info(f"Tool: custom_web_search (via authenticated Cloud Run) called with query: '{search_query}', num_results: {num_results}")

    if not CUSTOM_SEARCH_CLOUD_RUN_URL:
        logger.error("Custom Search Cloud Run URL is not configured.")
        return {"status": "error",
                "error_message": "Search service endpoint not configured.", 
                "search_results": [] }

    try:
        token = get_id_token(CUSTOM_SEARCH_CLOUD_RUN_URL)
    except Exception as auth_err:
        logger.error(f"Authentication failed for custom_web_search: {str(auth_err)}")
        return { "status": "error",
                 "error_message": f"Authentication failed for search service: {str(auth_err)}", 
                 "search_results": []}


    payload = {
        "search_terms": search_query,
        "num_results": num_results,
        "simplified_response": True 
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:
        response = requests.post(CUSTOM_SEARCH_CLOUD_RUN_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data: 
            logger.error(f"Custom Search Cloud Run service returned an error: {data['error']}")
            return {"status": "error",
                    "error_message": data["error"], 
                    "search_results": []}
        
        search_results = data.get("results", [])
        if not search_results:
             logger.info(f"No search results from Cloud Run for query: '{search_query}'")
        return { "status": "success", 
                 "search_results": search_results}

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error calling Custom Search Cloud Run: {http_err} - Response: {http_err.response.text if http_err.response else 'No response body'}")
        return {"status": "error", "search_results": [], "error_message": f"Search service request failed (HTTP {http_err.response.status_code if http_err.response else 'Unknown'})."}
    except requests.exceptions.RequestException as req_err:
        logger.exception(f"Error calling Custom Search Cloud Run: {req_err}")
        return {"status": "error", "search_results": [], "error_message": f"Could not connect to search service: {str(req_err)}"}
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON response from Custom Search Cloud Run. Response: {response.text if response else 'No response object'}")
        return {"status": "error", "search_results": [], "error_message": "Invalid response format from search service."}


def web_content_summarizer(url: str, tool_context: ToolContext) -> dict:
    """Summarize the contents of a specific webpage

    Args:
        url: url of the webpage to summarize.
        tool_context: The context of the tool invocation.

    Returns:
        A dictionary representing the cart contents.  Example:
        {'status': 'success', 'summary': "This is a summary of the webpage content."}
    """
    logger.info(f"Tool: web_content_summarizer (via authenticated Cloud Run) called for URL: '{url}'")

    if not WEB_SUMMARIZER_CLOUD_RUN_URL:
        logger.error("Web Summarizer Cloud Run URL is not configured.")
        return {"status": "error", "summary": None, "error_message": "Summarizer service endpoint not configured."}

    try:
        token = get_id_token(WEB_SUMMARIZER_CLOUD_RUN_URL)
    except Exception as auth_err:
        logger.error(f"Authentication failed for web_content_summarizer: {str(auth_err)}")
        return {"status": "error", "summary": None, "error_message": f"Authentication failed for summarizer service: {str(auth_err)}"}

    payload = {"url": url}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:
        response = requests.post(WEB_SUMMARIZER_CLOUD_RUN_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data: 
            logger.error(f"Web Summarizer Cloud Run service returned an error: {data['error']}")
            return {"status": "error", "summary": None, "error_message": data["error"]}
            
        summary = data.get("summary")
        if not summary: 
            logger.info(f"No summary returned or summary was empty from Cloud Run for URL: {url}")
            return {"status": "error", "summary": None, "error_message": "Content could not be summarized or the summary was empty."}
        return {"status": "success", "summary": summary}

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error calling Web Summarizer Cloud Run: {http_err} - Response: {http_err.response.text if http_err.response else 'No response body'}")
        return {"status": "error", "summary": None, "error_message": f"Summarizer service request failed (HTTP {http_err.response.status_code if http_err.response else 'Unknown'})."}
    except requests.exceptions.RequestException as req_err:
        logger.exception(f"Error calling Web Summarizer Cloud Run: {req_err}")
        return {"status": "error", "summary": None, "error_message": f"Could not connect to summarizer service: {str(req_err)}"}
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON response from Web Summarizer Cloud Run. Response: {response.text if response else 'No response object'}")
        return {"status": "error", "summary": None, "error_message": "Invalid response format from summarizer service."}

def get_customer_energy_usage(customer_id: str, tool_context: ToolContext) -> dict:
    """
    Retrieves the latest appliance-level electricity consumption data for a given customer.
    This data includes the current monthly percentage usage for appliances like the fridge,
    as well as the baseline percentage from previous months.

    Args:
        customer_id: The unique identifier for the customer (e.g., 'paul_barnes_123').
        tool_context: The context of the tool invocation.

    Returns:
        A dictionary containing the customer's energy usage data or an error message.
    """
    logger.info(f"Tool: get_customer_energy_usage called for customer_id: '{customer_id}'")
    usage_data = TallyContext.ENERGY_USAGE_DATA.get(customer_id)
    if usage_data:
        return {"status": "success", "usage_data": usage_data}
    else:
        return {"status": "error", "message": f"No usage data found for customer {customer_id}."}

def request_visual_input(reason_for_request: str, tool_context: ToolContext) -> dict:
    """
    Requests the user to provide visual input via their camera or an image upload.
    This is used to visually inspect an appliance or situation to aid in troubleshooting.

    Args:
        reason_for_request: A clear and concise reason for why the visual input is needed.
        tool_context: The context of the tool invocation.

    Returns:
        A dictionary indicating that a visual input has been requested.
    """
    logger.info(f"Tool: request_visual_input called. Reason: '{reason_for_request}'")
    return {
        "status": "visual_input_requested",
        "reason": reason_for_request,
        "message_to_user": f"Okay, to help me with '{reason_for_request}', could you please show it to me using your camera?"
    }

def search_energy_efficient_fridges(brand: str, tool_context: ToolContext, min_rating: float = 4.0) -> dict:
    """
    Searches the local product catalog for energy-efficient refrigerators.
    
    Args:
        brand: The brand of the fridge to search for (e.g., 'LG', 'Samsung'). Optional.
        tool_context: The context of the tool invocation.
        min_rating: The minimum energy star rating for the fridges to be returned. Defaults to 4.0.

    Returns:
        A dictionary containing a list of matching fridge products.
    """
    logger.info(f"Tool: search_energy_efficient_fridges called with brand: '{brand}', min_rating: {min_rating}")
    
    results = []
    for fridge in TallyContext.PRODUCT_CATALOG:
        brand_match = True
        rating_match = fridge.get("energy_rating_stars", 0) >= min_rating
        
        if brand:
            brand_match = brand.lower() in fridge.get("brand", "").lower()
        
        if brand_match and rating_match:
            results.append(fridge)
            
    if not results:
        return {"status": "success", "fridges": [], "message": "No fridges found matching the criteria."}

    return {"status": "success", "fridges": results}


def get_installation_info(customer_id: str, tool_context: ToolContext) -> dict:
    """
    Provides a quote for installation and removal of an old appliance, and lists available installation time slots.
    The quote and slots are based on the customer's general location, but for this mock tool, it returns default values.

    Args:
        customer_id: The unique identifier for the customer.
        tool_context: The context of the tool invocation.

    Returns:
        A dictionary with the installation quote and available time slots.
    """
    logger.info(f"Tool: get_installation_info called for customer: '{customer_id}'")
    # In a real scenario, you might use the customer_id to get location info and provide a specific quote.
    return {
        "status": "success",
        "quote": TallyContext.INSTALLATION_INFO["default_quote"],
        "available_slots": TallyContext.INSTALLATION_INFO["available_slots"]
    }

def book_appointment(customer_id: str, product_id: str, slot: str, tool_context: ToolContext) -> dict:
    """
    Books an installation appointment for a customer for a specific product and time slot.

    Args:
        customer_id: The unique identifier for the customer.
        product_id: The ID of the product to be installed (e.g., 'FR-LG-700S').
        slot: The chosen time slot for the installation (e.g., 'Tomorrow, 9am - 11am').
        tool_context: The context of the tool invocation.

    Returns:
        A dictionary confirming the booking with a unique appointment ID.
    """
    logger.info(f"Tool: book_appointment called for customer '{customer_id}', product '{product_id}', slot '{slot}'")
    
    # Simple mock implementation
    import random
    appointment_id = f"EA-APT-{random.randint(100000, 999999)}"
    
    return {
        "status": "success",
        "appointment_id": appointment_id,
        "product_id": product_id,
        "customer_id": customer_id,
        "confirmed_slot": slot,
        "message": f"Appointment {appointment_id} has been successfully booked for {slot}."
    }

