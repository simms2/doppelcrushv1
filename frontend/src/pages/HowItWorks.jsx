import Header from "@/components/Header";
import { Camera, Heart, Zap, MessageCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Sticker } from "@/components/Stickers";

const steps = [
  { icon: Camera, title: "Upload a selfie", body: "We use your selfie to build a face card. One face, well-lit, looking at the camera." },
  { icon: Heart, title: "Pick your vibe", body: "Twin Energy for the look-alike crushes. Chaos for the total opposite." },
  { icon: Zap, title: "Swipe smarter", body: "Our matcher ranks people by visual similarity (or difference, in Chaos)." },
  { icon: MessageCircle, title: "Match & chat", body: "Mutual ♥ unlocks a chat. Share the reveal card to flex on your group chat." },
];

export default function HowItWorks() {
  return (
    <div className="crush-bg min-h-screen" data-testid="how-page">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />
        <div className="crush-frame mt-4 p-6 sm:p-10 relative">
          <Sticker kind="spark" size={64} className="absolute -top-6 -right-4 rotate-12" />
          <h1 className="font-display text-5xl font-bold text-slate-900">How it works</h1>
          <p className="mt-3 text-slate-600 font-body max-w-2xl text-lg">Four steps. No essays. No biometric mumbo-jumbo. Just face card energy.</p>

          <div className="mt-8 grid sm:grid-cols-2 gap-4">
            {steps.map((s, i) => (
              <div key={s.title} className="bg-white rounded-3xl p-6 border-2 border-pink-100 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-pink-100 text-pink-600 grid place-items-center"><s.icon className="w-5 h-5" /></div>
                  <div className="font-display font-bold text-pink-600">Step {i + 1}</div>
                </div>
                <div className="font-display text-2xl font-bold text-slate-900 mt-2">{s.title}</div>
                <p className="font-body text-slate-600 mt-1">{s.body}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 text-center">
            <Link to="/auth" className="crush-cta rounded-full font-display font-bold px-6 py-3 inline-flex">Get started</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
