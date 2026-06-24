import { useState, useEffect, useRef } from "react";
import { X, Send, ChevronLeft, Volume2, Square, Loader2 } from "lucide-react";
import { EDGE_FN_URL, EDGE_FN_HEADERS } from "@/lib/supabase";
import { useCandidateProfile } from "@/hooks/useCandidateData";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface AIChatProps {
  isOpen: boolean;
  onClose: () => void;
  initialMessage?: string;
}

const SESSION_ID = crypto.randomUUID();

const DEFAULT_QUESTIONS = [
  "Tell me about yourself",
  "What's your biggest weakness?",
  "Why are you looking?",
  "Where do you see yourself in 5 years?",
  "What would your last manager say about you?",
  "What kind of work environment do you thrive in?",
  "Tell me about a time you failed",
];

const FAQ_ALIASES: Array<{ canonical: string; keywords: string[] }> = [
  { canonical: "Tell me about yourself", keywords: ["about yourself", "introduce yourself", "tell me about you", "your background", "who are you"] },
  { canonical: "What's your biggest weakness?", keywords: ["weakness", "weaknesses", "not good at", "areas for improvement", "where do you struggle"] },
  { canonical: "Why are you looking?", keywords: ["why are you looking", "why did you leave", "on the market", "job search", "looking for a new"] },
  { canonical: "Where do you see yourself in 5 years?", keywords: ["5 years", "five years", "where do you see yourself", "your future", "long-term goal"] },
  { canonical: "What would your last manager say about you?", keywords: ["manager say", "boss say", "supervisor say", "reference say", "would say about you", "former manager"] },
  { canonical: "What kind of work environment do you thrive in?", keywords: ["work environment", "company culture", "thrive in", "work style", "ideal workplace"] },
  { canonical: "Tell me about a time you failed", keywords: ["time you failed", "project that failed", "failure", "biggest failure", "went wrong"] },
];

function normalizeQuestion(input: string): string {
  const lower = input.toLowerCase();
  for (const { canonical, keywords } of FAQ_ALIASES) {
    if (keywords.some((kw) => lower.includes(kw))) return canonical;
  }
  return input;
}

