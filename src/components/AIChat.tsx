import { useState, useEffect, useRef } from "react";
import { X, Send, Sparkles, ChevronLeft, Volume2, Square, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { EDGE_FN_URL, EDGE_FN_HEADERS } from "@/lib/supabase";
import { useCandidateProfile } from "@/hooks/useCandidateData";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface AIChatProps {
  isOpen: boolean;
  onClose: () => void;
}

// Stable session ID for this browser tab
const SESSION_ID = crypto.randomUUID();

// Exact FAQ question keys — must match faq_responses.question in the DB
const DEFAULT_QUESTIONS = [
  "Tell me about yourself",
  "What's your biggest weakness?",
  "Why are you looking?",
  "Where do you see yourself in 5 years?",
  "What would your last manager say about you?",
  "What kind of work environment do you thrive in?",
  "Tell me about a time you failed",
];

// Maps common paraphrases to canonical FAQ keys so typed questions also get verbatim answers
const FAQ_ALIASES: Array<{ canonical: string; keywords: string[] }> = [
  {
    canonical: "Tell me about yourself",
    keywords: ["about yourself", "introduce yourself", "tell me about you", "your background", "who are you"],
  },
  {
    canonical: "What's your biggest weakness?",
    keywords: ["weakness", "weaknesses", "not good at", "areas for improvement", "where do you struggle"],
  },
  {
    canonical: "Why are you looking?",
    keywords: ["why are you looking", "why did you leave", "why did you leave your last", "on the market", "job search", "looking for a new"],
  },
  {
    canonical: "Where do you see yourself in 5 years?",
    keywords: ["5 years", "five years", "where do you see yourself", "your future", "long-term goal"],
  },
  {
    canonical: "What would your last manager say about you?",
    keywords: ["manager say", "boss say", "supervisor say", "reference say", "would say about you", "former manager"],
  },
  {
    canonical: "What kind of work environment do you thrive in?",
    keywords: ["work environment", "company culture", "thrive in", "work style", "ideal workplace", "team environment"],
  },
  {
    canonical: "Tell me about a time you failed",
    keywords: ["time you failed", "project that failed", "failure", "biggest failure", "memorable failure", "went wrong", "didn't work out"],
  },
];

function normalizeQuestion(input: string): string {
  const lower = input.toLowerCase();
  for (const { canonical, keywords } of FAQ_ALIASES) {
    if (keywords.some((kw) => lower.includes(kw))) return canonical;
  }
  return input;
}

const AIChat = ({ isOpen, onClose }: AIChatProps) => {
  const { data: profile } = useCandidateProfile();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [playingIndex, setPlayingIndex] = useState<number | null>(null);
  const [loadingAudioIndex, setLoadingAudioIndex] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
    }
    setPlayingIndex(null);
  };

  const speakMessage = async (text: string, index: number) => {
    if (playingIndex === index) {
      stopAudio();
      return;
    }
    stopAudio();

    setLoadingAudioIndex(index);
    try {
      const res = await fetch(`${EDGE_FN_URL}/tts`, {
        method: 'POST',
        headers: EDGE_FN_HEADERS,
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error(`TTS error ${res.status}`);

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onended = () => {
        URL.revokeObjectURL(url);
        setPlayingIndex(null);
        audioRef.current = null;
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        setPlayingIndex(null);
        audioRef.current = null;
      };

      setLoadingAudioIndex(null);
      setPlayingIndex(index);
      audio.play();
    } catch {
      setLoadingAudioIndex(null);
    }
  };

  const candidateName = profile?.name ?? "the candidate";
  const initial = candidateName.charAt(0).toUpperCase();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const sendMessage = async (question: string) => {
    if (!question.trim() || isLoading) return;

    const normalized = normalizeQuestion(question);
    const userMsg: Message = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
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
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I ran into an error. Please try again in a moment." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen) stopAudio();
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-2xl h-[80vh] bg-card border border-border rounded-2xl flex flex-col overflow-hidden shadow-2xl animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-accent to-primary flex items-center justify-center text-accent-foreground font-serif font-bold">
              {initial}
            </div>
            <div>
              <p className="text-foreground font-medium">Ask AI About {candidateName}</p>
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
                Ready to answer your questions
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {messages.length > 0 && (
              <button
                onClick={() => setMessages([])}
                className="flex items-center gap-1 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground border border-border hover:border-accent/50 rounded-lg transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
                Questions
              </button>
            )}
            <button
              onClick={onClose}
              className="p-2 text-muted-foreground hover:text-foreground transition-colors rounded-lg hover:bg-secondary"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && !isLoading && (
            <div className="h-full flex flex-col items-center justify-center text-center px-6">
              <Sparkles className="w-12 h-12 text-accent mb-4" />
              <h3 className="text-xl font-serif text-foreground mb-2">
                What would you like to know?
              </h3>
              <p className="text-muted-foreground text-sm mb-6 max-w-md">
                Ask specific questions about experience, skills, or fit for your role. Get honest, detailed answers.
              </p>
              <div className="w-full max-w-md space-y-2">
                {DEFAULT_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => sendMessage(q)}
                    className="w-full text-left p-3 bg-secondary rounded-xl text-sm text-foreground hover:bg-muted transition-colors border border-transparent hover:border-accent/30"
                  >
                    "{q}"
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={cn("flex flex-col", msg.role === "user" ? "items-end" : "items-start")}>
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-4 py-3",
                  msg.role === "user"
                    ? "bg-accent text-accent-foreground rounded-br-md"
                    : "bg-secondary text-foreground rounded-bl-md"
                )}
              >
                <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              </div>
              {msg.role === "assistant" && (
                <button
                  onClick={() => speakMessage(msg.content, i)}
                  disabled={loadingAudioIndex !== null}
                  className={cn(
                    "mt-1 flex items-center gap-1 px-2 py-1 rounded-lg text-sm transition-colors",
                    playingIndex === i
                      ? "text-accent bg-accent/10 hover:bg-accent/20"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                  )}
                  title={playingIndex === i ? "Stop" : "Hear this in Brett's voice"}
                >
                  {loadingAudioIndex === i ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : playingIndex === i ? (
                    <Square className="w-3 h-3 fill-current" />
                  ) : (
                    <Volume2 className="w-3 h-3" />
                  )}
                  <span>{playingIndex === i ? "Stop" : "Hear this"}</span>
                </button>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-secondary text-foreground rounded-2xl rounded-bl-md px-4 py-3">
                <div className="flex gap-1 items-center h-5">
                  <span className="w-2 h-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-border">
          <form
            onSubmit={(e) => { e.preventDefault(); sendMessage(input); }}
            className="flex gap-3"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question..."
              disabled={isLoading}
              className="flex-1 bg-secondary rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground border border-border focus:border-accent focus:outline-none transition-colors disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="px-4 py-3 bg-accent text-accent-foreground rounded-xl font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default AIChat;
