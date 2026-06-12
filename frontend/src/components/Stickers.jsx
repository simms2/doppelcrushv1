import { Heart, Zap, Sparkles, Star, Flame } from "lucide-react";

/** Decorative sticker — pure SVG-ish using lucide. */
export const Sticker = ({ kind = "heart", className = "", size = 56, color }) => {
  const map = {
    heart: { Icon: Heart, fill: color || "#ff2d8a", stroke: "#9d063e" },
    bolt: { Icon: Zap, fill: color || "#8a5cf6", stroke: "#5a2cc5" },
    spark: { Icon: Sparkles, fill: color || "#fbbf24", stroke: "#b45309" },
    star: { Icon: Star, fill: color || "#fbbf24", stroke: "#b45309" },
    flame: { Icon: Flame, fill: color || "#fb7185", stroke: "#9f1239" },
  };
  const { Icon, fill, stroke } = map[kind] || map.heart;
  return (
    <span className={`sticker-shadow inline-flex ${className}`} aria-hidden="true">
      <Icon
        width={size}
        height={size}
        strokeWidth={2.5}
        fill={fill}
        color={stroke}
      />
    </span>
  );
};

/** Hand-drawn scribble SVG used as background flair. */
export const Scribble = ({ className = "", color = "#ff2d8a" }) => (
  <svg
    viewBox="0 0 120 80"
    className={className}
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M5 70 C 25 20, 55 80, 75 30 S 110 65, 115 20"
      fill="none"
      stroke={color}
      strokeWidth="6"
      strokeLinecap="round"
    />
  </svg>
);

/** The kawaii winking heart sticker hero element. */
export const KawaiiHeart = ({ className = "" }) => (
  <div className={`relative ${className}`}>
    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" className="w-full h-full sticker-shadow">
      <defs>
        <linearGradient id="kawaiiHeart" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ff5fa3" />
          <stop offset="60%" stopColor="#ff2d8a" />
          <stop offset="100%" stopColor="#c41768" />
        </linearGradient>
      </defs>
      <path
        d="M100 175 C 35 130, 15 90, 30 55 C 45 25, 85 30, 100 60 C 115 30, 155 25, 170 55 C 185 90, 165 130, 100 175 Z"
        fill="url(#kawaiiHeart)"
        stroke="#fff"
        strokeWidth="6"
      />
      {/* Star eye */}
      <path
        d="M75 78 l5 -14 l5 14 l14 5 l-14 5 l-5 14 l-5 -14 l-14 -5 z"
        fill="#fff"
      />
      {/* Wink */}
      <path
        d="M120 80 q10 8 20 0"
        stroke="#fff"
        strokeWidth="6"
        strokeLinecap="round"
        fill="none"
      />
      {/* Mouth */}
      <ellipse cx="100" cy="115" rx="14" ry="9" fill="#3b0d22" />
      <path d="M86 115 q14 -14 28 0" stroke="#fff" strokeWidth="3" fill="none" />
    </svg>
  </div>
);
