import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

export const LogoBadge = () => (
  <div className="flex items-center gap-3" data-testid="dc-logo">
    <div className="relative w-12 h-12 rounded-2xl overflow-hidden shadow-lg shadow-pink-200">
      <div className="absolute inset-0 bg-gradient-to-br from-pink-400 via-pink-500 to-orange-400" />
      <div className="absolute inset-0 flex items-center justify-center font-display text-white text-2xl font-bold">D</div>
    </div>
    <div className="leading-tight">
      <div className="font-display text-xl sm:text-2xl font-bold tracking-tight text-slate-900">DoppelCrush</div>
      <div className="text-xs sm:text-sm text-slate-500 font-body">Because clearly you have good taste.</div>
    </div>
  </div>
);

export default function Header({ inline = false }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div
      className={`crush-frame flex items-center justify-between gap-4 px-5 py-3 sm:px-6 sm:py-4 ${inline ? "" : "mb-6"}`}
      data-testid="site-header"
    >
      <Link to="/" className="flex items-center"><LogoBadge /></Link>
      <nav className="hidden md:flex items-center gap-6 font-body font-semibold text-slate-700">
        <Link to="/how-it-works" className="hover:text-pink-600" data-testid="nav-how">How it works</Link>
        <Link to="/safety" className="hover:text-pink-600" data-testid="nav-safety">Safety</Link>
        <Link to="/faq" className="hover:text-pink-600" data-testid="nav-faq">FAQ</Link>
        {user && user.onboarding_complete ? (
          <Link to="/discover" className="hover:text-pink-600" data-testid="nav-discover">Discover</Link>
        ) : null}
        {user && user.onboarding_complete ? (
          <Link to="/messages" className="hover:text-pink-600" data-testid="nav-messages">Messages</Link>
        ) : null}
      </nav>
      <div className="flex items-center gap-2">
        {user ? (
          <>
            <button
              onClick={() => navigate(user.onboarding_complete ? "/discover" : "/onboarding")}
              className="crush-cta rounded-full font-display font-bold px-5 py-2.5 text-sm"
              data-testid="header-app-btn"
            >
              {user.onboarding_complete ? "Discover" : "Finish setup"}
            </button>
            <button
              onClick={() => { logout(); navigate("/"); }}
              className="crush-secondary rounded-full font-display font-bold px-4 py-2.5 text-sm"
              data-testid="header-logout-btn"
            >
              Log out
            </button>
          </>
        ) : (
          <button
            onClick={() => navigate("/auth")}
            className="bg-slate-900 text-white rounded-full font-display font-bold px-7 py-3 text-base hover:bg-black transition-transform hover:scale-105 inline-flex items-center gap-2 relative"
            data-testid="header-start-btn"
          >
            Start
            <svg width="22" height="22" viewBox="0 0 22 22" className="absolute -right-3 -top-2 rotate-12" aria-hidden="true">
              <path d="M2 18 C 8 4, 14 16, 20 4" stroke="#ff2d8a" strokeWidth="3" strokeLinecap="round" fill="none"/>
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
