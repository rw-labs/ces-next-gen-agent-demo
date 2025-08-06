# ./server/core/websocket_handler.py
"""
WebSocket message handling using aiohttp.web.WebSocketResponse.
Handles communication between the client/frontend and the live Agent.
"""

import asyncio
import base64
import json
from typing import Any, Dict, Optional

from aiohttp import WSCloseCode, WSMsgType, web
from config.config import (
    MODEL,
    MODEL_LANGUAGE,
    PROMPT_LANGUAGE,
    RUN_CONFIG,
    TTS_CLIENT,
    TTS_CONFIG,
    USE_TTS,
    VOICE,
)
from core.agent_factory import get_agent_config
from google.adk.agents import Agent
from google.cloud import texttospeech_v1beta1 as texttospeech
from google.genai import types as google_types
from websockets.exceptions import (
    ConnectionClosedError as WebsocketsConnectionClosedError,
)

from .logger import logger
from .session_state import SessionState

# --- Server-Side Buffer Configuration ---
TARGET_SAMPLE_RATE = 24000  # Matches client and API
BYTES_PER_SAMPLE = 2  # For 16-bit PCM
SERVER_BUFFER_DURATION_S = 0.3  # Target duration to send (e.g., 200ms)
SERVER_BUFFER_TIMEOUT_S = (
    0.25  # Max time to wait before sending incomplete buffer (must be < duration)
)
SERVER_BUFFER_MAX_SIZE_BYTES = int(
    TARGET_SAMPLE_RATE * SERVER_BUFFER_DURATION_S * BYTES_PER_SAMPLE
)
# --- End Configuration ---


# Global session storage
ACTIVE_SESSIONS: Dict[str, SessionState] = {}


# --- Session Management (Unchanged) ---
async def create_session(
    session_id: str, agent: Agent, app_name: str, context: Dict[str, Any]
) -> SessionState:
    """Creates and stores a new session."""
    logger.info(f"Creating session {session_id} for app {app_name}")
    session = await SessionState.create(
        agent=agent, app_name=app_name, user_id=session_id, context=context
    )

    # Start the agent's live runner
    session.events = session.runner.run_live(
        session=session.session,
        live_request_queue=session.live_request_queue,
        run_config=RUN_CONFIG,
    )
    logger.info(f"Agent live runner started for session {session_id}")

    ACTIVE_SESSIONS[session_id] = session
    return session


def get_session(session_id: str) -> Optional[SessionState]:
    """Retrieves an existing session."""
    return ACTIVE_SESSIONS.get(session_id)


def remove_session(session_id: str) -> None:
    """Removes a session."""
    if session_id in ACTIVE_SESSIONS:
        logger.info(f"Removing session {session_id}")
        del ACTIVE_SESSIONS[session_id]
    else:
        logger.warning(f"Attempted to remove non-existent session {session_id}")


# --- WebSocket Communication Helpers (Adapted for aiohttp) ---


async def send_json_message(
    websocket: web.WebSocketResponse, message_type: str, data: Any
) -> None:
    """Sends a JSON message over the WebSocket."""
    if websocket.closed:
        logger.warning(f"Attempted to send {message_type} message on closed websocket.")
        return
    try:
        payload = {"type": message_type, "data": data}
        # logger.debug(f"Sending WebSocket JSON: {payload}") # Can be very verbose
        await websocket.send_json(payload)
    except ConnectionResetError:
        logger.warning(f"Connection reset while sending {message_type} message.")
    except Exception as e:
        logger.exception(f"Failed to send WebSocket JSON message ({message_type}): {e}")


async def send_error_message(
    websocket: web.WebSocketResponse, error_data: dict
) -> None:
    """Sends a formatted error message to the client."""
    await send_json_message(websocket, "error", error_data)


