import { useEffect, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Heart, X, Zap, Share2 } from "lucide-react";
import Header from "@/components/Header";
import { useAuth } from "@/contexts/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { Sticker } from "@/components/Stickers";

const ModePill = ({ mode, onChange }) => (
  <div className="inline-flex items-center bg-white rounded-full p-1 border-2 border-slate-200 shadow-sm">
    {["doppel", "chaos"].map((m) => (
      <button
        key={m}
        onClick={() => onChange(m)}
        className={`px-4 py-2 rounded-full font-display font-bold text-sm capitalize ${
          mode === m ? "crush-cta" : "text-slate-600"
        }`}
        data-testid={`mode-toggle-${m}`}
      >
        {m === "doppel" ? "Twin Energy" : "Chaos"}
      </button>
    ))}
  </div>
);

export default function Discover() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const initialMode = params.get("mode") === "chaos" ? "chaos" : user?.mode || "doppel";
  const [mode, setMode] = useState(initialMode);
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastMatch, setLastMatch] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get(`/discover?mode=${mode}`);
      setCards(data.results || []);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => { load(); }, [load]);

  const switchMode = async (next) => {
    setMode(next);
    try {
      await api.patch("/me/mode", { mode: next });
      setUser({ ...user, mode: next });
    } catch {}
  };

  const swipe = async (direction) => {
    const top = cards[0];
    if (!top) return;
    setCards((c) => c.slice(1));
    try {
      const { data } = await api.post("/swipe", { target_id: top.id, direction });
      if (data.match) {
        setLastMatch({ ...top, match_id: data.match_id });
      }
    } catch (err) {
      setError(formatApiError(err));
    }
  };

  const top = cards[0];

  return (
    <div className="crush-bg min-h-screen" data-testid="discover-page">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />

        <div className="crush-frame p-5 sm:p-8 mt-4 relative overflow-hidden">
          <Sticker kind="heart" size={64} className="absolute -top-6 -right-4 rotate-12 hidden md:inline-flex" />
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h1 className="font-display text-3xl sm:text-4xl font-bold text-slate-900">Discover</h1>
              <p className="text-slate-600 font-body text-sm">Pick. Pass. Plot twist.</p>
            </div>
            <ModePill mode={mode} onChange={switchMode} />
          </div>

          <div className="mt-6 grid lg:grid-cols-12 gap-6">
            {/* Card stack */}
            <div className="lg:col-span-7 relative min-h-[520px]" data-testid="card-stack">
              {loading ? (
                <div className="absolute inset-0 grid place-items-center text-pink-600 font-display text-xl">Loading crushes…</div>
              ) : !top ? (
                <div className="absolute inset-0 grid place-items-center text-center text-slate-500 font-body">
                  <div>
                    <Sticker kind="spark" size={72} className="mx-auto" />
                    <p className="mt-3">You hit the end of the feed. Try the other mode!</p>
                  </div>
                </div>
              ) : (
                <AnimatePresence>
                  {cards.slice(0, 3).reverse().map((c, idx) => {
                    const isTop = idx === cards.slice(0, 3).length - 1;
                    return (
                      <motion.div
                        key={c.id}
                        initial={{ y: 30, opacity: 0, scale: 0.95 }}
                        animate={{ y: idx * -8, opacity: 1, scale: 1 - (cards.slice(0, 3).length - 1 - idx) * 0.04 }}
                        exit={{ x: 300, opacity: 0, rotate: 12 }}
                        transition={{ type: "spring", stiffness: 200, damping: 24 }}
                        className="absolute inset-0"
                        style={{ zIndex: idx }}
                      >
                        <div className="crush-window h-full">
                          <div className="relative h-full">
                            <img src={c.photo_url} alt={c.name} className="w-full h-full object-cover" />
                            <div className="absolute inset-x-0 bottom-0 p-5 bg-gradient-to-t from-black/80 via-black/30 to-transparent text-white">
                              <div className="flex items-center gap-2 mb-2">
                                <span className={`px-3 py-1 rounded-full text-xs font-bold font-display ${
                                  mode === "doppel" ? "bg-pink-200 text-pink-800" : "bg-orange-200 text-orange-800"
                                }`}>
                                  {mode === "doppel" ? `Twin Energy ${c.score}%` : `Chaos ${c.score}%`}
                                </span>
                                {c.location ? <span className="text-xs font-body opacity-80">{c.location}</span> : null}
                              </div>
                              <h2 className="font-display text-3xl font-bold leading-tight">{c.name}, {c.age}</h2>
                              {c.bio ? <p className="font-body text-sm mt-1 opacity-90">{c.bio}</p> : null}
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              )}
            </div>

            {/* Side actions */}
            <div className="lg:col-span-5 space-y-4">
              <div className="bg-white rounded-3xl p-5 border-2 border-pink-100">
                <div className="text-xs font-display font-bold uppercase tracking-widest text-slate-500">Up next</div>
                <div className="mt-2 flex -space-x-3">
                  {cards.slice(1, 6).map((c) => (
                    <img key={c.id} src={c.photo_url} alt={c.name} className="w-12 h-12 rounded-full object-cover border-2 border-white" />
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3 justify-center">
                <button
                  onClick={() => swipe("pass")}
                  className="w-16 h-16 rounded-full bg-white border-2 border-slate-200 grid place-items-center shadow hover:scale-110 transition-transform"
                  data-testid="pass-btn"
                  aria-label="Pass"
                >
                  <X className="w-7 h-7 text-slate-700" />
                </button>
                <button
                  onClick={() => swipe("like")}
                  className="crush-cta w-20 h-20 rounded-full grid place-items-center hover:scale-110 transition-transform"
                  data-testid="into-it-btn"
                  aria-label="Into it"
                >
                  <Heart className="w-9 h-9" fill="#fff" />
                </button>
              </div>

              <div className="bg-white rounded-3xl p-5 border-2 border-orange-100">
                <div className="flex items-center gap-2 text-orange-600 font-display font-bold">
                  <Zap className="w-4 h-4" /> Need a shake-up?
                </div>
                <p className="text-sm font-body text-slate-600 mt-1">Switch to {mode === "doppel" ? "Chaos" : "Twin Energy"} for a different vibe.</p>
                <button
                  className="crush-secondary rounded-full font-display font-bold mt-3 px-5 py-2"
                  onClick={() => switchMode(mode === "doppel" ? "chaos" : "doppel")}
                  data-testid="switch-mode-btn"
                >
                  Try {mode === "doppel" ? "Chaos" : "Twin Energy"}
                </button>
              </div>
            </div>
          </div>

          {error ? <div className="mt-4 text-sm text-rose-600 font-body">{error}</div> : null}
        </div>
      </div>

      {/* Match modal */}
      <AnimatePresence>
        {lastMatch ? (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm grid place-items-center z-50 p-4"
            data-testid="match-modal"
          >
            <motion.div
              initial={{ scale: 0.85, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.9 }}
              className="crush-frame max-w-md w-full p-8 text-center relative"
            >
              <Sticker kind="heart" size={80} className="absolute -top-10 left-1/2 -translate-x-1/2" />
              <h2 className="font-display text-5xl crush-text-grad font-bold mt-6">It's a match!</h2>
              <div className="mt-5 flex items-center justify-center gap-4">
                <img src={user?.photo_url || "https://images.unsplash.com/photo-1607746882042-944635dfe10e?w=200&q=80"} alt="You" className="w-24 h-24 rounded-full object-cover border-4 border-pink-300" />
                <Heart className="w-10 h-10 text-pink-500" fill="#ff2d8a" />
                <img src={lastMatch.photo_url} alt={lastMatch.name} className="w-24 h-24 rounded-full object-cover border-4 border-orange-300" />
              </div>
              <p className="font-display text-2xl mt-4 text-slate-900">You and {lastMatch.name} are into it.</p>
              <div className="mt-6 flex flex-col gap-2">
                <button
                  onClick={() => { setLastMatch(null); navigate(`/chat/${lastMatch.match_id}`); }}
                  className="crush-cta rounded-full font-display font-bold py-3"
                  data-testid="match-message-btn"
                >Message them</button>
                <button
                  onClick={async () => {
                    try { await api.post("/share", { kind: "match_card", target_id: lastMatch.id }); } catch {}
                    navigate(`/match/${lastMatch.id}`);
                  }}
                  className="crush-secondary rounded-full font-display font-bold py-3 inline-flex items-center justify-center gap-2"
                  data-testid="match-share-btn"
                >
                  <Share2 className="w-4 h-4" /> Share the reveal
                </button>
                <button
                  onClick={() => setLastMatch(null)}
                  className="text-slate-500 font-body text-sm mt-2 hover:text-slate-700"
                  data-testid="match-close-btn"
                >Keep swiping</button>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
