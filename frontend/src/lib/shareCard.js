// Bold meme-y share card generator for DoppelCrush Invite flow.
// Renders an 1080x1080 PNG using HTML5 Canvas (no server roundtrip).

const W = 1080;
const H = 1080;

// ---- helpers ----
function roundRect(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

function drawStrokedText(ctx, text, x, y, {
  font = "900 140px 'Bricolage Grotesque', 'Inter', system-ui, sans-serif",
  fill = "#ffffff",
  stroke = "#0f172a",
  strokeWidth = 14,
  align = "center",
  baseline = "alphabetic",
  rotate = 0,
} = {}) {
  ctx.save();
  ctx.translate(x, y);
  if (rotate) ctx.rotate(rotate);
  ctx.font = font;
  ctx.textAlign = align;
  ctx.textBaseline = baseline;
  ctx.lineJoin = "round";
  ctx.miterLimit = 2;
  ctx.lineWidth = strokeWidth;
  ctx.strokeStyle = stroke;
  ctx.strokeText(text, 0, 0);
  ctx.fillStyle = fill;
  ctx.fillText(text, 0, 0);
  ctx.restore();
}

function drawHeart(ctx, cx, cy, size, color = "#ff2d8a", rotate = 0) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(rotate);
  ctx.scale(size / 100, size / 100);
  ctx.fillStyle = color;
  ctx.strokeStyle = "#0f172a";
  ctx.lineWidth = 8;
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(0, 30);
  ctx.bezierCurveTo(-60, -30, -110, 30, 0, 90);
  ctx.bezierCurveTo(110, 30, 60, -30, 0, 30);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  // gloss
  ctx.fillStyle = "rgba(255,255,255,0.55)";
  ctx.beginPath();
  ctx.ellipse(-22, 8, 18, 10, -0.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawSpark(ctx, cx, cy, size, color = "#ffd84d", rotate = 0) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(rotate);
  ctx.scale(size / 100, size / 100);
  ctx.fillStyle = color;
  ctx.strokeStyle = "#0f172a";
  ctx.lineWidth = 8;
  ctx.lineJoin = "round";
  ctx.beginPath();
  for (let i = 0; i < 4; i++) {
    const a = (i * Math.PI) / 2;
    const x = Math.cos(a) * 70;
    const y = Math.sin(a) * 70;
    const x2 = Math.cos(a + Math.PI / 4) * 22;
    const y2 = Math.sin(a + Math.PI / 4) * 22;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
    ctx.lineTo(x2, y2);
  }
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function drawBolt(ctx, cx, cy, size, color = "#8a5cf6", rotate = 0) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(rotate);
  ctx.scale(size / 100, size / 100);
  ctx.fillStyle = color;
  ctx.strokeStyle = "#0f172a";
  ctx.lineWidth = 8;
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(-20, -70);
  ctx.lineTo(35, -10);
  ctx.lineTo(5, -5);
  ctx.lineTo(25, 70);
  ctx.lineTo(-35, 5);
  ctx.lineTo(-5, 0);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

// Generate the share card.
// Returns a Promise<Blob> (PNG) plus the dataURL preview.
export async function generateShareCard({ code = "—", url = "" } = {}) {
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  // Wait for fonts that the page already loaded
  if (document.fonts && document.fonts.ready) {
    try { await document.fonts.ready; } catch { /* fonts api unsupported */ }
  }

  // --- Background: bold gradient (yellow -> pink -> orange) ---
  const grad = ctx.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, "#ffd84d");
  grad.addColorStop(0.45, "#ff3d8a");
  grad.addColorStop(1, "#ff6a3d");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // halftone dots
  ctx.fillStyle = "rgba(15,23,42,0.08)";
  for (let y = 0; y < H; y += 28) {
    for (let x = 0; x < W; x += 28) {
      ctx.beginPath();
      ctx.arc(x, y, 2.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // bold inner frame
  ctx.lineWidth = 14;
  ctx.strokeStyle = "#0f172a";
  roundRect(ctx, 36, 36, W - 72, H - 72, 56);
  ctx.stroke();

  // --- Top tag pill ---
  ctx.save();
  ctx.translate(W / 2, 130);
  ctx.rotate(-0.04);
  const tagW = 460, tagH = 78;
  roundRect(ctx, -tagW / 2, -tagH / 2, tagW, tagH, tagH / 2);
  ctx.fillStyle = "#0f172a";
  ctx.fill();
  ctx.font = "800 34px 'Bricolage Grotesque', 'Inter', system-ui, sans-serif";
  ctx.fillStyle = "#ffd84d";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("✦  DOPPELCRUSH  ✦", 0, 2);
  ctx.restore();

  // --- Headline: I FOUND MY DOPPEL ---
  drawStrokedText(ctx, "I FOUND", W / 2, 290, {
    font: "900 150px 'Bricolage Grotesque', 'Inter', system-ui, sans-serif",
    fill: "#ffffff",
    strokeWidth: 16,
    rotate: -0.02,
  });
  drawStrokedText(ctx, "MY DOPPEL", W / 2, 430, {
    font: "900 150px 'Bricolage Grotesque', 'Inter', system-ui, sans-serif",
    fill: "#ffd84d",
    strokeWidth: 16,
    rotate: 0.015,
  });

  // --- Code bubble ---
  ctx.save();
  ctx.translate(W / 2, 640);
  ctx.rotate(-0.025);
  const bubbleW = 760, bubbleH = 220;
  roundRect(ctx, -bubbleW / 2, -bubbleH / 2, bubbleW, bubbleH, 48);
  ctx.fillStyle = "#ffffff";
  ctx.fill();
  ctx.lineWidth = 12;
  ctx.strokeStyle = "#0f172a";
  ctx.stroke();
  ctx.font = "800 30px 'Bricolage Grotesque', 'Inter', system-ui, sans-serif";
  ctx.fillStyle = "#94a3b8";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("USE MY CODE", 0, -55);

  // code text gradient
  const codeGrad = ctx.createLinearGradient(-300, 0, 300, 0);
  codeGrad.addColorStop(0, "#ff2d8a");
  codeGrad.addColorStop(1, "#ff6a3d");
  ctx.font = "900 120px 'Bricolage Grotesque', 'Inter', system-ui, sans-serif";
  ctx.fillStyle = codeGrad;
  ctx.fillText((code || "—").toString().toUpperCase(), 0, 40);
  ctx.restore();

  // --- Subtitle: TWIN ENERGY or CHAOS. ---
  drawStrokedText(ctx, "TWIN ENERGY ⚡ OR CHAOS", W / 2, 830, {
    font: "900 56px 'Bricolage Grotesque', 'Inter', system-ui, sans-serif",
    fill: "#ffffff",
    strokeWidth: 10,
    rotate: 0,
  });

  drawStrokedText(ctx, "join me, it's wild 💀", W / 2, 900, {
    font: "800 42px 'Bricolage Grotesque', 'Inter', system-ui, sans-serif",
    fill: "#0f172a",
    stroke: "#ffd84d",
    strokeWidth: 10,
  });

  // --- Footer URL ---
  ctx.save();
  ctx.translate(W / 2, 1000);
  const footW = 820, footH = 70;
  roundRect(ctx, -footW / 2, -footH / 2, footW, footH, footH / 2);
  ctx.fillStyle = "#0f172a";
  ctx.fill();
  ctx.font = "800 30px 'Bricolage Grotesque', 'Inter', system-ui, sans-serif";
  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  // strip protocol for cleanliness
  const cleanUrl = (url || "").replace(/^https?:\/\//, "");
  ctx.fillText(cleanUrl || "doppelcrush.app", 0, 2);
  ctx.restore();

  // --- Stickers (drawn last to overlap) ---
  drawHeart(ctx, 140, 240, 150, "#ff2d8a", -0.35);
  drawHeart(ctx, W - 150, 200, 130, "#ffd84d", 0.45);
  drawSpark(ctx, W - 130, 560, 120, "#ffffff", 0.2);
  drawSpark(ctx, 100, 720, 100, "#ffd84d", -0.4);
  drawBolt(ctx, W - 110, 870, 130, "#8a5cf6", 0.25);
  drawBolt(ctx, 120, 470, 110, "#0f172a", -0.2);

  // export
  const dataUrl = canvas.toDataURL("image/png");
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png", 0.95));
  return { blob, dataUrl };
}

export function downloadBlob(blob, filename = "doppelcrush-invite.png") {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}
