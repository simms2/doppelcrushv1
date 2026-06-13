import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Send, Loader2, Heart, Share2 } from "lucide-react";
import Header from "@/components/Header";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Sticker } from "@/components/Stickers";

export default function Chat() {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [match, setMatch] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef();
  const lastSeenRef = useRef("");

  useEffect(() => {
    let cancelled = false;
    const init = async () => {
      try {
        const { data } = await api.get(`/matches/${matchId}`);
        if (!cancelled) setMatch(data);
        const msgs = await api.get(`/matches/${matchId}/messages`);
        if (!cancelled) {
          setMessages(msgs.data);
          if (msgs.data.length) lastSeenRef.current = msgs.data[msgs.data.length - 1].created_at;
        }
      } catch (err) {
        if (!cancelled) setError(formatApiError(err));
      }
    };
    init();

    const poll = setInterval(async () => {
      try {
        const params = lastSeenRef.current ? `?since=${encodeURIComponent(lastSeenRef.current)}` : "";
        const { data } = await api.get(`/matches/${matchId}/messages${params}`);
        if (data.length && !cancelled) {
          setMessages((prev) => [...prev, ...data]);
          lastSeenRef.current = data[data.length - 1].created_at;
        }
      } catch {}
    }, 2500);

    return () => { cancelled = true; clearInterval(poll); };
  }, [matchId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (e) => {
    e?.preventDefault();
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    setText("");
    // optimistic add
    const optimistic = {
      id: `tmp-${Date.now()}`,
      sender_id: user.id,
      body,
      created_at: new Date().toISOString(),
      _pending: true,
    };
    setMessages((m) => [...m, optimistic]);
    try {
      const { data } = await api.post(`/matches/${matchId}/messages`, { body });
      setMessages((m) => m.map((x) => (x.id === optimistic.id ? data : x)));
      lastSeenRef.current = data.created_at;
    } catch (err) {
      setMessages((m) => m.filter((x) => x.id !== optimistic.id));
      setError(formatApiError(err));
    } finally {
      setSending(false);
    }
  };

  const profile = match?.profile;

  return (
    <div className="crush-bg min-h-screen" data-testid="chat-page">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />

        <div className="crush-frame mt-4 overflow-hidden relative">
          <Sticker kind="heart" size={56} className="absolute -top-5 -right-3 rotate-12 hidden md:inline-flex" />

          {/* Chat header */}
          <div className="flex items-center gap-3 p-4 sm:p-5 border-b-2 border-slate-100 bg-gradient-to-r from-pink-50 via-white to-orange-50">
            <button onClick={() => navigate("/messages")} className="text-slate-500 hover:text-pink-600" data-testid="chat-back-btn" aria-label="Back to messages">
              <ArrowLeft className="w-5 h-5" />
            </button>
            {profile ? (
              <>
                <img src={profile.photo_url} alt={profile.name} className="w-12 h-12 rounded-2xl object-cover border-2 border-white shadow" />
                <div className="flex-1 min-w-0">
                  <div className="font-display text-lg font-bold text-slate-900 truncate">{profile.name}, {profile.age}</div>
                  <div className="text-xs font-body text-slate-500 truncate">{profile.bio || "It's a match!"}</div>
                </div>
                <Link
                  to={`/match/${profile.id}`}
                  className="crush-secondary rounded-full px-3 py-2 text-xs font-display font-bold inline-flex items-center gap-1"
                  data-testid="chat-share-btn"
                >
                  <Share2 className="w-3 h-3" /> Share
                </Link>
              </>
            ) : (
              <div className="font-body text-slate-500 inline-flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>
            )}
          </div>

          {/* Messages list */}
          <div
            ref={scrollRef}
            className="h-[55vh] overflow-y-auto p-4 sm:p-6 space-y-3 bg-white"
            data-testid="chat-messages"
          >
            {messages.length === 0 ? (
              <div className="h-full grid place-items-center text-center">
                <div>
                  <Heart className="w-10 h-10 text-pink-300 mx-auto" fill="#ffd1e3" />
                  <p className="mt-2 font-body text-slate-500 max-w-xs">
                    You two matched. Say something cute — or chaotic.
                  </p>
                </div>
              </div>
            ) : (
              messages.map((m) => {
                const mine = m.sender_id === user.id;
                return (
                  <div key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`} data-testid={mine ? "msg-mine" : "msg-theirs"}>
                    <div
                      className={`max-w-[78%] px-4 py-2.5 rounded-3xl font-body text-sm leading-relaxed ${
                        mine
                          ? "crush-cta text-white rounded-br-md"
                          : "bg-pink-50 text-slate-900 border-2 border-pink-100 rounded-bl-md"
                      } ${m._pending ? "opacity-70" : ""}`}
                    >
                      {m.body}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Input */}
          <form
            onSubmit={send}
            className="flex items-center gap-2 p-3 sm:p-4 border-t-2 border-slate-100 bg-gradient-to-r from-pink-50 via-white to-orange-50"
            data-testid="chat-form"
          >
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={1000}
              placeholder="Type something cute…"
              className="flex-1 rounded-full border-2 border-slate-200 px-4 py-3 font-body bg-white focus:border-pink-400 outline-none"
              data-testid="chat-input"
            />
            <button
              type="submit"
              disabled={sending || !text.trim()}
              className="crush-cta rounded-full px-5 py-3 font-display font-bold inline-flex items-center gap-2 disabled:opacity-60"
              data-testid="chat-send-btn"
            >
              <Send className="w-4 h-4" /> Send
            </button>
          </form>
        </div>

        {error ? <div className="mt-3 text-rose-600 font-body text-sm" data-testid="chat-error">{error}</div> : null}
      </div>
    </div>
  );
}
