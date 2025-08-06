# ./server/core/agents/xtelcom/tools.py
import logging
import os
import json
import requests
import re # For parsing prices

# For Google Cloud authentication and ID token generation (retained for other tools)
import google.auth
import google.auth.transport.requests
from google.oauth2 import id_token as google_id_token
import google.auth.exceptions

from google.adk.tools.tool_context import ToolContext
from .context import XtelcomContext # Imports LIVE_XTELCOM_CATALOG_DATA

logger = logging.getLogger(__name__)

# --- Configuration for your Cloud Run Endpoints ---
CUSTOM_SEARCH_CLOUD_RUN_URL = os.environ.get("CUSTOM_SEARCH_CLOUD_RUN_URL")
WEB_SUMMARIZER_CLOUD_RUN_URL = os.environ.get("WEB_SUMMARIZER_CLOUD_RUN_URL")
# LIVE_CATALOG_CLOUD_RUN_URL is no longer used by search_live_xtelcom_catalog

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

# --- Tool Implementations for Xtelcom ---

def greeting() -> dict:
    logger.info("Tool: greeting called")
    return {"status": "success", 
            "greeting_message": f"Hello! I'm Telly, your Xtelcom Android Assistant. How can I help you with your Android needs today?"}

def get_current_datetime_tool() -> dict:
    logger.info("Tool: get_current_datetime_tool called")
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "status": "success", 
        "current_datetime_str": now_str}

def custom_web_search(search_query: str, tool_context: ToolContext, num_results: int = 3) -> dict:
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

def _get_price_string(product_data: dict) -> str:
    """Extracts a representative price string from product data."""
    price_outright = product_data.get("Price Outright", "")
    price_monthly = product_data.get("Price over 36 months", "")

    if isinstance(price_outright, str) and "$" in price_outright and "not available" not in price_outright.lower() and "not explicitly stated" not in price_outright.lower():
        return price_outright.split('/month')[0].strip() # Return outright if it looks like a price
    
    if isinstance(price_monthly, str) and "$" in price_monthly and "not available" not in price_monthly.lower() and "not explicitly stated" not in price_monthly.lower():
        return f"{price_monthly.split('/month')[0].strip()} /month" # Return monthly if outright is not good

    return "Price not available"

def _get_stock_status(product_data: dict) -> str:
    """Infers stock status from product data."""
    price_outright = product_data.get("Price Outright", "")
    price_monthly = product_data.get("Price over 36 months", "")
    url = product_data.get("URL", "").lower()

    if "out of stock" in url or \
       (isinstance(price_outright, str) and ("out of stock" in price_outright.lower() or "not available" == price_outright.lower())) or \
       (isinstance(price_monthly, str) and ("out of stock" in price_monthly.lower() or "not available" == price_monthly.lower())):
        return "Out of Stock"
    # Check for models known to be out of stock from product_v3.json examples
    if product_data.get("Model") == "Galaxy Z Flip6" and "Not available/Out of Stock" in price_outright :
        return "Out of Stock"
    if product_data.get("Model") == "Galaxy Z Fold6" and "Not available (Out of Stock)" in price_outright :
        return "Out of Stock"
    if product_data.get("Model") == "Galaxy S22" and "Not available - Out of Stock" in price_outright :
        return "Out of Stock"
        
    # If price is "N/A" it might also indicate out of stock for some entries in product_v3.json
    if price_outright == "N/A" or price_monthly == "N/A":
        # A more robust check might be needed if "N/A" doesn't always mean out of stock
        # For now, let's assume it might be unavailable.
        if "iphone 16" in product_data.get("Model","").lower() or "galaxy s25" in product_data.get("Model","").lower(): # Newer models might be pre-order
             return "Check availability (possibly pre-order)"


    # Default if no explicit out-of-stock indicators
    return "In Stock"


