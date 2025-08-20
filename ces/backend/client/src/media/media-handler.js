/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

export class MediaHandler {
  constructor() {
    this.videoElement = null;
    this.currentStream = null;
    this.isWebcamActive = false;
    this.isScreenActive = false;
    this.frameCapture = null;
    this.frameCallback = null;
    this.usingFrontCamera = false;
  }

  initialize(videoElement) {
    this.videoElement = videoElement;
  }

  // Helper function to detect mobile devices
  async isMobileDevice() {
    if (navigator.userAgentData && navigator.userAgentData.mobile) {
      return true;
    }
    const userAgent = navigator.userAgent || navigator.vendor || window.opera;
    return /Mobi|Android|iPhone/i.test(userAgent);
  }

  async getCameras() {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    console.info(devices)
    return devices.filter(device => device.kind === 'videoinput');
    } catch (error) {
      console.error('Error getting cameras:', error);
      return [];
    }
  }

  async startWebcam(options = {}) {
    try {
      const { useFrontCamera = false, deviceId = null } = options;
      const isMobile = await this.isMobileDevice();

      const constraints = {
        video: {
          width: 1280,
          height: 720,
        }
      };

      if (isMobile) {
        constraints.video.facingMode = useFrontCamera ? "user" : "environment";
      } else if (deviceId) {
        constraints.video.deviceId = { exact: deviceId };
      }

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.handleNewStream(stream);
      this.isWebcamActive = true;
      this.usingFrontCamera = isMobile ? useFrontCamera : false;
      return true;

    } catch (error) {
      console.error('Error accessing webcam:', error);
      // Fallback for desktop if specific constraints fail
      if (! (await this.isMobileDevice())) {
          try {
              console.log('Trying webcam with no constraints...');
              const stream = await navigator.mediaDevices.getUserMedia({ video: true });
              this.handleNewStream(stream);
              this.isWebcamActive = true;
              return true;
          } catch (fallbackError) {
              console.error('Fallback webcam access also failed:', fallbackError);
              return false;
          }
      }
      return false;
    }
  }

  // async startWebcam(useFrontCamera = false) {
  //   try {
  //     const stream = await navigator.mediaDevices.getUserMedia({ 
  //       video: { 
  //         width: 1280, 
  //         height: 720,
  //         facingMode: useFrontCamera ? "user" : "environment"
  //       } 
  //     });
  //     this.handleNewStream(stream);
  //     this.isWebcamActive = true;
  //     this.usingFrontCamera = useFrontCamera;
  //     return true;
  //   } catch (error) {
  //     console.error('Error accessing webcam:', error);
  //     return false;
  //   }
  // }

  async startScreenShare() {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ 
        video: true 
      });
      this.handleNewStream(stream);
      this.isScreenActive = true;
      
      // Handle when user stops sharing via browser controls
      stream.getVideoTracks()[0].addEventListener('ended', () => {
        this.stopAll();
      });
      
      return true;
    } catch (error) {
      console.error('Error sharing screen:', error);
      return false;
    }
  }

  async switchCamera() {
    if (!this.isWebcamActive) return false;
    
    // On mobile, we can just flip the facing mode.
    if (await this.isMobileDevice()) {
        this.stopAll(); // Stop current stream and capture
        const success = await this.startWebcam({ useFrontCamera: !this.usingFrontCamera });
        if (success && this.frameCallback) {
            this.startFrameCapture(this.frameCallback);
        }
        return success;
    } 
    // For desktop, use device enumeration
    else {
        const cameras = await this.getCameras();
        if (cameras.length < 2) {
            console.log("Not enough cameras to switch.");
            return false;
        }

        const currentTrack = this.currentStream.getVideoTracks()[0];
        const currentDeviceId = currentTrack.getSettings().deviceId;

        const currentCameraIndex = cameras.findIndex(device => device.deviceId === currentDeviceId);
        const nextCameraIndex = (currentCameraIndex + 1) % cameras.length;
        const nextCamera = cameras[nextCameraIndex];

        this.stopAll(); // This also stops frame capture

        const success = await this.startWebcam({ deviceId: nextCamera.deviceId });
        if (success && this.frameCallback) {
            this.startFrameCapture(this.frameCallback);
        }
        return success;
    }
  }

  handleNewStream(stream) {
    if (this.currentStream) {
      this.stopAll();
    }
    this.currentStream = stream;
    if (this.videoElement) {
      this.videoElement.srcObject = stream;
      this.videoElement.classList.remove('hidden');
    }
  }

  stopAll() {
    if (this.currentStream) {
      this.currentStream.getTracks().forEach(track => track.stop());
      this.currentStream = null;
    }
    if (this.videoElement) {
      this.videoElement.srcObject = null;
      this.videoElement.classList.add('hidden');
    }
    this.isWebcamActive = false;
    this.isScreenActive = false;
    this.stopFrameCapture();
  }

  startFrameCapture(onFrame) {
    this.frameCallback = onFrame;

    const startCaptureInterval = () => {
      if (this.frameCapture) {
        clearInterval(this.frameCapture);
      }
      const captureFrame = () => {
        if (!this.currentStream || !this.videoElement || !this.videoElement.videoWidth) {
          return;
        }
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = this.videoElement.videoWidth;
        canvas.height = this.videoElement.videoHeight;
        context.drawImage(this.videoElement, 0, 0, canvas.width, canvas.height);
        const base64Image = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
        this.frameCallback(base64Image);
      };
      this.frameCapture = setInterval(captureFrame, 1000);
    };

    if (this.videoElement) {
      // If the video is already playing, start capturing.
      if (!this.videoElement.paused) {
        startCaptureInterval();
      } else {
        // Otherwise, wait for it to start playing.
        this.videoElement.addEventListener('playing', startCaptureInterval, { once: true });
      }
    }
  }

  stopFrameCapture() {
    if (this.frameCapture) {
      clearInterval(this.frameCapture);
      this.frameCapture = null;
    }
  }
} 