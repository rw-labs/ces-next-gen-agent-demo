# Muting Logic Explanation (Final)

### The Goal

The primary goal is to prevent the audio coming from your speakers (the agent's voice) from being picked up by your microphone. If this happens, the system would think you are speaking and interrupt the agent, creating a feedback loop. The solution is to automatically mute the microphone whenever the agent is speaking and unmute it only when the agent has completely finished.

### The Core Problem: A Race Condition

The bug was caused by a race condition. When the agent sent a very short initial audio chunk, the system would:
1.  **Mute** the microphone correctly.
2.  Play the tiny audio chunk instantly.
3.  Incorrectly think the entire turn was over and immediately **unmute** the microphone.
4.  Continue playing the rest of the agent's speech, but with the microphone now open, causing feedback.

### The Files Involved

1.  **`client/mobile.html`**: This is the main orchestrator. It contains the high-level application logic that decides *when* to mute and unmute by listening to events from the server and the other JavaScript components.

2.  **`client/src/audio/audio-recorder.js`**: This class handles the microphone. It contains the actual `mute()` and `unmute()` functions that physically disconnect and reconnect the microphone's audio stream.

3.  **`client/src/audio/audio-streamer.js`**: This class plays the agent's audio through your speakers. It now contains critical state management logic (`turnIsComplete` flag) to prevent the race condition and signal when it has truly finished playing all the audio for a given turn.

### The Final, Working Step-by-Step Process

Here is the lifecycle of a single agent response with the final fix in place:

1.  **Agent Responds & Mute Kicks In:**
    *   The server sends the first chunk of audio data.
    *   In `mobile.html`, the `api.onAudioData` function receives this data and immediately calls `audioRecorder.mute()`.
    *   The `mute()` function in `audio-recorder.js` disconnects the microphone's audio source.

2.  **Detecting the End of the Agent's Turn:**
    *   The server does not send a specific "I'm done" message.
    *   To solve this, `mobile.html` uses a 500ms timer. Every time an audio chunk arrives, the timer is reset. If 500ms pass without new audio, the client assumes the agent's turn is over and calls its own `api.onTurnComplete` function.

3.  **Signaling the End of the Turn:**
    *   The `api.onTurnComplete` function in `mobile.html` now calls `audioStreamer.complete()`.
    *   The `complete()` method in `audio-streamer.js` does one simple, important thing: it sets a flag, `this.turnIsComplete = true`.

4.  **Finishing Playback & Unmuting (The Fix):**
    *   The `audioStreamer` continues to play any audio left in its buffer.
    *   When the very last audio chunk finishes playing, an `onended` event fires inside the streamer.
    *   This `onended` handler now checks for two conditions: Is the audio queue empty? **AND** Is the `turnIsComplete` flag true?
    *   Because both are now true, it knows the turn is definitively over and it is safe to unmute. It now fires its `onComplete` event.

5.  **Unmuting Triggered:**
    *   The `onComplete` event is caught by the listener in `mobile.html`, which calls `audioRecorder.unmute()`.
    *   The `unmute()` function in `audio-recorder.js` reconnects the microphone, allowing you to speak again.

This new state-driven logic ensures that the unmute action only happens after the turn-completion timer has fired *and* all buffered audio has finished playing, completely resolving the race condition.
