import { useEffect, useRef, useState } from "react";
import { Download, Share2, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

/**
 * Branded share card generator using HTML5 canvas.
 * Renders user + match side-by-side with score + branding.
 * Supports "square" (1080x1080) and "story" (1080x1920) formats.
 */

function loadImage(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

async function drawCard({ format, user, match, score, mode }) {
  const W = 1080;
  const H = format === "story" ? 1920 : 1080;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  // bg gradient
  const grad = ctx.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, "#ffeaf3");
  grad.addColorStop(0.5, "#fff3e6");
  grad.addColorStop(1, "#ffd9e6");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // soft blobs
  const radial = ctx.createRadialGradient(W * 0.85, H * 0.1, 50, W * 0.85, H * 0.1, 700);
  radial.addColorStop(0, "rgba(255,90,160,0.35)");
  radial.addColorStop(1, "rgba(255,90,160,0)");
  ctx.fillStyle = radial;
  ctx.fillRect(0, 0, W, H);

  // brand pill
  ctx.font = "bold 56px Fredoka, system-ui";
  ctx.fillStyle = "#ff2d8a";
  ctx.textAlign = "center";
  ctx.fillText("DoppelCrush", W / 2, 130);
  ctx.font = "500 30px Quicksand, system-ui";
  ctx.fillStyle = "#475569";
  ctx.fillText("Find your Doppel. Flirt with chaos.", W / 2, 178);

  // photos side by side
  const photoW = 380;
  const photoH = 480;
  const gap = 60;
  const startX = (W - (photoW * 2 + gap)) / 2;
  const photoY = format === "story" ? 360 : 260;

  const drawPhoto = async (src, x) => {
    const img = await loadImage(src);
    ctx.save();
    roundRect(ctx, x, photoY, photoW, photoH, 40);
    ctx.fillStyle = "#fff";
    ctx.fill();
    ctx.shadowColor = "rgba(255,45,138,0.25)";
    ctx.shadowBlur = 32;
    ctx.shadowOffsetY = 18;
    ctx.fill();
    ctx.shadowColor = "transparent";
    ctx.restore();

    ctx.save();
    roundRect(ctx, x + 10, photoY + 10, photoW - 20, photoH - 20, 30);
    ctx.clip();
    if (img) {
      // cover fit
      const ratio = Math.max((photoW - 20) / img.width, (photoH - 20) / img.height);
      const w = img.width * ratio;
      const h = img.height * ratio;
      ctx.drawImage(img, x + 10 + ((photoW - 20) - w) / 2, photoY + 10 + ((photoH - 20) - h) / 2, w, h);
    } else {
      ctx.fillStyle = "#ffd4e6";
      ctx.fillRect(x + 10, photoY + 10, photoW - 20, photoH - 20);
    }
    ctx.restore();
  };

  await drawPhoto(user?.photo_url, startX);
  await drawPhoto(match?.photo_url, startX + photoW + gap);

  // names under photos
  ctx.font = "bold 44px Fredoka";
  ctx.textAlign = "center";
  ctx.fillStyle = "#0f172a";
  ctx.fillText(user?.name || "You", startX + photoW / 2, photoY + photoH + 70);
  ctx.fillText(match?.name || "Match", startX + photoW + gap + photoW / 2, photoY + photoH + 70);

  // big heart between
  ctx.font = "120px Fredoka";
  ctx.fillStyle = "#ff2d8a";
  ctx.fillText("♥", W / 2, photoY + photoH / 2 + 40);

  // score badge
  const badgeY = photoY + photoH + 140;
  const badgeW = 720;
  const badgeH = 130;
  const bx = (W - badgeW) / 2;
  const isChaos = mode === "chaos";
  ctx.save();
  roundRect(ctx, bx, badgeY, badgeW, badgeH, 65);
  const bg = ctx.createLinearGradient(bx, badgeY, bx + badgeW, badgeY);
  if (isChaos) {
    bg.addColorStop(0, "#ff7a3d");
    bg.addColorStop(1, "#ff2d8a");
  } else {
    bg.addColorStop(0, "#ff2d8a");
    bg.addColorStop(1, "#ff7a3d");
  }
  ctx.fillStyle = bg;
  ctx.fill();
  ctx.restore();

  ctx.font = "bold 60px Fredoka";
  ctx.fillStyle = "#fff";
  ctx.textAlign = "center";
  ctx.fillText(
    isChaos ? `Chaos ${score}% match` : `Twin Energy ${score}%`,
    W / 2,
    badgeY + 85
  );

  // CTA at bottom
  if (format === "story") {
    ctx.font = "600 40px Quicksand";
    ctx.fillStyle = "#0f172a";
    ctx.fillText("Find yours at", W / 2, H - 180);
    ctx.font = "bold 64px Fredoka";
    const g = ctx.createLinearGradient(0, 0, W, 0);
    g.addColorStop(0, "#ff2d8a");
    g.addColorStop(1, "#ff7a3d");
    ctx.fillStyle = g;
    ctx.fillText("doppelcrush.app", W / 2, H - 110);
  } else {
    ctx.font = "600 32px Quicksand";
    ctx.fillStyle = "#0f172a";
    ctx.fillText("Find yours at doppelcrush.app", W / 2, H - 80);
  }

  return canvas;
}

export default function ShareCard({ user, match, score, mode = "doppel" }) {
  const [busy, setBusy] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const previewRef = useRef();

  // Build a preview (square) once
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const c = await drawCard({ format: "square", user, match, score, mode });
        if (!cancelled) setPreviewUrl(c.toDataURL("image/png"));
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [user, match, score, mode]);

  const download = async (format) => {
    setBusy(true);
    try {
      const canvas = await drawCard({ format, user, match, score, mode });
      const link = document.createElement("a");
      link.download = `doppelcrush-${format}-${(match?.name || "match").toLowerCase()}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      api.post("/share", { kind: format, target_id: match?.id }).catch(() => {});
    } finally {
      setBusy(false);
    }
  };

  const shareNative = async () => {
    try {
      const canvas = await drawCard({ format: "square", user, match, score, mode });
      const blob = await new Promise((r) => canvas.toBlob(r, "image/png"));
      if (navigator.canShare && navigator.canShare({ files: [new File([blob], "doppelcrush.png", { type: "image/png" })] })) {
        await navigator.share({
          title: "My DoppelCrush",
          text: `${score}% ${mode === "chaos" ? "Chaos" : "Twin Energy"} with ${match?.name} on DoppelCrush`,
          files: [new File([blob], "doppelcrush.png", { type: "image/png" })],
        });
        api.post("/share", { kind: "match_card", target_id: match?.id }).catch(() => {});
      } else {
        download("square");
      }
    } catch {}
  };

  return (
    <div className="space-y-3" data-testid="share-card">
      {previewUrl ? (
        <img
          ref={previewRef}
          src={previewUrl}
          alt="Share preview"
          className="w-full rounded-3xl border-4 border-white shadow-2xl"
          data-testid="share-card-preview"
        />
      ) : (
        <div className="aspect-square w-full rounded-3xl border-4 border-white bg-pink-50 grid place-items-center">
          <Loader2 className="w-8 h-8 animate-spin text-pink-500" />
        </div>
      )}
      <div className="grid grid-cols-3 gap-2">
        <button
          onClick={() => download("square")}
          disabled={busy}
          className="crush-secondary rounded-full py-2.5 font-display font-bold text-sm inline-flex items-center justify-center gap-1.5"
          data-testid="download-square-btn"
        >
          <Download className="w-4 h-4" /> Square
        </button>
        <button
          onClick={() => download("story")}
          disabled={busy}
          className="crush-secondary rounded-full py-2.5 font-display font-bold text-sm inline-flex items-center justify-center gap-1.5"
          data-testid="download-story-btn"
        >
          <Download className="w-4 h-4" /> Story
        </button>
        <button
          onClick={shareNative}
          disabled={busy}
          className="crush-cta rounded-full py-2.5 font-display font-bold text-sm inline-flex items-center justify-center gap-1.5"
          data-testid="share-native-btn"
        >
          <Share2 className="w-4 h-4" /> Share
        </button>
      </div>
    </div>
  );
}
