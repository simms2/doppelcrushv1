import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Copy, Gift, Users, Sparkles, Send, Share2, Trophy, Download, Instagram, AtSign } from "lucide-react";
import Header from "@/components/Header";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Sticker } from "@/components/Stickers";
import { generateShareCard, downloadBlob } from "@/lib/shareCard";

const REWARDS = [
  { thresh: 1, label: "Chaos Boost", desc: "Unlock a 24h Chaos boost", icon: Sparkles },
  { thresh: 3, label: "Friend Compare", desc: "Unlock group challenge", icon: Users },
  { thresh: 5, label: "Premium Reveals", desc: "See who liked you", icon: Trophy },
  { thresh: 10, label: "Early User Badge", desc: "Flex on your profile", icon: Gift },
];

export default function Invite() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [copied, setCopied] = useState(false);
  const [toast, setToast] = useState("");
  const [cardPreview, setCardPreview] = useState("");
  const cardBlobRef = useRef(null);

  useEffect(() => {
    api.get("/me/stats").then(({ data }) => setStats(data)).catch(() => {});
  }, []);

  const code = user?.referral_code || stats?.referral_code || "";

  const shareUrl = useMemo(() => {
    const base = window.location.origin;
    return `${base}/signup?ref=${code}&source=invite&mode=${user?.mode || "doppel"}`;
  }, [user, code]);

  const shareText = `Join me on DoppelCrush 💖 Find your twin or your chaos match. Use my code: ${code}`;
  const fullShare = `${shareText}\n${shareUrl}`;
  const encoded = encodeURIComponent(fullShare);

  // Build the card whenever code/url is ready
  useEffect(() => {
    let alive = true;
    if (!code) return;
    generateShareCard({ code, url: shareUrl }).then(({ blob, dataUrl }) => {
      if (!alive) return;
      cardBlobRef.current = blob;
      setCardPreview(dataUrl);
    }).catch(() => {});
    return () => { alive = false; };
  }, [code, shareUrl]);

  const flashToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2400);
  };

  const trackShare = (kind) => {
    api.post("/share", { kind }).catch(() => {});
  };

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      trackShare("invite");
      setTimeout(() => setCopied(false), 1800);
    } catch { /* clipboard blocked */ }
  };

  const onNative = async () => {
    try {
      // Try to share with the image file when supported
      const blob = cardBlobRef.current;
      if (blob && navigator.canShare) {
        const file = new File([blob], "doppelcrush-invite.png", { type: "image/png" });
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({ title: "DoppelCrush", text: shareText, url: shareUrl, files: [file] });
          trackShare("invite");
          return;
        }
      }
      if (navigator.share) {
        await navigator.share({ title: "DoppelCrush", text: shareText, url: shareUrl });
        trackShare("invite");
      } else {
        onCopy();
      }
    } catch { /* user cancelled */ }
  };

  const onDownload = () => {
    if (!cardBlobRef.current) return;
    downloadBlob(cardBlobRef.current, `doppelcrush-${(code || "card").toLowerCase()}.png`);
    trackShare("invite_card");
    flashToast("Card downloaded — drop it in your story 💖");
  };

  const onInstagram = async () => {
    // Instagram has no web share intent: best practice = download the card,
    // copy the caption, then open Instagram so the user can paste into a Story / DM / post.
    try {
      if (cardBlobRef.current) {
        downloadBlob(cardBlobRef.current, `doppelcrush-${(code || "card").toLowerCase()}.png`);
      }
      await navigator.clipboard.writeText(fullShare).catch(() => {});
      trackShare("instagram");
      flashToast("Card downloaded + caption copied. Opening Instagram…");
      setTimeout(() => {
        window.open("https://www.instagram.com/", "_blank", "noopener,noreferrer");
      }, 600);
    } catch { /* clipboard blocked */ }
  };

  const onThreads = () => {
    // Threads supports a web intent for posting text.
    const url = `https://www.threads.net/intent/post?text=${encoded}`;
    trackShare("threads");
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const friendsJoined = stats?.friends_joined ?? 0;
  const bonus = stats?.bonus_matches ?? 0;

  return (
    <div className="crush-bg min-h-screen" data-testid="invite-page">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />

        <div className="crush-frame mt-4 p-6 sm:p-10 relative overflow-hidden">
          <Sticker kind="heart" size={84} className="absolute -top-6 -right-4 rotate-12" />
          <Sticker kind="bolt" size={64} className="absolute top-10 left-4 -rotate-6 hidden md:inline-flex" color="#8a5cf6" />
          <Sticker kind="spark" size={52} className="absolute bottom-8 right-12 rotate-6 hidden md:inline-flex" />

          <div className="grid lg:grid-cols-2 gap-10 items-start">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-pink-100 text-pink-700 font-display font-bold text-xs uppercase tracking-widest">
                <Gift className="w-3 h-3" /> Invite friends
              </div>
              <h1 className="font-display text-5xl sm:text-6xl font-bold leading-[0.95] mt-3">
                <span className="crush-sticker-text crush-text-grad">Invite friends,</span><br />
                <span className="crush-sticker-text-dark">unlock chaos.</span>
              </h1>
              <p className="mt-5 text-slate-600 font-body text-lg max-w-md">
                Share your code. Every friend who joins unlocks bonus matches, Chaos boosts and friend-compare for both of you.
              </p>

              <div className="mt-6 grid grid-cols-2 gap-3">
                <div className="rounded-3xl p-5 bg-pink-50 border-2 border-pink-100">
                  <div className="font-display text-5xl font-bold text-pink-600" data-testid="invite-friends-joined">{friendsJoined}</div>
                  <div className="text-sm font-body text-slate-600 mt-1">Friends joined</div>
                </div>
                <div className="rounded-3xl p-5 bg-amber-50 border-2 border-amber-100">
                  <div className="font-display text-5xl font-bold text-amber-600" data-testid="invite-bonus-matches">{bonus}</div>
                  <div className="text-sm font-body text-slate-600 mt-1">Bonus matches</div>
                </div>
              </div>

              <div className="mt-6 space-y-2">
                {REWARDS.map((r) => {
                  const unlocked = friendsJoined >= r.thresh;
                  return (
                    <div
                      key={r.label}
                      className={`flex items-center gap-3 p-3 rounded-2xl border-2 ${unlocked ? "bg-emerald-50 border-emerald-200" : "bg-white border-slate-100"}`}
                      data-testid={`reward-${r.thresh}`}
                    >
                      <div className={`w-10 h-10 rounded-xl grid place-items-center ${unlocked ? "bg-emerald-200 text-emerald-800" : "bg-slate-100 text-slate-500"}`}>
                        <r.icon className="w-5 h-5" />
                      </div>
                      <div className="flex-1">
                        <div className="font-display font-bold text-slate-900">{r.label}</div>
                        <div className="text-xs font-body text-slate-600">{r.desc}</div>
                      </div>
                      <div className={`text-xs font-display font-bold ${unlocked ? "text-emerald-700" : "text-slate-400"}`}>
                        {unlocked ? "Unlocked" : `${r.thresh} friends`}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div>
              <div className="crush-frame p-6 sm:p-8 text-center bg-gradient-to-br from-white via-pink-50 to-orange-50">
                <div className="text-xs font-display font-bold uppercase tracking-widest text-slate-500">Your code</div>
                <div className="font-display text-5xl font-bold mt-2 crush-text-grad tracking-wider" data-testid="invite-code">
                  {code || "—"}
                </div>

                {/* Fun card preview */}
                <div className="mt-5 relative" data-testid="share-card-preview-wrap">
                  <div className="rounded-3xl overflow-hidden border-2 border-slate-900/10 shadow-lg shadow-pink-200 bg-white">
                    {cardPreview ? (
                      <img
                        src={cardPreview}
                        alt="Your DoppelCrush share card"
                        className="block w-full h-auto"
                        data-testid="share-card-preview"
                      />
                    ) : (
                      <div className="aspect-square w-full grid place-items-center bg-gradient-to-br from-yellow-100 via-pink-100 to-orange-100">
                        <div className="font-display font-bold text-slate-500 text-sm">Cooking up your card…</div>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={onDownload}
                    disabled={!cardPreview}
                    className="absolute top-3 right-3 crush-cta rounded-full px-3 py-1.5 text-xs font-display font-bold inline-flex items-center gap-1.5 disabled:opacity-50"
                    data-testid="share-card-download-btn"
                  >
                    <Download className="w-3.5 h-3.5" /> PNG
                  </button>
                </div>

                <div className="mt-5 flex items-center gap-2 bg-white rounded-full p-1.5 border-2 border-slate-100">
                  <input
                    value={shareUrl}
                    readOnly
                    className="flex-1 bg-transparent px-3 py-2 font-body text-sm truncate outline-none"
                    data-testid="invite-share-url"
                  />
                  <button
                    onClick={onCopy}
                    className="crush-cta rounded-full px-5 py-2 font-display font-bold text-sm inline-flex items-center gap-1.5"
                    data-testid="invite-copy-btn"
                  >
                    <Copy className="w-4 h-4" /> {copied ? "Copied" : "Copy"}
                  </button>
                </div>

                <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 gap-2">
                  <a
                    href={`https://wa.me/?text=${encoded}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="crush-secondary rounded-full py-2.5 font-display font-bold text-sm inline-flex items-center justify-center gap-1.5"
                    data-testid="share-whatsapp-btn"
                    onClick={() => trackShare("whatsapp")}
                  >
                    <Send className="w-4 h-4 text-emerald-600" /> WhatsApp
                  </a>
                  <a
                    href={`https://twitter.com/intent/tweet?text=${encoded}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="crush-secondary rounded-full py-2.5 font-display font-bold text-sm inline-flex items-center justify-center gap-1.5"
                    data-testid="share-x-btn"
                    onClick={() => trackShare("x")}
                  >
                    <span className="font-display">𝕏</span> Post
                  </a>
                  <button
                    type="button"
                    onClick={onInstagram}
                    className="crush-secondary rounded-full py-2.5 font-display font-bold text-sm inline-flex items-center justify-center gap-1.5"
                    data-testid="share-instagram-btn"
                  >
                    <Instagram className="w-4 h-4 text-pink-600" /> Instagram
                  </button>
                  <button
                    type="button"
                    onClick={onThreads}
                    className="crush-secondary rounded-full py-2.5 font-display font-bold text-sm inline-flex items-center justify-center gap-1.5"
                    data-testid="share-threads-btn"
                  >
                    <AtSign className="w-4 h-4 text-slate-900" /> Threads
                  </button>
                  <button
                    onClick={onNative}
                    className="crush-cta rounded-full py-2.5 font-display font-bold text-sm inline-flex items-center justify-center gap-1.5 col-span-2 sm:col-span-1"
                    data-testid="share-native-btn"
                  >
                    <Share2 className="w-4 h-4" /> Share
                  </button>
                </div>

                <p className="mt-4 text-[11px] font-body text-slate-500">
                  Instagram doesn&apos;t allow direct web posting — we&apos;ll download the card and copy the caption so you can paste it into your Story or DM.
                </p>
              </div>

              <Link
                to="/compare"
                className="mt-4 block crush-frame p-5 hover:scale-[1.02] transition-transform"
                data-testid="compare-cta-card"
              >
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-2xl bg-purple-100 text-purple-700 grid place-items-center">
                    <Users className="w-6 h-6" />
                  </div>
                  <div className="flex-1">
                    <div className="font-display text-lg font-bold text-slate-900">Compare with friends</div>
                    <div className="text-xs font-body text-slate-600">Start a group challenge — strongest twin pair wins.</div>
                  </div>
                  <span className="text-pink-600 font-bold font-display">→</span>
                </div>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {toast ? (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-full bg-slate-900 text-white font-display font-bold text-sm shadow-xl shadow-pink-300/40"
          data-testid="share-toast"
        >
          {toast}
        </div>
      ) : null}
    </div>
  );
}
