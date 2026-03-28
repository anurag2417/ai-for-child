import { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";
import { Send, Plus, MessageCircle, Shield, ChevronLeft } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BOT_AVATAR = "https://static.prod-images.emergentagent.com/jobs/c981f2d7-a198-4751-9292-bd3ea3733509/images/d376ea840d4cf39f522230889ca79fd1bbc7322d0f233bce72b70b50dca8ebdc.png";

export default function ChatPage() {
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(() => {
    return localStorage.getItem("buddybot_active_conv") || null;
  });
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  // Persist active conversation
  useEffect(() => {
    if (activeConvId) {
      localStorage.setItem("buddybot_active_conv", activeConvId);
    } else {
      localStorage.removeItem("buddybot_active_conv");
    }
  }, [activeConvId]);

  const fetchConversations = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/chat/conversations`);
      setConversations(res.data);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { fetchConversations(); }, [fetchConversations]);

  // Restore conversation on mount
  useEffect(() => {
    if (activeConvId) {
      loadConversation(activeConvId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadConversation = async (convId) => {
    setActiveConvId(convId);
    try {
      const res = await axios.get(`${API}/chat/conversations/${convId}`);
      setMessages(res.data.messages || []);
    } catch (e) { console.error(e); }
    if (window.innerWidth < 768) setSidebarOpen(false);
  };

  const startNewChat = () => {
    setActiveConvId(null);
    setMessages([]);
    setInput("");
    localStorage.removeItem("buddybot_active_conv");
    inputRef.current?.focus();
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    setLoading(true);

    // Optimistic user message
    const tempUserMsg = {
      id: "temp-" + Date.now(),
      role: "user",
      text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res = await axios.post(`${API}/chat/send`, {
        conversation_id: activeConvId,
        text,
      });
      const { conversation_id, user_message, bot_message } = res.data;

      if (!activeConvId) setActiveConvId(conversation_id);

      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== tempUserMsg.id);
        return [...filtered, user_message, bot_message];
      });

      fetchConversations();
    } catch (e) {
      console.error(e);
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div
      data-testid="chat-page"
      className="h-screen flex bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-sky-100 via-white to-slate-50"
    >
      {/* Sidebar */}
      <aside
        data-testid="chat-sidebar"
        className={`${
          sidebarOpen ? "w-72" : "w-0"
        } transition-all duration-300 overflow-hidden bg-white/70 backdrop-blur-xl border-r border-white/40 flex flex-col`}
      >
        <div className="p-5 border-b border-slate-100">
          <div className="flex items-center gap-3 mb-5">
            <img
              src={BOT_AVATAR}
              alt="BuddyBot"
              className="w-11 h-11 rounded-full border-2 border-white shadow-md"
            />
            <h1 className="font-['Nunito'] text-2xl font-extrabold text-sky-900 tracking-tight">
              BuddyBot
            </h1>
          </div>
          <button
            data-testid="new-chat-btn"
            onClick={startNewChat}
            className="w-full flex items-center justify-center gap-2 bg-sky-400 hover:bg-sky-500 text-white rounded-full py-3.5 px-5 text-lg font-bold shadow-[0_4px_0_0_rgba(14,165,233,0.3)] hover:translate-y-[2px] hover:shadow-[0_2px_0_0_rgba(14,165,233,0.3)] active:translate-y-[4px] active:shadow-none transition-all duration-150"
          >
            <Plus className="w-5 h-5" strokeWidth={3} />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-2">
          {conversations.map((c) => (
            <button
              key={c.id}
              data-testid={`conversation-item-${c.id}`}
              onClick={() => loadConversation(c.id)}
              className={`w-full text-left p-3.5 rounded-2xl transition-all duration-200 flex items-center gap-3 ${
                activeConvId === c.id
                  ? "bg-sky-100 text-sky-900 shadow-sm"
                  : "hover:bg-slate-100 text-slate-600"
              }`}
            >
              <MessageCircle
                className={`w-5 h-5 flex-shrink-0 ${
                  activeConvId === c.id ? "text-sky-500" : "text-slate-400"
                }`}
                strokeWidth={2.5}
              />
              <span className="truncate text-base font-medium">{c.title}</span>
              {c.has_flags && (
                <span className="ml-auto flex-shrink-0 w-2.5 h-2.5 bg-rose-400 rounded-full" />
              )}
            </button>
          ))}
          {conversations.length === 0 && (
            <p className="text-center text-slate-400 text-base font-medium mt-8">
              No chats yet! Start one above
            </p>
          )}
        </div>

        <div className="p-4 border-t border-slate-100">
          <a
            href="/parent"
            data-testid="parent-dashboard-link"
            className="flex items-center gap-2.5 text-emerald-700 hover:text-emerald-800 font-semibold text-base transition-colors p-2.5 rounded-xl hover:bg-emerald-50"
          >
            <Shield className="w-5 h-5" strokeWidth={2.5} />
            Parent Dashboard
          </a>
        </div>
      </aside>

      {/* Main chat area */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header
          data-testid="chat-header"
          className="flex items-center gap-4 px-6 py-4 bg-white/60 backdrop-blur-xl border-b border-white/40"
        >
          <button
            data-testid="toggle-sidebar-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-xl hover:bg-slate-100 transition-colors text-slate-500"
          >
            <ChevronLeft
              className={`w-6 h-6 transition-transform ${
                sidebarOpen ? "" : "rotate-180"
              }`}
              strokeWidth={2.5}
            />
          </button>
          <img
            src={BOT_AVATAR}
            alt="BuddyBot"
            className="w-10 h-10 rounded-full border-2 border-white shadow-sm float-animation"
          />
          <div>
            <h2 className="font-['Nunito'] text-xl font-bold text-slate-800">
              BuddyBot
            </h2>
            <p className="text-sm font-medium text-emerald-500">
              Online and ready to chat!
            </p>
          </div>
        </header>

        {/* Messages */}
        <div
          data-testid="messages-container"
          className="flex-1 overflow-y-auto custom-scrollbar px-4 md:px-8 py-6"
        >
          <div className="max-w-3xl mx-auto space-y-5">
            {messages.length === 0 && !loading && (
              <div data-testid="empty-chat-state" className="flex flex-col items-center justify-center h-full pt-20">
                <img
                  src={BOT_AVATAR}
                  alt="BuddyBot"
                  className="w-28 h-28 rounded-full border-4 border-white shadow-lg mb-6 float-animation"
                />
                <h2 className="font-['Nunito'] text-3xl font-extrabold text-sky-900 mb-3">
                  Hi there, friend!
                </h2>
                <p className="text-lg font-medium text-slate-500 text-center max-w-md">
                  I'm BuddyBot, your friendly AI buddy! Ask me anything — I love talking about animals, space, games, and all sorts of fun stuff!
                </p>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div
                key={msg.id || idx}
                data-testid={`message-${msg.role}-${idx}`}
                className={`flex items-end gap-3 bubble-enter ${
                  msg.role === "user" ? "flex-row-reverse" : ""
                }`}
                style={{ animationDelay: `${idx * 0.05}s` }}
              >
                {msg.role === "assistant" && (
                  <img
                    src={BOT_AVATAR}
                    alt="BuddyBot"
                    className="w-10 h-10 rounded-full border-2 border-white shadow-sm flex-shrink-0"
                  />
                )}
                <div
                  className={`max-w-[75%] p-4 md:p-5 text-lg font-medium leading-relaxed ${
                    msg.role === "user"
                      ? "bg-sky-100 text-sky-900 rounded-[2rem] rounded-br-lg"
                      : "bg-emerald-100 text-emerald-900 rounded-[2rem] rounded-bl-lg"
                  } ${msg.blocked ? "opacity-60 line-through" : ""}`}
                >
                  {msg.text}
                  {msg.blocked && (
                    <span className="block text-sm text-rose-500 font-semibold mt-2 no-underline" style={{textDecoration:'none'}}>
                      This message was filtered
                    </span>
                  )}
                </div>
                {msg.role === "user" && (
                  <div className="w-10 h-10 rounded-full bg-amber-200 flex items-center justify-center flex-shrink-0 border-2 border-white shadow-sm text-xl">
                    <span role="img" aria-label="child">&#x1F9D2;</span>
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div data-testid="typing-indicator" className="flex items-end gap-3 bubble-enter">
                <img
                  src={BOT_AVATAR}
                  alt="BuddyBot"
                  className="w-10 h-10 rounded-full border-2 border-white shadow-sm"
                />
                <div className="bg-emerald-100 rounded-[2rem] rounded-bl-lg p-5 flex gap-1.5">
                  <span className="typing-dot w-3 h-3 bg-emerald-400 rounded-full inline-block" />
                  <span className="typing-dot w-3 h-3 bg-emerald-400 rounded-full inline-block" />
                  <span className="typing-dot w-3 h-3 bg-emerald-400 rounded-full inline-block" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <div className="px-4 md:px-8 pb-5 pt-3">
          <div
            data-testid="chat-input-area"
            className="max-w-3xl mx-auto flex items-center gap-3 bg-white rounded-full border-2 border-slate-200 p-2 pl-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] focus-within:border-sky-400 focus-within:ring-4 focus-within:ring-sky-100 transition-all"
          >
            <input
              ref={inputRef}
              data-testid="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message here..."
              className="flex-1 bg-transparent outline-none text-lg font-medium text-slate-800 placeholder:text-slate-400"
              disabled={loading}
            />
            <button
              data-testid="send-message-btn"
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="bg-sky-400 hover:bg-sky-500 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-full p-3.5 shadow-[0_4px_0_0_rgba(14,165,233,0.3)] hover:translate-y-[2px] hover:shadow-[0_2px_0_0_rgba(14,165,233,0.3)] active:translate-y-[4px] active:shadow-none disabled:shadow-none disabled:translate-y-0 transition-all duration-150"
            >
              <Send className="w-5 h-5" strokeWidth={3} />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