def search_live_xtelcom_catalog(search_term: str, tool_context: ToolContext) -> dict:
    """
    Searches the Xtelcom product catalog (from a local JSON data source) for Android devices using a search term.
    The tool filters devices based on brand, model, color, and storage capacity.
    It returns a JSON response with a list of matching devices.
    Example device structure in the returned JSON:
    {
      "deviceName": "Samsung Galaxy S25", // Combined Brand and Model
      "keyFeatures": ["Colours: color1, color2", "Storage: capacity1, capacity2"], // Derived from product data
      "price": "$1398.96", // Typically outright price, or monthly if outright not available
      "productURL": "https://optus.com.au/samsung-s25",
      "imageURL": null, // Not available from the current data source
      "stockStatus": "In Stock" // Or "Out of Stock" / "Availability not specified" / "Check availability (possibly pre-order)"
    }
    """
    logger.info(f"Tool: search_live_xtelcom_catalog (local JSON) called with search_term: '{search_term}'")

    catalog_data = XtelcomContext.LIVE_XTELCOM_CATALOG_DATA
    if not catalog_data:
        logger.warning("Xtelcom product catalog data is not loaded or is empty.")
        return {"devices": [], "message": "Sorry, the product catalog is currently unavailable."}

    search_term_lower = search_term.lower()
    # Remove generic terms that don't help with filtering this specific JSON
    search_term_lower = search_term_lower.replace("xtelcom", "").replace("android", "").replace("phone", "").replace("phones", "").replace("deals", "").replace("latest","").strip()
    # Normalize storage terms
    search_term_lower = search_term_lower.replace("gigabytes", "gb").replace("gigabyte", "gb")
    
    results = []

    for product in catalog_data:
        # Ensure essential fields exist, skip product if not
        brand = product.get("Brand", "")
        model = product.get("Model", "")
        if not brand or not model: # Skip items that are not clearly phones or lack essential data
            if "iphone" not in model.lower() and "galaxy" not in model.lower() and "pixel" not in model.lower(): # Heuristic to skip accessories if any
                if product.get("URL", "").count('/') < 4 : # Skip generic /mobile/phones or /mobile/phones/budget
                    continue


        # Exclude Apple products explicitly as this is an Android assistant
        if "apple" in brand.lower() or "iphone" in model.lower():
            continue
        
        # Skip "Spacetalk Adventurer 2" as it's a watch
        if "spacetalk" in brand.lower() and "adventurer 2" in model.lower():
            continue


        match_score = 0
        product_name_lower = f"{brand.lower()} {model.lower()}"

        # Direct name match gives higher score
        if search_term_lower in product_name_lower:
            match_score += 10
        
        # Partial matches for brand and model
        search_tokens = set(search_term_lower.split())
        product_tokens = set(product_name_lower.split())
        
        common_tokens = search_tokens.intersection(product_tokens)
        match_score += len(common_tokens) * 2


        # Check for brand match
        if brand.lower() in search_term_lower:
            match_score += 3
        # Check for model match (more specific parts of model name)
        model_parts = model.lower().split()
        for part in model_parts:
            if len(part)>1 and part not in brand.lower() and part in search_term_lower : # avoid matching 'a' in 'galaxy a'
                 match_score +=2


        # Check available colours
        available_colours = [str(c).lower() for c in product.get("Available Colours", [])]
        for color_token in search_tokens:
            if color_token in available_colours:
                match_score += 2 # Found a matching color term
                break 
            for actual_color in available_colours:
                if color_token in actual_color: # e.g. search "blue" matches "icyblue"
                    match_score +=1
                    break


        # Check available storage
        available_storage = [str(s).lower() for s in product.get("Available Storage Capacity", [])]
        # Normalize search term for storage, e.g., "256gb"
        normalized_search_storage = None
        for token in search_tokens:
            if re.match(r"^\d+gb$", token):
                normalized_search_storage = token
                break
        
        if normalized_search_storage:
            if normalized_search_storage in available_storage:
                match_score += 5 # Exact storage match
            else: # check if search storage is a substring of any available storage (e.g. "1tb" in "1TB")
                for storage_option in available_storage:
                    if normalized_search_storage in storage_option:
                        match_score +=2
                        break


        if match_score > 0:
            # Transform product to the desired output structure
            key_features = []
            if product.get("Available Colours"):
                key_features.append(f"Colours: {', '.join(product['Available Colours'])}")
            storage_capacities = product.get("Available Storage Capacity", [])
            # Filter out non-storage related strings like "35mm (Note: This appears to be watch face size, not storage capacity)"
            valid_storage = [s for s in storage_capacities if "gb" in s.lower() or "tb" in s.lower()]
            if valid_storage:
                key_features.append(f"Storage: {', '.join(valid_storage)}")

            device_info = {
                "deviceName": f"{brand} {model}",
                "keyFeatures": key_features,
                "price": _get_price_string(product),
                "productURL": product.get("URL"),
                "imageURL": None,  # Not available in product_v3.json
                "stockStatus": _get_stock_status(product),
                "_match_score": match_score # For sorting
            }
            results.append(device_info)

    # Sort results by match score, highest first
    sorted_results = sorted(results, key=lambda x: x["_match_score"], reverse=True)
    
    # Remove the temporary score key
    for res in sorted_results:
        del res["_match_score"]

    if not sorted_results:
        logger.info(f"No devices found in local catalog for search_term: '{search_term}' (processed as '{search_term_lower}')")
        return {"devices": [], "message": f"Sorry, I couldn't find any Android devices matching '{search_term}' in the Xtelcom catalog right now."}
    
    logger.info(f"Found {len(sorted_results)} device(s) for search_term: '{search_term}'")
    # The prompt suggests Telly will pick 1-2 recommendations.
    # The tool should return all relevant found devices (or a reasonable subset).
    # Let's return up to, say, 5 top matches to give the agent some choice.
    return {"devices": sorted_results[:5]}


def request_visual_input(reason_for_request: str, tool_context: ToolContext) -> dict:
    logger.info(f"Tool: request_visual_input called. Reason: '{reason_for_request}'")
    return {
        "status": "visual_input_requested",
        "reason": reason_for_request,
        "message_to_user": f"Okay, to help with '{reason_for_request}', could you please show it to me using your camera or by uploading an image?"
    }

def affirmative() -> dict:
    logger.info("Tool: affirmative called. User gave affirmative response.")
    return {"status": "success", "user_affirmed": True}

def update_crm(customer_id: str, details: str, tool_context: ToolContext) -> dict:
    logger.info(f"Tool: update_crm called for customer '{customer_id}' with details: '{details}'")
    # In a real scenario, this would interact with a CRM system.
    return {"status": "success", "message": f"CRM record for '{customer_id}' updated."}

