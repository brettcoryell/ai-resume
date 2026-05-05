import { useState } from "react";
import { ChevronDown, ChevronUp, Sparkles } from "lucide-react";
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
}

interface ExperienceCardProps {
  experience: Experience;
  index: number;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    year: "numeric",
  });
}

const ExperienceCard = ({ experience, index }: ExperienceCardProps) => {
  const [expanded, setExpanded] = useState(false);

  const {
    company_name,
    title,
    title_progression,
    start_date,
    end_date,
    is_current,
    bullet_points,
  } = experience;

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

      {/* AI Context Toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm text-accent hover:text-accent/80 transition-colors"
      >
        <Sparkles className="w-4 h-4" />
        <span>{expanded ? "Hide" : "View"} AI Context</span>
        {expanded ? (
          <ChevronUp className="w-4 h-4" />
        ) : (
          <ChevronDown className="w-4 h-4" />
        )}
      </button>

      {/* Expanded AI Context placeholder */}
      {expanded && (
        <div className="mt-4 p-4 bg-secondary rounded-xl border border-border animate-slide-down">
          <p className="text-muted-foreground text-sm italic">
            AI context available via chat — ask me about my time at {company_name}.
          </p>
        </div>
      )}
    </div>
  );
};

export default ExperienceCard;
