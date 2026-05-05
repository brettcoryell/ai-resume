import { MessageSquare } from "lucide-react";
import { useCandidateProfile } from "@/hooks/useCandidateData";

interface HeroProps {
  onOpenChat: () => void;
}

const Hero = ({ onOpenChat }: HeroProps) => {
  const { data: profile, isLoading } = useCandidateProfile();

  if (isLoading) {
    return (
      <section id="hero" className="min-h-screen flex flex-col justify-center px-6 pt-20 opacity-50">
        <div className="max-w-4xl mx-auto w-full animate-pulse">
          <div className="h-8 w-48 bg-secondary rounded-full mb-8" />
          <div className="h-20 w-3/4 bg-secondary rounded-xl mb-6" />
          <div className="h-8 w-1/2 bg-secondary rounded-xl mb-4" />
          <div className="h-6 w-2/3 bg-secondary rounded-xl mb-8" />
          <div className="flex gap-3 mb-12">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 w-28 bg-secondary rounded-full" />
            ))}
          </div>
          <div className="h-14 w-48 bg-secondary rounded-2xl" />
        </div>
      </section>
    );
  }

  if (!profile) {
    return (
      <section id="hero" className="min-h-screen flex flex-col justify-center px-6 pt-20">
        <div className="max-w-4xl mx-auto w-full">
          <p className="text-muted-foreground text-2xl font-serif">Coming soon.</p>
        </div>
      </section>
    );
  }

  return (
    <section
      id="hero"
      className="min-h-screen flex flex-col justify-center px-6 pt-20"
    >
      <div className="max-w-4xl mx-auto w-full">
        {/* Status badge */}
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-secondary rounded-full mb-8 animate-fade-in">
          <span className="w-2 h-2 rounded-full bg-success animate-pulse-soft" />
          <span className="text-sm text-muted-foreground">{profile.availability_status}</span>
        </div>

        {/* Main heading */}
        <h1 className="text-5xl md:text-7xl lg:text-8xl font-serif text-foreground mb-6 animate-slide-up">
          {profile.name}
        </h1>

        {/* Role */}
        <p className="text-2xl md:text-3xl text-primary font-serif mb-4 animate-slide-up stagger-1">
          {profile.title}
        </p>

        {/* Subtitle */}
        <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mb-8 animate-slide-up stagger-2">
          {profile.elevator_pitch}
        </p>

        {/* Company badges */}
        {profile.target_company_stages && profile.target_company_stages.length > 0 && (
          <div className="flex flex-wrap gap-3 mb-12 animate-slide-up stagger-3">
            {profile.target_company_stages.map((stage: string) => (
              <span
                key={stage}
                className="px-4 py-2 bg-card border border-border rounded-full text-sm text-foreground"
              >
                {stage}
              </span>
            ))}
          </div>
        )}

        {/* CTA Button */}
        <button
          onClick={onOpenChat}
          className="group relative inline-flex items-center gap-3 px-8 py-4 bg-accent text-accent-foreground rounded-2xl font-medium transition-all hover:scale-[1.02] hover:shadow-lg hover:shadow-accent/20 animate-slide-up stagger-4"
        >
          <MessageSquare className="w-5 h-5" />
          <span>Ask AI About Me</span>
          <span className="absolute -top-2 -right-2 px-2 py-0.5 bg-success text-primary-foreground rounded-full text-xs font-medium">
            New
          </span>
        </button>

        {/* Scroll indicator */}
        <div className="absolute bottom-12 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-muted-foreground animate-fade-in opacity-0" style={{ animationDelay: "1.5s", animationFillMode: "forwards" }}>
          <span className="text-xs uppercase tracking-widest">Scroll to explore</span>
          <div className="w-px h-8 bg-gradient-to-b from-muted-foreground to-transparent" />
        </div>
      </div>
    </section>
  );
};

export default Hero;
