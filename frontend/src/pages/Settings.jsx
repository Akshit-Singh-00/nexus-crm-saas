import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Plus, Trash2, GripVertical, Palette } from "lucide-react";

export default function Settings() {
  const { activeWorkspace, refresh } = useAuth();
  const [ws, setWs] = useState(null);
  const [name, setName] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [industry, setIndustry] = useState("");
  const [stages, setStages] = useState([]);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/workspaces/settings");
      setWs(data); setName(data.name || ""); setLogoUrl(data.logo_url || "");
      setIndustry(data.industry || ""); setStages(data.pipeline_stages || []);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to load settings"); }
  };
  useEffect(() => { load(); }, []);

  const saveGeneral = async () => {
    setSaving(true);
    try {
      await api.put("/workspaces/settings", { name, logo_url: logoUrl, industry });
      toast.success("Workspace updated"); refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  const saveStages = async () => {
    setSaving(true);
    try {
      await api.put("/workspaces/settings", { pipeline_stages: stages });
      toast.success("Pipeline stages updated");
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  const updateStage = (i, k, v) =>
    setStages(stages.map((s, idx) => (idx === i ? { ...s, [k]: v } : s)));

  const addStage = () => {
    const id = "stage_" + Math.random().toString(36).slice(2, 8);
    setStages([...stages, { id, label: "New stage", color: "#0047FF", probability: 30 }]);
  };
  const removeStage = (i) => setStages(stages.filter((_, idx) => idx !== i));

  const canEditSettings = ["owner", "admin"].includes(activeWorkspace?.role);

  if (!ws) return <div className="text-sm text-muted-foreground">Loading settings…</div>;
  if (!canEditSettings) {
    return (
      <div className="max-w-md">
        <h1 className="font-heading text-3xl">Settings</h1>
        <p className="text-sm text-muted-foreground mt-2">You don&apos;t have permission to view workspace settings.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl" data-testid="settings-page">
      <div>
        <h1 className="font-heading text-4xl md:text-5xl">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1 font-mono-data uppercase tracking-widest">Workspace configuration</p>
      </div>

      <Card className="rounded-sm border-border shadow-sm p-6 space-y-4">
        <div className="text-xs uppercase tracking-widest font-mono-data text-muted-foreground">General</div>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <Label>Workspace name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)}
                   className="rounded-sm mt-1" data-testid="settings-name-input" />
          </div>
          <div>
            <Label>Industry</Label>
            <Input value={industry} onChange={(e) => setIndustry(e.target.value)}
                   className="rounded-sm mt-1" data-testid="settings-industry-input" />
          </div>
          <div className="md:col-span-2">
            <Label>Logo URL</Label>
            <Input value={logoUrl} onChange={(e) => setLogoUrl(e.target.value)}
                   placeholder="https://…"
                   className="rounded-sm mt-1" data-testid="settings-logo-input" />
            {logoUrl && (
              <div className="mt-3 flex items-center gap-3">
                <img src={logoUrl} alt="workspace logo" className="h-10 w-10 rounded-sm object-cover border border-border" />
                <span className="text-xs text-muted-foreground font-mono-data">Preview</span>
              </div>
            )}
          </div>
        </div>
        <div className="pt-2">
          <Button onClick={saveGeneral} disabled={saving}
                  className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="save-general-btn">
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </Card>

      <Card className="rounded-sm border-border shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-widest font-mono-data text-muted-foreground">Pipeline stages</div>
            <p className="text-sm mt-1">Customize deal stages for your sales process.</p>
          </div>
          <Button onClick={addStage} variant="outline" className="rounded-sm" data-testid="add-stage-btn">
            <Plus className="h-4 w-4 mr-2" /> Add stage
          </Button>
        </div>
        <div className="space-y-2">
          {stages.map((s, i) => (
            <div key={i} className="flex items-center gap-2 p-2 border border-border rounded-sm bg-card" data-testid={`stage-row-${i}`}>
              <GripVertical className="h-4 w-4 text-muted-foreground" />
              <Input value={s.label} onChange={(e) => updateStage(i, "label", e.target.value)}
                     className="rounded-sm flex-1" data-testid={`stage-label-${i}`} />
              <Input type="color" value={s.color} onChange={(e) => updateStage(i, "color", e.target.value)}
                     className="w-14 h-9 p-1 rounded-sm" title="Stage color" data-testid={`stage-color-${i}`} />
              <div className="w-24">
                <Input type="number" min={0} max={100} value={s.probability}
                       onChange={(e) => updateStage(i, "probability", parseInt(e.target.value || "0", 10))}
                       className="rounded-sm font-mono-data text-xs" title="Probability %"
                       data-testid={`stage-prob-${i}`} />
              </div>
              <Button variant="ghost" size="sm" onClick={() => removeStage(i)}
                      className="text-muted-foreground hover:text-[#FF3823]" data-testid={`stage-remove-${i}`}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
        <div className="pt-2">
          <Button onClick={saveStages} disabled={saving}
                  className="rounded-sm bg-[#0047FF] hover:bg-[#0036CC] text-white" data-testid="save-stages-btn">
            {saving ? "Saving…" : "Save pipeline"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
