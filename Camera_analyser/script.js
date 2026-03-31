const video = document.getElementById("video");
const chat = document.getElementById("chat");

let previousState = {
  poseIsUpright: null,
  isLooking: null,
  faceCentered: null,
};

let currentState = {
  poseIsUpright: null,
  isLooking: null,
  faceCentered: null,
};

function renderStatus() {
  if (!chat) return;

  if (
    previousState.poseIsUpright === currentState.poseIsUpright &&
    previousState.isLooking === currentState.isLooking &&
    previousState.faceCentered === currentState.faceCentered
  ) {
    return;
  }

  previousState = { ...currentState };
  chat.innerHTML = `
    <div class="user">posture Is Upright: ${currentState.poseIsUpright}</div>
    <div class="user">is Looking: ${currentState.isLooking}</div>
    <div class="user">face Centered: ${currentState.faceCentered}</div>
  `;
}

renderStatus();

navigator.mediaDevices.getUserMedia({ video: true })
  .then((stream) => {
    video.srcObject = stream;
  });

const faceMesh = new FaceMesh({
  locateFile: (file) =>
    `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`,
});

faceMesh.setOptions({
  maxNumFaces: 1,
  refineLandmarks: true,
  minDetectionConfidence: 0.5,
  minTrackingConfidence: 0.5,
});

faceMesh.onResults((results) => {
  if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
    const landmarks = results.multiFaceLandmarks[0];

    const nose = landmarks[1];

   // Horizontal
    const leftEye = (landmarks[468].x - landmarks[33].x) / (landmarks[133].x - landmarks[33].x);
    const rightEye = (landmarks[473].x - landmarks[362].x) / (landmarks[263].x - landmarks[362].x);
    const irisPos = (leftEye + rightEye) / 2;

    // Vertical
    const rightVertical = (landmarks[468].y - landmarks[159].y) / (landmarks[145].y - landmarks[159].y);
    const leftVertical = (landmarks[473].y - landmarks[386].y) / (landmarks[374].y - landmarks[386].y);
    const verticalPos = (rightVertical + leftVertical) / 2;

    // Final decision
    const isLooking =
        irisPos > 0.35 && irisPos < 0.65 &&
        verticalPos > 0.35 && verticalPos < 0.65;
    const faceCentered = nose.x > 0.4 && nose.x < 0.6 && nose.y > 0.4 && nose.y < 0.6;

    currentState = {
      ...currentState,
      isLooking,
      faceCentered,
    };
    renderStatus();

    console.log("isLooking:", isLooking, "faceCentered:", faceCentered);
  }
});

const pose = new Pose({
  locateFile: (file) =>
    `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
});

pose.setOptions({
  modelComplexity: 0,
  smoothLandmarks: true,
  minDetectionConfidence: 0.5,
  minTrackingConfidence: 0.5,
});

pose.onResults((results) => {
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

  currentState = {
    ...currentState,
    poseIsUpright: isUpright,
  };
  renderStatus();

  console.log("isUpright:", isUpright);
});

const camera = new Camera(video, {
  onFrame: async () => {
    await faceMesh.send({ image: video });
    await pose.send({ image: video });
  },
  width: 640,
  height: 480,
});

camera.start();