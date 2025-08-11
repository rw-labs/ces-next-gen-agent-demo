# Quick start for Live AP demo

## Prerequisites
- Setup `.env` file
- Setup gcloud `gcloud auth login`
- Setup ADC `gcloud auth application-default login`

- Generate a Desktop type client using `Google Auth Platform`. Setup required permission and then download the credential `credentials.json`
- Generate `gmail_token.json` (must be this filename) by running the following
```bash
cd es/backend/server
uv run secret_manager.py
# click browser to authenticate if necessary
```

- Setup gmail token secret key: `gcloud secrets create gmail-token --data-file=gmail_token.json`
- Backend cloudrun service account need to have the required permission.

## Virtual Env
```bash
uv sync
```

## Local Run
- `make client-local`
- `make backend-local`
- Browse to `http://localhost:8000/index.html`


## Cloud Run
- `make client-cloudrun-deploy`
- `make backend-cloudrun-deploy`
- Browse to `https://live-agent-ui-xxx.us-central1.run.app`


## High Level Architecture

![arch](arch.png)

## Detailed Architecture

![arch](architecture.png)


# Automatic Muting Logic

The automatic muting of the microphone while the agent's audio is playing is a client-side implementation designed to prevent feedback loops and interruptions. Here’s a breakdown of how it works, referencing the key files and code snippets.

### 1. `client/mobile.html` - The Orchestrator

This file contains the primary logic that connects the user interface, the audio recorder, the audio player (streamer), and the WebSocket API.

#### Muting on Audio Playback

When a new audio chunk arrives from the server, the `api.onAudioData` event handler is triggered. The first action within this handler is to mute the microphone.

```javascript
// client/mobile.html

    api.onAudioData = async (audioData) => {
      // ... (other code) ...
      try {
        if (!api.isSpeaking || lastAudioTurn !== currentTurn) {
          api.isSpeaking = true;
          lastAudioTurn = currentTurn;

          // --- Automatic Mute on Playback ---
          // Mute the microphone when the agent starts speaking to prevent
          // feedback loops or unwanted interruptions.
          audioRecorder.mute();
          audioRecorder.off('data');
        }
        const arrayBuffer = base64ToArrayBuffer(audioData);
        audioStreamer.addPCM16(new Uint8Array(arrayBuffer));
        audioStreamer.resume();
      } catch (error) {
        console.error('Error playing audio:', error);
      }
    };
```

#### Unmuting After Playback

Once the `AudioStreamer` has finished playing all the audio chunks it received from the server for a given turn, it fires an `onComplete` event. The handler for this event in `mobile.html` is responsible for unmuting the microphone.

Crucially, it respects the user's choice by checking the `isMuted` flag. If the user has manually muted the microphone, it will remain muted.

```javascript
// client/mobile.html

    audioStreamer.onComplete = () => {
      // --- Automatic Unmute after Playback ---
      // Unmute the microphone, but only if the user hasn't manually muted it.
      if (!isMuted) {
        audioRecorder.unmute();
        audioRecorder.on('data', (base64Data) => api.sendAudioChunk(base64Data));
      }
    };
```

### 2. `client/src/audio/audio-recorder.js` - The Muting Mechanism

This class handles the actual process of capturing audio from the user's microphone. The `mute()` and `unmute()` methods work by manipulating the Web Audio API graph.

The core idea is that the microphone's audio stream (`this.source`) is connected to a processing node (`this.recordingWorklet`) that sends the data to the server.

*   **`mute()`**: Disconnects the source from the worklet, stopping the flow of audio data.
*   **`unmute()`**: Reconnects the source to the worklet, resuming the flow of audio data.

```javascript
// client/src/audio/audio-recorder.js

  mute() {
    console.log('[AudioRecorder] Mute called. isMuted:', this.isMuted);
    if (this.source && this.recordingWorklet && !this.isMuted) {
      console.log('[AudioRecorder] Muting: Disconnecting source from worklet.');
      this.source.disconnect(this.recordingWorklet);
      this.isMuted = true;
    } else {
      console.log('[AudioRecorder] Mute skipped. Source:', this.source, 'Worklet:', this.recordingWorklet, 'isMuted:', this.isMuted);
    }
  }

  unmute() {
    console.log('[AudioRecorder] Unmute called. isMuted:', this.isMuted);
    if (this.source && this.recordingWorklet && this.isMuted) {
      console.log('[AudioRecorder] Unmuting: Connecting source to worklet.');
      this.source.connect(this.recordingWorklet);
      this.isMuted = false;
    } else {
      console.log('[AudioRecorder] Unmute skipped. Source:', this.source, 'Worklet:', this.recordingWorklet, 'isMuted:', this.isMuted);
    }
  }
```

