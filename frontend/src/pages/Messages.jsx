import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "@/components/Header";
import { api } from "@/lib/api";
import { Sticker } from "@/components/Stickers";

export default function Messages() {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/matches")
      .then(({ data }) => setMatches(data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="crush-bg min-h-screen" data-testid="messages-page">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />
        <div className="crush-frame mt-4 p-6 sm:p-8 relative">
          <Sticker kind="heart" size={64} className="absolute -top-6 -right-4 rotate-12" />
          <h1 className="font-display text-4xl font-bold text-slate-900">Messages</h1>
          <p className="text-slate-600 font-body">Your match list. Chat is coming soon — for now, react to the vibe.</p>

          <div className="mt-6">
            {loading ? (
              <div className="text-pink-600 font-display">Loading…</div>
            ) : matches.length === 0 ? (
              <div className="text-center py-12">
                <Sticker kind="spark" size={72} className="mx-auto" />
                <p className="mt-3 text-slate-600 font-body">No matches yet. Head to <button className="text-pink-600 font-bold underline" onClick={() => navigate("/discover")}>Discover</button>.</p>
              </div>
            ) : (
              <ul className="space-y-3">
                {matches.map((m) => (
                  <li
                    key={m.id}
                    className="flex items-center gap-4 p-3 rounded-2xl bg-white border-2 border-slate-100 hover:border-pink-200 cursor-pointer"
                    onClick={() => navigate(`/chat/${m.id}`)}
                    data-testid={`match-row-${m.profile.id}`}
                  >
                    <img src={m.profile.photo_url} alt={m.profile.name} className="w-16 h-16 rounded-2xl object-cover" />
                    <div className="flex-1 min-w-0">
                      <div className="font-display text-xl font-bold text-slate-900">{m.profile.name}, {m.profile.age}</div>
                      <div className="text-sm text-slate-500 font-body truncate">{m.profile.bio || "Say hi 👋"}</div>
                    </div>
                    <span className="text-xs text-pink-600 font-bold">Chat →</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
