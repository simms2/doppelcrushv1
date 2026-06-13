import { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { formatApiError } from "@/lib/api";
import { LogoBadge } from "@/components/Header";
import { Sticker, KawaiiHeart } from "@/components/Stickers";

export default function Auth() {
  const [mode, setMode] = useState("signup"); // signup or login
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { login, signup } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const ref = params.get("ref");
  const twinId = params.get("twin_id");
  const source = params.get("source");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "signup") {
        const u = await signup(email, password, name || "Crush", ref, twinId, source);
        navigate(u.onboarding_complete ? "/discover" : "/onboarding");
      } else {
        const u = await login(email, password);
        navigate(u.onboarding_complete ? "/discover" : "/onboarding");
      }
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="crush-bg min-h-screen" data-testid="auth-page">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-16">
        <Link to="/"><LogoBadge /></Link>

        <div className="mt-8 grid md:grid-cols-2 gap-8 items-center">
          <div className="relative">
            <h1 className="font-display text-5xl sm:text-6xl font-bold leading-[0.95] text-slate-900">
              {mode === "signup" ? <>Make a <span className="crush-text-grad">crush account</span>.</> : <>Welcome <span className="crush-text-grad">back</span>.</>}
            </h1>
            <p className="mt-4 text-slate-600 font-body text-lg max-w-md">
              {mode === "signup"
                ? "We just need an email and password. Your face card comes next."
                : "Drop your email and we'll get your matches warmed up."}
            </p>
            <div className="hidden md:block absolute -bottom-8 -left-4 w-40 animate-floaty"><KawaiiHeart /></div>
            <Sticker kind="bolt" size={64} className="absolute -top-4 right-10 rotate-12 hidden md:inline-flex animate-wiggle" color="#8a5cf6" />
            <Sticker kind="spark" size={56} className="absolute bottom-2 right-2 -rotate-6 hidden md:inline-flex animate-floaty" />
          </div>

          <form onSubmit={submit} className="crush-frame p-6 sm:p-8" data-testid="auth-form">
            <div className="flex gap-2 mb-6">
              <button
                type="button"
                onClick={() => setMode("signup")}
                className={`flex-1 rounded-full font-display font-bold py-2.5 ${mode === "signup" ? "crush-cta" : "crush-secondary"}`}
                data-testid="auth-mode-signup"
              >Sign up</button>
              <button
                type="button"
                onClick={() => setMode("login")}
                className={`flex-1 rounded-full font-display font-bold py-2.5 ${mode === "login" ? "crush-cta" : "crush-secondary"}`}
                data-testid="auth-mode-login"
              >Log in</button>
            </div>

            {mode === "signup" && (
              <label className="block mb-3">
                <span className="block text-sm font-display font-bold text-slate-700 mb-1">Your name</span>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Pookie"
                  className="w-full rounded-2xl border-2 border-slate-200 px-4 py-3 font-body focus:border-pink-400 outline-none"
                  data-testid="auth-name-input"
                />
              </label>
            )}

            <label className="block mb-3">
              <span className="block text-sm font-display font-bold text-slate-700 mb-1">Email</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@vibes.com"
                className="w-full rounded-2xl border-2 border-slate-200 px-4 py-3 font-body focus:border-pink-400 outline-none"
                data-testid="auth-email-input"
              />
            </label>

            <label className="block mb-4">
              <span className="block text-sm font-display font-bold text-slate-700 mb-1">Password</span>
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-2xl border-2 border-slate-200 px-4 py-3 font-body focus:border-pink-400 outline-none"
                data-testid="auth-password-input"
              />
            </label>

            {error ? (
              <div className="text-sm text-rose-600 font-body mb-3" data-testid="auth-error">{error}</div>
            ) : null}

            {ref ? (
              <div className="text-xs font-body text-pink-600 mb-3" data-testid="auth-ref-info">
                Invited by code <b>{ref}</b> — you both get extra daily matches.
              </div>
            ) : null}

            <button
              type="submit"
              disabled={busy}
              className="crush-cta rounded-full font-display font-bold w-full py-3 text-lg disabled:opacity-60"
              data-testid="auth-submit-btn"
            >
              {busy ? "…" : mode === "signup" ? "Create my account" : "Log me in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
