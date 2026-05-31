import { useExperiences } from "@/hooks/useCandidateData";
import ExperienceCard from "./ExperienceCard";

interface ExperienceProps {
  onOpenChat?: (initialMessage: string) => void;
}

const Experience = ({ onOpenChat }: ExperienceProps) => {
  const { data: experiences, isLoading } = useExperiences();

  return (
    <section id="experience" className="py-24 px-6">
      <div className="max-w-4xl mx-auto">
        {/* Section header */}
        <div className="mb-12">
          <h2 className="text-4xl md:text-5xl font-serif text-foreground mb-4">
            Experience
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl">
            Each role includes queryable AI context—the real story behind the bullet points.
          </p>
        </div>

        {/* Experience cards */}
        {isLoading && (
          <div className="space-y-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse p-6 md:p-8 bg-card border border-border rounded-2xl">
                <div className="flex justify-between mb-6">
                  <div>
                    <div className="h-7 w-48 bg-secondary rounded mb-2" />
                    <div className="h-5 w-32 bg-secondary rounded" />
                  </div>
                  <div className="h-5 w-24 bg-secondary rounded" />
                </div>
                <div className="space-y-3">
                  <div className="h-4 w-full bg-secondary rounded" />
                  <div className="h-4 w-5/6 bg-secondary rounded" />
                  <div className="h-4 w-4/6 bg-secondary rounded" />
                </div>
              </div>
            ))}
          </div>
        )}

        {!isLoading && (!experiences || experiences.length === 0) && (
          <p className="text-muted-foreground text-lg">No experience records yet.</p>
        )}

        {!isLoading && experiences && experiences.length > 0 && (
          <div className="space-y-6">
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
