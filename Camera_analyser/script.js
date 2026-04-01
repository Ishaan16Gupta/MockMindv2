/**
 * Camera Analyzer Module - Tracks pose, face centering, and eye gaze
 * Usage: const analyzer = new CameraAnalyzer(videoElement, callbackFn)
 */

class CameraAnalyzer {
  constructor(videoElement, onStateChange = null) {
    this.video = videoElement;
    this.onStateChange = onStateChange;
    this.camera = null;
    this.faceMesh = null;
    this.pose = null;

    this.currentState = {
      poseIsUpright: null,
      isLooking: null,
      faceCentered: null,
    };

    this.violations = {
      poseNotUpright: 0,
      notLooking: 0,
      faceNotCentered: 0,
      total: 0,
    };

    this.initialized = false;
  }

  async init() {
    if (this.initialized) return;

    try {
      // Initialize FaceMesh
      this.faceMesh = new FaceMesh({
        locateFile: (file) =>
          `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`,
      });

      this.faceMesh.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });

      this.faceMesh.onResults((results) => this._processFaceMesh(results));

      // Initialize Pose
      this.pose = new Pose({
        locateFile: (file) =>
          `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
      });

      this.pose.setOptions({
        modelComplexity: 0,
        smoothLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });

      this.pose.onResults((results) => this._processPose(results));

      // Initialize Camera
      this.camera = new Camera(this.video, {
        onFrame: async () => {
          await this.faceMesh.send({ image: this.video });
          await this.pose.send({ image: this.video });
        },
        width: 640,
        height: 480,
      });

      this.camera.start();
      this.initialized = true;
      console.log('[CameraAnalyzer] Initialized successfully');
    } catch (error) {
      console.error('[CameraAnalyzer] Initialization failed:', error);
      throw error;
    }
  }

  _processFaceMesh(results) {
    if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) {
      return;
    }

    const landmarks = results.multiFaceLandmarks[0];
    const nose = landmarks[1];

    // Horizontal eye tracking
    const leftEye = (landmarks[468].x - landmarks[33].x) / (landmarks[133].x - landmarks[33].x);
    const rightEye = (landmarks[473].x - landmarks[362].x) / (landmarks[263].x - landmarks[362].x);
    const irisPos = (leftEye + rightEye) / 2;

    // Vertical eye tracking
    const rightVertical = (landmarks[468].y - landmarks[159].y) / (landmarks[145].y - landmarks[159].y);
    const leftVertical = (landmarks[473].y - landmarks[386].y) / (landmarks[374].y - landmarks[386].y);
    const verticalPos = (rightVertical + leftVertical) / 2;

    // Final decisions
    const isLooking =
      irisPos > 0.35 && irisPos < 0.65 &&
      verticalPos > 0.35 && verticalPos < 0.65;

    const faceCentered = nose.x > 0.4 && nose.x < 0.6 && nose.y > 0.4 && nose.y < 0.6;

    const prevLooking = this.currentState.isLooking;
    const prevFaceCentered = this.currentState.faceCentered;

    this.currentState.isLooking = isLooking;
    this.currentState.faceCentered = faceCentered;

    // Track violations
    if (prevLooking === true && isLooking === false) {
      this.violations.notLooking++;
      this.violations.total++;
    }
    if (prevFaceCentered === true && faceCentered === false) {
      this.violations.faceNotCentered++;
      this.violations.total++;
    }

    this._notifyStateChange();
  }

  _processPose(results) {
    if (!results.poseLandmarks) return;

    const nose = results.poseLandmarks[0];
    const leftShoulder = results.poseLandmarks[11];
    const rightShoulder = results.poseLandmarks[12];

    const shoulderMidX = (leftShoulder.x + rightShoulder.x) / 2;

    // Horizontal alignment (leaning)
    const lean = Math.abs(nose.x - shoulderMidX);

    // Vertical alignment (slouching)
    const shoulderY = (leftShoulder.y + rightShoulder.y) / 2;
    const headToShoulder = shoulderY - nose.y;

    const isUpright =
      lean < 0.05 &&        // not leaning sideways
      headToShoulder > 0.15; // head clearly above shoulders

    const prevUpright = this.currentState.poseIsUpright;
    this.currentState.poseIsUpright = isUpright;

    // Track violations
    if (prevUpright === true && isUpright === false) {
      this.violations.poseNotUpright++;
      this.violations.total++;
    }

    this._notifyStateChange();
  }

  _notifyStateChange() {
    if (this.onStateChange) {
      this.onStateChange({
        state: this.currentState,
        violations: this.violations,
      });
    }
  }

  getViolations() {
    return this.violations;
  }

  getState() {
    return this.currentState;
  }

  stop() {
    if (this.camera) {
      this.camera.stop();
      this.initialized = false;
    }
  }
}
