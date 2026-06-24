import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

export interface Experience {
  id: string;
  company_name: string;
  title: string;
  title_progression: string | null;
  start_date: string;
  end_date: string | null;
  is_current: boolean;
  bullet_points: string[];
  display_order: number;
  situation: string | null;
  approach: string | null;
  technical_work: string | null;
  lessons_learned: string | null;
}

interface ExperienceCardProps {
  experience: Experience;
  index: number;
  onOpenChat?: (initialMessage: string) => void;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    year: "numeric",
  });
}

const CONTEXT_LABEL: React.CSSProperties = {
  fontSize: "0.7rem",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: "var(--color-text-faint)",
  fontFamily: "var(--font-sans)",
  marginBottom: "0.375rem",
};

const ExperienceCard = ({ experience, index, onOpenChat }: ExperienceCardProps) => {
  const [expanded, setExpanded] = useState(false);

  const {
    company_name,
    title,
    title_progression,
    start_date,
    end_date,
    is_current,
    bullet_points,
    situation,
    approach,
    technical_work,
    lessons_learned,
  } = experience;

  const hasContext = situation || approach || technical_work || lessons_learned;
  const period = `${formatDate(start_date)} — ${is_current || !end_date ? "Present" : formatDate(end_date)}`;

  return (
    <div
      className="animate-slide-up opacity-0"
      style={{
        backgroundColor: "var(--color-bg-page)",
        border: "1px solid var(--color-border)",
        borderRadius: "8px",
        padding: "1.75rem",
        boxShadow: "0 1px 4px rgba(26,35,50,0.05)",
        animationDelay: `${index * 0.08 + 0.1}s`,
        animationFillMode: "forwards",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: "0.75rem",
          marginBottom: "1.25rem",
        }}
      >
        <div>
          <h3
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: "1.25rem",
              fontWeight: 400,
              color: "var(--color-text-primary)",
              marginBottom: "0.25rem",
            }}
          >
            {company_name}
          </h3>
          <p style={{ fontSize: "0.9375rem", color: "var(--color-interactive)", fontFamily: "var(--font-sans)" }}>
            {title_progression || title}
          </p>
        </div>
        <span
          style={{
            fontSize: "0.8rem",
            color: "var(--color-text-faint)",
            fontFamily: "var(--font-sans)",
            fontVariantNumeric: "tabular-nums",
            whiteSpace: "nowrap",
            paddingTop: "0.2rem",
          }}
        >
          {period}
        </span>
      </div>

      {/* Bullet points */}
      {bullet_points && bullet_points.length > 0 && (
        <ul style={{ marginBottom: "1.25rem", display: "flex", flexDirection: "column", gap: "0.625rem" }}>
          {bullet_points.map((point, i) => (
            <li key={i} style={{ display: "flex", alignItems: "flex-start", gap: "0.625rem" }}>
              <span
                style={{
                  color: "var(--color-interactive)",
                  fontFamily: "var(--font-sans)",
                  flexShrink: 0,
                  marginTop: "0.1em",
                  fontSize: "0.9375rem",
                }}
              >
                →
              </span>
              <span style={{ color: "var(--color-text-secondary)", fontSize: "0.9375rem", lineHeight: 1.6, fontFamily: "var(--font-sans)" }}>
                {point}
              </span>
            </li>
          ))}
        </ul>
      )}

      {/* Context toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.375rem",
          fontSize: "0.875rem",
          color: "var(--color-interactive)",
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: 0,
          fontFamily: "var(--font-sans)",
          transition: "color 0.15s ease",
        }}
        onMouseEnter={e => (e.currentTarget.style.color = "var(--color-interactive-hover)")}
        onMouseLeave={e => (e.currentTarget.style.color = "var(--color-interactive)")}
      >
        <span>{expanded ? "Hide" : "View"} context</span>
        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {/* Expanded context panel */}
      {expanded && (
        <div
          className="animate-slide-down"
          style={{
            marginTop: "1rem",
            padding: "1.25rem",
            backgroundColor: "var(--color-bg-alt)",
            borderLeft: "4px solid var(--color-bg-raised)",
            borderRadius: "0 6px 6px 0",
          }}
        >
          {hasContext ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {situation && (
                <div>
                  <p style={CONTEXT_LABEL}>Situation</p>
                  <p style={{ color: "var(--color-text-primary)", fontSize: "0.9375rem", lineHeight: 1.65, fontFamily: "var(--font-sans)" }}>{situation}</p>
                </div>
              )}
              {approach && (
                <div>
                  <p style={CONTEXT_LABEL}>Approach</p>
                  <p style={{ color: "var(--color-text-primary)", fontSize: "0.9375rem", lineHeight: 1.65, fontFamily: "var(--font-sans)" }}>{approach}</p>
                </div>
              )}
              {technical_work && (
                <div>
                  <p style={CONTEXT_LABEL}>Technical work</p>
                  <p style={{ color: "var(--color-text-primary)", fontSize: "0.9375rem", lineHeight: 1.65, fontFamily: "var(--font-sans)" }}>{technical_work}</p>
                </div>
              )}
              {lessons_learned && (
                <div>
                  <p style={CONTEXT_LABEL}>Lessons learned</p>
                  <p style={{ color: "var(--color-text-primary)", fontSize: "0.9375rem", lineHeight: 1.65, fontStyle: "italic", fontFamily: "var(--font-sans)" }}>
                    {lessons_learned}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <p style={{ color: "var(--color-text-faint)", fontSize: "0.9rem", fontStyle: "italic", fontFamily: "var(--font-sans)" }}>
              Context is being built — check back soon.
            </p>
          )}

          {onOpenChat && (
            <button
              onClick={() => onOpenChat(`Tell me more about Brett's time at ${company_name}.`)}
              style={{
                marginTop: "1rem",
                display: "inline-flex",
                alignItems: "center",
                gap: "0.375rem",
                fontSize: "0.875rem",
                color: "var(--color-interactive)",
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 0,
                fontFamily: "var(--font-sans)",
                transition: "color 0.15s ease",
              }}
              onMouseEnter={e => (e.currentTarget.style.color = "var(--color-interactive-hover)")}
              onMouseLeave={e => (e.currentTarget.style.color = "var(--color-interactive)")}
            >
              Ask me more in the chat →
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default ExperienceCard;