In summary, the process is a clear sequence of events orchestrated by `mobile.html`: audio arrival triggers a `mute()` call on the `AudioRecorder`, and the completion of audio playback triggers an `unmute()` call, effectively preventing the user's microphone from capturing the agent's speech.



# Camera State Management Logic

The process involves a clear flow of information from the client to the server, where the agent's session state is updated, which is then read by a specific tool. Here is a detailed breakdown of that process for the `optus_modem` agent.

### The Process: From Client Action to Agent Awareness

The core principle is that the client-side application is responsible for notifying the server whenever the camera's state changes. The server then updates a state dictionary associated with the user's session, which the agent's tools can access during the conversation.

Here is the step-by-step flow:

#### 1. Initial State at Session Creation

When a new session for the `optus_modem_setup` demo is created, the server initializes the video status to `"inactive"`.

- **File:** `server/core/agent_factory.py`
- **Logic:** The `get_agent_config` function checks if `DEMO_TYPE` is `optus_modem_setup` and, if so, adds a `video_status` key to the initial context dictionary for the session.

```python
# server/core/agent_factory.py

    # --- Add Optus Modem Option ---
    elif DEMO_TYPE == "optus_modem_setup":
        agent_config["app_name"] = "optus_modem_setup"
        agent_config["context"] = OptusModemContext.CUSTOMER_PROFILE
        agent_config["context"]["session_id"] = session_id # Add session_id to context
        agent_config["context"]["video_status"] = "inactive" # Set initial video status
        agent_config["root_agent"] = create_optus_modem_agent ()
    # --- End Optus Modem Option ---
```

This initial context is used to create the `SessionState` object.

#### 2. Client Sends a State Update Message

When the user clicks the camera button on the frontend, the client-side JavaScript sends a WebSocket message to the server with `type: 'state'`. This message includes a boolean payload indicating if the video is now active.

*(This part happens in `client/mobile.html`, where `api.sendStateUpdate({ "video_active": true })` is called).*

#### 3. Server Receives the Message and Updates Session State

The server's WebSocket handler is constantly listening for messages from the client.

- **File:** `server/core/websocket_handler.py`
- **Logic:** The `handle_client_messages` function receives the message. When it identifies a message of `type == "state"`, it parses the `video_active` boolean and **directly mutates the session's live state dictionary**.

This is the most critical step. The handler determines a descriptive status (`"started"`, `"ended"`, `"active"`, or `"inactive"`) and writes it to `session.session.state["video_status"]`. This is the same state object that the agent's tools will have access to.

```python
# server/core/websocket_handler.py

                    elif msg_type == "state":
                        if msg_data and isinstance(msg_data, dict) and "video_active" in msg_data:
                            new_video_state = msg_data.get("video_active", False)
                            logger.info(
                                f"[Session: {session_id}] Received video state update: {new_video_state}"
                            )

                            # Determine the video status based on state change
                            if new_video_state and not session.video_active:
                                video_status = "started"
                            elif not new_video_state and session.video_active:
                                video_status = "ended"
                            elif new_video_state:
                                video_status = "active"
                            else:
                                video_status = "inactive"

                            # Update the session state for the next turn
                            session.video_active = new_video_state

                            # This is the live state dictionary used by the ADK runner.
                            # Directly mutating the state is the most reliable way to ensure
                            # the agent sees the update, given the constraints.
                            live_state = session.session.state
                            live_state["video_status"] = video_status
                            logger.info(
                                f"[Session: {session_id}] Directly updated agent state for video_status: {video_status}"
                            )
```

#### 4. Agent Tool Reads the Updated State

When the agent needs to verify if the camera is active (as instructed by its prompt), it calls the `confirm_visual_context` tool.

- **File:** `server/core/agents/optus_modem/tools.py`
- **Logic:** The tool receives a `tool_context` object from the ADK runner. This context object contains a snapshot of the session state at that moment. The tool simply reads the `video_status` value from the state dictionary and returns a result based on that value.

```python
# server/core/agents/optus_modem/tools.py

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
```

The agent then uses the `status` from the tool's output (`"video_active"` or `"video_inactive"`) to decide its next conversational step, as defined in its prompt.

