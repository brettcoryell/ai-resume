import { useState, useEffect } from "react";
import { Menu, X } from "lucide-react";
import { useCandidateProfile } from "@/hooks/useCandidateData";

interface HeaderProps {
  onOpenChat?: () => void;
}

const NAV_LINK_BASE: React.CSSProperties = {
  fontSize: "0.875rem",
  fontWeight: 500,
  background: "none",
  border: "none",
  cursor: "pointer",
  padding: 0,
  transition: "color 0.15s ease",
  fontFamily: "var(--font-sans)",
};

const Header = ({ onOpenChat }: HeaderProps) => {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { data: profile } = useCandidateProfile();

  const name = profile?.name ?? "Brett Coryell";

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    setMobileMenuOpen(false);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  const handleAskAI = () => {
    setMobileMenuOpen(false);
    if (onOpenChat) onOpenChat();
  };

  const linkColor = scrolled ? "var(--site-ink)" : "var(--site-sky)";

  return (
    <header
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 50,
        transition: "background-color 0.3s ease, box-shadow 0.3s ease",
        backgroundColor: scrolled ? "rgba(255,255,255,0.95)" : "transparent",
        backdropFilter: scrolled ? "blur(8px)" : "none",
        boxShadow: scrolled ? "0 1px 0 var(--site-fog)" : "none",
      }}
    >
      <nav
        style={{
          maxWidth: "900px",
          margin: "0 auto",
          padding: "1rem 2rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        {/* Site name */}
        <a
          href="https://brettcoryell.com"
          style={{
            ...NAV_LINK_BASE,
            fontSize: "0.9rem",
            fontWeight: 600,
            color: "var(--site-sky)",
            textDecoration: "none",
          }}
        >
          {name}
        </a>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-8">
          <button
            onClick={() => scrollToSection("experience")}
            style={{ ...NAV_LINK_BASE, color: linkColor }}
            onMouseEnter={e => (e.currentTarget.style.color = "var(--site-sky)")}
            onMouseLeave={e => (e.currentTarget.style.color = linkColor)}
          >
            Experience
          </button>
          <button
            onClick={() => scrollToSection("fit-assessment")}
            style={{ ...NAV_LINK_BASE, color: linkColor }}
            onMouseEnter={e => (e.currentTarget.style.color = "var(--site-sky)")}
            onMouseLeave={e => (e.currentTarget.style.color = linkColor)}
          >
            Fit Check
          </button>
          <button
            onClick={handleAskAI}
            style={{
              ...NAV_LINK_BASE,
              backgroundColor: "var(--site-sky)",
              color: "#ffffff",
              padding: "0.5rem 1.25rem",
              borderRadius: "4px",
              transition: "background-color 0.15s ease",
            }}
            onMouseEnter={e => (e.currentTarget.style.backgroundColor = "var(--site-sky-deep)")}
            onMouseLeave={e => (e.currentTarget.style.backgroundColor = "var(--site-sky)")}
          >
            Ask AI
          </button>
        </div>

        {/* Mobile menu button */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="md:hidden p-2"
          style={{ color: "var(--site-mist)", background: "none", border: "none", cursor: "pointer" }}
        >
          {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </nav>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div
          className="md:hidden animate-slide-down"
          style={{
            backgroundColor: "#ffffff",
            borderTop: "1px solid var(--site-fog)",
          }}
        >
          <div style={{ padding: "1rem 2rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
            <button
              onClick={() => scrollToSection("experience")}
              style={{ ...NAV_LINK_BASE, color: "var(--site-ink)", textAlign: "left", fontSize: "1rem" }}
            >
              Experience
            </button>
            <button
              onClick={() => scrollToSection("fit-assessment")}
              style={{ ...NAV_LINK_BASE, color: "var(--site-ink)", textAlign: "left", fontSize: "1rem" }}
            >
              Fit Check
            </button>
            <button
              onClick={handleAskAI}
              style={{ ...NAV_LINK_BASE, color: "var(--site-sky)", textAlign: "left", fontSize: "1rem" }}
            >
              Ask AI About Me
            </button>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;
