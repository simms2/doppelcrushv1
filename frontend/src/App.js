import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";

import Home from "@/pages/Home";
import Auth from "@/pages/Auth";
import Onboarding from "@/pages/Onboarding";
import Discover from "@/pages/Discover";
import MatchReveal from "@/pages/MatchReveal";
import Messages from "@/pages/Messages";
import Chat from "@/pages/Chat";
import HowItWorks from "@/pages/HowItWorks";
import Safety from "@/pages/Safety";
import FAQ from "@/pages/FAQ";
import Invite from "@/pages/Invite";
import Compare from "@/pages/Compare";
import Profile from "@/pages/Profile";
import Twin from "@/pages/Twin";

import "@/App.css";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/signup" element={<Auth />} />
          <Route path="/auth" element={<Auth />} />
          <Route path="/how-it-works" element={<HowItWorks />} />
          <Route path="/safety" element={<Safety />} />
          <Route path="/faq" element={<FAQ />} />
          <Route path="/your-twin/:userId" element={<Twin />} />
          <Route
            path="/onboarding"
            element={<ProtectedRoute><Onboarding /></ProtectedRoute>}
          />
          <Route
            path="/discover"
            element={<ProtectedRoute requireOnboarding><Discover /></ProtectedRoute>}
          />
          <Route
            path="/messages"
            element={<ProtectedRoute requireOnboarding><Messages /></ProtectedRoute>}
          />
          <Route
            path="/match/:matchId"
            element={<ProtectedRoute requireOnboarding><MatchReveal /></ProtectedRoute>}
          />
          <Route
            path="/chat/:matchId"
            element={<ProtectedRoute requireOnboarding><Chat /></ProtectedRoute>}
          />
          <Route
            path="/invite"
            element={<ProtectedRoute><Invite /></ProtectedRoute>}
          />
          <Route
            path="/compare"
            element={<ProtectedRoute requireOnboarding><Compare /></ProtectedRoute>}
          />
          <Route
            path="/compare/:roomId"
            element={<ProtectedRoute requireOnboarding><Compare /></ProtectedRoute>}
          />
          <Route
            path="/profile"
            element={<ProtectedRoute requireOnboarding><Profile /></ProtectedRoute>}
          />
        </Routes>
        <Toaster />
      </BrowserRouter>
    </AuthProvider>
  );
}
