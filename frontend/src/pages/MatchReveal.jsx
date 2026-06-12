import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Share2, Copy, ArrowLeft } from "lucide-react";
import Header from "@/components/Header";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Sticker } from "@/components/Stickers";

export default function MatchReveal() {
  const { matchId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [matches, setMatches] = useState([]);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get("/matches").then(({ data }) => setMatches(data)).catch(() => {});
  }, []);

  const target = useMemo(() => {
    const m = matches.find((x) => x.profile?.id === matchId);
    return m?.profile;
  }, [matches, matchId]);

  const shareUrl = useMemo(() => {
    const base = window.location.origin;
    return `${base}/signup?ref=${user?.referral_code || ""}&source=share_card&mode=${user?.mode || "doppel"}`;
  }, [user]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      api.post("/share", { kind: "reveal_card", target_id: matchId }).catch(() => {});
      setTimeout(() => setCopied(false), 1800);
    } catch {}
  };

  return (
    <div className="crush-bg min-h-screen" data-testid="match-reveal-page">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />

        <button onClick={() => navigate(-1)} className="mt-2 inline-flex items-center gap-1 text-slate-600 font-body hover:text-pink-600" data-testid="back-btn">
          <ArrowLeft className="w-4 h-4" /> Back
        </button>

        <div className="crush-frame mt-3 p-6 sm:p-10 text-center relative overflow-hidden">
          <Sticker kind="heart" size={96} className="absolute -top-10 left-1/2 -translate-x-1/2" />
          <Sticker kind="spark" size={64} className="absolute top-6 right-6 rotate-12" />
          <Sticker kind="bolt" size={64} className="absolute bottom-6 left-6 -rotate-12" color="#8a5cf6" />

          <h1 className="font-display text-5xl sm:text-6xl crush-text-grad font-bold mt-8">It's a match!</h1>
          {target ? (
            <>
              <div className="mt-6 flex items-center justify-center gap-4">
                <img src={user?.photo_url || "https://images.unsplash.com/photo-1607746882042-944635dfe10e?w=200&q=80"} alt="you" className="w-28 h-28 rounded-full object-cover border-4 border-pink-300" />
                <div className="font-display text-3xl text-pink-500">+</div>
                <img src={target.photo_url} alt={target.name} className="w-28 h-28 rounded-full object-cover border-4 border-orange-300" />
              </div>
              <p className="font-display text-2xl mt-4 text-slate-900">You and {target.name} are into it.</p>
            </>
          ) : (
            <p className="font-body text-slate-600 mt-4">That match isn't loaded — head back to <Link to="/discover" className="text-pink-600 font-bold">Discover</Link>.</p>
          )}

          <div className="mt-8 bg-slate-50 rounded-2xl p-4 border-2 border-slate-100">
            <div className="text-xs font-display font-bold uppercase text-slate-500 tracking-widest">Your share link</div>
            <div className="mt-2 flex items-center gap-2">
              <input
                value={shareUrl}
                readOnly
                className="flex-1 bg-white rounded-xl border-2 border-slate-200 px-3 py-2 font-body text-sm"
                data-testid="share-url-input"
              />
              <button onClick={copy} className="crush-cta rounded-full px-4 py-2 font-display font-bold inline-flex items-center gap-2" data-testid="copy-share-btn">
                <Copy className="w-4 h-4" /> {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-2 font-body">Invite friends to compare and you both get extra daily matches.</p>
          </div>

          <button
            onClick={() => navigate("/discover")}
            className="crush-secondary rounded-full font-display font-bold px-6 py-3 mt-6"
            data-testid="keep-swiping-btn"
          >
            Keep swiping
          </button>
        </div>
      </div>
    </div>
  );
}
