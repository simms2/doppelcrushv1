/**
 * Face detection + embedding helpers powered by face-api.js.
 * Models are loaded lazily from a CDN.
 */
import * as faceapi from "face-api.js";

const MODEL_URL = "https://justadudewhohacks.github.io/face-api.js/models";

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

/**
 * Given an <img> element already loaded with a selfie, return:
 *  { embedding: number[128], ok: true } or { ok: false, reason }
 */
export async function getFaceEmbedding(imgEl) {
  await loadFaceModels();
  const opts = new faceapi.TinyFaceDetectorOptions({
    inputSize: 320,
    scoreThreshold: 0.4,
  });
  const detection = await faceapi
    .detectSingleFace(imgEl, opts)
    .withFaceLandmarks()
    .withFaceDescriptor();
  if (!detection) {
    return { ok: false, reason: "no_face" };
  }
  return { ok: true, embedding: Array.from(detection.descriptor) };
}

/** Read a File into an <img> element (for face-api). */
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
