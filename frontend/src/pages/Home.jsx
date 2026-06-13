import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Camera, Zap, Heart, MessageCircle, ArrowRight } from "lucide-react";
import Header from "@/components/Header";
import LivePreview from "@/components/LivePreview";
import { KawaiiHeart, Sticker, Scribble } from "@/components/Stickers";
import { useAuth } from "@/contexts/AuthContext";

export default function Home() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [params] = useSearchParams();
  const ref = params.get("ref");

  const startCTA = () => {
    if (user?.onboarding_complete) navigate("/discover");
    else if (user) navigate("/onboarding");
    else navigate(`/auth${ref ? `?ref=${ref}` : ""}`);
  };

  return (
    <div className="crush-bg" data-testid="home-page">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />

        {/* HERO */}
        <section className="relative crush-frame mt-4 p-6 sm:p-10 lg:p-12 overflow-hidden">
          {/* Decorative stickers — placed in safe gutters, never over text/CTAs */}
          <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
            {/* top-right corner of hero panel */}
            <Sticker kind="star" size={56} className="absolute top-4 right-6 -rotate-12 hidden md:inline-flex animate-floaty" />
            {/* gutter between left column and right column on large screens */}
            <Sticker kind="bolt" size={56} className="absolute top-1/3 left-[58%] rotate-12 hidden xl:inline-flex animate-wiggle" color="#ff7a3d" />
            <Scribble className="absolute top-6 left-[55%] w-24 hidden xl:block animate-wiggle" color="#ff5fa3" />
            {/* bottom-left empty space below the value-prop chips */}
            <Sticker kind="spark" size={44} className="absolute bottom-6 left-8 -rotate-6 hidden lg:inline-flex animate-floaty" />
            {/* small wisp on far-right edge between hero and frame */}
            <Sticker kind="flame" size={56} className="absolute -bottom-2 right-2 rotate-6 hidden md:inline-flex animate-floaty" />
          </div>

          <div className="grid lg:grid-cols-12 gap-8 lg:gap-10 items-start relative">
            {/* LEFT: copy + CTAs */}
            <div className="lg:col-span-7 relative">
              <div className="crush-tag-pill mb-5 font-display">
                <Camera className="w-4 h-4" />
                Selfie first. Crush later.
              </div>

              <h1 className="font-display text-6xl sm:text-7xl lg:text-[5.5rem] xl:text-[6.5rem] font-bold leading-[0.92] text-slate-900 relative z-10">
                <span className="crush-sticker-text-dark">Find your</span>
                <span className="inline-block align-middle w-14 sm:w-16 lg:w-20 ml-2 -mt-3 animate-floaty" aria-hidden="true">
                  <KawaiiHeart />
                </span>
                <br />
                <span className="crush-sticker-text crush-text-grad">DoppelCrush</span>
              </h1>

              <p className="mt-8 text-lg sm:text-xl text-slate-700 max-w-xl font-body leading-relaxed relative z-10">
                Ever wondered why so many couples look alike?
                <br className="hidden sm:block" />
                Wonder no more and find your DoppelCrush.
                <br className="hidden sm:block" />
                Upload your selfie and <span className="underline decoration-pink-400 decoration-4 underline-offset-2 font-semibold">we'll do the rest</span>.
              </p>

              <div className="mt-8 flex flex-wrap items-center gap-3 sm:gap-4">
                <button
                  onClick={startCTA}
                  className="crush-cta rounded-full font-display font-bold px-7 py-4 text-lg sm:text-xl inline-flex items-center gap-3"
                  data-testid="hero-upload-selfie-btn"
                >
                  <Camera className="w-5 h-5" /> Upload my selfie <ArrowRight className="w-5 h-5" />
                </button>
                <button
                  onClick={() => navigate(user ? "/discover?mode=chaos" : `/auth?mode=chaos${ref ? `&ref=${ref}` : ""}`)}
                  className="crush-secondary rounded-full font-display font-bold px-7 py-4 text-lg sm:text-xl inline-flex items-center gap-3"
                  data-testid="hero-chaos-mode-btn"
                >
                  <Zap className="w-5 h-5 text-purple-600" /> Chaos Mode
                </button>
              </div>

              {/* mini value props */}
              <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-2xl">
                {[
                  { icon: Camera, title: "Upload selfie", sub: "Face card only" },
                  { icon: Heart, title: "Get matches", sub: "Cute people, similar vibe" },
                  { icon: MessageCircle, title: "Start chatting", sub: "If it's a match" },
                ].map((v) => (
                  <div key={v.title} className="bg-white rounded-2xl border-2 border-white shadow-md p-4 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-pink-100 text-pink-600 grid place-items-center">
                      <v.icon className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="font-display font-bold text-slate-900">{v.title}</div>
                      <div className="text-xs text-slate-500 font-body">{v.sub}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* RIGHT: live preview */}
            <div className="lg:col-span-5">
              <LivePreview />
            </div>
          </div>
        </section>

        {/* Lower cards: Twin Energy + Chaos Mode */}
        <section className="grid md:grid-cols-2 gap-6 mt-6">
          {/* Twin Energy */}
          <div className="relative crush-frame p-7 sm:p-9 overflow-hidden bg-gradient-to-br from-pink-50 via-white to-pink-100">
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-purple-200 text-purple-800 text-xs font-bold border-2 border-purple-300 font-display">
              Twin Energy
            </span>
            <div className="grid grid-cols-3 gap-4 mt-4 items-end">
              <div className="col-span-2">
                <h2 className="font-display text-3xl sm:text-4xl font-bold text-slate-900 leading-tight">
                  Cute, familiar,<br />iconic.
                </h2>
                <p className="mt-3 text-slate-600 font-body">
                  Discover people who look like your mirror — familiar faces, matching energy, and instant twin vibes.
                </p>
              </div>
              <div className="relative">
                <Sticker kind="heart" size={108} className="absolute -bottom-2 -left-6 -rotate-12" />
                <div className="bg-white rounded-2xl p-2 rotate-3 shadow-lg border-2 border-pink-100">
                  <img
                    src="https://images.unsplash.com/photo-1494774157365-9e04c6720e47?w=600&q=85"
                    alt="Twin duo"
                    className="w-full h-32 sm:h-36 object-cover rounded-xl"
                  />
                  <div className="text-center text-xs font-display font-bold text-pink-600 mt-1">
                    You, but make it us.
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Chaos Mode */}
          <div className="relative crush-frame p-7 sm:p-9 overflow-hidden bg-gradient-to-br from-orange-50 via-white to-amber-100">
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-orange-200 text-orange-900 text-xs font-bold border-2 border-orange-300 font-display">
              Chaos Mode
            </span>
            <h2 className="font-display text-3xl sm:text-4xl font-bold text-slate-900 leading-tight mt-4">
              Plot twist energy.
            </h2>
            <p className="mt-3 text-slate-600 font-body max-w-md">
              Go for the total opposite when your usual type needs a little <span className="underline decoration-orange-400 decoration-4 font-semibold">shake-up</span>.
            </p>
            <Sticker kind="bolt" size={96} className="absolute bottom-4 right-6 rotate-12" color="#ff7a3d" />
            <Sticker kind="flame" size={64} className="absolute top-6 right-10 -rotate-12" />
          </div>
        </section>

        {/* Viral growth band */}
        <section className="mt-6 grid md:grid-cols-2 gap-6">
          <Link to={user ? "/invite" : "/auth"} className="crush-frame p-6 sm:p-8 relative overflow-hidden hover:scale-[1.01] transition-transform bg-gradient-to-br from-pink-50 via-white to-orange-50" data-testid="home-invite-card">
            <Sticker kind="heart" size={64} className="absolute top-4 right-4 rotate-12" />
            <div className="text-xs font-display font-bold uppercase tracking-widest text-pink-600">Invite friends</div>
            <h3 className="font-display text-3xl sm:text-4xl font-bold text-slate-900 mt-2">Unlock chaos boosts.</h3>
            <p className="font-body text-slate-600 mt-2 max-w-md">Every friend who joins via your link gets you a bonus match + a Chaos boost.</p>
            <div className="mt-4 inline-flex items-center gap-2 text-pink-600 font-display font-bold">Get my code →</div>
          </Link>
          <Link to={user ? "/compare" : "/auth"} className="crush-frame p-6 sm:p-8 relative overflow-hidden hover:scale-[1.01] transition-transform bg-gradient-to-br from-purple-50 via-white to-pink-50" data-testid="home-compare-card">
            <Sticker kind="bolt" size={64} className="absolute top-4 right-4 rotate-12" color="#8a5cf6" />
            <div className="text-xs font-display font-bold uppercase tracking-widest text-purple-700">Group challenge</div>
            <h3 className="font-display text-3xl sm:text-4xl font-bold text-slate-900 mt-2">Compare with friends.</h3>
            <p className="font-body text-slate-600 mt-2 max-w-md">Who has the strongest Doppel? Who gets the wildest Chaos? Settle it in the group chat.</p>
            <div className="mt-4 inline-flex items-center gap-2 text-purple-700 font-display font-bold">Start a room →</div>
          </Link>
        </section>

        {/* Bottom band */}
        <section className="mt-10 text-center">
          <p className="font-display text-2xl text-slate-700">
            <span className="crush-text-grad font-bold">Ready?</span> Selfie first, crush later.
          </p>
          <button
            onClick={startCTA}
            className="crush-cta mt-4 rounded-full font-display font-bold px-8 py-4 text-lg inline-flex items-center gap-2"
            data-testid="bottom-cta-btn"
          >
            Get started <ArrowRight className="w-5 h-5" />
          </button>
          <div className="mt-6 text-sm text-slate-500">
            <Link to="/how-it-works" className="hover:text-pink-600 mx-2">How it works</Link>·
            <Link to="/safety" className="hover:text-pink-600 mx-2">Safety</Link>·
            <Link to="/faq" className="hover:text-pink-600 mx-2">FAQ</Link>
          </div>
        </section>
      </div>
    </div>
  );
}
