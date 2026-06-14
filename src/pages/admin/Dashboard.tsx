import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { supabaseAdmin as supabase } from "@/lib/supabase";

interface Stats {
  experiences: number;
  skills: number;
}

const Dashboard = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats>({ experiences: 0, skills: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        navigate("/admin/login");
        return;
      }

      // Load counts in parallel
      try {
        const [expRes, skillRes] = await Promise.all([
          supabase.from("experiences").select("id", { count: "exact", head: true }),
          supabase.from("skills").select("id", { count: "exact", head: true }),
        ]);
        setStats({
          experiences: expRes.count ?? 0,
          skills: skillRes.count ?? 0,
        });
      } catch (_) {
        // counts unavailable — display zeros
      }
      setLoading(false);
    };

    init();
  }, [navigate]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate("/admin/login");
  };

  const navLinks = [
    { label: "Profile", to: "/admin/profile" },
  ];

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside className="w-56 bg-card border-r border-border flex flex-col">
        <div className="p-6 border-b border-border">
          <h1 className="text-lg font-serif text-foreground mb-3">Admin</h1>
          <Link to="/" className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            ← Back to site
          </Link>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="block px-4 py-2.5 rounded-xl text-sm text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="p-4 border-t border-border">
          <button
            onClick={handleLogout}
            className="w-full px-4 py-2.5 rounded-xl text-sm text-warning hover:bg-warning-muted transition-colors text-left"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 p-10">
        <h2 className="text-3xl font-serif text-foreground mb-2">Dashboard</h2>
        <p className="text-muted-foreground mb-8">Welcome back.</p>

        {loading ? (
          <div className="grid grid-cols-2 gap-6">
            {[1, 2].map((i) => (
              <div key={i} className="animate-pulse h-24 bg-card border border-border rounded-2xl" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-6">
            <div className="p-6 bg-card border border-border rounded-2xl">
              <p className="text-3xl font-serif text-foreground mb-1">{stats.experiences}</p>
              <p className="text-sm text-muted-foreground">Experiences</p>
            </div>
            <div className="p-6 bg-card border border-border rounded-2xl">
              <p className="text-3xl font-serif text-foreground mb-1">{stats.skills}</p>
              <p className="text-sm text-muted-foreground">Skills</p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
