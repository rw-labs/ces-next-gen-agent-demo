# ./server/core/agents/ollie/tools.py
import logging
import os
import json
import requests
import re # For parsing prices
import aiohttp
from typing import Dict, Any
from urllib.parse import urlencode

from google.adk.tools.tool_context import ToolContext
from .context import GenericContext # Imports LIVE_OPTUS_CATALOG_DATA

logger = logging.getLogger(__name__)

# --- Configuration for your Cloud Run Endpoints ---
WEATHER_FUNCTION_URL = os.environ.get("WEATHER_FUNCTION_URL")
FORECAST_FUNCTION_URL = os.environ.get("FORECAST_FUNCTION_URL")
HEALTH_STATS_FUNCTION_URL = os.environ.get("HEALTH_STATS_FUNCTION_URL")

# --- Tool Implementations for Ollie ---

def greeting() -> dict:
    logger.info("Tool: greeting called")
    return {"greeting_message": f"Hello! I'm your AI Assistant. How can I help you today?"}

def get_current_datetime_tool() -> dict:
    logger.info("Tool: get_current_datetime_tool called")
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"current_datetime_str": now_str}

async def get_weather(city: str) -> Dict[str, Any]:
    """Gets the current weather for a given city.

    Args:
        city: The city or location to get the weather for.
    """
    if not WEATHER_FUNCTION_URL:
        logger.error("Weather function URL is not configured.")
        return {"error": "Weather service endpoint not configured."}

    params = {"city": city}
    query_string = urlencode(params)
    function_url = f"{WEATHER_FUNCTION_URL}?{query_string}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(function_url) as response:
                response_text = await response.text()
                logger.debug(f"Weather Response status: {response.status}")
                logger.debug(f"Weather Response body: {response_text}")
                if response.status != 200:
                    logger.error(f"Cloud function error: {response_text}")
                    return {"error": f"Cloud function returned status {response.status}"}
                return await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"Network error calling weather function: {str(e)}")
        return {"error": f"Failed to call weather service: {str(e)}"}
    except Exception as e:
        logger.error(f"Error getting weather for {city}: {str(e)}")
        return {"error": f"Tool execution failed: {str(e)}"}

async def get_weather_forecast(city: str) -> Dict[str, Any]:
    """Get weather forecast information for a location.

    Args:
        city: The city or location to get weather forecast for.
    """
    if not FORECAST_FUNCTION_URL:
        logger.error("Forecast function URL is not configured.")
        return {"error": "Forecast service endpoint not configured."}

    params = {"city": city}
    query_string = urlencode(params)
    function_url = f"{FORECAST_FUNCTION_URL}?{query_string}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(function_url) as response:
                response_text = await response.text()
                logger.debug(f"Forecast Response status: {response.status}")
                logger.debug(f"Forecast Response body: {response_text}")
                if response.status != 200:
                    logger.error(f"Cloud function error: {response_text}")
                    return {"error": f"Cloud function returned status {response.status}"}
                return await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"Network error calling forecast function: {str(e)}")
        return {"error": f"Failed to call forecast service: {str(e)}"}
    except Exception as e:
        logger.error(f"Error getting forecast for {city}: {str(e)}")
        return {"error": f"Tool execution failed: {str(e)}"}

async def get_health_stats(search_query: str) -> Dict[str, Any]:
    """Get the users health stats including sleep, activities, heart rate.

    Args:
        search_query: The query to search health stats.
    """
    if not HEALTH_STATS_FUNCTION_URL:
        logger.error("Health stats function URL is not configured.")
        return {"error": "Health stats service endpoint not configured."}

    params = {"search_query": search_query}
    query_string = urlencode(params)
    function_url = f"{HEALTH_STATS_FUNCTION_URL}?{query_string}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(function_url) as response:
                response_text = await response.text()
                logger.debug(f"Health Stats Response status: {response.status}")
                logger.debug(f"Health Stats Response body: {response_text}")
                if response.status != 200:
                    logger.error(f"Cloud function error: {response_text}")
                    return {"error": f"Cloud function returned status {response.status}"}
                return await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"Network error calling health stats function: {str(e)}")
        return {"error": f"Failed to call health stats service: {str(e)}"}
    except Exception as e:
        logger.error(f"Error getting health stats for {search_query}: {str(e)}")
        return {"error": f"Tool execution failed: {str(e)}"}

def request_visual_input(reason_for_request: str, tool_context: ToolContext) -> dict:
    logger.info(f"Tool: request_visual_input called. Reason: '{reason_for_request}'")
    return {
        "status": "visual_input_requested",
        "reason": reason_for_request,
        "message_to_user": f"Okay, to help with '{reason_for_request}', could you please show it to me using your camera?"
    }

def affirmative() -> dict:
    logger.info("Tool: affirmative called. User gave affirmative response.")
    return {"status": "success", "user_affirmed": True}

def update_crm(customer_id: str, details: str, tool_context: ToolContext) -> dict:
    logger.info(f"Tool: update_crm called for customer '{customer_id}' with details: '{details}'")
    # In a real scenario, this would interact with a CRM system.
    return {"status": "success", "message": f"CRM record for '{customer_id}' updated."}

def confirm_visual_context(tool_context: ToolContext) -> dict:
    """
    Checks if the user's video stream is currently active.
    This tool MUST be called before making any statement about seeing the user's camera.
    Returns a status indicating if the agent is allowed to proceed with a visual description.
    """
    logger.info("Tool: confirm_visual_context called")
    video_status = "inactive"
    
    if hasattr(tool_context, 'state'):
        state_obj = tool_context.state
        if hasattr(state_obj, 'get') and callable(state_obj.get):
            video_status = state_obj.get("video_status", "inactive")

    if video_status in ["started", "active"]:
        logger.info(f"Tool returned video_status as: {video_status}")
        return {"status": "video_active", "message": "Confirmation successful. Video is active. You may now describe what you see."}

    else:
        logger.info(f"Tool returned video_status as: {video_status}")
        return {"status": "video_inactive", "message": "Confirmation failed. Video is not active. You must ask the user to share their camera."}