async def send_buffered_audio(
    websocket: Any,
    audio_buffer: bytearray,
    last_send_time: float,
    force_send: bool = False,
) -> float:
    """
    Sends the content of the audio buffer if conditions are met.
    Args:
        websocket: The websocket connection.
        audio_buffer: The bytearray buffer holding audio data.
        last_send_time: The timestamp of the last buffer send.
        force_send: If True, sends the buffer regardless of size/timeout (for cleanup).
    Returns:
        The timestamp when the buffer was sent (or the original last_send_time if not sent).
    """
    now = asyncio.get_event_loop().time()
    should_send = False
    reason = ""

    if len(audio_buffer) == 0:
        return last_send_time  # Nothing to send

    # Check conditions for sending
    if len(audio_buffer) >= SERVER_BUFFER_MAX_SIZE_BYTES:
        should_send = True
        reason = (
            f"size threshold ({len(audio_buffer)} >= {SERVER_BUFFER_MAX_SIZE_BYTES})"
        )
    elif (now - last_send_time) >= SERVER_BUFFER_TIMEOUT_S:
        should_send = True
        reason = f"timeout ({(now - last_send_time) * 1000:.1f}ms >= {SERVER_BUFFER_TIMEOUT_S * 1000:.1f}ms)"
    elif force_send:
        should_send = True
        reason = "force send"

    if should_send:
        logger.debug(
            f"Server buffer sending: Reason={reason}, Size={len(audio_buffer)} bytes"
        )
        try:
            # Send a copy and clear original buffer immediately
            data_to_send = bytes(audio_buffer)
            audio_buffer.clear()
            # Update time *before* await, assuming send attempt will proceed
            last_send_time = now

            # --- decode and send the audio
            audio_base64 = base64.b64encode(data_to_send).decode("utf-8")
            await send_json_message(websocket, "audio", audio_base64)

            logger.debug("Server buffer sent successfully.")

        except Exception as send_err:
            logger.error(
                f"Error sending buffered audio: {send_err} (Client likely disconnected)"
            )
            # Buffer was already cleared, just log the error
            # Reset last_send_time to avoid potential rapid retries if connection persists but fails
            last_send_time = now
        return now  # Return the time send was initiated

    return last_send_time  # Return original time if not sent


# --- Session Cleanup (Adapted for clarity) ---


async def cleanup_session(session: Optional[SessionState], session_id: str) -> None:
    """Cleans up session resources."""
    logger.info(f"Starting cleanup for session {session_id}")
    if session:
        if session.session:
            try:
                logger.info(
                    f"Attempting to clean up agent resources for session {session_id} (Placeholder)"
                )
                pass  # Replace with actual cleanup logic
            except Exception as e:
                logger.error(
                    f"Error during agent resource cleanup for session {session_id}: {e}"
                )
        else:
            logger.warning(
                f"No active agent session object found for cleanup in session {session_id}"
            )

    # Remove session from active sessions *after* attempting cleanup
    remove_session(session_id)
    logger.info(f"Session {session_id} removed from active sessions.")


# --- Agent Response Handling (Adapted for aiohttp) ---


