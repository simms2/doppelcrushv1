/**
 * Browser-side selfie validation + embedding via face-api.js.
 *
 * Returns a structured verdict so onboarding can show user-friendly errors
 * and store a quality_score alongside the embedding.
 */
import * as faceapi from "face-api.js";

const MODEL_URL = "https://justadudewhohacks.github.io/face-api.js/models";
export const MODEL_VERSION = "face-api.js@0.22.2/face_recognition_net";

let loadPromise = null;

export async function loadFaceModels() {
  if (!loadPromise) {
    loadPromise = Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
      faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
      faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
    ]).catch((e) => {
      loadPromise = null;
      throw e;
    });
  }
  return loadPromise;
}

export function fileToImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve({ img, url });
    img.onerror = (e) => reject(e);
    img.src = url;
  });
}

const FRIENDLY_REASONS = {
  no_face: "We couldn't find a face. Try a brighter, front-facing selfie.",
  multiple_faces: "We saw more than one face. Solo selfies only.",
  tiny_face: "Move closer — your face is too small in this photo.",
  low_confidence: "The angle is too extreme. Face the camera.",
  too_dark: "It's too dark. Find better light and try again.",
  too_small_image: "This image is too small. Use a higher-resolution photo.",
  decode_failed: "We couldn't read that image. Try a JPG or PNG.",
};

function reasonText(code) {
  return FRIENDLY_REASONS[code] || "We couldn't process that photo. Pick another.";
}

/** Sample the image at a downscaled resolution to estimate average brightness. */
function estimateBrightness(img) {
  try {
    const canvas = document.createElement("canvas");
    const W = 80, H = 80;
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0, W, H);
    const data = ctx.getImageData(0, 0, W, H).data;
    let total = 0;
    for (let i = 0; i < data.length; i += 4) {
      // Rec. 601 luma
      total += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    }
    return total / (W * H * 255); // 0..1
  } catch {
    return 0.5;
  }
}

/**
 * Full selfie validation pipeline.
 * Returns:
 *   { ok: true, embedding: number[128], quality_score: 0..1, brightness, face_area_pct, confidence }
 *   { ok: false, reason: string, message: string }
 */
export async function validateSelfie(imgEl) {
  if (!imgEl || !imgEl.complete) {
    return { ok: false, reason: "decode_failed", message: reasonText("decode_failed") };
  }
  const W = imgEl.naturalWidth || imgEl.width;
  const H = imgEl.naturalHeight || imgEl.height;
  if (W < 240 || H < 240) {
    return { ok: false, reason: "too_small_image", message: reasonText("too_small_image") };
  }

  await loadFaceModels();

  // Detect ALL faces so we can reject group selfies.
  const opts = new faceapi.TinyFaceDetectorOptions({ inputSize: 416, scoreThreshold: 0.35 });
  const allDetections = await faceapi.detectAllFaces(imgEl, opts);
  if (!allDetections || allDetections.length === 0) {
    return { ok: false, reason: "no_face", message: reasonText("no_face") };
  }
  if (allDetections.length > 1) {
    return { ok: false, reason: "multiple_faces", message: reasonText("multiple_faces") };
  }

  // Detailed pass with landmarks + descriptor.
  const detection = await faceapi
    .detectSingleFace(imgEl, opts)
    .withFaceLandmarks()
    .withFaceDescriptor();
  if (!detection) {
    return { ok: false, reason: "no_face", message: reasonText("no_face") };
  }
  const conf = detection.detection.score;
  const box = detection.detection.box;
  const faceArea = (box.width * box.height) / (W * H);

  if (faceArea < 0.04) {
    return { ok: false, reason: "tiny_face", message: reasonText("tiny_face") };
  }
  if (conf < 0.5) {
    return { ok: false, reason: "low_confidence", message: reasonText("low_confidence") };
  }
  const brightness = estimateBrightness(imgEl);
  if (brightness < 0.18) {
    return { ok: false, reason: "too_dark", message: reasonText("too_dark") };
  }

  // Quality score combines: confidence, face area sweet-spot (10–40%), brightness sweet-spot (~0.5)
  const areaScore = 1 - Math.min(1, Math.abs(faceArea - 0.22) / 0.22);
  const brightnessScore = 1 - Math.min(1, Math.abs(brightness - 0.55) / 0.55);
  const quality = Math.max(
    0,
    Math.min(1, 0.5 * conf + 0.25 * areaScore + 0.25 * brightnessScore),
  );

  return {
    ok: true,
    embedding: Array.from(detection.descriptor),
    quality_score: Number(quality.toFixed(3)),
    brightness: Number(brightness.toFixed(3)),
    face_area_pct: Number(faceArea.toFixed(3)),
    confidence: Number(conf.toFixed(3)),
    model_version: MODEL_VERSION,
  };
}

// Legacy export retained so callers that only need a descriptor still work.
export async function getFaceEmbedding(imgEl) {
  const v = await validateSelfie(imgEl);
  if (!v.ok) return { ok: false, reason: v.reason, message: v.message };
  return { ok: true, embedding: v.embedding, quality_score: v.quality_score };
}
