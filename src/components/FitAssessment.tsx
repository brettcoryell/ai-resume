import { useState } from "react";
import { FileText, Check, AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { EDGE_FN_URL, EDGE_FN_HEADERS } from "@/lib/supabase";

type TabType = "strong" | "weak" | "custom";

type Verdict = "strong_fit" | "worth_conversation" | "probably_not";

interface Gap {
  requirement: string;
  gap_title: string;
  explanation: string;
}

interface AnalysisResult {
  verdict: Verdict;
  headline: string;
  opening: string;
  gaps: Gap[];
  transfers: string;
  recommendation: string;
}

const DEMO_JDS = {
  strong: `Chief Information Officer — Global Financial Services Firm ($5B+ revenue)

We are seeking a seasoned CIO to lead enterprise technology strategy across a 2,000-person global organization. The ideal candidate has served as a senior technology executive at a multi-billion dollar company, with demonstrated success in large-scale digital transformation, enterprise architecture modernization, and building high-performance IT organizations.

Key Responsibilities:
• Define and execute a multi-year technology roadmap aligned to business strategy
• Own enterprise cybersecurity posture in partnership with the CISO function
• Lead a technology organization of 150+ across infrastructure, applications, and security
• Partner with the CEO, CFO, and Board on technology risk, investment, and AI strategy
• Drive AI/ML adoption across the enterprise to accelerate operational efficiency
• Manage $80M+ annual IT budget and key vendor relationships

Requirements:
• 15+ years of technology leadership; 5+ years as CIO, CISO, or equivalent C-suite role
• Track record leading transformations at companies with $1B+ revenue
• Deep expertise in enterprise security, risk management, and compliance
• Experience presenting to boards and audit committees on technology risk and investment
• Background in regulated industries (financial services, healthcare, or pharma a plus)
• Demonstrated ability to build and scale high-performing technology organizations`,

  weak: `IT Manager — Regional Logistics Company (250 employees)

We're looking for a hands-on IT Manager to oversee day-to-day technology operations and a small internal team. This is a player-coach role in a lean environment where you'll be expected to handle both strategic direction and direct technical work.

Key Responsibilities:
• Manage a team of 4 IT support and systems staff
• Maintain and troubleshoot on-premise server infrastructure and network
• Own helpdesk operations and SLA management for internal users
• Evaluate and implement SaaS tools within a $500K annual IT budget
• Ensure basic compliance with data protection regulations
• Serve as the primary escalation point for all IT issues

Requirements:
• 5–8 years of IT experience, including 2+ years in a management role
• Hands-on experience with Windows Server, Active Directory, and networking
• Comfortable rolling up your sleeves — this is a lean, generalist team
• Experience with Microsoft 365 administration
• CompTIA, MCSA, or similar certifications preferred`,
};

const verdictStyle: Record<Verdict, { banner: string; icon: string; text: string }> = {
  strong_fit: {
    banner: "bg-success-muted border-success/20",
    icon: "bg-success/20",
    text: "text-success",
  },
  worth_conversation: {
    banner: "bg-secondary border-border",
    icon: "bg-muted/20",
    text: "text-foreground",
  },
  probably_not: {
    banner: "bg-warning-muted border-warning/20",
    icon: "bg-warning/20",
    text: "text-warning",
  },
};

const FitAssessment = () => {
  const [activeTab, setActiveTab] = useState<TabType>("strong");
  const [jdText, setJdText] = useState(DEMO_JDS.strong);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleTabClick = (tab: TabType) => {
    setActiveTab(tab);
    setResult(null);
    setError(null);
    if (tab === "strong") setJdText(DEMO_JDS.strong);
    else if (tab === "weak") setJdText(DEMO_JDS.weak);
    else setJdText("");
  };

  const handleAnalyze = async () => {
    if (!jdText.trim()) return;
    setAnalyzing(true);
    setResult(null);
    setError(null);

    try {
      const res = await fetch(`${EDGE_FN_URL}/analyze-jd`, {
        method: "POST",
        headers: EDGE_FN_HEADERS,
        body: JSON.stringify({ jobDescription: jdText }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }

      const data: AnalysisResult = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setAnalyzing(false);
    }
  };

  const style = result ? verdictStyle[result.verdict] : null;

  return (
    <section id="fit-assessment" className="py-24 px-6 bg-secondary/30">
      <div className="max-w-4xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-12">
          <h2 className="text-4xl md:text-5xl font-serif text-foreground mb-4">
            Honest Fit Assessment
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Paste a job description. Get an honest assessment of whether I'm the right person—including when I'm not.
          </p>
        </div>

        {/* Tab buttons */}
        <div className="flex justify-center gap-4 mb-8">
          <button
            onClick={() => handleTabClick("strong")}
            className={cn(
              "px-6 py-3 rounded-xl font-medium transition-all border",
              activeTab === "strong"
                ? "bg-success-muted text-success border-success/30"
                : "bg-card text-muted-foreground border-border hover:border-muted-foreground"
            )}
          >
            Strong Fit Example
          </button>
          <button
            onClick={() => handleTabClick("weak")}
            className={cn(
              "px-6 py-3 rounded-xl font-medium transition-all border",
              activeTab === "weak"
                ? "bg-warning-muted text-warning border-warning/30"
                : "bg-card text-muted-foreground border-border hover:border-muted-foreground"
            )}
          >
            Weak Fit Example
          </button>
          <button
            onClick={() => handleTabClick("custom")}
            className={cn(
              "px-6 py-3 rounded-xl font-medium transition-all border",
              activeTab === "custom"
                ? "bg-accent/20 text-accent border-accent/30"
                : "bg-card text-muted-foreground border-border hover:border-muted-foreground"
            )}
          >
            Paste Your Own JD
          </button>
        </div>

        {/* Main interface */}
        <div className="bg-card border border-border rounded-2xl overflow-hidden">
          {/* Input section */}
          <div className="p-6 border-b border-border">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
                <FileText className="w-4 h-4 text-accent" />
              </div>
              <span className="text-muted-foreground text-sm">
                Job description to analyze
              </span>
            </div>
            <textarea
              className={cn(
                "w-full bg-secondary rounded-xl p-4 border border-border text-sm font-mono text-muted-foreground leading-relaxed resize-none transition-colors",
                activeTab === "custom"
                  ? "focus:outline-none focus:border-accent/50 cursor-text"
                  : "cursor-default opacity-80"
              )}
              rows={8}
              value={jdText}
              onChange={(e) => activeTab === "custom" && setJdText(e.target.value)}
              readOnly={activeTab !== "custom"}
              placeholder="Paste a job description here..."
            />
            <div className="mt-4 flex justify-end">
              <button
                onClick={handleAnalyze}
                disabled={analyzing || !jdText.trim()}
                className="px-6 py-2.5 bg-accent text-accent-foreground rounded-xl font-medium transition-all hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {analyzing && <Loader2 className="w-4 h-4 animate-spin" />}
                Analyze Fit
              </button>
            </div>
          </div>

          {/* Analysis section */}
          <div className="p-6">
            {analyzing && (
              <div className="flex items-center justify-center py-12">
                <div className="flex items-center gap-3 text-muted-foreground">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Analyzing against my experience...</span>
                </div>
              </div>
            )}

            {error && !analyzing && (
              <div className="flex items-center justify-center py-12">
                <div className="text-warning text-sm bg-warning-muted border border-warning/20 rounded-xl px-6 py-4 max-w-lg text-center">
                  {error}
                </div>
              </div>
            )}

            {result && !analyzing && style && (
              <div className="animate-slide-up">
                {/* Verdict header */}
                <div className={cn("flex items-center gap-4 mb-6 p-4 rounded-xl border", style.banner)}>
                  <div className={cn("w-12 h-12 rounded-full flex items-center justify-center", style.icon)}>
                    {result.verdict === "probably_not" ? (
                      <AlertTriangle className={cn("w-6 h-6", style.text)} />
                    ) : (
                      <Check className={cn("w-6 h-6", style.text)} />
                    )}
                  </div>
                  <div>
                    <h3 className={cn("text-xl font-serif", style.text)}>
                      {result.headline}
                    </h3>
                    <p className="text-muted-foreground text-sm mt-1">{result.opening}</p>
                  </div>
                </div>

                {/* Gaps */}
                {result.gaps && result.gaps.length > 0 && (
                  <div className="space-y-4 mb-6">
                    <h4 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                      Gaps to Note
                    </h4>
                    {result.gaps.map((gap, i) => (
                      <div key={i} className="p-4 bg-secondary rounded-xl border border-border">
                        <div className="flex items-start gap-3">
                          <span className="text-warning mt-0.5">✗</span>
                          <div>
                            <p className="text-warning font-medium mb-1">{gap.gap_title}</p>
                            <p className="text-muted-foreground text-xs font-mono mb-1">{gap.requirement}</p>
                            <p className="text-muted-foreground text-sm leading-relaxed">{gap.explanation}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Transfers */}
                {result.transfers && (
                  <div className="p-4 bg-secondary rounded-xl border border-border mb-6">
                    <h4 className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-2">
                      What Transfers
                    </h4>
                    <p className="text-muted-foreground text-sm">{result.transfers}</p>
                  </div>
                )}

                {/* Recommendation */}
                <div className={cn("p-4 rounded-xl border", style.banner)}>
                  <h4 className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-2">
                    My Recommendation
                  </h4>
                  <p className={cn("leading-relaxed", style.text)}>{result.recommendation}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Bottom insight */}
        <div className="mt-8 text-center">
          <div className="inline-block p-6 bg-card rounded-2xl border border-border max-w-2xl">
            <p className="text-muted-foreground leading-relaxed">
              This signals something completely different than "please consider my resume."
              <br />
              <br />
              <span className="text-foreground font-medium">
                You're qualifying them. Your time is valuable too.
              </span>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

export default FitAssessment;