async def handle_agent_responses(
    websocket: web.WebSocketResponse, session: SessionState
) -> None:
    """Handles responses from the agent, forwarding data to the client."""
    session_id = session.user_id  # Get session_id for logging
    logger.info(f"[Session: {session_id}] Starting agent response handler task.")
    agent_turn_completed_normally = False

    # Buffer setup
    audio_buffer = bytearray()  # Buffer specific to this handler invocation
    last_send_time = asyncio.get_event_loop().time()
    buffer_task = None
    # End buffer setup

    # --- Define Buffer check loop ---
    async def buffer_check_loop():
        """Periodically checks if the buffer timeout requires sending."""
        nonlocal last_send_time  # Allow modification of the outer scope variable
        while True:
            # Calculate sleep duration dynamically based on last send time
            now = asyncio.get_event_loop().time()
            time_since_last_send = now - last_send_time
            sleep_duration = max(
                0.01, SERVER_BUFFER_TIMEOUT_S - time_since_last_send
            )  # Sleep at least 10ms
            await asyncio.sleep(sleep_duration)
            try:
                # Pass the current buffer and last send time
                current_last_send = await send_buffered_audio(
                    websocket, audio_buffer, last_send_time
                )
                last_send_time = current_last_send  # Update last_send_time
            except Exception as check_err:
                logger.error(f"Error in buffer_check_loop: {check_err}")
                break  # Stop the loop on error

    # --- End buffer check loop ---

    try:
        # Start the background task to handle buffer timeouts
        buffer_task = asyncio.create_task(buffer_check_loop())
        logger.debug(
            f"Session {session.user_id}: Started server-side audio buffer check loop."
        )

        full_text = ""
        async for event in session.events:
            if websocket.closed:
                logger.warning(
                    f"[Session: {session_id}] WebSocket closed during agent response handling. Exiting task."
                )
                break

            # --- Interruption ---
            if event.interrupted:
                logger.info(f"[Session: {session_id}] Agent response interrupted.")
                await send_json_message(
                    websocket,
                    "interrupted",
                    {"message": "Response interrupted by user input"},
                )

                # --- clear buffer on interruption
                if len(audio_buffer) > 0:
                    logger.debug("Clearing server audio buffer due to interruption.")
                    audio_buffer.clear()
                # --- End buffer clearing ---

                continue  # Skip processing the rest of this interrupted event

            # --- Tool Call and Result handling ---
            if event.content and event.content.parts:
                part = event.content.parts[0]
                if part.function_call:
                    # --- Flush buffer before sending non-audio message ---
                    if len(audio_buffer) > 0:
                        last_send_time = await send_buffered_audio(
                            websocket, audio_buffer, last_send_time, force_send=True
                        )
                    # --- End flush ---
                    tool = part.function_call
                    logger.info(
                        f"[Session: {session_id}] Sending tool_call: {tool.name}"
                    )
                    await send_json_message(
                        websocket, "tool_call", {"name": tool.name, "args": tool.args}
                    )

                elif part.function_response:
                    # --- Flush buffer before sending non-audio message ---
                    if len(audio_buffer) > 0:
                        last_send_time = await send_buffered_audio(
                            websocket, audio_buffer, last_send_time, force_send=True
                        )
                    # --- End flush ---
                    tool_result = part.function_response
                    logger.info(
                        f"[Session: {session_id}] Sending tool_result for: {tool_result.name}"
                    )
                    await send_json_message(
                        websocket, "tool_result", tool_result.response
                    )  # Send the actual response content

                elif part.text:
                    text_chunk = part.text
                    # --- Text and TTS handling ---
                    if not event.partial:  # Process complete text chunks
                        # --- Flush buffer before sending text/starting TTS ---
                        if len(audio_buffer) > 0:
                            last_send_time = await send_buffered_audio(
                                websocket, audio_buffer, last_send_time, force_send=True
                            )
                        # --- End flush ---
                        if USE_TTS and TTS_CLIENT:
                            if text_chunk.strip():
                                logger.info(
                                    f"[Session: {session_id}] Synthesizing TTS for chunk: '{text_chunk[:50]}...'"
                                )
                                if not TTS_CONFIG:
                                    logger.error(
                                        f"[Session: {session_id}] Cannot synthesize TTS, config unavailable."
                                    )
                                    await send_json_message(
                                        websocket, "text", text_chunk
                                    )  # Fallback to text
                                    continue

                                config_request = (
                                    texttospeech.StreamingSynthesizeRequest(
                                        streaming_config=TTS_CONFIG
                                    )
                                )

                                def request_generator():
                                    yield config_request
                                    # Send text in manageable chunks if necessary, though here we send the whole chunk
                                    yield texttospeech.StreamingSynthesizeRequest(
                                        input=texttospeech.StreamingSynthesisInput(
                                            text=text_chunk
                                        )
                                    )

                                try:
                                    streaming_responses = (
                                        TTS_CLIENT.streaming_synthesize(
                                            request_generator()
                                        )
                                    )
                                    for response in streaming_responses:
                                        if response.audio_content:
                                            # --- Append to buffer instead of sending directly ---
                                            audio_chunk_bytes = response.audio_content
                                            logger.debug(
                                                f"Session {session_id}: Received TTS audio chunk: {len(audio_chunk_bytes)} bytes"
                                            )
                                            audio_buffer.extend(audio_chunk_bytes)
                                            # Check immediately if buffer is full enough to send
                                            last_send_time = await send_buffered_audio(
                                                websocket, audio_buffer, last_send_time
                                            )
                                            # --- End buffer modification ---

                                            # audio_base64 = base64.b64encode(response.audio_content).decode('utf-8')
                                            # await send_json_message(websocket, "audio", audio_base64)

                                except Exception as tts_error:
                                    logger.exception(
                                        f"[Session: {session_id}] Error during TTS streaming: {tts_error}"
                                    )
                                    await send_json_message(
                                        websocket, "text", text_chunk
                                    )  # Fallback to text on TTS error
                        else:
                            # Send complete text if not using TTS or TTS failed
                            logger.info(
                                f"[Session: {session_id}] Sending complete text chunk: '{text_chunk[:50]}...'"
                            )
                            await send_json_message(websocket, "text", text_chunk)

                # --- Image handling ---
                elif part.inline_data and part.inline_data.mime_type.startswith(
                    "image"
                ):
                    # --- Flush buffer before sending non-audio message ---
                    if len(audio_buffer) > 0:
                        last_send_time = await send_buffered_audio(
                            websocket, audio_buffer, last_send_time, force_send=True
                        )
                    # --- End flush ---
                    logger.info(
                        f"[Session: {session_id}] Sending image data ({part.inline_data.mime_type})"
                    )
                    image_base64 = base64.b64encode(part.inline_data.data).decode(
                        "utf-8"
                    )
                    await send_json_message(
                        websocket,
                        "image",
                        f"data:{part.inline_data.mime_type};base64,{image_base64}",
                    )

                # --- Audio handling with buffering ---
                # TODO: Replace this once b/403379753 is resolved (if agent sends audio directly)
                elif part.inline_data and part.inline_data.mime_type.startswith(
                    "audio/pcm"
                ):
                    logger.debug(
                        f"[Session: {session_id}] Received direct audio data (PCM): {len(part.inline_data.data)} bytes"
                    )
                    # --- Append direct audio to buffer ---
                    audio_chunk_bytes = part.inline_data.data
                    audio_buffer.extend(audio_chunk_bytes)
                    # Check immediately if buffer is full enough to send
                    last_send_time = await send_buffered_audio(
                        websocket, audio_buffer, last_send_time
                    )
                    # --- End buffer modification ---
                    continue  # Handled direct audio

            # Yield control briefly to allow other tasks to run
            await asyncio.sleep(0)
        else:
            # Loop finished without breaking (i.e., no client disconnect)
            agent_turn_completed_normally = True

    except (WebsocketsConnectionClosedError, ConnectionRefusedError) as conn_err:
        # --- Catch specific backend connection errors ---
        logger.warning(
            f"[Session: {session_id}] Connection error while receiving agent events: {conn_err}"
        )
        logger.warning(
            f"[Session: {session_id}] This likely means the connection to the Gemini API backend was lost (e.g., RPC::DEADLINE_EXCEEDED)."
        )
        # Inform the client about the temporary issue
        await send_error_message(
            websocket,
            {
                "message": "There was a temporary issue communicating with the AI assistant.",
                "action": "Please try sending your message again.",
                "error_type": "backend_connection_error",
            },
        )
        # Do NOT re-raise. Let this task end gracefully.
    except asyncio.CancelledError:
        logger.info(f"[Session: {session_id}] Agent response handler task cancelled.")
    except Exception as e:
        logger.exception(
            f"[Session: {session_id}] Error in handle_agent_responses: {e}"
        )
        # Attempt to send an error message to the client if the websocket is still open
        await send_error_message(
            websocket,
            {
                "message": "An internal error occurred while processing the assistant's response.",
                "action": "Please try sending your message again or reconnect if issues persist.",
                "error_type": "agent_response_processing_error",
            },
        )
        # Do NOT re-raise. Let this task end gracefully.
    finally:
        logger.info(f"[Session: {session_id}] Agent response handler task finished.")
        # --- Cleanup Buffer Task and Flush Buffer ---
        if buffer_task and not buffer_task.done():
            logger.debug(f"Session {session_id}: Cancelling buffer check loop task.")
            buffer_task.cancel()
            try:
                await buffer_task  # Wait for cancellation to complete
            except asyncio.CancelledError:
                logger.debug(
                    f"Session {session_id}: Buffer check loop task successfully cancelled."
                )
            except Exception as task_cancel_err:
                logger.error(
                    f"Session {session_id}: Error awaiting cancelled buffer task: {task_cancel_err}"
                )

        # Force send any remaining audio in the buffer *after* cancelling the loop
        if len(audio_buffer) > 0:
            logger.info(
                f"Session {session_id}: Flushing remaining audio buffer ({len(audio_buffer)} bytes) in finally block."
            )
            # Use the last known send time, or current time if none exists
            final_flush_time = (
                last_send_time if last_send_time else asyncio.get_event_loop().time()
            )
            await send_buffered_audio(
                websocket, audio_buffer, final_flush_time, force_send=True
            )
        # --- End Cleanup ---

        # Only signal turn complete if the agent finished its turn normally,
        # not if it was interrupted by an error or cancellation.
        if agent_turn_completed_normally and not websocket.closed:
            logger.info(f"[Session: {session_id}] Sending turn_complete signal.")
            await send_json_message(websocket, "turn_complete", {})
        else:
            logger.info(
                f"[Session: {session_id}] Not sending turn_complete signal (error, cancellation, or client closed)."
            )


