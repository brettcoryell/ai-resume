import { useEffect, useState, FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { supabaseAdmin, ar, arAdmin } from "@/lib/supabase";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Info } from "lucide-react";

interface ProfileData {
  id?: string;
  name: string;
  title: string;
  email: string;
  elevator_pitch: string;
  availability_status: string;
  linkedin_url: string;
  target_company_stages: string;
}

const EMPTY: ProfileData = {
  name: "",
  title: "",
  email: "",
  elevator_pitch: "",
  availability_status: "",
  linkedin_url: "",
  target_company_stages: "",
};

const AVAILABILITY_OPTIONS = [
  { value: "", label: "— Hidden (no badge shown) —" },
  { value: "Open to new opportunities", label: "Open to new opportunities" },
  { value: "Selectively exploring", label: "Selectively exploring" },
  { value: "Not currently looking", label: "Not currently looking" },
];

function InfoTip({ text }: { text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Info size={13} className="inline-block ml-1.5 text-muted-foreground cursor-help align-middle" />
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs text-xs">
        {text}
      </TooltipContent>
    </Tooltip>
  );
}

function FieldLabel({ htmlFor, label, tip }: { htmlFor: string; label: string; tip: string }) {
  return (
    <Label htmlFor={htmlFor}>
      {label}
      <InfoTip text={tip} />
    </Label>
  );
}

const ProfileForm = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProfileData>(EMPTY);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const init = async () => {
      const { data: { user } } = await supabaseAdmin.auth.getUser();
      if (!user) { navigate("/admin/login"); return; }

      // Read via public client — candidate_profile has USING (true) for all roles
      const { data, error } = await ar.from("candidate_profile").select("*").maybeSingle();
      if (error) {
        setLoadError(error.message);
      } else if (data) {
        setProfileId(data.id);
        setForm({
          name: data.name ?? "",
          title: data.title ?? "",
          email: data.email ?? "",
          elevator_pitch: data.elevator_pitch ?? "",
          availability_status: data.availability_status ?? "",
          linkedin_url: data.linkedin_url ?? "",
          target_company_stages: Array.isArray(data.target_company_stages)
            ? data.target_company_stages.join(", ")
            : "",
        });
      }
      setLoading(false);
    };
    init();
  }, [navigate]);

  const set = (field: keyof ProfileData) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);

    const payload: Record<string, unknown> = {
      name: form.name,
      title: form.title,
      email: form.email,
      elevator_pitch: form.elevator_pitch,
      availability_status: form.availability_status || null,
      linkedin_url: form.linkedin_url,
      target_company_stages: form.target_company_stages
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };

    if (profileId) payload.id = profileId;

    const { error } = await arAdmin.from("candidate_profile").upsert(payload);

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
        <p className="text-muted-foreground text-sm">Loading…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside className="w-56 bg-card border-r border-border flex flex-col shrink-0">
        <div className="p-6 border-b border-border">
          <h1 className="text-lg font-serif text-foreground mb-3">Admin</h1>
          <Link to="/" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            ← Back to site
          </Link>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          <Link
            to="/admin"
            className="block px-4 py-2.5 rounded-xl text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
          >
            Dashboard
          </Link>
          <Link
            to="/admin/profile"
            className="block px-4 py-2.5 rounded-xl text-sm text-foreground bg-secondary"
          >
            Profile
          </Link>
        </nav>
        <div className="p-4 border-t border-border">
          <button
            onClick={async () => { await supabaseAdmin.auth.signOut(); navigate("/admin/login"); }}
            className="w-full px-4 py-2.5 rounded-xl text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors text-left"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 p-10 max-w-2xl">
        <h2 className="text-3xl font-serif text-foreground mb-1">Profile</h2>
        <p className="text-sm text-muted-foreground mb-8">
          These fields are live on the public site. Changes take effect immediately after saving.
        </p>

        {loadError && (
          <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 rounded-xl text-sm text-destructive">
            Failed to load profile: {loadError}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">

          {/* Availability — most actionable field, first */}
          <div className="space-y-1.5">
            <FieldLabel
              htmlFor="availability_status"
              label="Availability Status"
              tip="Shown as a pill badge in the hero section. Set to hidden when you're not actively looking."
            />
            <select
              id="availability_status"
              value={form.availability_status}
              onChange={set("availability_status")}
              className="w-full bg-background border border-input rounded-xl px-4 py-2.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring transition-colors"
            >
              {AVAILABILITY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <FieldLabel htmlFor="name" label="Name" tip="Shown in the nav header, hero section, and footer." />
              <Input id="name" value={form.name} onChange={set("name")} />
            </div>
            <div className="space-y-1.5">
              <FieldLabel htmlFor="title" label="Title" tip="Shown below your name in the hero section and in the footer." />
              <Input id="title" value={form.title} onChange={set("title")} />
            </div>
          </div>

          <div className="space-y-1.5">
            <FieldLabel htmlFor="elevator_pitch" label="Elevator Pitch" tip="The short paragraph shown below your title in the hero section." />
            <Textarea id="elevator_pitch" rows={3} value={form.elevator_pitch} onChange={set("elevator_pitch")} />
          </div>

          <div className="space-y-1.5">
            <FieldLabel
              htmlFor="target_company_stages"
              label="Target Company Stages"
              tip="Shown as pills in the hero section. Comma-separated — e.g. Series B, Series C, Growth."
            />
            <Input
              id="target_company_stages"
              value={form.target_company_stages}
              onChange={set("target_company_stages")}
              placeholder="Series B, Series C, Growth"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <FieldLabel htmlFor="email" label="Email" tip="Shown as a mailto link in the footer." />
              <Input id="email" type="email" value={form.email} onChange={set("email")} />
            </div>
            <div className="space-y-1.5">
              <FieldLabel htmlFor="linkedin_url" label="LinkedIn URL" tip="Shown as a link in the footer." />
              <Input id="linkedin_url" value={form.linkedin_url} onChange={set("linkedin_url")} placeholder="https://linkedin.com/in/..." />
            </div>
          </div>

          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save Profile"}
          </Button>
        </form>

        {/* Not implemented yet */}
        <div className="mt-12 pt-8 border-t border-border">
          <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wide mb-1">Not implemented yet</h3>
          <p className="text-xs text-muted-foreground mb-5">
            These fields exist in the database but aren't wired to any part of the public site yet.
          </p>
          <div className="space-y-4 opacity-50 pointer-events-none select-none">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="salary_min">Salary Min</Label>
                <Input id="salary_min" placeholder="e.g. 300000" disabled />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="salary_max">Salary Max</Label>
                <Input id="salary_max" placeholder="e.g. 450000" disabled />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="location">Location</Label>
                <Input id="location" placeholder="e.g. Denver, CO" disabled />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="remote_preference">Remote Preference</Label>
                <Input id="remote_preference" placeholder="e.g. Remote, Hybrid" disabled />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="github_url">GitHub URL</Label>
              <Input id="github_url" placeholder="https://github.com/..." disabled />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="career_narrative">Career Narrative</Label>
              <Textarea id="career_narrative" rows={3} disabled placeholder="Long-form narrative — not yet wired to the site." />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ProfileForm;
