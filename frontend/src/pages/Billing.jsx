import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Check, Sparkles, Zap, Rocket, CreditCard } from "lucide-react";

const ICONS = { starter: Sparkles, pro: Zap, team: Rocket };

export default function Billing() {
  const [plans, setPlans] = useState({});
  const [sub, setSub] = useState(null);
  const [busy, setBusy] = useState(null);
  const [params, setParams] = useSearchParams();

  const load = async () => {
    try {
      const [p, s] = await Promise.all([
        api.get("/billing/plans"),
        api.get("/billing/subscription"),
      ]);
      setPlans(p.data.plans);
      setSub(s.data);
    } catch { toast.error("Failed to load billing"); }
  };
  useEffect(() => { load(); }, []);

  // Handle success/cancel redirects from Stripe
  useEffect(() => {
    const st = params.get("status");
    const sid = params.get("session_id");
    if (st === "success" && sid) {
      let tries = 0;
      const poll = async () => {
        try {
          const { data } = await api.get(`/payments/status/${sid}`);
          if (data.payment_status === "paid") {
            toast.success("Payment successful — your plan is upgraded.");
            setParams({});
            load();
            return;
          }
        } catch { /* keep polling */ }
        if (tries++ < 8) setTimeout(poll, 2000);
        else { toast.info("Payment processing — check back shortly."); setParams({}); }
      };
      poll();
    } else if (st === "cancel") {
      toast.info("Payment cancelled.");
      setParams({});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const upgrade = async (planId) => {
    setBusy(planId);
    try {
      const { data } = await api.post("/billing/checkout", {
        plan_id: planId,
        origin_url: window.location.origin,
      });
      window.location.href = data.checkout_url;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Checkout failed");
      setBusy(null);
    }
  };

  const currentPlan = sub?.plan || "starter";

  return (
    <div className="space-y-8" data-testid="billing-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-heading text-4xl md:text-5xl">Billing</h1>
          <p className="text-sm text-muted-foreground mt-1 font-mono-data uppercase tracking-widest">
            Current plan · {currentPlan}
          </p>
        </div>
        <Card className="rounded-sm border-border p-4 flex items-center gap-3 shadow-sm">
          <CreditCard className="h-5 w-5 text-primary" />
          <div>
            <div className="text-xs uppercase font-mono-data text-muted-foreground">Status</div>
            <div className="text-sm font-medium capitalize">{sub?.status || "active"}</div>
          </div>
        </Card>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {Object.entries(plans).map(([id, plan]) => {
          const Icon = ICONS[id] || Sparkles;
          const isCurrent = id === currentPlan;
          const isFree = plan.price === 0;
          return (
            <Card key={id}
                  className={`rounded-sm border shadow-sm p-6 flex flex-col ${isCurrent ? "border-primary border-2" : "border-border"}`}
                  data-testid={`plan-${id}`}>
              <div className="flex items-center justify-between">
                <Icon className={`h-5 w-5 ${id === "team" ? "text-[#FF3823]" : "text-primary"}`} />
                {isCurrent && <Badge className="bg-primary text-primary-foreground rounded-sm hover:bg-primary">Current</Badge>}
              </div>
              <div className="mt-4">
                <div className="font-heading text-2xl">{plan.name}</div>
                <div className="mt-2 flex items-baseline gap-1">
                  <span className="font-heading text-4xl">${plan.price}</span>
                  <span className="text-sm text-muted-foreground">/month</span>
                </div>
              </div>
              <ul className="mt-6 space-y-2 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm">
                    <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" /> {f}
                  </li>
                ))}
              </ul>
              <div className="mt-6">
                {isFree ? (
                  <Button disabled variant="outline" className="w-full rounded-sm" data-testid={`plan-cta-${id}`}>
                    Free forever
                  </Button>
                ) : isCurrent ? (
                  <Button disabled variant="outline" className="w-full rounded-sm" data-testid={`plan-cta-${id}`}>
                    You&apos;re on this plan
                  </Button>
                ) : (
                  <Button onClick={() => upgrade(id)} disabled={busy === id}
                          className="w-full rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white dark:bg-[#0047FF] dark:hover:bg-[#0036CC]"
                          data-testid={`plan-cta-${id}`}>
                    {busy === id ? "Redirecting…" : `Upgrade to ${plan.name}`}
                  </Button>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      <Card className="rounded-sm border-border shadow-sm p-6">
        <div className="text-xs uppercase tracking-widest font-mono-data text-muted-foreground mb-3">Test cards</div>
        <p className="text-sm text-muted-foreground">
          Use Stripe test card <span className="font-mono-data text-foreground">4242 4242 4242 4242</span> with any future expiry and any CVC to complete a test upgrade. No real charges are made.
        </p>
      </Card>
    </div>
  );
}
