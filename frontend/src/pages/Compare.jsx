import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Copy, Users, Crown, Zap, Sparkles, Loader2 } from "lucide-react";
import Header from "@/components/Header";
import { api, formatApiError } from "@/lib/api";
import { Sticker } from "@/components/Stickers";

function PairCard({ pair, title, accent, icon: Icon }) {
  if (!pair) return null;
  return (
    <div className={`crush-frame p-5 ${accent}`}>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-9 h-9 rounded-xl bg-white/70 grid place-items-center">
          <Icon className="w-5 h-5" />
        </div>
        <div className="font-display font-bold text-sm uppercase tracking-widest">{title}</div>
      </div>
      <div className="flex items-center gap-3">
        <img src={pair.a.photo_url} alt={pair.a.name} className="w-20 h-20 rounded-2xl object-cover border-2 border-white shadow" />
        <div className="font-display text-3xl crush-text-grad font-bold">×</div>
        <img src={pair.b.photo_url} alt={pair.b.name} className="w-20 h-20 rounded-2xl object-cover border-2 border-white shadow" />
        <div className="ml-auto text-right">
          <div className="font-display text-3xl font-bold text-slate-900">{pair.score}%</div>
          <div className="text-xs font-body text-slate-500">{pair.a.name} & {pair.b.name}</div>
        </div>
      </div>
    </div>
  );
}

export default function Compare() {
  const { roomId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [room, setRoom] = useState(null);
  const [copied, setCopied] = useState(false);

  const shareUrl = useMemo(() => {
    if (!room?.id) return "";
    return `${window.location.origin}/compare/${room.id}`;
  }, [room]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        if (roomId) {
          const { data } = await api.get(`/compare/${roomId}`);
          if (!cancelled) setRoom(data);
        } else {
          const { data } = await api.post("/compare", { title: "Who has the strongest Doppel?" });
          if (!cancelled) {
            navigate(`/compare/${data.id}`, { replace: true });
          }
        }
      } catch (err) {
        setError(formatApiError(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    const interval = roomId ? setInterval(async () => {
      try {
        const { data } = await api.get(`/compare/${roomId}`);
        if (!cancelled) setRoom(data);
      } catch {}
    }, 5000) : null;
    return () => { cancelled = true; if (interval) clearInterval(interval); };
  }, [roomId, navigate]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  return (
    <div className="crush-bg min-h-screen" data-testid="compare-page">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />

        <div className="crush-frame mt-4 p-6 sm:p-10 relative overflow-hidden">
          <Sticker kind="bolt" size={64} className="absolute -top-6 -right-4 rotate-12" color="#8a5cf6" />
          <Sticker kind="spark" size={56} className="absolute bottom-8 left-4 -rotate-6 hidden md:inline-flex" />

          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-purple-100 text-purple-700 font-display font-bold text-xs uppercase tracking-widest">
            <Users className="w-3 h-3" /> Group challenge
          </div>
          <h1 className="font-display text-5xl sm:text-6xl font-bold leading-[0.95] mt-3">
            <span className="crush-sticker-text-dark">Who has the </span>
            <span className="crush-sticker-text crush-text-grad">strongest Doppel?</span>
          </h1>
          <p className="mt-4 text-slate-600 font-body text-lg max-w-2xl">
            Send this link to your group chat. When friends join, we rank pairs by Twin Energy, Chaos contrast and the funniest mismatch.
          </p>

          {loading ? (
            <div className="mt-10 text-center text-pink-600 font-display inline-flex items-center gap-2">
              <Loader2 className="w-5 h-5 animate-spin" /> Spinning up the room…
            </div>
          ) : error ? (
            <div className="mt-6 text-rose-600 font-body" data-testid="compare-error">{error}</div>
          ) : room ? (
            <>
              {/* Share link */}
              <div className="mt-6 max-w-2xl flex items-center gap-2 bg-white rounded-full p-1.5 border-2 border-slate-100">
                <input
                  value={shareUrl}
                  readOnly
                  className="flex-1 bg-transparent px-3 py-2 font-body text-sm truncate outline-none"
                  data-testid="compare-share-url"
                />
                <button
                  onClick={copy}
                  className="crush-cta rounded-full px-5 py-2 font-display font-bold text-sm inline-flex items-center gap-1.5"
                  data-testid="compare-copy-btn"
                >
                  <Copy className="w-4 h-4" /> {copied ? "Copied" : "Copy"}
                </button>
              </div>

              {/* Participants */}
              <div className="mt-6">
                <div className="text-xs font-display font-bold uppercase tracking-widest text-slate-500">
                  In the room ({room.participant_count})
                </div>
                <div className="mt-2 flex -space-x-3" data-testid="compare-participants">
                  {room.participants.map((p) => (
                    <img
                      key={p.id}
                      src={p.photo_url}
                      alt={p.name}
                      title={p.name}
                      className="w-14 h-14 rounded-full object-cover border-2 border-white shadow"
                    />
                  ))}
                  {room.participant_count === 1 ? (
                    <div className="ml-3 font-body text-sm text-slate-500 self-center">Waiting for friends to join…</div>
                  ) : null}
                </div>
              </div>

              {/* Results */}
              {room.pairs && room.pairs.length > 0 ? (
                <div className="mt-8 grid md:grid-cols-2 gap-4">
                  <PairCard
                    pair={room.strongest_twin}
                    title="Strongest twin pair"
                    accent="bg-gradient-to-br from-pink-50 to-white"
                    icon={Crown}
                  />
                  <PairCard
                    pair={room.chaos_contrast}
                    title="Chaos contrast"
                    accent="bg-gradient-to-br from-orange-50 to-white"
                    icon={Zap}
                  />
                  <PairCard
                    pair={room.funniest_mismatch}
                    title="Funniest mismatch"
                    accent="bg-gradient-to-br from-purple-50 to-white"
                    icon={Sparkles}
                  />
                  <div className="crush-frame p-5 bg-gradient-to-br from-amber-50 to-white">
                    <div className="font-display font-bold text-sm uppercase tracking-widest mb-3">All pairs</div>
                    <ul className="space-y-2 max-h-48 overflow-y-auto pr-1">
                      {room.pairs.map((p, i) => (
                        <li key={i} className="flex items-center gap-2 text-sm font-body">
                          <img src={p.a.photo_url} alt={p.a.name} className="w-7 h-7 rounded-full object-cover" />
                          <img src={p.b.photo_url} alt={p.b.name} className="w-7 h-7 rounded-full object-cover" />
                          <span className="flex-1 text-slate-700">{p.a.name} × {p.b.name}</span>
                          <span className="font-display font-bold text-pink-600">{p.score}%</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : (
                <div className="mt-10 text-center text-slate-500 font-body">
                  Share the link above with at least one friend to see results.
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
