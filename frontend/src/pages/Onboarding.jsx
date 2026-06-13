import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Camera, Check, ArrowRight, Loader2, AlertTriangle, Zap, Heart } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { fileToImage, getFaceEmbedding, loadFaceModels } from "@/lib/face";
import { LogoBadge } from "@/components/Header";
import { Sticker } from "@/components/Stickers";

const STEPS = ["Selfie", "Age", "About you", "Match mode"];

export default function Onboarding() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // selfie state
  const [previewUrl, setPreviewUrl] = useState("");
  const [photoData, setPhotoData] = useState(""); // dataURL stored alongside
  const [embedding, setEmbedding] = useState([]);
  const [faceStatus, setFaceStatus] = useState(""); // "loading" | "ok" | "no_face"
  const fileRef = useRef();

  // profile state
  const [age, setAge] = useState(20);
  const [over18, setOver18] = useState(false);
  const [gender, setGender] = useState("");
  const [lookingFor, setLookingFor] = useState("");
  const [mode, setMode] = useState("doppel");
  const [bio, setBio] = useState("");
  const [location, setLocation] = useState("");

  useEffect(() => {
    loadFaceModels().catch(() => {});
  }, []);

  const handleFile = async (file) => {
    if (!file) return;
    setError("");
    setFaceStatus("loading");
    try {
      const { img } = await fileToImage(file);
      // wait for image to be ready
      await new Promise((r) => (img.complete ? r() : (img.onload = r)));
      const result = await getFaceEmbedding(img);
      if (!result.ok) {
        setFaceStatus("no_face");
        setError("We couldn't find a clear face. Try a brighter, front-facing selfie.");
        return;
      }
      setEmbedding(result.embedding);
      // Upload to object storage instead of stashing a base64 data URL
      const form = new FormData();
      form.append("file", file, file.name || "selfie.jpg");
      const { data } = await api.post("/upload/selfie", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const absolute = data.url.startsWith("http")
        ? data.url
        : `${process.env.REACT_APP_BACKEND_URL}${data.url}`;
      setPhotoData(absolute);
      setPreviewUrl(absolute);
      setFaceStatus("ok");
    } catch (e) {
      setFaceStatus("no_face");
      setError("Couldn't upload that photo. Pick another.");
    }
  };

  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep((s) => Math.max(0, s - 1));

  const finish = async () => {
    setError("");
    setBusy(true);
    try {
      const { data } = await api.post("/onboarding", {
        age,
        gender,
        looking_for: lookingFor,
        mode,
        bio,
        location,
        photo_url: photoData || (user?.photo_url ?? null),
        embedding,
      });
      setUser(data);
      navigate("/discover");
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  const canContinue = (() => {
    if (step === 0) return faceStatus === "ok";
    if (step === 1) return over18 && age >= 18;
    if (step === 2) return gender && lookingFor;
    if (step === 3) return Boolean(mode);
    return false;
  })();

  return (
    <div className="crush-bg min-h-screen" data-testid="onboarding-page">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <LogoBadge />

        {/* progress */}
        <div className="mt-6 flex items-center gap-3">
          {STEPS.map((label, i) => (
            <div key={label} className="flex-1">
              <div className={`h-2 rounded-full ${i <= step ? "bg-gradient-to-r from-pink-500 to-orange-400" : "bg-slate-200"}`} />
              <div className={`mt-2 text-xs font-display font-bold ${i === step ? "text-pink-600" : "text-slate-400"}`}>{label}</div>
            </div>
          ))}
        </div>

        <div className="crush-frame mt-6 p-6 sm:p-10 relative">
          <Sticker kind="heart" size={56} className="absolute -top-6 -right-4 rotate-12 hidden sm:inline-flex" />

          {step === 0 && (
            <div data-testid="step-selfie">
              <h2 className="font-display text-4xl font-bold text-slate-900">Drop the selfie 📸</h2>
              <p className="mt-2 text-slate-600 font-body">We use it to find your DoppelCrush. One face, please.</p>

              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => handleFile(e.target.files?.[0])}
                data-testid="selfie-file-input"
              />

              <div className="mt-6 flex flex-col sm:flex-row items-center gap-6">
                <div className="w-40 h-40 rounded-3xl overflow-hidden bg-pink-50 border-4 border-dashed border-pink-200 grid place-items-center">
                  {previewUrl ? (
                    <img src={previewUrl} alt="Selfie preview" className="w-full h-full object-cover" />
                  ) : (
                    <Camera className="w-12 h-12 text-pink-400" />
                  )}
                </div>
                <div>
                  <button
                    type="button"
                    onClick={() => fileRef.current?.click()}
                    className="crush-cta rounded-full font-display font-bold px-6 py-3 inline-flex items-center gap-2"
                    data-testid="selfie-upload-btn"
                  >
                    <Camera className="w-5 h-5" /> {previewUrl ? "Pick a different selfie" : "Upload selfie"}
                  </button>
                  <div className="mt-3 text-sm font-body">
                    {faceStatus === "loading" && (
                      <span className="text-slate-600 inline-flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Reading your face card…</span>
                    )}
                    {faceStatus === "ok" && (
                      <span className="text-emerald-600 inline-flex items-center gap-2"><Check className="w-4 h-4" /> Face card captured.</span>
                    )}
                    {faceStatus === "no_face" && (
                      <span className="text-rose-600 inline-flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> Need a clearer single face.</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 1 && (
            <div data-testid="step-age">
              <h2 className="font-display text-4xl font-bold text-slate-900">Are you 18+?</h2>
              <p className="mt-2 text-slate-600 font-body">DoppelCrush is 18 and over. We have to ask.</p>
              <div className="mt-6">
                <label className="block">
                  <span className="block text-sm font-display font-bold text-slate-700 mb-1">Your age</span>
                  <input
                    type="number"
                    min={18}
                    max={120}
                    value={age}
                    onChange={(e) => setAge(parseInt(e.target.value || "0", 10))}
                    className="w-40 rounded-2xl border-2 border-slate-200 px-4 py-3 font-body focus:border-pink-400 outline-none"
                    data-testid="age-input"
                  />
                </label>
                <label className="mt-5 flex items-center gap-3 cursor-pointer">
                  <input type="checkbox" checked={over18} onChange={(e) => setOver18(e.target.checked)} className="w-5 h-5 accent-pink-500" data-testid="age-confirm-checkbox" />
                  <span className="font-body text-slate-700">I confirm I'm 18 years or older.</span>
                </label>
              </div>
            </div>
          )}

          {step === 2 && (
            <div data-testid="step-about">
              <h2 className="font-display text-4xl font-bold text-slate-900">About you</h2>
              <p className="mt-2 text-slate-600 font-body">Tell us your vibe and who you want to see.</p>

              <div className="mt-6 grid md:grid-cols-2 gap-6">
                <div>
                  <div className="text-sm font-display font-bold text-slate-700 mb-2">I am a…</div>
                  <div className="flex flex-wrap gap-2">
                    {[
                      ["woman", "Woman"],
                      ["man", "Man"],
                      ["nonbinary", "Nonbinary"],
                    ].map(([k, l]) => (
                      <button
                        key={k}
                        type="button"
                        onClick={() => setGender(k)}
                        className={`rounded-full px-4 py-2 font-display font-bold border-2 ${gender === k ? "crush-cta border-transparent" : "bg-white border-slate-200 text-slate-700"}`}
                        data-testid={`gender-${k}`}
                      >{l}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-sm font-display font-bold text-slate-700 mb-2">Show me…</div>
                  <div className="flex flex-wrap gap-2">
                    {[
                      ["women", "Women"],
                      ["men", "Men"],
                      ["everyone", "Everyone"],
                    ].map(([k, l]) => (
                      <button
                        key={k}
                        type="button"
                        onClick={() => setLookingFor(k)}
                        className={`rounded-full px-4 py-2 font-display font-bold border-2 ${lookingFor === k ? "crush-cta border-transparent" : "bg-white border-slate-200 text-slate-700"}`}
                        data-testid={`looking-${k}`}
                      >{l}</button>
                    ))}
                  </div>
                </div>
              </div>
              <div className="mt-6 grid md:grid-cols-2 gap-4">
                <label className="block">
                  <span className="block text-sm font-display font-bold text-slate-700 mb-1">Location (optional)</span>
                  <input
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="Brooklyn"
                    className="w-full rounded-2xl border-2 border-slate-200 px-4 py-3 font-body focus:border-pink-400 outline-none"
                    data-testid="location-input"
                  />
                </label>
                <label className="block">
                  <span className="block text-sm font-display font-bold text-slate-700 mb-1">Bio (optional)</span>
                  <input
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                    maxLength={80}
                    placeholder="Late-reply queen with strong opinions on pasta."
                    className="w-full rounded-2xl border-2 border-slate-200 px-4 py-3 font-body focus:border-pink-400 outline-none"
                    data-testid="bio-input"
                  />
                </label>
              </div>
            </div>
          )}

          {step === 3 && (
            <div data-testid="step-mode">
              <h2 className="font-display text-4xl font-bold text-slate-900">Pick your mode</h2>
              <p className="mt-2 text-slate-600 font-body">You can switch any time.</p>
              <div className="mt-6 grid md:grid-cols-2 gap-4">
                <button
                  type="button"
                  onClick={() => setMode("doppel")}
                  className={`text-left p-6 rounded-3xl border-4 ${mode === "doppel" ? "border-pink-500 bg-pink-50" : "border-white bg-white"} shadow-md`}
                  data-testid="mode-doppel"
                >
                  <div className="flex items-center gap-2 text-pink-600"><Heart className="w-5 h-5" /><span className="font-display font-bold">Doppel Mode</span></div>
                  <div className="font-display text-2xl font-bold mt-1">Twin energy.</div>
                  <div className="text-slate-600 font-body mt-1">People who match your face card.</div>
                </button>
                <button
                  type="button"
                  onClick={() => setMode("chaos")}
                  className={`text-left p-6 rounded-3xl border-4 ${mode === "chaos" ? "border-orange-500 bg-orange-50" : "border-white bg-white"} shadow-md`}
                  data-testid="mode-chaos"
                >
                  <div className="flex items-center gap-2 text-orange-600"><Zap className="w-5 h-5" /><span className="font-display font-bold">Chaos Mode</span></div>
                  <div className="font-display text-2xl font-bold mt-1">Plot twist.</div>
                  <div className="text-slate-600 font-body mt-1">A total switch-up from your usual type.</div>
                </button>
              </div>
            </div>
          )}

          {error ? <div className="mt-4 text-sm text-rose-600 font-body" data-testid="onboarding-error">{error}</div> : null}

          <div className="mt-8 flex items-center justify-between">
            <button
              type="button"
              onClick={back}
              disabled={step === 0}
              className="crush-secondary rounded-full px-5 py-2.5 font-display font-bold disabled:opacity-40"
              data-testid="onboarding-back-btn"
            >Back</button>
            {step < STEPS.length - 1 ? (
              <button
                type="button"
                onClick={next}
                disabled={!canContinue}
                className="crush-cta rounded-full px-6 py-3 font-display font-bold inline-flex items-center gap-2 disabled:opacity-60"
                data-testid="onboarding-next-btn"
              >Next <ArrowRight className="w-5 h-5" /></button>
            ) : (
              <button
                type="button"
                onClick={finish}
                disabled={!canContinue || busy}
                className="crush-cta rounded-full px-6 py-3 font-display font-bold inline-flex items-center gap-2 disabled:opacity-60"
                data-testid="onboarding-finish-btn"
              >{busy ? "Loading…" : "Find my matches"} <ArrowRight className="w-5 h-5" /></button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
