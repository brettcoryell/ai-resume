import { Linkedin, Mail } from "lucide-react";
import { useCandidateProfile } from "@/hooks/useCandidateData";

const Footer = () => {
  const { data: profile } = useCandidateProfile();

  const name  = profile?.name  ?? "Brett Coryell";
  const title = profile?.title ?? "CIO | CISO | Enterprise AI | Board Advisor";
  const email      = profile?.email;
  const linkedinUrl = profile?.linkedin_url;

  return (
    <footer style={{ backgroundColor: "var(--site-ink)", padding: "3.5rem 2rem" }}>
      <div
        style={{
          maxWidth: "900px",
          margin: "0 auto",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "1.5rem",
        }}
      >
        <div>
          <p
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: "1.125rem",
              fontWeight: 400,
              color: "rgba(255,255,255,0.9)",
              marginBottom: "0.25rem",
            }}
          >
            {name}
          </p>
          <p style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.5)", fontFamily: "var(--font-sans)" }}>
            {title}
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          {linkedinUrl && (
            <a
              href={linkedinUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: "rgba(255,255,255,0.5)",
                transition: "color 0.15s ease",
                display: "flex",
              }}
              onMouseEnter={e => (e.currentTarget.style.color = "rgba(255,255,255,0.9)")}
              onMouseLeave={e => (e.currentTarget.style.color = "rgba(255,255,255,0.5)")}
              aria-label="LinkedIn"
            >
              <Linkedin className="w-5 h-5" />
            </a>
          )}
          {email && (
            <a
              href={`mailto:${email}`}
              style={{
                color: "rgba(255,255,255,0.5)",
                transition: "color 0.15s ease",
                display: "flex",
              }}
              onMouseEnter={e => (e.currentTarget.style.color = "rgba(255,255,255,0.9)")}
              onMouseLeave={e => (e.currentTarget.style.color = "rgba(255,255,255,0.5)")}
              aria-label="Email"
            >
              <Mail className="w-5 h-5" />
            </a>
          )}
        </div>
      </div>

      <div
        style={{
          maxWidth: "900px",
          margin: "2rem auto 0",
          paddingTop: "1.5rem",
          borderTop: "1px solid rgba(255,255,255,0.1)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "0.5rem",
        }}
      >
        <p style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.35)", fontFamily: "var(--font-sans)" }}>
          © 2026 Brett Coryell
        </p>
        <p style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.35)", fontFamily: "var(--font-sans)" }}>
          AI powered by{" "}
          <a
            href="https://brettcoryell.com"
            style={{ color: "rgba(255,255,255,0.5)", textDecoration: "none", transition: "color 0.15s ease" }}
            onMouseEnter={e => (e.currentTarget.style.color = "rgba(255,255,255,0.8)")}
            onMouseLeave={e => (e.currentTarget.style.color = "rgba(255,255,255,0.5)")}
          >
            Ariel
          </a>
        </p>
      </div>
    </footer>
  );
};

export default Footer;
