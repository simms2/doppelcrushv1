import { Sticker } from "./Stickers";
import { Camera, Zap } from "lucide-react";

const matches = [
  {
    name: "Lola",
    age: 19,
    img: "https://images.unsplash.com/photo-1557002665-c552e1832483?w=300&q=80",
    badge: { kind: "twin", label: "Twin Energy 92%" },
    blurb: "Cute. Familiar. Elite taste.",
  },
  {
    name: "Kai",
    age: 20,
    img: "https://images.unsplash.com/photo-1647593782884-1a6779139eb5?w=300&q=80",
    badge: { kind: "chaos", label: "Chaos Mode" },
    blurb: "A total switch-up. Still a yes.",
  },
  {
    name: "Ivy",
    age: 18,
    img: "https://images.unsplash.com/photo-1713812956759-371b4e8fc468?w=300&q=80",
    badge: { kind: "twin", label: "Twin Energy 87%" },
    blurb: "Same vibe. Same face card energy.",
  },
];

const Badge = ({ kind, label }) => {
  const cls = kind === "twin"
    ? "bg-pink-100 text-pink-700 border-pink-200"
    : "bg-orange-100 text-orange-700 border-orange-200";
  return (
    <span className={`inline-flex items-center gap-1 text-xs sm:text-sm px-3 py-1 rounded-full font-bold border-2 ${cls}`}>
      {kind === "chaos" ? <Zap className="w-3 h-3" /> : null}
      {label}
    </span>
  );
};

export default function LivePreview() {
  return (
    <div className="crush-window relative" data-testid="live-preview">
      <div className="crush-window-bar">
        <span className="crush-window-dot bg-rose-400" />
        <span className="crush-window-dot bg-amber-300" />
        <span className="crush-window-dot bg-emerald-400" />
      </div>
      <div className="p-5 sm:p-6">
        <div className="flex items-center gap-2 text-pink-600 font-display font-bold text-xs tracking-wider uppercase">
          <span className="w-2 h-2 rounded-full bg-pink-500 animate-pulse" />
          Live preview
        </div>
        <h3 className="font-display text-3xl sm:text-4xl font-bold text-slate-900 mt-1">
          Your matches
        </h3>

        <div className="mt-4 space-y-3">
          {matches.map((m) => (
            <div
              key={m.name}
              className="flex items-center gap-3 sm:gap-4 p-3 rounded-2xl bg-white border-2 border-slate-100 hover:border-pink-200 transition-colors"
              data-testid={`preview-card-${m.name.toLowerCase()}`}
            >
              <img
                src={m.img}
                alt={m.name}
                className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl object-cover flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <div className="font-display text-lg sm:text-xl font-bold text-slate-900">
                  {m.name}, {m.age}
                </div>
                <div className="mt-1"><Badge {...m.badge} /></div>
                <div className="text-xs sm:text-sm text-slate-500 mt-1 truncate">{m.blurb}</div>
              </div>
              <div className="hidden sm:flex flex-col gap-2">
                <button className="rounded-full px-4 py-2 text-sm bg-white border-2 border-slate-200 font-bold text-slate-700">Pass</button>
                <button className="crush-cta rounded-full px-4 py-2 text-sm font-bold">♥ Into it</button>
              </div>
            </div>
          ))}
        </div>

        <button className="mt-4 w-full text-purple-600 font-bold font-display py-2 hover:text-purple-800">
          See more matches ⌄
        </button>
      </div>

      {/* corner stickers — pointer-events-none so they don't intercept clicks */}
      <div className="pointer-events-none" aria-hidden="true">
        <Sticker kind="heart" size={48} className="absolute -top-4 -right-2 rotate-12 hidden lg:inline-flex" />
        <Sticker kind="bolt" size={44} className="absolute -bottom-4 -left-2 -rotate-12 hidden lg:inline-flex" color="#ff7a3d" />
      </div>
    </div>
  );
}

export { matches as previewMatches };
