import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Hexagon } from "lucide-react";

export default function Onboarding() {
  const { createWorkspace } = useAuth();
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await createWorkspace(name, industry);
      toast.success("Workspace created");
      nav("/app");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to create workspace");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f7f7f5] p-6">
      <div className="max-w-md w-full">
        <div className="flex items-center gap-2 mb-8">
          <Hexagon className="h-6 w-6 text-[#FF3823]" strokeWidth={2.5} />
          <span className="font-heading text-xl">NexusCRM</span>
        </div>
        <h1 className="font-heading text-4xl leading-tight">Set up your<br />workspace.</h1>
        <p className="text-neutral-500 mt-3">Give your company workspace a name. You can invite teammates later.</p>

        <form onSubmit={onSubmit} className="mt-8 space-y-5" data-testid="onboarding-form">
          <div>
            <Label htmlFor="wname">Company name</Label>
            <Input id="wname" value={name} onChange={e=>setName(e.target.value)} required
                   placeholder="Acme Inc."
                   className="rounded-sm mt-1.5" data-testid="workspace-name-input" />
          </div>
          <div>
            <Label htmlFor="wind">Industry (optional)</Label>
            <Input id="wind" value={industry} onChange={e=>setIndustry(e.target.value)}
                   placeholder="SaaS, Fintech, Healthcare…"
                   className="rounded-sm mt-1.5" data-testid="workspace-industry-input" />
          </div>
          <Button type="submit" disabled={busy}
                  className="w-full rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 h-11" data-testid="workspace-create-submit">
            {busy ? "Creating…" : "Create workspace"}
          </Button>
        </form>
      </div>
    </div>
  );
}
