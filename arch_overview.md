  1. User Interaction (Input)

   * Action: The user speaks into their microphone, or clicks the camera button.
   * Files:
       * client/mobile.html: Captures the button clicks and orchestrates the media handling.
       * client/src/audio/audio-recorder.js: Captures raw audio from the microphone.
       * client/src/media/media-handler.js: Manages access to the camera and captures video frames.

  2. Frontend to Backend (WebSocket Transmission)

   * Action: The frontend packages the user's input into JSON messages and sends them over a
     WebSocket connection to the backend server.
       * Audio is sent as base64-encoded chunks.
       * Camera status changes are sent as state update objects (e.g., { "video_active": true }).
   * Files:
       * client/src/api/gemini-api.js: Manages the WebSocket connection and provides methods
         (sendAudioChunk, sendStateUpdate) to send data to the server.

  3. Backend Processing (Receiving Data)

   * Action: The Python server listens for incoming WebSocket messages. When a message arrives, it's
     decoded, and the content is put onto a queue that the ADK's live runner is monitoring.
   * Files:
       * server/core/websocket_handler.py: The handle_client_messages function receives the raw
         messages. Based on the message type (audio, state, etc.), it processes the data and uses
         the session.live_request_queue to send it to the agent.

  4. ADK to Model (Prompting)

   * Action: The ADK's run_live method continuously processes the live_request_queue. It assembles
     the incoming data (audio, state changes from the context, etc.) into a structured prompt that
     is sent to the Gemini model.
   * Files:
       * google.adk.agents.Agent: The core ADK Agent class and its run_live method manage the
         interaction with the model.
       * server/core/agent_factory.py: This file configures the agent, including its initial context
         and tools.

  5. Model to ADK (Response Generation)

   * Action: The Gemini model processes the prompt and generates a response. This response is
     streamed back to the ADK as a series of events. These events can include text chunks, tool
     calls, or other data.
   * Files: This interaction is handled by the underlying Google Generative AI SDK, which the ADK
     uses.

  6. ADK to Backend (Event Handling)

   * Action: The ADK's run_live method yields the events it receives from the model. The backend
     code iterates through these events.
   * Files:
       * server/core/websocket_handler.py: The handle_agent_responses function iterates through the
         session.events generator, which yields the events from the ADK.

  7. Backend to Frontend (Response Transmission)

   * Action: As the backend receives events from the ADK, it forwards them to the frontend over the
     WebSocket connection. If Text-to-Speech is enabled, the backend first synthesizes the audio and
     then sends the audio data.
   * Files:
       * server/core/websocket_handler.py: The handle_agent_responses function uses
         send_json_message to send the processed events back to the client.

  8. Frontend to User (Output)

   * Action: The frontend receives the messages from the server and presents them to the user.
       * Text messages are displayed in the chat log.
       * Audio data is decoded and played through the user's speakers.
   * Files:
       * client/src/api/gemini-api.js: The onmessage handler receives the events from the server and
         triggers the appropriate callbacks (onTextContent, onAudioData).
       * client/mobile.html: The main HTML file contains the logic to handle these callbacks,
         updating the DOM to display text and using AudioStreamer to play audio.
       * client/src/audio/audio-streamer.js: Decodes and plays the incoming audio stream.