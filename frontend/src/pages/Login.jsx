import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Hexagon } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      toast.success("Welcome back");
      nav("/app");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#f7f7f5]">
      <div className="hidden lg:flex bg-[#0A0A0A] text-white p-12 flex-col justify-between">
        <div className="flex items-center gap-2">
          <Hexagon className="h-6 w-6 text-[#FF3823]" strokeWidth={2.5} />
          <span className="font-heading text-xl">NexusCRM</span>
        </div>
        <div>
          <h2 className="font-heading text-5xl leading-[0.95]">Signal.<br />Not noise.</h2>
          <p className="text-neutral-400 mt-6 max-w-md">
            The tactical CRM for teams that need to move fast and close deals — with AI insights baked in.
          </p>
        </div>
        <div className="text-[10px] font-mono-data uppercase tracking-widest text-neutral-500">
          v1.0 · Multi-tenant
        </div>
      </div>

      <div className="flex items-center justify-center p-8 text-neutral-900">
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-6" data-testid="login-form">
          <div>
            <h1 className="font-heading text-3xl">Welcome back</h1>
            <p className="text-sm text-neutral-500 mt-1">Sign in to your workspace.</p>
          </div>

          <div className="space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={e=>setEmail(e.target.value)} required
                     placeholder="name@company.com" autoComplete="email"
                     className="rounded-sm mt-1.5" data-testid="login-email" />
            </div>
            <div>
              <Label htmlFor="pw">Password</Label>
              <Input id="pw" type="password" value={password} onChange={e=>setPassword(e.target.value)} required
                     placeholder="••••••••" autoComplete="current-password"
                     className="rounded-sm mt-1.5" data-testid="login-password" />
            </div>
          </div>

          <Button type="submit" disabled={busy}
                  className="w-full rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 h-11" data-testid="login-submit">
            {busy ? "Signing in…" : "Sign in"}
          </Button>

          <div className="text-sm text-center text-neutral-500">
            No account? <Link to="/signup" className="text-[#0047FF] hover:underline" data-testid="login-goto-signup">Create one</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