const AIChat = ({ isOpen, onClose, initialMessage }: AIChatProps) => {
  const { data: profile } = useCandidateProfile();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [playingIndex, setPlayingIndex] = useState<number | null>(null);
  const [loadingAudioIndex, setLoadingAudioIndex] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && initialMessage) setInput(initialMessage);
  }, [isOpen, initialMessage]);

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
      audioRef.current = null;
    }
    setPlayingIndex(null);
  };

  const speakMessage = async (text: string, index: number) => {
    if (playingIndex === index) { stopAudio(); return; }
    stopAudio();
    setLoadingAudioIndex(index);
    try {
      const res = await fetch(`${EDGE_FN_URL}/tts`, {
        method: "POST",
        headers: EDGE_FN_HEADERS,
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error(`TTS error ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => { URL.revokeObjectURL(url); setPlayingIndex(null); audioRef.current = null; };
      audio.onerror = () => { URL.revokeObjectURL(url); setPlayingIndex(null); audioRef.current = null; };
      setLoadingAudioIndex(null);
      setPlayingIndex(index);
      audio.play();
    } catch {
      setLoadingAudioIndex(null);
    }
  };

  const candidateName = profile?.name ?? "the candidate";

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const sendMessage = async (question: string) => {
    if (!question.trim() || isLoading) return;
    const normalized = normalizeQuestion(question);
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setIsLoading(true);
    try {
      const res = await fetch(`${EDGE_FN_URL}/chat`, {
        method: "POST",
        headers: EDGE_FN_HEADERS,
        body: JSON.stringify({ message: normalized, sessionId: SESSION_ID }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const { message: reply } = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, I ran into an error. Please try again in a moment." }]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { if (!isOpen) stopAudio(); }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="animate-fade-in"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
        backgroundColor: "rgba(26,35,50,0.55)",
        backdropFilter: "blur(4px)",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="animate-slide-up"
        style={{
          width: "100%",
          maxWidth: "38rem",
          height: "82vh",
          maxHeight: "680px",
          backgroundColor: "var(--color-bg-page)",
          border: "1px solid var(--color-border)",
          borderRadius: "8px",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 8px 40px rgba(26,35,50,0.18)",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "1rem 1.25rem",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div
              style={{
                width: "2.25rem",
                height: "2.25rem",
                borderRadius: "50%",
                backgroundColor: "var(--color-bg-raised)",
                border: "1px solid var(--color-border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: "var(--font-serif)",
                fontSize: "1rem",
                color: "var(--color-interactive-hover)",
                fontWeight: 400,
                flexShrink: 0,
              }}
            >
              {candidateName.charAt(0).toUpperCase()}
            </div>
            <div>
              <p style={{ fontSize: "0.9375rem", fontWeight: 500, color: "var(--color-text-primary)", fontFamily: "var(--font-sans)" }}>
                Ask about {candidateName}
              </p>
              <p style={{ fontSize: "0.75rem", color: "var(--color-text-faint)", display: "flex", alignItems: "center", gap: "0.375rem", fontFamily: "var(--font-sans)" }}>
                <span
                  className="animate-pulse-soft"
                  style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#15803d", display: "inline-block" }}
                />
                Ready to answer your questions
              </p>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            {messages.length > 0 && (
              <button
                onClick={() => setMessages([])}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.25rem",
                  padding: "0.375rem 0.75rem",
                  fontSize: "0.8125rem",
                  color: "var(--color-text-faint)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "4px",
                  background: "none",
                  cursor: "pointer",
                  fontFamily: "var(--font-sans)",
                  transition: "color 0.15s ease, border-color 0.15s ease",
                }}
                onMouseEnter={e => { e.currentTarget.style.color = "var(--color-text-primary)"; e.currentTarget.style.borderColor = "var(--color-text-faint)"; }}
                onMouseLeave={e => { e.currentTarget.style.color = "var(--color-text-faint)"; e.currentTarget.style.borderColor = "var(--color-border)"; }}
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Questions
              </button>
            )}
            <button
              onClick={onClose}
              style={{
                padding: "0.375rem",
                color: "var(--color-text-faint)",
                background: "none",
                border: "none",
                cursor: "pointer",
                borderRadius: "4px",
                display: "flex",
                transition: "color 0.15s ease",
              }}
              onMouseEnter={e => (e.currentTarget.style.color = "var(--color-text-primary)")}
              onMouseLeave={e => (e.currentTarget.style.color = "var(--color-text-faint)")}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", padding: "1rem 1.25rem", display: "flex", flexDirection: "column", gap: "0.875rem" }}>
          {messages.length === 0 && !isLoading && (
            <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", padding: "1rem" }}>
              <h3 style={{ fontFamily: "var(--font-serif)", fontSize: "1.2rem", fontWeight: 400, color: "var(--color-text-primary)", marginBottom: "0.5rem" }}>
                What would you like to know?
              </h3>
              <p style={{ color: "var(--color-text-faint)", fontSize: "0.875rem", fontFamily: "var(--font-sans)", lineHeight: 1.6, marginBottom: "1.5rem", maxWidth: "28rem" }}>
                Ask specific questions about experience, skills, or fit. Get honest, direct answers.
              </p>
              <div style={{ width: "100%", maxWidth: "28rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {DEFAULT_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => sendMessage(q)}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      padding: "0.625rem 0.875rem",
                      backgroundColor: "var(--color-bg-alt)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "6px",
                      fontSize: "0.875rem",
                      color: "var(--color-text-secondary)",
                      fontFamily: "var(--font-sans)",
                      cursor: "pointer",
                      transition: "border-color 0.15s ease, background-color 0.15s ease",
                    }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--color-interactive)"; e.currentTarget.style.backgroundColor = "var(--color-bg-raised)"; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--color-border)"; e.currentTarget.style.backgroundColor = "var(--color-bg-alt)"; }}
                  >
                    "{q}"
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: msg.role === "user" ? "flex-end" : "flex-start" }}>
              <div
                style={{
                  maxWidth: "85%",
                  padding: "0.625rem 0.875rem",
                  borderRadius: msg.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                  backgroundColor: msg.role === "user" ? "var(--color-interactive)" : "var(--color-bg-alt)",
                  color: msg.role === "user" ? "var(--color-interactive-text)" : "var(--color-text-primary)",
                }}
              >
                <p style={{ fontSize: "0.9rem", lineHeight: 1.6, fontFamily: "var(--font-sans)", whiteSpace: "pre-wrap" }}>
                  {msg.content}
                </p>
              </div>
              {msg.role === "assistant" && (
                <button
                  onClick={() => speakMessage(msg.content, i)}
                  disabled={loadingAudioIndex !== null}
                  style={{
                    marginTop: "0.25rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.25rem",
                    padding: "0.25rem 0.5rem",
                    fontSize: "0.8rem",
                    fontFamily: "var(--font-sans)",
                    color: playingIndex === i ? "var(--color-interactive)" : "var(--color-text-faint)",
                    backgroundColor: playingIndex === i ? "var(--color-bg-raised)" : "transparent",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer",
                    transition: "color 0.15s ease",
                  }}
                  title={playingIndex === i ? "Stop" : "Hear this in Brett's voice"}
                >
                  {loadingAudioIndex === i
                    ? <Loader2 className="w-3 h-3 animate-spin" />
                    : playingIndex === i
                    ? <Square className="w-3 h-3" style={{ fill: "currentColor" }} />
                    : <Volume2 className="w-3 h-3" />
                  }
                  <span>{playingIndex === i ? "Stop" : "Hear this"}</span>
                </button>
              )}
            </div>
          ))}

          {isLoading && (
            <div style={{ display: "flex", justifyContent: "flex-start" }}>
              <div
                style={{
                  padding: "0.625rem 0.875rem",
                  borderRadius: "12px 12px 12px 2px",
                  backgroundColor: "var(--color-bg-alt)",
                }}
              >
                <div style={{ display: "flex", gap: "4px", alignItems: "center", height: "1.25rem" }}>
                  {[0, 150, 300].map((delay) => (
                    <span
                      key={delay}
                      style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        backgroundColor: "var(--color-text-faint)",
                        display: "inline-block",
                        animation: `bounce-dots 1.2s ease-in-out ${delay}ms infinite`,
                      }}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div style={{ padding: "1rem 1.25rem", borderTop: "1px solid var(--color-border)" }}>
          <form
            onSubmit={(e) => { e.preventDefault(); sendMessage(input); }}
            style={{ display: "flex", gap: "0.625rem" }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question…"
              disabled={isLoading}
              style={{
                flex: 1,
                backgroundColor: "var(--color-bg-alt)",
                border: "1px solid var(--color-border)",
                borderRadius: "6px",
                padding: "0.625rem 0.875rem",
                fontSize: "0.9rem",
                fontFamily: "var(--font-sans)",
                color: "var(--color-text-primary)",
                outline: "none",
                transition: "border-color 0.15s ease",
                opacity: isLoading ? 0.6 : 1,
              }}
              onFocus={e => (e.currentTarget.style.borderColor = "var(--color-interactive)")}
              onBlur={e => (e.currentTarget.style.borderColor = "var(--color-border)")}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              style={{
                padding: "0.625rem 0.875rem",
                backgroundColor: "var(--color-interactive)",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                cursor: !input.trim() || isLoading ? "not-allowed" : "pointer",
                opacity: !input.trim() || isLoading ? 0.5 : 1,
                display: "flex",
                alignItems: "center",
                transition: "background-color 0.15s ease",
              }}
              onMouseEnter={e => { if (input.trim() && !isLoading) e.currentTarget.style.backgroundColor = "var(--color-interactive-hover)"; }}
              onMouseLeave={e => { e.currentTarget.style.backgroundColor = "var(--color-interactive)"; }}
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default AIChat;
