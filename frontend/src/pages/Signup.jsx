import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Hexagon } from "lucide-react";

export default function Signup() {
  const { signup } = useAuth();
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await signup(email, password, name);
      toast.success("Account created");
      nav("/onboarding");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Signup failed");
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
          <h2 className="font-heading text-5xl leading-[0.95]">Ship deals.<br />Not spreadsheets.</h2>
          <p className="text-neutral-400 mt-6 max-w-md">
            Get your workspace running in under 60 seconds. AI insights included.
          </p>
        </div>
        <div className="text-[10px] font-mono-data uppercase tracking-widest text-neutral-500">Free · 14-day trial</div>
      </div>

      <div className="flex items-center justify-center p-8 text-neutral-900">
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-6" data-testid="signup-form">
          <div>
            <h1 className="font-heading text-3xl">Create your account</h1>
            <p className="text-sm text-neutral-500 mt-1">You&apos;ll set up your workspace next.</p>
          </div>

          <div className="space-y-4">
            <div>
              <Label htmlFor="name">Full name</Label>
              <Input id="name" value={name} onChange={e=>setName(e.target.value)} required
                     placeholder="John Doe" autoComplete="name"
                     className="rounded-sm mt-1.5" data-testid="signup-name" />
            </div>
            <div>
              <Label htmlFor="email">Work email</Label>
              <Input id="email" type="email" value={email} onChange={e=>setEmail(e.target.value)} required
                     placeholder="name@company.com" autoComplete="email"
                     className="rounded-sm mt-1.5" data-testid="signup-email" />
            </div>
            <div>
              <Label htmlFor="pw">Password</Label>
              <Input id="pw" type="password" value={password} onChange={e=>setPassword(e.target.value)} required minLength={6}
                     placeholder="••••••••" autoComplete="new-password"
                     className="rounded-sm mt-1.5" data-testid="signup-password" />
              <p className="text-xs text-neutral-500 mt-1">Minimum 6 characters</p>
            </div>
          </div>

          <Button type="submit" disabled={busy}
                  className="w-full rounded-sm bg-[#0047FF] hover:bg-[#0036CC] h-11" data-testid="signup-submit">
            {busy ? "Creating…" : "Create account"}
          </Button>

          <div className="text-sm text-center text-neutral-500">
            Have an account? <Link to="/login" className="text-[#0047FF] hover:underline" data-testid="signup-goto-login">Sign in</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
