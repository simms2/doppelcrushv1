import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

export default function ProtectedRoute({ children, requireOnboarding = false }) {
  const { user, bootstrapped } = useAuth();
  if (!bootstrapped) {
    return (
      <div className="crush-bg flex items-center justify-center min-h-screen font-display text-pink-600 text-xl">
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/auth" replace />;
  if (requireOnboarding && !user.onboarding_complete) return <Navigate to="/onboarding" replace />;
  return children;
}
