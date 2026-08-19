import { Link } from "react-router-dom";
import { Hexagon, ArrowUpRight, Zap, Users, Kanban, Brain } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#f7f7f5] text-[#0A0A0A]">
      <header className="border-b border-[#E2E2E0]">
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Hexagon className="h-6 w-6 text-[#FF3823]" strokeWidth={2.5} />
            {/* NexusCRM — AI-Powered Customer Relationship Management */}
            <span className="font-heading text-xl" title="NexusCRM — AI-Powered Customer Relationship Management" aria-label="NexusCRM — AI-Powered Customer Relationship Management">Nexus<span className="text-neutral-500">CRM</span></span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" data-testid="landing-login" className="text-sm hover:underline">Sign in</Link>
            <Link to="/signup">
              <Button data-testid="landing-signup" className="rounded-sm bg-[#0047FF] hover:bg-[#0036CC]">
                Start free
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <section className="max-w-7xl mx-auto px-6 py-24 grid lg:grid-cols-12 gap-12 items-center">
        <div className="lg:col-span-7 space-y-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 border border-[#E2E2E0] bg-white rounded-sm font-mono-data text-[11px] uppercase tracking-widest text-neutral-600">
            <span className="h-1.5 w-1.5 rounded-full bg-[#FF3823] animate-pulse" />
            AI Lead Scoring · Live
          </div>
          <h1 className="font-heading text-5xl md:text-6xl lg:text-7xl leading-[0.95]">
            The tactical CRM<br />
            <span className="text-[#0047FF]">for teams that ship.</span>
          </h1>
          <p className="text-lg text-neutral-600 max-w-xl leading-relaxed">
            Multi-tenant workspaces, kanban deal pipelines, and AI-powered lead insights
            built for lean sales teams that need signal — not noise.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link to="/signup">
              <Button className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white h-11 px-6" data-testid="hero-cta">
                Create your workspace <ArrowUpRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
            <Link to="/login">
              <Button variant="outline" className="rounded-sm border-[#0A0A0A] h-11 px-6">
                Sign in
              </Button>
            </Link>
          </div>
        </div>

        <div className="lg:col-span-5 relative">
          <div className="bg-[#0A0A0A] text-white rounded-sm p-6 shadow-sm">
            <div className="font-mono-data text-[10px] uppercase tracking-widest text-neutral-500 mb-3">Pipeline · Q1</div>
            <div className="font-heading text-4xl">$284,500</div>
            <div className="text-xs text-neutral-400 mt-1">across 47 open deals</div>
            <div className="mt-6 grid grid-cols-4 gap-2">
              {["Lead","Qual","Prop","Neg"].map((s, i) => (
                <div key={s} className="border border-white/10 p-2">
                  <div className="text-[10px] uppercase text-neutral-500 font-mono-data">{s}</div>
                  <div className="text-sm mt-1">{[12,8,5,4][i]}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="ai-grain absolute -bottom-6 -right-6 bg-white border-l-4 border-[#FF3823] border-t border-r border-b border-[#E2E2E0] p-4 max-w-xs shadow-sm">
            <div className="flex items-center gap-2 font-mono-data text-[10px] uppercase tracking-widest text-[#FF3823]">
              <Brain className="h-3.5 w-3.5" /> AI Insight
            </div>
            <p className="text-sm mt-2 leading-snug">
              Acme Corp shows 87% conversion likelihood — book a follow-up this week.
            </p>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-6 py-16 grid md:grid-cols-4 gap-6 border-t border-[#E2E2E0]">
        {[
          { icon: Users, label: "Customers", desc: "Unified profiles with activity history and notes." },
          { icon: Kanban, label: "Pipeline", desc: "Drag-and-drop kanban across six deal stages." },
          { icon: Zap, label: "Tasks", desc: "Priority-driven task management with due dates." },
          { icon: Brain, label: "AI Insights", desc: "Claude-powered scoring, summaries, forecasts." },
        ].map((f) => (
          <div key={f.label} className="p-5 border border-[#E2E2E0] rounded-sm bg-white">
            <f.icon className="h-5 w-5 text-[#0047FF]" />
            <div className="font-heading text-lg mt-3">{f.label}</div>
            <div className="text-sm text-neutral-600 mt-1">{f.desc}</div>
          </div>
        ))}
      </section>

      <footer className="max-w-7xl mx-auto px-6 py-10 text-xs text-neutral-500 font-mono-data uppercase tracking-widest border-t border-[#E2E2E0]">
        NexusCRM · Built for teams that ship
      </footer>
    </div>
  );
}
