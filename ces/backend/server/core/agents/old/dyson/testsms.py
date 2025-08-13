import logging
import requests
import json
import base64
logger = logging.getLogger(__name__)

def send_sms(to_phone: str, message: str) -> dict:
    """ Send sessionless SMS using the POST REST API call to ujet API 
        POST https://<subdomain>.<domain>/apps/api/v1/sessionless_sms
    """
    logger.info(f"Sending SMS to {to_phone}: {message}")   

    url = "https://ccaip-canada-7xd3onk.ue1.ccaiplatform.com/apps/api/v1/sessionless_sms" ## your CCaaS url
    username = "ccaip-canada-7xd3onk.ue1"   ## Sub-domain of your CCaaS instance
    password = "ehhQv-vs2lFeWFwZVbsfD8JWvC_MZJR-vBSom-d6R3Y"  ## API key from your CCaaS instance
    from_phone='+13527178480'  ## phone number enabled with sessionless SMS in your CCaaS

    credentials = f"{username}:{password}"
    authorization_string = f"Basic {base64.b64encode(credentials.encode()).decode()}"


    headers = {
        "Content-Type": "application/json",
        "Authorization": authorization_string
    }

    if len(message) > 320:
        message = message[:315] + "..."
        logger.info("Message truncated to 320 characters")

    data = {
        "from_phone": from_phone,
        "to_phones": [to_phone],
        "messages": [message]
    }

    try:
        response = requests.post(url,headers=headers, data=json.dumps(data))
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending SMS: {e}")
        
    return response

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    response = send_sms('+14185693648', 'You have been upgraded you to our Pure Fiber 5 gig plan which would total $145 per month')