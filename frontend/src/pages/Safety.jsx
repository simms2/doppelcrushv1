import Header from "@/components/Header";
import { ShieldCheck, Lock, Eye, UserX } from "lucide-react";
import { Sticker } from "@/components/Stickers";

const items = [
  { icon: ShieldCheck, title: "Selfie only", body: "We use your selfie for matching. No surveillance. No third-party biometric resale. Ever." },
  { icon: Lock, title: "Encrypted at rest", body: "Your data is stored securely. Delete your account and it's gone." },
  { icon: Eye, title: "Block & report", body: "One tap to block or report. We review reports fast." },
  { icon: UserX, title: "18+ only", body: "DoppelCrush is for adults. Age confirmation is part of onboarding." },
];

export default function Safety() {
  return (
    <div className="crush-bg min-h-screen" data-testid="safety-page">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />
        <div className="crush-frame mt-4 p-6 sm:p-10 relative">
          <Sticker kind="heart" size={64} className="absolute -top-6 -right-4 rotate-12" />
          <h1 className="font-display text-5xl font-bold text-slate-900">Safety</h1>
          <p className="mt-3 text-slate-600 font-body max-w-2xl text-lg">Glossy and playful, never creepy. Here's the deal on your data and your safety.</p>

          <div className="mt-8 grid sm:grid-cols-2 gap-4">
            {items.map((s) => (
              <div key={s.title} className="bg-white rounded-3xl p-6 border-2 border-pink-100">
                <div className="w-10 h-10 rounded-xl bg-orange-100 text-orange-600 grid place-items-center"><s.icon className="w-5 h-5" /></div>
                <div className="font-display text-2xl font-bold text-slate-900 mt-3">{s.title}</div>
                <p className="font-body text-slate-600 mt-1">{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
