import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Camera,
  Check,
  Loader2,
  AlertTriangle,
  LogOut,
  Save,
  Trash2,
  ShieldAlert,
  Copy,
  Share2,
} from "lucide-react";
import Header from "@/components/Header";
import { useAuth } from "@/contexts/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { fileToImage, validateSelfie, loadFaceModels, MODEL_VERSION } from "@/lib/face";
import { Sticker } from "@/components/Stickers";

export default function Profile() {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();
  const fileRef = useRef();

  const [name, setName] = useState(user?.name || "");
  const [bio, setBio] = useState(user?.bio || "");
  const [location, setLocation] = useState(user?.location || "");
  const [mode, setMode] = useState(user?.mode || "doppel");
  const [lookingFor, setLookingFor] = useState(user?.looking_for || "everyone");
  const [photoUrl, setPhotoUrl] = useState(user?.photo_url || "");
  const [newEmbedding, setNewEmbedding] = useState(null);
  const [newQuality, setNewQuality] = useState(null);

  const [faceStatus, setFaceStatus] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [showDelete, setShowDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [twinCopied, setTwinCopied] = useState(false);

  const currentQuality = newQuality ?? user?.embedding_quality ?? 0.6;
  const qualityPct = Math.round(currentQuality * 100);
  const twinUrl = user?.id
    ? `${process.env.REACT_APP_BACKEND_URL}/api/share/twin-page/${user.id}`
    : "";

  useEffect(() => {
    loadFaceModels().catch(() => {});
  }, []);

  const handleFile = async (file) => {
    if (!file) return;
    setError("");
    setFaceStatus("loading");
    try {
      const { img } = await fileToImage(file);
      await new Promise((r) => (img.complete ? r() : (img.onload = r)));
      const v = await validateSelfie(img);
      if (!v.ok) { setFaceStatus("no_face"); setError(v.message); return; }
      const form = new FormData();
      form.append("file", file, file.name || "selfie.jpg");
      const { data } = await api.post("/upload/selfie", form, { headers: { "Content-Type": "multipart/form-data" } });
      const absolute = data.url.startsWith("http") ? data.url : `${process.env.REACT_APP_BACKEND_URL}${data.url}`;
      setPhotoUrl(absolute);
      setNewEmbedding(v.embedding);
      setNewQuality(v.quality_score);
      setFaceStatus("ok");
    } catch {
      setFaceStatus("no_face"); setError("Couldn't upload that photo.");
    }
  };

  const save = async () => {
    setSaving(true); setError("");
    try {
      const body = { name, bio, location, mode, looking_for: lookingFor };
      if (photoUrl && photoUrl !== user?.photo_url) body.photo_url = photoUrl;
      if (newEmbedding) {
        body.embedding = newEmbedding;
        body.embedding_quality = newQuality ?? 0.6;
        body.embedding_model = MODEL_VERSION;
      }
      const { data } = await api.patch("/me", body);
      setUser(data);
      setSavedAt(Date.now());
      setTimeout(() => setSavedAt(null), 1800);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const deleteAccount = async () => {
    setDeleting(true); setError("");
    try {
      await api.delete("/me");
      logout();
      navigate("/");
    } catch (err) {
      setError(formatApiError(err));
      setDeleting(false);
    }
  };

  const copyTwinUrl = async () => {
    try {
      await navigator.clipboard.writeText(twinUrl);
      setTwinCopied(true);
      api.post("/share", { kind: "invite" }).catch(() => {});
      setTimeout(() => setTwinCopied(false), 1800);
    } catch {}
  };

  const shareTwinNative = async () => {
    try {
      if (navigator.share) {
        await navigator.share({
          title: "DoppelCrush",
          text: "Could you be my DoppelCrush twin? Try it →",
          url: twinUrl,
        });
        api.post("/share", { kind: "invite" }).catch(() => {});
      } else {
        copyTwinUrl();
      }
    } catch {}
  };

  return (
    <div className="crush-bg min-h-screen" data-testid="profile-page">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />

        <div className="crush-frame mt-4 p-6 sm:p-10 relative overflow-hidden">
          <div className="pointer-events-none" aria-hidden="true">
            <Sticker kind="heart" size={56} className="absolute -top-4 -right-2 rotate-12 hidden md:inline-flex" />
          </div>

          <h1 className="font-display text-5xl font-bold leading-[0.95]">
            <span className="crush-sticker-text-dark">Your </span>
            <span className="crush-sticker-text crush-text-grad">profile</span>
          </h1>
          <p className="mt-2 text-slate-600 font-body">Update your face card, vibe and who you want to see.</p>

          <div className="mt-8 grid md:grid-cols-3 gap-6 items-start">
            {/* LEFT: Selfie + quality */}
            <div>
              <div className="aspect-square rounded-3xl overflow-hidden bg-pink-50 border-4 border-pink-100 grid place-items-center">
                {photoUrl ? (
                  <img src={photoUrl} alt="selfie" className="w-full h-full object-cover" />
                ) : (
                  <Camera className="w-10 h-10 text-pink-400" />
                )}
              </div>
              <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => handleFile(e.target.files?.[0])} data-testid="profile-file-input" />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="crush-cta rounded-full font-display font-bold px-5 py-2.5 mt-3 w-full inline-flex items-center justify-center gap-2"
                data-testid="profile-change-selfie-btn"
              >
                <Camera className="w-4 h-4" /> Change selfie
              </button>
              <div className="mt-2 text-sm font-body min-h-[24px]">
                {faceStatus === "loading" && <span className="text-slate-600 inline-flex items-center gap-1"><Loader2 className="w-4 h-4 animate-spin" /> Reading…</span>}
                {faceStatus === "ok" && <span className="text-emerald-600 inline-flex items-center gap-1"><Check className="w-4 h-4" /> Got it.</span>}
                {faceStatus === "no_face" && <span className="text-rose-600 inline-flex items-center gap-1"><AlertTriangle className="w-4 h-4" /> {error || "Need a clear single face."}</span>}
              </div>

              {/* Quality bar */}
              <div className="mt-3 rounded-2xl border-2 border-slate-100 p-3 bg-white" data-testid="profile-quality-card">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="text-xs font-display font-bold uppercase tracking-widest text-slate-500">Face card quality</div>
                  <div className="font-display font-bold text-slate-900 text-sm" data-testid="profile-quality-pct">{qualityPct}%</div>
                </div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-pink-500 via-pink-400 to-orange-400" style={{ width: `${qualityPct}%` }} />
                </div>
                <p className="text-[11px] font-body text-slate-500 mt-1.5">
                  {qualityPct >= 75 ? "Elite face card. Matches will love it."
                    : qualityPct >= 50 ? "Solid. Consider a brighter, closer shot."
                    : "Low quality — try better light and a closer angle."}
                </p>
              </div>
            </div>

            {/* RIGHT: Form */}
            <div className="md:col-span-2 space-y-4">
              <label className="block">
                <span className="block text-sm font-display font-bold text-slate-700 mb-1">Name</span>
                <input value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-2xl border-2 border-slate-200 px-4 py-3 font-body focus:border-pink-400 outline-none" data-testid="profile-name-input" />
              </label>
              <label className="block">
                <span className="block text-sm font-display font-bold text-slate-700 mb-1">Bio</span>
                <input value={bio} onChange={(e) => setBio(e.target.value)} maxLength={80} placeholder="Late-reply queen with strong opinions on pasta." className="w-full rounded-2xl border-2 border-slate-200 px-4 py-3 font-body focus:border-pink-400 outline-none" data-testid="profile-bio-input" />
              </label>
              <label className="block">
                <span className="block text-sm font-display font-bold text-slate-700 mb-1">Location</span>
                <input value={location} onChange={(e) => setLocation(e.target.value)} className="w-full rounded-2xl border-2 border-slate-200 px-4 py-3 font-body focus:border-pink-400 outline-none" data-testid="profile-location-input" />
              </label>

              <div>
                <div className="text-sm font-display font-bold text-slate-700 mb-2">Show me</div>
                <div className="flex flex-wrap gap-2">
                  {[["women","Women"],["men","Men"],["everyone","Everyone"]].map(([k,l]) => (
                    <button key={k} type="button" onClick={() => setLookingFor(k)} className={`rounded-full px-4 py-2 font-display font-bold border-2 ${lookingFor === k ? "crush-cta border-transparent" : "bg-white border-slate-200 text-slate-700"}`} data-testid={`profile-looking-${k}`}>{l}</button>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-sm font-display font-bold text-slate-700 mb-2">Match mode</div>
                <div className="flex flex-wrap gap-2">
                  {[["doppel","Twin Energy"],["chaos","Chaos"]].map(([k,l]) => (
                    <button key={k} type="button" onClick={() => setMode(k)} className={`rounded-full px-4 py-2 font-display font-bold border-2 ${mode === k ? "crush-cta border-transparent" : "bg-white border-slate-200 text-slate-700"}`} data-testid={`profile-mode-${k}`}>{l}</button>
                  ))}
                </div>
              </div>

              {error ? <div className="text-sm text-rose-600 font-body" data-testid="profile-error">{error}</div> : null}
              {savedAt ? <div className="text-sm text-emerald-600 font-body inline-flex items-center gap-1"><Check className="w-4 h-4" /> Saved.</div> : null}

              <div className="flex gap-3 pt-3">
                <button onClick={save} disabled={saving} className="crush-cta rounded-full font-display font-bold px-6 py-3 inline-flex items-center gap-2 disabled:opacity-60" data-testid="profile-save-btn">
                  <Save className="w-4 h-4" /> {saving ? "Saving…" : "Save changes"}
                </button>
                <button onClick={() => { logout(); navigate("/"); }} className="crush-secondary rounded-full font-display font-bold px-5 py-3 inline-flex items-center gap-2" data-testid="profile-logout-btn">
                  <LogOut className="w-4 h-4" /> Log out
                </button>
              </div>

              {/* Twin share */}
              <div className="mt-4 rounded-3xl border-2 border-pink-100 p-4 bg-gradient-to-br from-pink-50 via-white to-orange-50" data-testid="profile-twin-share">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <div className="font-display text-lg font-bold text-slate-900">Share your twin page</div>
                    <div className="text-xs font-body text-slate-600">Anyone who signs up via this link gets an instant compare room with you.</div>
                  </div>
                  <button onClick={shareTwinNative} className="crush-cta rounded-full px-4 py-2 font-display font-bold text-sm inline-flex items-center gap-1.5" data-testid="profile-twin-share-btn">
                    <Share2 className="w-4 h-4" /> Share
                  </button>
                </div>
                <div className="mt-3 flex items-center gap-2 bg-white rounded-full p-1.5 border-2 border-slate-100">
                  <input value={twinUrl} readOnly className="flex-1 bg-transparent px-3 py-2 font-body text-xs truncate outline-none" data-testid="profile-twin-url" />
                  <button onClick={copyTwinUrl} className="crush-secondary rounded-full px-4 py-2 font-display font-bold text-xs inline-flex items-center gap-1.5" data-testid="profile-twin-copy-btn">
                    <Copy className="w-3 h-3" /> {twinCopied ? "Copied" : "Copy"}
                  </button>
                </div>
              </div>

              <div className="text-xs font-body text-slate-500 pt-2">
                Referral code: <b className="text-pink-600">{user?.referral_code}</b> · Email: {user?.email}
              </div>

              {/* Danger zone */}
              <div className="mt-6 pt-6 border-t-2 border-slate-100">
                <div className="text-xs font-display font-bold uppercase tracking-widest text-rose-500 mb-2">Privacy</div>
                <p className="text-sm font-body text-slate-600 max-w-md">
                  Delete your account, selfie and face embedding. This is immediate and cannot be undone.
                </p>
                <button
                  type="button"
                  onClick={() => setShowDelete(true)}
                  className="mt-3 inline-flex items-center gap-2 rounded-full px-4 py-2 font-display font-bold text-sm bg-white border-2 border-rose-200 text-rose-600 hover:border-rose-400 transition-colors"
                  data-testid="profile-delete-data-btn"
                >
                  <Trash2 className="w-4 h-4" /> Delete my data
                </button>
              </div>
            </div>
          </div>
        </div>

        {showDelete ? (
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm grid place-items-center z-50 p-4"
            data-testid="delete-confirm-modal"
            onClick={() => !deleting && setShowDelete(false)}
          >
            <div className="crush-frame max-w-md w-full p-6 sm:p-8 text-center" onClick={(e) => e.stopPropagation()}>
              <div className="w-14 h-14 rounded-full bg-rose-100 text-rose-600 grid place-items-center mx-auto">
                <ShieldAlert className="w-7 h-7" />
              </div>
              <h2 className="font-display text-3xl font-bold text-slate-900 mt-3">Delete everything?</h2>
              <p className="font-body text-slate-600 mt-2">
                Your selfie, face embedding, swipes, matches and messages will be wiped immediately. You'll be signed out.
              </p>
              {error ? <div className="mt-3 text-sm text-rose-600 font-body">{error}</div> : null}
              <div className="mt-5 flex flex-col gap-2">
                <button
                  onClick={deleteAccount}
                  disabled={deleting}
                  className="rounded-full font-display font-bold py-3 bg-rose-500 text-white hover:bg-rose-600 transition-colors disabled:opacity-60"
                  data-testid="profile-delete-confirm-btn"
                >
                  {deleting ? "Deleting…" : "Yes, delete my data"}
                </button>
                <button
                  onClick={() => setShowDelete(false)}
                  disabled={deleting}
                  className="crush-secondary rounded-full font-display font-bold py-3"
                  data-testid="profile-delete-cancel-btn"
                >
                  Keep my account
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
