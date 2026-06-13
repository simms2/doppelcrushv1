import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

export const LogoBadge = () => (
  <div className="flex items-center gap-3" data-testid="dc-logo">
    <div className="relative w-11 h-11 sm:w-12 sm:h-12 rounded-2xl overflow-hidden shadow-lg shadow-pink-200 flex-shrink-0">
      <div className="absolute inset-0 bg-gradient-to-br from-yellow-300 via-pink-500 to-orange-500" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_25%,rgba(255,255,255,0.6),rgba(255,255,255,0)_50%)]" />
      <div className="absolute inset-0 flex items-center justify-center font-display text-white text-2xl sm:text-3xl font-bold" style={{ textShadow: "0 2px 0 rgba(155,18,76,0.4)" }}>D</div>
    </div>
    <div className="leading-tight">
      <div className="font-display text-lg sm:text-xl font-bold tracking-tight text-slate-900 whitespace-nowrap">DoppelCrush</div>
      <div className="text-[11px] sm:text-xs text-slate-500 font-body whitespace-nowrap">Find your Doppel. Flirt with chaos.</div>
    </div>
  </div>
);

const NavLink = ({ to, active, children, ...rest }) => (
  <Link
    to={to}
    className={`whitespace-nowrap hover:text-pink-600 transition-colors ${active ? "text-pink-600" : "text-slate-700"}`}
    {...rest}
  >
    {children}
  </Link>
);

export default function Header({ inline = false }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!user || !user.onboarding_complete) return;
    let alive = true;
    const tick = async () => {
      try {
        const { data } = await api.get("/me/unread");
        if (alive) setUnread(data.unread || 0);
      } catch {}
    };
    tick();
    const id = setInterval(tick, 8000);
    return () => { alive = false; clearInterval(id); };
  }, [user]);

  const onboarded = Boolean(user?.onboarding_complete);
  const path = location.pathname;
  const isActive = (p) => path === p || (p !== "/" && path.startsWith(p));

  return (
    <div
      className={`crush-frame flex items-center justify-between gap-3 px-4 py-3 sm:px-6 sm:py-4 ${inline ? "" : "mb-6"}`}
      data-testid="site-header"
    >
      <Link to="/" className="flex items-center min-w-0" data-testid="header-logo-link">
        <LogoBadge />
      </Link>

      <nav className="hidden md:flex items-center gap-4 lg:gap-5 font-body font-semibold text-sm lg:text-[15px]">
        {onboarded ? (
          <>
            <NavLink to="/discover" active={isActive("/discover")} data-testid="nav-discover">Discover</NavLink>
            <NavLink to="/messages" active={isActive("/messages")} data-testid="nav-messages">
              <span className="relative">
                Messages
                {unread > 0 ? (
                  <span className="absolute -top-2 -right-4 min-w-[18px] h-[18px] px-1.5 rounded-full bg-pink-500 text-white text-[10px] font-bold grid place-items-center" data-testid="unread-badge">
                    {unread > 9 ? "9+" : unread}
                  </span>
                ) : null}
              </span>
            </NavLink>
            <NavLink to="/compare" active={isActive("/compare")} data-testid="nav-compare">Compare</NavLink>
            <NavLink to="/invite" active={isActive("/invite")} data-testid="nav-invite">Invite</NavLink>
            <NavLink to="/profile" active={isActive("/profile")} data-testid="nav-profile">Profile</NavLink>
          </>
        ) : (
          <>
            <NavLink to="/how-it-works" active={isActive("/how-it-works")} data-testid="nav-how">How it works</NavLink>
            <NavLink to="/safety" active={isActive("/safety")} data-testid="nav-safety">Safety</NavLink>
            <NavLink to="/faq" active={isActive("/faq")} data-testid="nav-faq">FAQ</NavLink>
            {user ? (
              <NavLink to="/invite" active={isActive("/invite")} data-testid="nav-invite">Invite</NavLink>
            ) : null}
          </>
        )}
      </nav>

      <div className="flex items-center gap-2 flex-shrink-0">
        {user ? (
          onboarded ? (
            <button
              onClick={() => { logout(); navigate("/"); }}
              className="crush-secondary rounded-full font-display font-bold px-4 py-2 text-xs sm:text-sm whitespace-nowrap"
              data-testid="header-logout-btn"
            >
              Log out
            </button>
          ) : (
            <>
              <button
                onClick={() => navigate("/onboarding")}
                className="crush-cta rounded-full font-display font-bold px-4 py-2 text-xs sm:text-sm whitespace-nowrap"
                data-testid="header-app-btn"
              >
                Finish setup
              </button>
              <button
                onClick={() => { logout(); navigate("/"); }}
                className="crush-secondary rounded-full font-display font-bold px-3 py-2 text-xs sm:text-sm whitespace-nowrap"
                data-testid="header-logout-btn"
              >
                Log out
              </button>
            </>
          )
        ) : (
          <button
            onClick={() => navigate("/auth")}
            className="bg-slate-900 text-white rounded-full font-display font-bold px-6 py-2.5 text-sm sm:text-base hover:bg-black transition-transform hover:scale-105 inline-flex items-center gap-2 relative whitespace-nowrap"
            data-testid="header-start-btn"
          >
            Start
            <svg width="22" height="22" viewBox="0 0 22 22" className="absolute -right-3 -top-2 rotate-12" aria-hidden="true">
              <path d="M2 18 C 8 4, 14 16, 20 4" stroke="#ff2d8a" strokeWidth="3" strokeLinecap="round" fill="none" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
