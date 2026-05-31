import { useState } from "react";
import { ChevronDown, ChevronUp, Sparkles, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

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
      className={cn(
        "group relative p-6 md:p-8 bg-card border border-border rounded-2xl transition-all duration-300 hover:border-accent/50",
        "animate-slide-up opacity-0"
      )}
      style={{ animationDelay: `${index * 0.1 + 0.2}s`, animationFillMode: "forwards" }}
    >
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6">
        <div>
          <h3 className="text-2xl font-serif text-foreground mb-1">{company_name}</h3>
          <p className="text-primary">{title_progression || title}</p>
        </div>
        <span className="text-sm font-mono text-muted-foreground">{period}</span>
      </div>

      {/* Bullet points */}
      {bullet_points && bullet_points.length > 0 && (
        <ul className="space-y-3 mb-6">
          {bullet_points.map((point, i) => (
            <li key={i} className="flex items-start gap-3 text-muted-foreground">
              <span className="text-accent mt-1.5">→</span>
              <span>{point}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Context Toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm text-accent hover:text-accent/80 transition-colors"
      >
        <Sparkles className="w-4 h-4" />
        <span>{expanded ? "Hide" : "View"} Context</span>
        {expanded ? (
          <ChevronUp className="w-4 h-4" />
        ) : (
          <ChevronDown className="w-4 h-4" />
        )}
      </button>

      {/* Expanded Context Panel */}
      {expanded && (
        <div className="mt-4 p-4 bg-secondary rounded-xl border border-border animate-slide-down">
          {hasContext ? (
            <div className="grid gap-4 text-sm">
              {situation && (
                <div>
                  <span className="text-muted-foreground font-mono text-xs uppercase tracking-wider">
                    Situation
                  </span>
                  <p className="text-foreground mt-1">{situation}</p>
                </div>
              )}
              {approach && (
                <div>
                  <span className="text-muted-foreground font-mono text-xs uppercase tracking-wider">
                    Approach
                  </span>
                  <p className="text-foreground mt-1">{approach}</p>
                </div>
              )}
              {technical_work && (
                <div>
                  <span className="text-muted-foreground font-mono text-xs uppercase tracking-wider">
                    Technical Work
                  </span>
                  <p className="text-foreground mt-1">{technical_work}</p>
                </div>
              )}
              {lessons_learned && (
                <div>
                  <span className="text-muted-foreground font-mono text-xs uppercase tracking-wider">
                    Lessons Learned
                  </span>
                  <p className="text-foreground mt-1 italic">{lessons_learned}</p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-muted-foreground text-sm italic">
              Context is being built — check back soon.
            </p>
          )}

          {onOpenChat && (
            <button
              onClick={() => onOpenChat(`Tell me more about Brett's time at ${company_name}.`)}
              className="mt-4 flex items-center gap-2 text-sm text-accent hover:text-accent/80 transition-colors"
            >
              <MessageSquare className="w-4 h-4" />
              <span>Ask me more in the chat →</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default ExperienceCard;
