import { Github, Linkedin, Mail } from "lucide-react";
import { useCandidateProfile } from "@/hooks/useCandidateData";

const Footer = () => {
  const { data: profile } = useCandidateProfile();

  const name = profile?.name ?? "Brett Coryell";
  const title = profile?.title ?? "CIO | CISO | Enterprise AI | Board Advisor";
  const email = profile?.email;
  const linkedinUrl = profile?.linkedin_url;
  const githubUrl = profile?.github_url;

  return (
    <footer className="py-16 px-6 border-t border-border">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col md:flex-row items-center justify-between gap-8">
          <div>
            <p className="text-2xl font-serif text-foreground mb-2">{name}</p>
            <p className="text-muted-foreground">{title}</p>
          </div>

          <div className="flex items-center gap-4">
            {githubUrl && (
              <a
                href={githubUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="p-3 bg-secondary rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <Github className="w-5 h-5" />
              </a>
            )}
            {linkedinUrl && (
              <a
                href={linkedinUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="p-3 bg-secondary rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <Linkedin className="w-5 h-5" />
              </a>
            )}
            {email && (
              <a
                href={`mailto:${email}`}
                className="p-3 bg-secondary rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <Mail className="w-5 h-5" />
              </a>
            )}
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-border text-center">
          <p className="text-sm text-muted-foreground">
            This portfolio demonstrates AI-queryable professional presentation.
            <br />
            <span className="text-text-subtle">The interface is the proof.</span>
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
