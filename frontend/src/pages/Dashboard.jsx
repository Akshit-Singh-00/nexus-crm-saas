import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Brain, TrendingUp, Users, Target, Kanban, CheckSquare, LifeBuoy,
  AlertTriangle, Trophy, Percent, Clock,
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from "recharts";

const money = (n) => `$${Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [forecastText, setForecastText] = useState("");
  const [aiBusy, setAiBusy] = useState(false);

  useEffect(() => { (async () => {
    try { const { data } = await api.get("/analytics/overview"); setData(data); }
    catch { toast.error("Failed to load analytics"); }
  })(); }, []);

  const runForecast = async () => {
    setAiBusy(true);
    try {
      const { data } = await api.get("/ai/sales-forecast");
      setForecastText(data.forecast || "");
    } catch (e) { toast.error(e?.response?.data?.detail || "AI forecast failed"); }
    finally { setAiBusy(false); }
  };

  if (!data) return <div className="text-sm text-muted-foreground">Loading dashboard…</div>;

  const kpis = [
    { label: "Customers", val: data.totals.customers, icon: Users },
    { label: "Leads", val: data.totals.leads, icon: Target },
    { label: "Deals", val: data.totals.deals, icon: Kanban },
    { label: "Open tasks", val: data.totals.open_tasks, icon: CheckSquare },
    { label: "Open tickets", val: data.totals.open_tickets, icon: LifeBuoy },
  ];

  const salesKpis = [
    { label: "Win rate", val: `${data.kpis.win_rate}%`, icon: Trophy, color: "text-green-600" },
    { label: "Avg deal size", val: money(data.kpis.avg_deal_size), icon: Percent, color: "text-[#0047FF]" },
    { label: "Sales cycle", val: `${data.kpis.sales_cycle_days}d`, icon: Clock, color: "text-muted-foreground" },
  ];

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-heading text-4xl md:text-5xl">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1 font-mono-data uppercase tracking-widest">Real-time · overview</p>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {kpis.map((k) => (
          <Card key={k.label} className="rounded-sm border-border shadow-sm p-5" data-testid={`kpi-${k.label.toLowerCase().replace(' ','-')}`}>
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs uppercase tracking-widest font-mono-data">{k.label}</span>
              <k.icon className="h-4 w-4" />
            </div>
            <div className="font-heading text-3xl mt-3">{k.val}</div>
          </Card>
        ))}
      </div>

      {/* Revenue forecast cards */}
      <div>
        <div className="text-xs uppercase tracking-widest font-mono-data text-muted-foreground mb-3">Revenue forecast</div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Committed", val: data.forecast.committed, hint: "≥ 90% probability", accent: "text-green-600" },
            { label: "Best case", val: data.forecast.best_case, hint: "≥ 60% probability", accent: "text-[#0047FF]" },
            { label: "Pipeline", val: data.forecast.pipeline, hint: "All open deals", accent: "text-foreground" },
            { label: "Weighted forecast", val: data.forecast.weighted, hint: "Value × probability", accent: "text-[#FF3823]" },
          ].map((f) => (
            <Card key={f.label} className="rounded-sm border-border shadow-sm p-5" data-testid={`forecast-${f.label.toLowerCase().replace(' ','-')}`}>
              <div className="text-xs uppercase tracking-widest font-mono-data text-muted-foreground">{f.label}</div>
              <div className={`font-heading text-3xl mt-2 ${f.accent}`}>{money(f.val)}</div>
              <div className="text-[11px] text-muted-foreground font-mono-data mt-1">{f.hint}</div>
            </Card>
          ))}
        </div>
      </div>

      {/* Sales KPIs */}
      <div className="grid grid-cols-3 gap-4">
        {salesKpis.map((k) => (
          <Card key={k.label} className="rounded-sm border-border shadow-sm p-5" data-testid={`sales-kpi-${k.label.toLowerCase().replace(' ','-')}`}>
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs uppercase tracking-widest font-mono-data">{k.label}</span>
              <k.icon className={`h-4 w-4 ${k.color}`} />
            </div>
            <div className="font-heading text-3xl mt-3">{k.val}</div>
          </Card>
        ))}
      </div>

      {/* Pipeline chart + AI forecast */}
      <div className="grid lg:grid-cols-12 gap-4">
        <Card className="rounded-sm border-border shadow-sm p-6 lg:col-span-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-xs uppercase tracking-widest font-mono-data text-muted-foreground">Pipeline by stage</div>
              <div className="font-heading text-2xl mt-1">{money(data.totals.pipeline_value)}</div>
            </div>
            <div className="text-right">
              <div className="text-xs uppercase tracking-widest font-mono-data text-muted-foreground">Won</div>
              <div className="font-heading text-2xl mt-1 text-green-600">{money(data.totals.won_value)}</div>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.pipeline_by_stage}>
                <XAxis dataKey="label" tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono', fill: 'currentColor', fillOpacity: 0.6 }} tickLine={false} axisLine={{ stroke: 'currentColor', strokeOpacity: 0.15 }} />
                <YAxis tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono', fill: 'currentColor', fillOpacity: 0.6 }} tickLine={false} axisLine={{ stroke: 'currentColor', strokeOpacity: 0.15 }} />
                <Tooltip contentStyle={{ background: '#0A0A0A', border: 'none', borderRadius: 4, color: 'white', fontFamily: 'IBM Plex Mono', fontSize: 12 }}
                         formatter={(v) => money(v)} />
                <Bar dataKey="value" radius={0}>
                  {data.pipeline_by_stage.map((s) => <Cell key={s.stage} fill={s.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="ai-grain rounded-sm border-border border-l-4 border-l-[#FF3823] shadow-sm p-6 lg:col-span-4 bg-[#FFF0EE]/40 dark:bg-[#FF3823]/5">
          <div className="flex items-center gap-2 text-[#FF3823]">
            <Brain className="h-4 w-4" />
            <span className="text-xs uppercase tracking-widest font-mono-data">AI Forecast Narrative</span>
          </div>
          <div className="font-heading text-xl mt-3">Q1 outlook</div>
          <p className="text-sm text-muted-foreground mt-2">Claude analyses your current pipeline to project next-quarter revenue.</p>
          {forecastText ? (
            <div className="mt-4 text-sm bg-card/70 border border-border p-3 rounded-sm whitespace-pre-wrap" data-testid="ai-forecast-result">
              {forecastText}
            </div>
          ) : (
            <Button onClick={runForecast} disabled={aiBusy}
                    className="mt-4 rounded-sm bg-[#FF3823] hover:bg-[#e02f1c] text-white h-10" data-testid="run-forecast-btn">
              <TrendingUp className="h-4 w-4 mr-2" />
              {aiBusy ? "Analysing…" : "Run forecast"}
            </Button>
          )}
        </Card>
      </div>

      {/* At-risk deals */}
      {data.at_risk_deals && data.at_risk_deals.length > 0 && (
        <Card className="rounded-sm border-border border-l-4 border-l-[#FF3823] shadow-sm p-6" data-testid="at-risk-section">
          <div className="flex items-center gap-2 text-[#FF3823] mb-3">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-xs uppercase tracking-widest font-mono-data">Deals at risk · {data.at_risk_deals.length}</span>
          </div>
          <div className="space-y-2">
            {data.at_risk_deals.map((d) => (
              <Link key={d.id} to="/app/deals" className="flex items-start justify-between gap-3 p-3 border border-border rounded-sm hover:border-[#FF3823] transition-colors" data-testid={`at-risk-${d.id}`}>
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{d.title}</div>
                  <div className="text-xs text-muted-foreground mt-1">{d.risk.reasons.join(" · ")}</div>
                </div>
                <div className="text-right shrink-0">
                  <span className={`text-[10px] uppercase font-mono-data px-2 py-0.5 rounded-sm ${d.risk.level === "high" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-800"}`}>
                    {d.risk.level}
                  </span>
                  <div className="font-mono-data text-sm mt-1">{money(d.value)}</div>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      )}

      {/* Leads by status */}
      <Card className="rounded-sm border-border shadow-sm p-6">
        <div className="text-xs uppercase tracking-widest font-mono-data text-muted-foreground mb-4">Leads by status</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {["new", "contacted", "qualified", "unqualified"].map((s) => {
            const item = data.leads_by_status.find((x) => x.status === s);
            return (
              <div key={s} className="border border-border rounded-sm p-4">
                <div className="text-[11px] uppercase font-mono-data text-muted-foreground">{s}</div>
                <div className="font-heading text-3xl mt-1">{item?.count || 0}</div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
