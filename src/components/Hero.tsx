import { useCandidateProfile } from "@/hooks/useCandidateData";

interface HeroProps {
  onOpenChat: () => void;
}

const Hero = ({ onOpenChat }: HeroProps) => {
  const { data: profile, isLoading } = useCandidateProfile();

  if (isLoading) {
    return (
      <section
        id="hero"
        style={{ minHeight: "80vh", display: "flex", flexDirection: "column", justifyContent: "center", padding: "6rem 2rem 4rem" }}
      >
        <div style={{ maxWidth: "900px", margin: "0 auto", width: "100%", opacity: 0.4 }}>
          <div style={{ height: "1.5rem", width: "12rem", backgroundColor: "var(--color-border)", borderRadius: "4px", marginBottom: "2rem" }} />
          <div style={{ height: "4rem", width: "75%", backgroundColor: "var(--color-border)", borderRadius: "4px", marginBottom: "1.5rem" }} />
          <div style={{ height: "1.5rem", width: "40%", backgroundColor: "var(--color-border)", borderRadius: "4px", marginBottom: "1rem" }} />
          <div style={{ height: "1.25rem", width: "60%", backgroundColor: "var(--color-border)", borderRadius: "4px", marginBottom: "2rem" }} />
        </div>
      </section>
    );
  }

  if (!profile) {
    return (
      <section
        id="hero"
        style={{ minHeight: "80vh", display: "flex", flexDirection: "column", justifyContent: "center", padding: "6rem 2rem 4rem" }}
      >
        <div style={{ maxWidth: "900px", margin: "0 auto" }}>
          <p style={{ fontFamily: "var(--font-serif)", fontSize: "1.25rem", color: "var(--color-text-faint)" }}>
            Coming soon.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section
      id="hero"
      style={{
        minHeight: "80vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: "6rem 2rem 4rem",
        backgroundColor: "var(--color-bg-page)",
      }}
    >
      <div style={{ maxWidth: "900px", margin: "0 auto", width: "100%" }}>

        {/* Availability badge */}
        {profile.availability_status && (
          <div
            className="animate-fade-in"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.375rem 0.875rem",
              backgroundColor: "var(--color-bg-raised)",
              border: "1px solid var(--color-border)",
              borderRadius: "100px",
              marginBottom: "2rem",
            }}
          >
            <span
              className="animate-pulse-soft"
              style={{
                width: "7px",
                height: "7px",
                borderRadius: "50%",
                backgroundColor: "#15803d",
                flexShrink: 0,
              }}
            />
            <span style={{ fontSize: "0.8125rem", color: "var(--color-text-secondary)", fontFamily: "var(--font-sans)" }}>
              {profile.availability_status}
            </span>
          </div>
        )}

        {/* Name */}
        <h1
          className="animate-slide-up"
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: "clamp(2.5rem, 6vw, 4.5rem)",
            fontWeight: 400,
            color: "var(--color-text-primary)",
            lineHeight: 1.1,
            marginBottom: "1rem",
          }}
        >
          {profile.name}
        </h1>

        {/* Title */}
        <p
          className="animate-slide-up stagger-1"
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: "1.125rem",
            fontWeight: 500,
            color: "var(--color-interactive)",
            marginBottom: "1.25rem",
            letterSpacing: "0.01em",
          }}
        >
          {profile.title}
        </p>

        {/* Elevator pitch */}
        {profile.elevator_pitch && (
          <p
            className="animate-slide-up stagger-2"
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "1.0625rem",
              color: "var(--color-text-secondary)",
              lineHeight: 1.75,
              maxWidth: "56ch",
              marginBottom: "2rem",
            }}
          >
            {profile.elevator_pitch}
          </p>
        )}

        {/* Target company stages */}
        {profile.target_company_stages && profile.target_company_stages.length > 0 && (
          <div
            className="animate-slide-up stagger-3"
            style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "2.5rem" }}
          >
            {profile.target_company_stages.map((stage: string) => (
              <span
                key={stage}
                style={{
                  padding: "0.25rem 0.75rem",
                  border: "1px solid var(--color-border)",
                  borderRadius: "100px",
                  fontSize: "0.8125rem",
                  color: "var(--color-text-secondary)",
                  backgroundColor: "var(--color-bg-alt)",
                }}
              >
                {stage}
              </span>
            ))}
          </div>
        )}

        {/* CTA */}
        <button
          onClick={onOpenChat}
          className="animate-slide-up stagger-4"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.625rem 1.5rem",
            backgroundColor: "var(--color-interactive)",
            color: "#ffffff",
            border: "none",
            borderRadius: "4px",
            fontSize: "0.9375rem",
            fontWeight: 500,
            fontFamily: "var(--font-sans)",
            cursor: "pointer",
            transition: "background-color 0.15s ease",
          }}
          onMouseEnter={e => (e.currentTarget.style.backgroundColor = "var(--color-interactive-hover)")}
          onMouseLeave={e => (e.currentTarget.style.backgroundColor = "var(--color-interactive)")}
        >
          Ask AI about me
        </button>
      </div>
    </section>
  );
};

export default Hero;
