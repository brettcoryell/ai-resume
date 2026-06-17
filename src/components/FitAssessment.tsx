import { useState } from "react";
import { FileText, Check, AlertTriangle, Loader2 } from "lucide-react";
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

const VERDICT_STYLES: Record<Verdict, { bg: string; txt: string; border: string; iconBg: string }> = {
  strong_fit: {
    bg:     "var(--ar-fit-strong-bg)",
    txt:    "var(--ar-fit-strong-txt)",
    border: "var(--ar-fit-strong-border)",
    iconBg: "rgba(21,128,61,0.12)",
  },
  worth_conversation: {
    bg:     "var(--ar-fit-neutral-bg)",
    txt:    "var(--ar-fit-neutral-txt)",
    border: "var(--ar-fit-neutral-border)",
    iconBg: "rgba(74,85,104,0.08)",
  },
  probably_not: {
    bg:     "var(--ar-fit-weak-bg)",
    txt:    "var(--ar-fit-weak-txt)",
    border: "var(--ar-fit-weak-border)",
    iconBg: "rgba(146,64,14,0.10)",
  },
};

const SECTION_LABEL: React.CSSProperties = {
  fontSize: "0.7rem",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: "var(--color-text-faint)",
  fontFamily: "var(--font-sans)",
  marginBottom: "0.5rem",
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

  const vs = result ? VERDICT_STYLES[result.verdict] : null;

  const tabStyle = (tab: TabType): React.CSSProperties => {
    const isActive = activeTab === tab;
    const activeColors: Record<TabType, { bg: string; txt: string; border: string }> = {
      strong: { bg: "var(--ar-fit-strong-bg)", txt: "var(--ar-fit-strong-txt)", border: "var(--ar-fit-strong-border)" },
      weak:   { bg: "var(--ar-fit-weak-bg)",   txt: "var(--ar-fit-weak-txt)",   border: "var(--ar-fit-weak-border)" },
      custom: { bg: "var(--color-bg-raised)",    txt: "var(--color-interactive-hover)",    border: "var(--color-interactive)" },
    };
    const c = activeColors[tab];
    return {
      padding: "0.5rem 1.25rem",
      borderRadius: "4px",
      fontFamily: "var(--font-sans)",
      fontSize: "0.875rem",
      fontWeight: 500,
      cursor: "pointer",
      border: `1px solid ${isActive ? c.border : "var(--color-border)"}`,
      backgroundColor: isActive ? c.bg : "var(--color-bg-page)",
      color: isActive ? c.txt : "var(--color-text-secondary)",
      transition: "all 0.15s ease",
    };
  };

  return (
    <section
      id="fit-assessment"
      style={{ padding: "5rem 2rem", backgroundColor: "var(--color-bg-page)" }}
    >
      <div style={{ maxWidth: "900px", margin: "0 auto" }}>
        {/* Section header */}
        <div style={{ marginBottom: "2.5rem" }}>
          <p style={{ ...SECTION_LABEL, fontSize: "0.75rem" }}>JD Analysis</p>
          <h2
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: "1.6rem",
              fontWeight: 400,
              color: "var(--color-text-primary)",
              marginBottom: "0.75rem",
            }}
          >
            Honest Fit Assessment
          </h2>
          <p style={{ color: "var(--color-text-secondary)", fontSize: "1rem", lineHeight: 1.6, maxWidth: "52ch", fontFamily: "var(--font-sans)" }}>
            Paste a job description and get an honest read on fit — including when the answer is no.
          </p>
        </div>

        {/* Tab buttons */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "1.75rem" }}>
          <button onClick={() => handleTabClick("strong")} style={tabStyle("strong")}>Strong fit example</button>
          <button onClick={() => handleTabClick("weak")}   style={tabStyle("weak")}>Weak fit example</button>
          <button onClick={() => handleTabClick("custom")} style={tabStyle("custom")}>Paste your own JD</button>
        </div>

        {/* Main interface card */}
        <div
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: "8px",
            overflow: "hidden",
            backgroundColor: "var(--color-bg-page)",
          }}
        >
          {/* Input section */}
          <div style={{ padding: "1.5rem", borderBottom: "1px solid var(--color-border)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.625rem", marginBottom: "0.75rem" }}>
              <div
                style={{
                  width: "2rem",
                  height: "2rem",
                  borderRadius: "6px",
                  backgroundColor: "var(--color-bg-raised)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <FileText style={{ width: "1rem", height: "1rem", color: "var(--color-interactive-hover)" }} />
              </div>
              <span style={{ fontSize: "0.875rem", color: "var(--color-text-faint)", fontFamily: "var(--font-sans)" }}>
                Job description to analyze
              </span>
            </div>
            <textarea
              style={{
                width: "100%",
                backgroundColor: "var(--color-bg-alt)",
                borderRadius: "6px",
                padding: "1rem",
                border: "1px solid var(--color-border)",
                fontSize: "0.875rem",
                fontFamily: "var(--font-sans)",
                color: activeTab === "custom" ? "var(--color-text-primary)" : "var(--color-text-secondary)",
                lineHeight: 1.6,
                resize: "none",
                transition: "border-color 0.15s ease",
                outline: "none",
                opacity: activeTab !== "custom" ? 0.75 : 1,
                cursor: activeTab !== "custom" ? "default" : "text",
                boxSizing: "border-box",
              }}
              rows={8}
              value={jdText}
              onChange={(e) => activeTab === "custom" && setJdText(e.target.value)}
              readOnly={activeTab !== "custom"}
              placeholder="Paste a job description here..."
              onFocus={e => { if (activeTab === "custom") e.currentTarget.style.borderColor = "var(--color-interactive)"; }}
              onBlur={e => { e.currentTarget.style.borderColor = "var(--color-border)"; }}
            />
            <div style={{ marginTop: "1rem", display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={handleAnalyze}
                disabled={analyzing || !jdText.trim()}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  padding: "0.5rem 1.25rem",
                  backgroundColor: "var(--color-interactive)",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "4px",
                  fontSize: "0.875rem",
                  fontWeight: 500,
                  fontFamily: "var(--font-sans)",
                  cursor: analyzing || !jdText.trim() ? "not-allowed" : "pointer",
                  opacity: analyzing || !jdText.trim() ? 0.5 : 1,
                  transition: "background-color 0.15s ease",
                }}
                onMouseEnter={e => { if (!analyzing && jdText.trim()) e.currentTarget.style.backgroundColor = "var(--color-interactive-hover)"; }}
                onMouseLeave={e => { e.currentTarget.style.backgroundColor = "var(--color-interactive)"; }}
              >
                {analyzing && <Loader2 className="w-4 h-4 animate-spin" />}
                Analyze fit
              </button>
            </div>
          </div>

          {/* Results section */}
          <div style={{ padding: "1.5rem", minHeight: "6rem" }}>
            {analyzing && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "3rem 0" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", color: "var(--color-text-faint)", fontFamily: "var(--font-sans)", fontSize: "0.9375rem" }}>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Analyzing against my experience…</span>
                </div>
              </div>
            )}

            {error && !analyzing && (
              <div style={{ display: "flex", justifyContent: "center", padding: "3rem 0" }}>
                <div
                  style={{
                    backgroundColor: "var(--ar-fit-weak-bg)",
                    border: "1px solid var(--ar-fit-weak-border)",
                    borderRadius: "6px",
                    padding: "1rem 1.5rem",
                    color: "var(--ar-fit-weak-txt)",
                    fontSize: "0.875rem",
                    fontFamily: "var(--font-sans)",
                    maxWidth: "30rem",
                    textAlign: "center",
                  }}
                >
                  {error}
                </div>
              </div>
            )}

            {result && !analyzing && vs && (
              <div className="animate-slide-up">
                {/* Verdict banner */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "1rem",
                    padding: "1rem 1.25rem",
                    borderRadius: "6px",
                    border: `1px solid ${vs.border}`,
                    backgroundColor: vs.bg,
                    marginBottom: "1.5rem",
                  }}
                >
                  <div
                    style={{
                      width: "2.5rem",
                      height: "2.5rem",
                      borderRadius: "50%",
                      backgroundColor: vs.iconBg,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    {result.verdict === "probably_not"
                      ? <AlertTriangle style={{ width: "1.25rem", height: "1.25rem", color: vs.txt }} />
                      : <Check style={{ width: "1.25rem", height: "1.25rem", color: vs.txt }} />
                    }
                  </div>
                  <div>
                    <h3 style={{ fontFamily: "var(--font-serif)", fontSize: "1.2rem", fontWeight: 400, color: vs.txt, marginBottom: "0.25rem" }}>
                      {result.headline}
                    </h3>
                    <p style={{ color: "var(--color-text-secondary)", fontSize: "0.875rem", fontFamily: "var(--font-sans)", lineHeight: 1.5 }}>
                      {result.opening}
                    </p>
                  </div>
                </div>

                {/* Gaps */}
                {result.gaps && result.gaps.length > 0 && (
                  <div style={{ marginBottom: "1.25rem" }}>
                    <p style={SECTION_LABEL}>Gaps to note</p>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      {result.gaps.map((gap, i) => (
                        <div
                          key={i}
                          style={{
                            padding: "1rem",
                            backgroundColor: "var(--color-bg-alt)",
                            border: "1px solid var(--color-border)",
                            borderRadius: "6px",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem" }}>
                            <span style={{ color: "var(--ar-fit-weak-txt)", marginTop: "0.1em", flexShrink: 0 }}>✗</span>
                            <div>
                              <p style={{ color: "var(--ar-fit-weak-txt)", fontWeight: 500, fontSize: "0.9375rem", fontFamily: "var(--font-sans)", marginBottom: "0.25rem" }}>
                                {gap.gap_title}
                              </p>
                              <p style={{ color: "var(--color-text-faint)", fontSize: "0.8rem", fontFamily: "var(--font-sans)", marginBottom: "0.375rem" }}>
                                {gap.requirement}
                              </p>
                              <p style={{ color: "var(--color-text-secondary)", fontSize: "0.9rem", lineHeight: 1.6, fontFamily: "var(--font-sans)" }}>
                                {gap.explanation}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* What transfers */}
                {result.transfers && (
                  <div
                    style={{
                      padding: "1rem 1.25rem",
                      backgroundColor: "var(--color-bg-alt)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "6px",
                      marginBottom: "1.25rem",
                    }}
                  >
                    <p style={SECTION_LABEL}>What transfers</p>
                    <p style={{ color: "var(--color-text-secondary)", fontSize: "0.9375rem", lineHeight: 1.65, fontFamily: "var(--font-sans)" }}>
                      {result.transfers}
                    </p>
                  </div>
                )}

                {/* Recommendation */}
                <div
                  style={{
                    padding: "1rem 1.25rem",
                    backgroundColor: vs.bg,
                    border: `1px solid ${vs.border}`,
                    borderRadius: "6px",
                  }}
                >
                  <p style={SECTION_LABEL}>My recommendation</p>
                  <p style={{ color: vs.txt, lineHeight: 1.65, fontFamily: "var(--font-sans)", fontSize: "0.9375rem" }}>
                    {result.recommendation}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>
    </section>
  );
};

export default FitAssessment;
