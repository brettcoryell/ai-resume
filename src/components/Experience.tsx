import { useExperiences } from "@/hooks/useCandidateData";
import ExperienceCard from "./ExperienceCard";

interface ExperienceProps {
  onOpenChat?: (initialMessage: string) => void;
}

const Experience = ({ onOpenChat }: ExperienceProps) => {
  const { data: experiences, isLoading } = useExperiences();

  return (
    <section
      id="experience"
      style={{
        backgroundColor: "var(--site-cloud)",
        padding: "5rem 2rem",
      }}
    >
      <div style={{ maxWidth: "900px", margin: "0 auto" }}>
        {/* Section header */}
        <div style={{ marginBottom: "3rem" }}>
          <p
            style={{
              fontSize: "0.75rem",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--site-mist)",
              fontFamily: "var(--font-sans)",
              marginBottom: "0.5rem",
            }}
          >
            Career
          </p>
          <h2
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: "1.6rem",
              fontWeight: 400,
              color: "var(--site-ink)",
              marginBottom: "0.75rem",
            }}
          >
            Experience
          </h2>
          <p style={{ color: "var(--site-dusk)", fontSize: "1rem", lineHeight: 1.6, maxWidth: "48ch", fontFamily: "var(--font-sans)" }}>
            Each role includes AI context — the real story behind the bullet points.
          </p>
        </div>

        {/* Loading skeletons */}
        {isLoading && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                style={{
                  padding: "1.75rem",
                  backgroundColor: "var(--site-page)",
                  border: "1px solid var(--site-fog)",
                  borderRadius: "8px",
                  opacity: 0.5,
                }}
              >
                <div style={{ height: "1.5rem", width: "40%", backgroundColor: "var(--site-fog)", borderRadius: "3px", marginBottom: "0.75rem" }} />
                <div style={{ height: "1rem", width: "25%", backgroundColor: "var(--site-fog)", borderRadius: "3px", marginBottom: "1.5rem" }} />
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {[1, 2, 3].map(j => (
                    <div key={j} style={{ height: "0.875rem", width: `${90 - j * 10}%`, backgroundColor: "var(--site-fog)", borderRadius: "3px" }} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {!isLoading && (!experiences || experiences.length === 0) && (
          <p style={{ color: "var(--site-mist)", fontSize: "1rem" }}>No experience records yet.</p>
        )}

        {!isLoading && experiences && experiences.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            {experiences.map((exp, index) => (
              <ExperienceCard
                key={exp.id}
                experience={exp}
                index={index}
                onOpenChat={onOpenChat}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
};

export default Experience;