# --- Client Message Handling (Adapted for aiohttp) ---


async def handle_client_messages(
    websocket: web.WebSocketResponse, session: SessionState
) -> None:
    """Handles incoming messages from the client."""
    session_id = session.user_id
    logger.info(f"[Session: {session_id}] Starting client message handler task.")
    try:
        async for msg in websocket:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")
                    msg_data = data.get("data")  # Renamed to avoid conflict

                    if not msg_type:
                        logger.warning(
                            f"[Session: {session_id}] Received message without type: {data}"
                        )
                        continue

                    if msg_type == "audio":
                        if msg_data:
                            # logger.debug(f"[Session: {session_id}] Client -> Agent: Sending audio data...")
                            session.live_request_queue.send_realtime(
                                google_types.Blob(
                                    data=base64.b64decode(msg_data),
                                    mime_type="audio/pcm",
                                )
                            )
                        else:
                            logger.warning(
                                f"[Session: {session_id}] Received audio message with no data."
                            )
                    elif msg_type == "image":
                        if msg_data:
                            logger.debug(
                                f"[Session: {session_id}] Client -> Agent: Sending image data..."
                            )
                            # Assuming base64 encoded image data after comma
                            img_content = base64.b64decode(msg_data)
                            session.live_request_queue.send_realtime(
                                google_types.Blob(
                                    data=img_content, mime_type="image/jpeg"
                                )  # Assuming JPEG, adjust if needed
                            )
                        else:
                            logger.warning(
                                f"[Session: {session_id}] Received image message with no data."
                            )
                    elif msg_type == "text":
                        if msg_data is not None:  # Allow empty strings
                            logger.info(
                                f"[Session: {session_id}] Client -> Agent: Sending text: '{msg_data[:50]}...'"
                            )
                            session.live_request_queue.send_content(
                                google_types.Content(
                                    role="user",
                                    parts=[google_types.Part.from_text(text=msg_data)],
                                )
                            )
                        else:
                            logger.warning(
                                f"[Session: {session_id}] Received text message with no data."
                            )
                    elif msg_type == "end":
                        logger.info(
                            f"[Session: {session_id}] Received end signal from client."
                        )
                        # Optionally trigger agent finalization or specific actions here
                        # session.live_request_queue.send_content(...) # Example: send a final prompt
                    else:
                        logger.warning(
                            f"[Session: {session_id}] Unsupported message type received: {msg_type}"
                        )

                except json.JSONDecodeError:
                    logger.error(
                        f"[Session: {session_id}] Received invalid JSON from client: {msg.data}"
                    )
                except Exception as e:
                    logger.exception(
                        f"[Session: {session_id}] Error processing client message: {e}"
                    )

            elif msg.type == WSMsgType.BINARY:
                logger.warning(
                    f"[Session: {session_id}] Received unexpected binary message from client."
                )
                # Handle binary data if needed, e.g., direct audio stream
                # session.live_request_queue.send_realtime(google_types.Blob(data=msg.data, mime_type='...'))

            elif msg.type == WSMsgType.ERROR:
                logger.error(
                    f"[Session: {session_id}] WebSocket connection closed with exception {websocket.exception()}"
                )
                break  # Exit loop on WebSocket error

            elif msg.type == WSMsgType.CLOSE:
                logger.info(
                    f"[Session: {session_id}] WebSocket close message received from client."
                )
                break  # Exit loop gracefully on client close

    except asyncio.CancelledError:
        logger.info(f"[Session: {session_id}] Client message handler task cancelled.")
    except Exception as e:
        # Log unexpected errors in the message handling loop
        logger.exception(
            f"[Session: {session_id}] Unexpected error in handle_client_messages: {e}"
        )
    finally:
        logger.info(f"[Session: {session_id}] Client message handler task finished.")
        # Ensure the websocket is closed from the server side if the loop exits unexpectedly
        if not websocket.closed:
            await websocket.close(
                code=WSCloseCode.GOING_AWAY, message=b"Server closing connection"
            )


