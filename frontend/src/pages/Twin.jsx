import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Camera, Heart, ArrowRight, Loader2, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { LogoBadge } from "@/components/Header";
import { Sticker, KawaiiHeart, Scribble } from "@/components/Stickers";

/**
 * Public viral landing for a single user's "twin" share.
 * Anyone with the link can view a teaser — no auth required.
 * The "Find your DoppelCrush" CTA pre-fills signup with ?ref + ?twin_id so
 * once they sign up, a 1:1 compare room is auto-created between the inviter
 * and the new user.
 */
export default function Twin() {
  const { userId } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [teaser, setTeaser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get(`/share/twin/${userId}`);
        if (cancelled) return;
        if (!data.valid) setNotFound(true);
        else setTeaser(data);
      } catch {
        setNotFound(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [userId]);

  const ctaSignup = () => {
    const code = teaser?.referral_code;
    const q = new URLSearchParams();
    if (code) q.set("ref", code);
    q.set("source", "twin");
    q.set("twin_id", userId);
    navigate(`/auth?${q.toString()}`);
  };

  if (loading) {
    return (
      <div className="crush-bg min-h-screen grid place-items-center">
        <div className="text-pink-600 font-display inline-flex items-center gap-2">
          <Loader2 className="w-5 h-5 animate-spin" /> Loading their face card…
        </div>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="crush-bg min-h-screen" data-testid="twin-not-found">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 pt-10 pb-16">
          <Link to="/"><LogoBadge /></Link>
          <div className="crush-frame mt-8 p-8 text-center">
            <Sticker kind="spark" size={64} className="mx-auto" />
            <h1 className="font-display text-4xl font-bold mt-3">Couldn't find that twin.</h1>
            <p className="font-body text-slate-600 mt-2">The link may have expired or been removed.</p>
            <Link to="/" className="crush-cta rounded-full font-display font-bold px-6 py-3 inline-flex items-center gap-2 mt-5">
              Take me home <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const t = teaser.user;
  const isChaos = t.mode === "chaos";

  return (
    <div className="crush-bg min-h-screen" data-testid="twin-page">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Link to="/"><LogoBadge /></Link>

        <div className="relative crush-frame mt-6 p-6 sm:p-10 overflow-hidden">
          <div className="pointer-events-none absolute inset-0" aria-hidden="true">
            <Sticker kind="heart" size={64} className="absolute top-6 right-6 -rotate-12 hidden md:inline-flex animate-floaty" />
            <Sticker kind="bolt" size={56} className="absolute top-1/2 left-4 rotate-12 hidden lg:inline-flex animate-wiggle" color="#8a5cf6" />
            <Sticker kind="spark" size={48} className="absolute bottom-8 right-10 hidden md:inline-flex animate-floaty" />
            <Scribble className="absolute top-12 left-1/3 w-28 hidden lg:block animate-wiggle" color="#ff5fa3" />
          </div>

          <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 items-center">
            {/* LEFT: teaser */}
            <div>
              <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full font-display font-bold text-xs uppercase tracking-widest ${isChaos ? "bg-orange-100 text-orange-700" : "bg-pink-100 text-pink-700"}`}>
                <Sparkles className="w-3 h-3" /> {isChaos ? "Chaos pick" : "Twin energy"}
              </div>
              <h1 className="font-display text-5xl sm:text-6xl font-bold leading-[0.95] mt-3">
                <span className="crush-sticker-text-dark">Could you be </span>
                <span className="crush-sticker-text crush-text-grad">{t.name}'s twin?</span>
              </h1>
              <p className="mt-4 font-body text-slate-700 text-lg max-w-md">
                {t.name} just dropped their DoppelCrush card.{" "}
                {isChaos
                  ? `They're in Chaos mode — totally opposite of their usual type. Are you the plot twist?`
                  : `Twin Energy mode is on — they're hunting for face-card siblings. Could be you.`}
              </p>

              <div className="mt-6 flex flex-wrap items-center gap-3">
                <button
                  onClick={ctaSignup}
                  className="crush-cta rounded-full font-display font-bold px-7 py-4 text-lg inline-flex items-center gap-2"
                  data-testid="twin-cta-signup"
                >
                  <Camera className="w-5 h-5" /> Find your DoppelCrush
                  <ArrowRight className="w-5 h-5" />
                </button>
                <button
                  onClick={() => navigate("/how-it-works")}
                  className="crush-secondary rounded-full font-display font-bold px-6 py-4 text-base"
                  data-testid="twin-how-btn"
                >
                  How it works
                </button>
              </div>

              <div className="mt-5 text-sm font-body text-slate-500 max-w-md">
                Sign up via this link and you and {t.name} get an instant
                friend-compare room — see who has the strongest Twin Energy.
              </div>
            </div>

            {/* RIGHT: photo card */}
            <div className="relative">
              <div className="relative w-full max-w-sm mx-auto">
                <div className="absolute -inset-4 bg-gradient-to-br from-pink-200 via-orange-100 to-pink-100 rounded-[40px] -rotate-3"></div>
                <div className="relative crush-window rotate-2">
                  <div className="crush-window-bar">
                    <span className="crush-window-dot bg-rose-400" />
                    <span className="crush-window-dot bg-amber-300" />
                    <span className="crush-window-dot bg-emerald-400" />
                  </div>
                  <div className="relative">
                    <img
                      src={t.photo_url}
                      alt={t.name}
                      className="w-full aspect-[4/5] object-cover"
                    />
                    {/* Soft blur teaser overlay */}
                    <div className="absolute inset-0 backdrop-blur-[2px] bg-gradient-to-t from-black/40 via-transparent to-transparent" />
                    <div className="absolute inset-x-0 bottom-0 p-5 text-white">
                      <div className="font-display text-3xl font-bold">{t.name}</div>
                      <div className="text-sm font-body opacity-90">
                        {[t.age_band && `${t.age_band}`, t.location].filter(Boolean).join(" · ")}
                      </div>
                      {t.bio ? <div className="text-xs font-body opacity-80 mt-1 line-clamp-2">{t.bio}</div> : null}
                    </div>
                    <div className="absolute top-3 left-3 inline-flex items-center gap-1 bg-white/90 rounded-full px-3 py-1 text-xs font-display font-bold text-pink-600">
                      <Heart className="w-3 h-3" fill="#ff2d8a" /> Their DoppelCrush
                    </div>
                  </div>
                </div>
                <Sticker kind="heart" size={64} className="absolute -top-6 -right-6 rotate-12 pointer-events-none" />
                <KawaiiHeart className="absolute -bottom-8 -left-6 w-20 pointer-events-none" />
              </div>
            </div>
          </div>
        </div>

        {/* Mini explainer */}
        <div className="mt-6 grid sm:grid-cols-3 gap-4">
          {[
            { icon: Camera, title: "Upload a selfie", body: "10 seconds. One face." },
            { icon: Heart, title: "We compare", body: "Twin Energy or Chaos contrast." },
            { icon: Sparkles, title: "Reveal together", body: `You'll get an instant compare room with ${t.name}.` },
          ].map((s) => (
            <div key={s.title} className="bg-white rounded-3xl p-5 border-2 border-pink-100">
              <s.icon className="w-6 h-6 text-pink-500" />
              <div className="font-display text-lg font-bold text-slate-900 mt-2">{s.title}</div>
              <div className="text-sm font-body text-slate-600">{s.body}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
