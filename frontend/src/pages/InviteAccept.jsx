import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Hexagon, AlertTriangle } from "lucide-react";

export default function InviteAccept() {
  const { token } = useParams();
  const nav = useNavigate();
  const [invite, setInvite] = useState(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/invites/${token}`);
        setInvite(data);
      } catch (e) {
        setError(e?.response?.data?.detail || "Invalid or expired invite");
      }
    })();
  }, [token]);

  const accept = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post(`/invites/${token}/accept`, { password, name });
      localStorage.setItem("nexus_token", data.token);
      localStorage.setItem("nexus_workspace_id", data.workspace_id);
      toast.success("You're in!");
      window.location.href = "/app";
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to accept invite");
    } finally { setBusy(false); }
  };

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground p-6">
        <div className="max-w-md text-center">
          <AlertTriangle className="h-10 w-10 text-[#FF3823] mx-auto mb-4" />
          <h1 className="font-heading text-2xl">Invitation invalid</h1>
          <p className="text-sm text-muted-foreground mt-2">{error}</p>
          <Button onClick={() => nav("/login")} className="mt-6 rounded-sm">Go to sign in</Button>
        </div>
      </div>
    );
  }

  if (!invite) return <div className="min-h-screen flex items-center justify-center text-sm text-muted-foreground">Loading invitation…</div>;

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background text-foreground">
      <div className="hidden lg:flex bg-[#0A0A0A] text-white p-12 flex-col justify-between">
        <div className="flex items-center gap-2">
          <Hexagon className="h-6 w-6 text-[#FF3823]" strokeWidth={2.5} />
          <span className="font-heading text-xl">NexusCRM</span>
        </div>
        <div>
          <h2 className="font-heading text-5xl leading-[0.95]">Join the team.</h2>
          <p className="text-neutral-400 mt-6 max-w-md">
            You&apos;ve been invited to <strong className="text-white">{invite.workspace.name}</strong> as a <strong className="text-white">{invite.role}</strong>. Set a password to get in.
          </p>
        </div>
        <div className="text-[10px] font-mono-data uppercase tracking-widest text-neutral-500">
          Invitation for {invite.email}
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <form onSubmit={accept} className="w-full max-w-sm space-y-6" data-testid="invite-accept-form">
          <div>
            <h1 className="font-heading text-3xl">Accept invitation</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Joining <strong>{invite.workspace.name}</strong> as <strong>{invite.role}</strong>.
            </p>
          </div>
          <div className="space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" value={invite.email} disabled className="rounded-sm mt-1.5 opacity-70" />
            </div>
            {!invite.user_exists && (
              <div>
                <Label htmlFor="name">Full name</Label>
                <Input id="name" value={name} onChange={e => setName(e.target.value)} required
                       className="rounded-sm mt-1.5" data-testid="invite-name-input" />
              </div>
            )}
            <div>
              <Label htmlFor="pw">{invite.user_exists ? "Password" : "Set a password"}</Label>
              <Input id="pw" type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={6}
                     className="rounded-sm mt-1.5" data-testid="invite-password-input" />
              <p className="text-xs text-muted-foreground mt-1">Minimum 6 characters</p>
            </div>
          </div>
          <Button type="submit" disabled={busy}
                  className="w-full rounded-sm bg-[#0047FF] hover:bg-[#0036CC] h-11" data-testid="invite-accept-submit">
            {busy ? "Joining…" : `Join ${invite.workspace.name}`}
          </Button>
        </form>
      </div>
    </div>
  );
}