# --- Main Message Handling Orchestration (Adapted for aiohttp) ---


async def handle_messages(
    websocket: web.WebSocketResponse, session: SessionState
) -> None:
    """Handles bidirectional message flow using asyncio TaskGroup."""
    session_id = session.user_id
    client_task = None
    agent_task = None

    try:
        logger.info(f"[Session: {session_id}] Starting message handling tasks.")
        async with asyncio.TaskGroup() as tg:
            client_task = tg.create_task(
                handle_client_messages(websocket, session),
                name=f"client_handler_{session_id}",
            )
            agent_task = tg.create_task(
                handle_agent_responses(websocket, session),
                name=f"agent_handler_{session_id}",
            )

        logger.info(f"[Session: {session_id}] Both message handling tasks completed.")

    except* asyncio.CancelledError:
        logger.info(f"[Session: {session_id}] Message handling task group cancelled.")
        # Tasks are automatically cancelled by TaskGroup context exit
    except* Exception as eg:
        logger.error(
            f"[Session: {session_id}] Error occurred within message handling TaskGroup: {eg.exceptions}"
        )
        # Check for specific errors like quota exceeded
        handled = False
        for exc in eg.exceptions:
            if "Quota exceeded" in str(exc):  # Simple string check, adjust if needed
                logger.warning(
                    f"[Session: {session_id}] Quota exceeded error detected."
                )
                await send_error_message(
                    websocket,
                    {
                        "message": "Quota exceeded.",
                        "action": "Please wait a moment and try again.",
                        "error_type": "quota_exceeded",
                    },
                )
                # Optionally send a text message as well
                await send_json_message(
                    websocket,
                    "text",
                    "⚠️ Quota exceeded. Please wait a moment and try again.",
                )
                handled = True
                break  # Stop checking once handled

        if not handled:
            logger.exception(
                f"[Session: {session_id}] Unhandled error in message handling TaskGroup."
            )
            # Send a generic error if the connection is still open
            await send_error_message(
                websocket,
                {
                    "message": "An internal error occurred during message handling.",
                    "action": "Please try reconnecting.",
                    "error_type": "task_group_error",
                },
            )
        # Task cancellation is handled by TaskGroup context exit
    finally:
        logger.info(f"[Session: {session_id}] Exiting handle_messages function.")
        # Ensure tasks are cancelled if the function exits unexpectedly outside the TaskGroup block
        # (though TaskGroup usually handles this)
        if client_task and not client_task.done():
            client_task.cancel()
        if agent_task and not agent_task.done():
            agent_task.cancel()
        # Ensure websocket is closed if not already
        if not websocket.closed:
            logger.warning(
                f"[Session: {session_id}] Closing websocket in handle_messages finally block."
            )
            await websocket.close(
                code=WSCloseCode.NORMAL_CLOSURE, message=b"Session ending"
            )


