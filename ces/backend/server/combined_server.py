# ./server/server.py

"""
Combined HTTP/WebSocket Server Entry Point for Cloud Run using aiohttp.
Handles HTTP callbacks and delegates WebSocket connections to websocket_handler.handle_client.
"""

import asyncio
import json
import os

# Use aiohttp for both HTTP and WebSockets
from aiohttp import WSCloseCode, web
from core.logger import logger

# Type hinting and utils needed for the callback handler
from core.session_state import SessionState
from core.session_utils import SessionUtils

# Import necessary components from core modules
from core.websocket_handler import (
    ACTIVE_SESSIONS,  # Needed for callback handler
    handle_client,  # The original entry point for WS logic, now adapted for aiohttp
)


# --- HTTP Callback Handler (Unchanged from your original working version) ---
async def handle_callback(request: web.Request):
    """Handles HTTP POST requests to the /callback endpoint."""
    logger.info(f"Received callback request at {request.path}")
    raw_data_decoded = "<Could not read body>"
    try:
        raw_data = await request.read()
        raw_data_decoded = raw_data.decode("utf-8", errors="ignore")
        logger.info(f"Raw request body: {raw_data_decoded}")
    except Exception as e:
        logger.exception(f"Error reading request body: {e}")

    try:
        data = await request.json()
        logger.info(f"Callback Request data: {data}")
        session_id = data.get("requestId")

        if not session_id:
            logger.error("Callback missing session_id (requestId)")
            return web.json_response(
                {"error": "Missing session_id (requestId)"}, status=400
            )

        session: SessionState = ACTIVE_SESSIONS.get(session_id)
        if not session:
            logger.error(f"Callback received for invalid session_id: {session_id}")
            return web.json_response({"error": "Invalid session_id"}, status=404)

        # Inject the callback data into the session's request queue.
        logger.info(f"Injecting callback data into session {session_id}")
        content = data.get("agentMessage", "Callback received, processing.")
        manager_approved = data.get("manager_approved", True)

        # Update session state
        session.session.state["manager_approved"] = manager_approved
        session.live_request_queue.send_content(
            SessionUtils.model_response(text=content)
        )

        return web.json_response({"status": "success"})

    except json.JSONDecodeError:
        logger.error(f"Invalid JSON received in callback: {raw_data_decoded}")
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.exception(f"Error handling callback: {e}")
        return web.json_response({"error": "Internal server error"}, status=500)


# --- WebSocket Connection Handler (Delegates to handle_client) ---
async def handle_websocket_entrypoint(request: web.Request):
    """
    Accepts incoming WebSocket connections and delegates handling to
    core.websocket_handler.handle_client (adapted for aiohttp).
    """
    heartbeat_interval = 25.0
    ws = web.WebSocketResponse(heartbeat=heartbeat_interval)
    connection_id = str(id(ws))  # Unique ID for logging this specific socket attempt
    try:
        # Prepare the WebSocket handshake (upgrades connection)
        await ws.prepare(request)
        logger.info(
            f"WebSocket connection prepared (handshake successful) for connection_id: {connection_id}, heartbeat={heartbeat_interval}s"
        )

        # --- Delegate to the adapted handle_client ---
        # Pass the established aiohttp WebSocketResponse object
        await handle_client(ws)

        # Log when the handler function returns control (implies connection ended)
        logger.info(f"handle_client finished for connection_id: {connection_id}")

    except asyncio.CancelledError:
        logger.info(
            f"WebSocket connection handler cancelled for connection_id: {connection_id}."
        )
        if not ws.closed:
            await ws.close(
                code=WSCloseCode.GOING_AWAY, message=b"Server cancelling connection"
            )
    except Exception as e:
        # Catch errors during ws.prepare() or if handle_client raises unexpectedly
        logger.exception(
            f"Unhandled error in WebSocket entrypoint for connection_id {connection_id}: {e}"
        )
        if not ws.closed:
            await ws.close(
                code=WSCloseCode.INTERNAL_ERROR,
                message=b"Internal server error during connection handling",
            )

    logger.info(
        f"WebSocket connection processing fully completed for connection_id: {connection_id}"
    )
    return ws  # Return the WebSocketResponse


# --- Main Application Setup ---
async def main() -> None:
    """Starts the combined aiohttp server for HTTP and WebSocket."""
    # Get port from environment variable for Cloud Run, default to 8080 locally
    port = int(os.environ.get("PORT", 8080))

    app = web.Application()

    # Add routes
    app.router.add_post("/callback", handle_callback)
    app.router.add_get("/ws", handle_websocket_entrypoint)  # WebSocket endpoint

    runner = web.AppRunner(app)
    await runner.setup()

    # Listen on 0.0.0.0 to be accessible from Cloud Run's proxy
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"Running combined HTTP/WebSocket server on 0.0.0.0:{port}...")
    logger.info("WebSocket endpoint available at /ws")
    logger.info("HTTP callback endpoint available at /callback")

    # Keep the server running indefinitely
    await asyncio.Future()


if __name__ == "__main__":
    # Ensure logger is configured before running
    logger.info("Starting server...")
    asyncio.run(main())
