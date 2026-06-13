import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Send, Loader2, Heart, Share2, Wifi, WifiOff } from "lucide-react";
import Header from "@/components/Header";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Sticker } from "@/components/Stickers";

function buildWsUrl(matchId) {
  const base = process.env.REACT_APP_BACKEND_URL || window.location.origin;
  const wsBase = base.replace(/^http/, "ws");
  const token = encodeURIComponent(localStorage.getItem("dc_token") || "");
  return `${wsBase}/api/ws/chat/${matchId}?token=${token}`;
}

export default function Chat() {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [match, setMatch] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [state, setState] = useState({ typing: false, last_read_other_message_id: null });
  const [transport, setTransport] = useState("connecting"); // connecting | ws | polling

  const scrollRef = useRef();
  const lastSeenRef = useRef("");
  const typingTimerRef = useRef(null);
  const wsRef = useRef(null);
  const remoteTypingRef = useRef(null);

  // Initial load + WS connect + polling fallback
  useEffect(() => {
    let cancelled = false;
    let pollMessages = null;
    let pollState = null;
    let reconnectTimer = null;

    const startPolling = () => {
      if (pollMessages) return;
      setTransport("polling");
      pollMessages = setInterval(async () => {
        try {
          const params = lastSeenRef.current ? { since: lastSeenRef.current } : {};
          const { data } = await api.get(`/matches/${matchId}/messages`, { params });
          if (data.length && !cancelled) {
            setMessages((prev) => mergeUnique(prev, data));
            lastSeenRef.current = data[data.length - 1].created_at;
          }
        } catch {}
      }, 2500);
      pollState = setInterval(async () => {
        try {
          const { data } = await api.get(`/matches/${matchId}/state`);
          if (!cancelled) setState(data);
        } catch {}
      }, 2000);
    };

    const stopPolling = () => {
      if (pollMessages) { clearInterval(pollMessages); pollMessages = null; }
      if (pollState) { clearInterval(pollState); pollState = null; }
    };

    const connectWs = () => {
      try {
        const ws = new WebSocket(buildWsUrl(matchId));
        wsRef.current = ws;
        const wsTimeout = setTimeout(() => {
          if (ws.readyState !== WebSocket.OPEN) {
            try { ws.close(); } catch {}
            startPolling();
          }
        }, 3500);

        ws.onopen = () => {
          clearTimeout(wsTimeout);
          if (cancelled) return;
          stopPolling();
          setTransport("ws");
          // State (read receipts / unread) still needs HTTP — start light state poll only
          if (!pollState) {
            pollState = setInterval(async () => {
              try {
                const { data } = await api.get(`/matches/${matchId}/state`);
                if (!cancelled) setState(data);
              } catch {}
            }, 4000);
          }
        };
        ws.onmessage = (ev) => {
          if (cancelled) return;
          try {
            const evt = JSON.parse(ev.data);
            if (evt.type === "message" && evt.message) {
              const incoming = evt.message;
              setMessages((prev) => {
                // If this message echoes back our own optimistic send, replace it
                if (incoming.sender_id === user.id) {
                  const idx = prev.findIndex(
                    (m) => m._pending && m.sender_id === user.id && m.body === incoming.body,
                  );
                  if (idx >= 0) {
                    const next = prev.slice();
                    next[idx] = incoming;
                    return next;
                  }
                }
                return mergeUnique(prev, [incoming]);
              });
              lastSeenRef.current = incoming.created_at;
            } else if (evt.type === "typing" && evt.user_id !== user.id) {
              setState((s) => ({ ...s, typing: true }));
              if (remoteTypingRef.current) clearTimeout(remoteTypingRef.current);
              remoteTypingRef.current = setTimeout(() => setState((s) => ({ ...s, typing: false })), 3000);
            }
          } catch {}
        };
        ws.onerror = () => {};
        ws.onclose = () => {
          if (cancelled) return;
          wsRef.current = null;
          startPolling();
          // Try reconnect once after 5s in case of transient network hiccup
          if (!reconnectTimer) {
            reconnectTimer = setTimeout(() => { reconnectTimer = null; connectWs(); }, 5000);
          }
        };
      } catch {
        startPolling();
      }
    };

    const init = async () => {
      try {
        const { data } = await api.get(`/matches/${matchId}`);
        if (!cancelled) setMatch(data);
        const msgs = await api.get(`/matches/${matchId}/messages`);
        if (!cancelled) {
          setMessages(msgs.data);
          if (msgs.data.length) lastSeenRef.current = msgs.data[msgs.data.length - 1].created_at;
        }
        connectWs();
      } catch (err) {
        if (!cancelled) setError(formatApiError(err));
      }
    };
    init();

    return () => {
      cancelled = true;
      stopPolling();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (wsRef.current) { try { wsRef.current.close(); } catch {} wsRef.current = null; }
    };
  }, [matchId, user.id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, state.typing]);

  const onType = (val) => {
    setText(val);
    if (typingTimerRef.current) return;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send(JSON.stringify({ type: "typing" })); } catch {}
    } else {
      api.post(`/matches/${matchId}/typing`).catch(() => {});
    }
    typingTimerRef.current = setTimeout(() => { typingTimerRef.current = null; }, 1500);
  };

  const send = async (e) => {
    e?.preventDefault();
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    setText("");
    const optimistic = {
      id: `tmp-${Date.now()}`,
      sender_id: user.id,
      body,
      created_at: new Date().toISOString(),
      _pending: true,
    };
    setMessages((m) => [...m, optimistic]);

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ type: "message", body }));
        // Replace optimistic on next ws message (matched by body+sender). Drop pending flag after a beat.
        setTimeout(() => setMessages((m) => m.map((x) => x.id === optimistic.id ? { ...x, _pending: false } : x)), 600);
      } catch {
        // fallthrough to HTTP
        await sendHttp(body, optimistic);
      } finally {
        setSending(false);
      }
      return;
    }
    await sendHttp(body, optimistic);
    setSending(false);
  };

  const sendHttp = async (body, optimistic) => {
    try {
      const { data } = await api.post(`/matches/${matchId}/messages`, { body });
      setMessages((m) => m.map((x) => (x.id === optimistic.id ? data : x)));
      lastSeenRef.current = data.created_at;
    } catch (err) {
      setMessages((m) => m.filter((x) => x.id !== optimistic.id));
      setError(formatApiError(err));
    }
  };

  const profile = match?.profile;

  return (
    <div className="crush-bg min-h-screen" data-testid="chat-page">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-16">
        <Header />

        <div className="crush-frame mt-4 overflow-hidden relative">
          <Sticker kind="heart" size={48} className="absolute -top-3 -right-2 rotate-12 hidden md:inline-flex pointer-events-none" />

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
                  <div className="text-xs font-body text-slate-500 truncate flex items-center gap-1.5" data-testid="chat-transport">
                    {transport === "ws" ? (
                      <><Wifi className="w-3 h-3 text-emerald-500" /> Real-time</>
                    ) : transport === "polling" ? (
                      <><WifiOff className="w-3 h-3 text-amber-500" /> Polling</>
                    ) : (
                      <><Loader2 className="w-3 h-3 animate-spin" /> Connecting…</>
                    )}
                  </div>
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
              messages.map((m, idx) => {
                const mine = m.sender_id === user.id;
                const isLastMine = mine && idx === messages.length - 1;
                const isRead = state.last_read_other_message_id === m.id;
                return (
                  <div key={m.id} className={`flex flex-col ${mine ? "items-end" : "items-start"}`} data-testid={mine ? "msg-mine" : "msg-theirs"}>
                    <div
                      className={`max-w-[78%] px-4 py-2.5 rounded-3xl font-body text-sm leading-relaxed ${
                        mine
                          ? "crush-cta text-white rounded-br-md"
                          : "bg-pink-50 text-slate-900 border-2 border-pink-100 rounded-bl-md"
                      } ${m._pending ? "opacity-70" : ""}`}
                    >
                      {m.body}
                    </div>
                    {isLastMine ? (
                      <div className="text-[10px] font-body text-slate-400 mt-1 mr-1" data-testid="read-receipt">
                        {m._pending ? "Sending…" : isRead ? "Read ✓✓" : "Sent ✓"}
                      </div>
                    ) : null}
                  </div>
                );
              })
            )}
            {state.typing ? (
              <div className="flex items-center gap-2" data-testid="typing-indicator">
                <div className="bg-pink-50 text-slate-700 border-2 border-pink-100 rounded-3xl rounded-bl-md px-4 py-2.5 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-pink-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-pink-400 animate-bounce" style={{ animationDelay: "120ms" }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-pink-400 animate-bounce" style={{ animationDelay: "240ms" }} />
                </div>
              </div>
            ) : null}
          </div>

          {/* Input */}
          <form
            onSubmit={send}
            className="flex items-center gap-2 p-3 sm:p-4 border-t-2 border-slate-100 bg-gradient-to-r from-pink-50 via-white to-orange-50"
            data-testid="chat-form"
          >
            <input
              value={text}
              onChange={(e) => onType(e.target.value)}
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

function mergeUnique(prev, incoming) {
  const seen = new Set(prev.map((m) => m.id));
  const out = [...prev];
  for (const m of incoming) {
    if (!seen.has(m.id)) {
      out.push(m);
      seen.add(m.id);
    }
  }
  return out;
}