# --- Main Client Connection Handler (Entry Point - Adapted for aiohttp) ---


async def handle_client(websocket: web.WebSocketResponse) -> None:
    """
    Handles a new client connection established via aiohttp.
    This function is called by the WebSocket route handler in combined-server.py.
    """
    # Generate a unique session ID (using object ID is simple but not persistent across restarts)
    # Consider using a more robust method if session persistence is needed.
    session_id = str(id(websocket))
    logger.info(f"WebSocket connection established. Assigning session ID: {session_id}")

    session = None  # Initialize session to None
    try:
        # 1. Get Agent Configuration
        agent_config = get_agent_config(session_id)  # Pass session_id for context
        app_name = agent_config.get("app_name", "default_app")
        root_agent = agent_config.get("root_agent")
        context = agent_config.get("context", {})  # Ensure context is a dict

        if not root_agent:
            logger.error(
                f"[Session: {session_id}] Agent configuration failed: No root agent found."
            )
            await send_error_message(
                websocket, {"message": "Server configuration error: Agent not found."}
            )
            await websocket.close(
                code=WSCloseCode.INTERNAL_ERROR, message=b"Agent configuration failed"
            )
            return

        # 2. Create Session State
        session = await create_session(
            session_id, root_agent, app_name, context=context
        )

        config_data = {
            "model": MODEL,
            "voice": VOICE,
            "model_language": MODEL_LANGUAGE,
            "prompt_language": PROMPT_LANGUAGE,
            "use_tts": USE_TTS,
        }

        await send_json_message(websocket, "config", config_data)

        # 3. Send "ready" message to client
        await send_json_message(websocket, "ready", True)
        logger.info(
            f">>>>>>>>>>>>>>> NEW SESSION: {session_id} ({app_name}) <<<<<<<<<<<<<<<"
        )

        # 4. Start bidirectional message handling
        await handle_messages(websocket, session)

    except ConnectionResetError:
        logger.warning(f"[Session: {session_id}] Connection reset by peer.")
    except asyncio.CancelledError:
        logger.info(f"[Session: {session_id}] handle_client task cancelled.")
    except Exception as e:
        logger.exception(
            f"[Session: {session_id}] Error during handle_client execution: {e}"
        )
        # Attempt to send error to client if possible
        await send_error_message(
            websocket,
            {
                "message": "An unexpected error occurred on the server.",
                "action": "Please try reconnecting.",
                "error_type": "general_server_error",
            },
        )
    finally:
        logger.info(f"Cleaning up resources for session {session_id}")
        # Ensure cleanup happens even if session creation failed partially
        await cleanup_session(session, session_id)
        # Ensure websocket is closed
        if not websocket.closed:
            logger.info(
                f"[Session: {session_id}] Closing websocket connection in handle_client finally block."
            )
            await websocket.close(
                code=WSCloseCode.GOING_AWAY, message=b"Server shutting down session"
            )
        logger.info(f"Session {session_id} fully terminated.")
