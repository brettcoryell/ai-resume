import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ChevronDown, ChevronUp, Pencil, Trash2, Plus, X } from "lucide-react";

interface ExperienceRow {
  id: string;
  company_name: string;
  title: string;
  title_progression: string | null;
  start_date: string;
  end_date: string | null;
  is_current: boolean;
  bullet_points: string[];
  display_order: number;
  why_joined: string | null;
  why_left: string | null;
  actual_contributions: string | null;
  proudest_achievement: string | null;
  would_do_differently: string | null;
  challenges_faced: string | null;
  lessons_learned: string | null;
  manager_would_say: string | null;
  reports_would_say: string | null;
}

type FormData = Omit<ExperienceRow, "id"> & { id?: string };

const EMPTY_FORM: FormData = {
  company_name: "",
  title: "",
  title_progression: "",
  start_date: "",
  end_date: "",
  is_current: false,
  bullet_points: [],
  display_order: 0,
  why_joined: "",
  why_left: "",
  actual_contributions: "",
  proudest_achievement: "",
  would_do_differently: "",
  challenges_faced: "",
  lessons_learned: "",
  manager_would_say: "",
  reports_would_say: "",
};

function formatDate(dateStr: string): string {
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    year: "numeric",
  });
}

const ExperienceForm = () => {
  const navigate = useNavigate();
  const [experiences, setExperiences] = useState<ExperienceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [bulletText, setBulletText] = useState("");
  const [aiExpanded, setAiExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [candidateId, setCandidateId] = useState<string | null>(null);

  useEffect(() => {
    const init = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) { navigate("/admin/login"); return; }

      const { data: profile } = await supabase.from("candidate_profile").select("id").maybeSingle();
      if (profile) setCandidateId(profile.id);

      await loadExperiences();
    };
    init();
  }, [navigate]);

  const loadExperiences = async () => {
    const { data, error } = await supabase
      .from("experiences")
      .select("*")
      .order("display_order");
    if (error) { toast.error("Failed to load experiences"); return; }
    setExperiences(data ?? []);
    setLoading(false);
  };

  const set = (field: keyof FormData) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const value = e.target.type === "checkbox"
      ? (e.target as HTMLInputElement).checked
      : e.target.value;
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const openNew = () => {
    setForm(EMPTY_FORM);
    setBulletText("");
    setAiExpanded(false);
    setShowForm(true);
  };

  const openEdit = (exp: ExperienceRow) => {
    setForm({
      ...exp,
      title_progression: exp.title_progression ?? "",
      end_date: exp.end_date ?? "",
      why_joined: exp.why_joined ?? "",
      why_left: exp.why_left ?? "",
      actual_contributions: exp.actual_contributions ?? "",
      proudest_achievement: exp.proudest_achievement ?? "",
      would_do_differently: exp.would_do_differently ?? "",
      challenges_faced: exp.challenges_faced ?? "",
      lessons_learned: exp.lessons_learned ?? "",
      manager_would_say: exp.manager_would_say ?? "",
      reports_would_say: exp.reports_would_say ?? "",
    });
    setBulletText(exp.bullet_points ? exp.bullet_points.join("\n") : "");
    setAiExpanded(false);
    setShowForm(true);
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
    const { error } = await supabase.from("experiences").delete().eq("id", id);
    if (error) { toast.error("Delete failed: " + error.message); return; }
    toast.success("Experience deleted.");
    await loadExperiences();
  };

  const handleSave = async () => {
    if (!form.company_name || !form.title || !form.start_date) {
      toast.error("Company name, title, and start date are required.");
      return;
    }
    setSaving(true);

    const bullets = bulletText.split("\n").map((s) => s.trim()).filter(Boolean);

    const payload: Record<string, unknown> = {
      company_name: form.company_name,
      title: form.title,
      title_progression: form.title_progression || null,
      start_date: form.start_date,
      end_date: form.is_current ? null : (form.end_date || null),
      is_current: form.is_current,
      bullet_points: bullets,
      display_order: Number(form.display_order) || 0,
      why_joined: form.why_joined || null,
      why_left: form.why_left || null,
      actual_contributions: form.actual_contributions || null,
      proudest_achievement: form.proudest_achievement || null,
      would_do_differently: form.would_do_differently || null,
      challenges_faced: form.challenges_faced || null,
      lessons_learned: form.lessons_learned || null,
      manager_would_say: form.manager_would_say || null,
      reports_would_say: form.reports_would_say || null,
    };

    if (candidateId) payload.candidate_id = candidateId;

    let error;
    if (form.id) {
      ({ error } = await supabase.from("experiences").update(payload).eq("id", form.id));
    } else {
      ({ error } = await supabase.from("experiences").insert(payload));
    }

    if (error) {
      toast.error("Save failed: " + error.message);
    } else {
      toast.success("Experience saved.");
      setShowForm(false);
      await loadExperiences();
    }
    setSaving(false);
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside className="w-56 bg-card border-r border-border flex flex-col">
        <div className="p-6 border-b border-border">
          <h1 className="text-lg font-serif text-foreground">Admin</h1>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          <Link to="/admin" className="block px-4 py-2.5 rounded-xl text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors">Dashboard</Link>
          <Link to="/admin/profile" className="block px-4 py-2.5 rounded-xl text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors">Profile</Link>
          <Link to="/admin/experience" className="block px-4 py-2.5 rounded-xl text-sm text-foreground bg-secondary">Experience</Link>
        </nav>
      </aside>

      {/* Main */}
      <main className="flex-1 p-10">
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-3xl font-serif text-foreground">Experience</h2>
          <Button onClick={openNew} className="flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Add New
          </Button>
        </div>

        {loading && <p className="text-muted-foreground">Loading...</p>}

        {!loading && experiences.length === 0 && !showForm && (
          <p className="text-muted-foreground">No experiences yet. Add one above.</p>
        )}

        {/* List */}
        {!showForm && experiences.length > 0 && (
          <div className="space-y-3 mb-8">
            {experiences.map((exp) => (
              <div key={exp.id} className="flex items-center justify-between p-4 bg-card border border-border rounded-xl">
                <div>
                  <p className="text-foreground font-medium">{exp.company_name}</p>
                  <p className="text-muted-foreground text-sm">
                    {exp.title_progression || exp.title} &middot; {formatDate(exp.start_date)} — {exp.is_current || !exp.end_date ? "Present" : formatDate(exp.end_date)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => openEdit(exp)}
                    className="p-2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(exp.id, exp.company_name)}
                    className="p-2 text-muted-foreground hover:text-warning transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Form */}
        {showForm && (
          <div className="bg-card border border-border rounded-2xl p-8 max-w-2xl">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-serif text-foreground">
                {form.id ? "Edit Experience" : "New Experience"}
              </h3>
              <button onClick={() => setShowForm(false)} className="text-muted-foreground hover:text-foreground">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="company_name">Company Name *</Label>
                  <Input id="company_name" value={form.company_name} onChange={set("company_name")} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="display_order">Display Order</Label>
                  <Input id="display_order" type="number" value={form.display_order} onChange={set("display_order")} />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="title">Title *</Label>
                <Input id="title" value={form.title} onChange={set("title")} />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="title_progression">Title Progression (e.g. "Eng → Senior Eng → Staff Eng")</Label>
                <Input id="title_progression" value={form.title_progression ?? ""} onChange={set("title_progression")} />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="start_date">Start Date * (YYYY-MM-DD)</Label>
                  <Input id="start_date" value={form.start_date} onChange={set("start_date")} placeholder="2020-01-01" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="end_date">End Date (YYYY-MM-DD)</Label>
                  <Input id="end_date" value={form.end_date ?? ""} onChange={set("end_date")} placeholder="2023-06-30" disabled={form.is_current} />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <input
                  id="is_current"
                  type="checkbox"
                  checked={form.is_current}
                  onChange={(e) => setForm((prev) => ({ ...prev, is_current: e.target.checked }))}
                  className="w-4 h-4 accent-accent"
                />
                <Label htmlFor="is_current">Currently working here</Label>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="bullet_points">Bullet Points (one per line)</Label>
                <Textarea
                  id="bullet_points"
                  rows={5}
                  value={bulletText}
                  onChange={(e) => setBulletText(e.target.value)}
                  placeholder="Led migration of monolith to microservices&#10;Reduced p99 latency by 40%"
                />
              </div>

              {/* AI Context section */}
              <div className="border border-border rounded-xl overflow-hidden">
                <button
                  type="button"
                  onClick={() => setAiExpanded(!aiExpanded)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-secondary text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <span className="font-mono uppercase tracking-wider text-xs">AI Context (Private)</span>
                  {aiExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>

                {aiExpanded && (
                  <div className="p-5 space-y-4">
                    {(
                      [
                        ["why_joined", "Why Joined"],
                        ["why_left", "Why Left"],
                        ["actual_contributions", "Actual Contributions"],
                        ["proudest_achievement", "Proudest Achievement"],
                        ["would_do_differently", "Would Do Differently"],
                        ["challenges_faced", "Challenges Faced"],
                        ["lessons_learned", "Lessons Learned"],
                        ["manager_would_say", "Manager Would Say"],
                        ["reports_would_say", "Reports Would Say"],
                      ] as [keyof FormData, string][]
                    ).map(([field, label]) => (
                      <div key={field} className="space-y-1.5">
                        <Label htmlFor={field}>{label}</Label>
                        <Textarea
                          id={field}
                          rows={2}
                          value={(form[field] as string) ?? ""}
                          onChange={set(field)}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex gap-3">
                <Button onClick={handleSave} disabled={saving}>
                  {saving ? "Saving..." : "Save"}
                </Button>
                <Button variant="outline" onClick={() => setShowForm(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default ExperienceForm;
