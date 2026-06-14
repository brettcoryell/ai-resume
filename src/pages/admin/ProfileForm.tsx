import { useEffect, useState, FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { supabaseAdmin as supabase } from "@/lib/supabase";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

interface ProfileData {
  id?: string;
  name: string;
  title: string;
  elevator_pitch: string;
  career_narrative: string;
  looking_for: string;
  not_looking_for: string;
  availability_status: string;
  location: string;
  remote_preference: string;
  github_url: string;
  linkedin_url: string;
  target_titles: string; // comma-separated for form, stored as array
  target_company_stages: string; // comma-separated for form, stored as array
  salary_min: string;
  salary_max: string;
}

const EMPTY: ProfileData = {
  name: "",
  title: "",
  elevator_pitch: "",
  career_narrative: "",
  looking_for: "",
  not_looking_for: "",
  availability_status: "",
  location: "",
  remote_preference: "",
  github_url: "",
  linkedin_url: "",
  target_titles: "",
  target_company_stages: "",
  salary_min: "",
  salary_max: "",
};

const ProfileForm = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProfileData>(EMPTY);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) { navigate("/admin/login"); return; }

      const { data } = await supabase.from("candidate_profile").select("*").maybeSingle();
      if (data) {
        setProfileId(data.id);
        setForm({
          name: data.name ?? "",
          title: data.title ?? "",
          elevator_pitch: data.elevator_pitch ?? "",
          career_narrative: data.career_narrative ?? "",
          looking_for: data.looking_for ?? "",
          not_looking_for: data.not_looking_for ?? "",
          availability_status: data.availability_status ?? "",
          location: data.location ?? "",
          remote_preference: data.remote_preference ?? "",
          github_url: data.github_url ?? "",
          linkedin_url: data.linkedin_url ?? "",
          target_titles: Array.isArray(data.target_titles) ? data.target_titles.join(", ") : "",
          target_company_stages: Array.isArray(data.target_company_stages) ? data.target_company_stages.join(", ") : "",
          salary_min: data.salary_min != null ? String(data.salary_min) : "",
          salary_max: data.salary_max != null ? String(data.salary_max) : "",
        });
      }
      setLoading(false);
    };
    init();
  }, [navigate]);

  const set = (field: keyof ProfileData) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);

    const payload: Record<string, unknown> = {
      name: form.name,
      title: form.title,
      elevator_pitch: form.elevator_pitch,
      career_narrative: form.career_narrative,
      looking_for: form.looking_for,
      not_looking_for: form.not_looking_for,
      availability_status: form.availability_status,
      location: form.location,
      remote_preference: form.remote_preference,
      github_url: form.github_url,
      linkedin_url: form.linkedin_url,
      target_titles: form.target_titles.split(",").map((s) => s.trim()).filter(Boolean),
      target_company_stages: form.target_company_stages.split(",").map((s) => s.trim()).filter(Boolean),
      salary_min: form.salary_min ? parseInt(form.salary_min, 10) : null,
      salary_max: form.salary_max ? parseInt(form.salary_max, 10) : null,
    };

    if (profileId) payload.id = profileId;

    const { error } = await supabase.from("candidate_profile").upsert(payload);

    if (error) {
      toast.error("Save failed: " + error.message);
    } else {
      toast.success("Profile saved.");
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside className="w-56 bg-card border-r border-border flex flex-col">
        <div className="p-6 border-b border-border">
          <h1 className="text-lg font-serif text-foreground">Admin</h1>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          <Link to="/admin" className="block px-4 py-2.5 rounded-xl text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors">Dashboard</Link>
          <Link to="/admin/profile" className="block px-4 py-2.5 rounded-xl text-sm text-foreground bg-secondary">Profile</Link>
          <Link to="/admin/experience" className="block px-4 py-2.5 rounded-xl text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors">Experience</Link>
        </nav>
      </aside>

      {/* Main */}
      <main className="flex-1 p-10 max-w-3xl">
        <h2 className="text-3xl font-serif text-foreground mb-8">Profile</h2>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="name">Name</Label>
              <Input id="name" value={form.name} onChange={set("name")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="title">Title</Label>
              <Input id="title" value={form.title} onChange={set("title")} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="elevator_pitch">Elevator Pitch</Label>
            <Textarea id="elevator_pitch" rows={3} value={form.elevator_pitch} onChange={set("elevator_pitch")} />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="career_narrative">Career Narrative</Label>
            <Textarea id="career_narrative" rows={5} value={form.career_narrative} onChange={set("career_narrative")} />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="looking_for">Looking For</Label>
            <Textarea id="looking_for" rows={3} value={form.looking_for} onChange={set("looking_for")} />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="not_looking_for">Not Looking For</Label>
            <Textarea id="not_looking_for" rows={3} value={form.not_looking_for} onChange={set("not_looking_for")} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="availability_status">Availability Status</Label>
              <Input id="availability_status" value={form.availability_status} onChange={set("availability_status")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="location">Location</Label>
              <Input id="location" value={form.location} onChange={set("location")} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="remote_preference">Remote Preference</Label>
            <Input id="remote_preference" value={form.remote_preference} onChange={set("remote_preference")} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="github_url">GitHub URL</Label>
              <Input id="github_url" value={form.github_url} onChange={set("github_url")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="linkedin_url">LinkedIn URL</Label>
              <Input id="linkedin_url" value={form.linkedin_url} onChange={set("linkedin_url")} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="target_titles">Target Titles (comma-separated)</Label>
            <Input id="target_titles" value={form.target_titles} onChange={set("target_titles")} placeholder="VP Engineering, CTO, Director of Engineering" />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="target_company_stages">Target Company Stages (comma-separated)</Label>
            <Input id="target_company_stages" value={form.target_company_stages} onChange={set("target_company_stages")} placeholder="Series B, Series C, Growth" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="salary_min">Salary Min</Label>
              <Input id="salary_min" type="number" value={form.salary_min} onChange={set("salary_min")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="salary_max">Salary Max</Label>
              <Input id="salary_max" type="number" value={form.salary_max} onChange={set("salary_max")} />
            </div>
          </div>

          <Button type="submit" disabled={saving}>
            {saving ? "Saving..." : "Save Profile"}
          </Button>
        </form>
      </main>
    </div>
  );
};

export default ProfileForm;
