import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Brain, TrendingUp, Users, Target, Kanban, CheckSquare, DollarSign } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from "recharts";

const currency = (n) => `$${Number(n||0).toLocaleString()}`;

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [forecast, setForecast] = useState("");
  const [aiBusy, setAiBusy] = useState(false);

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const { data } = await api.get("/analytics/overview");
      setData(data);
    } catch (e) {
      toast.error("Failed to load analytics");
    }
  };

  const runForecast = async () => {
    setAiBusy(true);
    try {
      const { data } = await api.get("/ai/sales-forecast");
      setForecast(data.forecast || "");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "AI forecast failed");
    } finally { setAiBusy(false); }
  };

  if (!data) return <div className="text-sm text-neutral-500">Loading dashboard…</div>;

  const kpis = [
    { label: "Customers", val: data.totals.customers, icon: Users },
    { label: "Leads", val: data.totals.leads, icon: Target },
    { label: "Deals", val: data.totals.deals, icon: Kanban },
    { label: "Open Tasks", val: data.totals.open_tasks, icon: CheckSquare },
  ];

  const stageColors = {
    lead: "#94a3b8", qualified: "#0047FF", proposal: "#0036CC",
    negotiation: "#0A0A0A", won: "#10b981", lost: "#FF3823"
  };

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-heading text-4xl md:text-5xl">Dashboard</h1>
          <p className="text-sm text-neutral-500 mt-1 font-mono-data uppercase tracking-widest">Real-time · overview</p>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpis.map(k => (
          <Card key={k.label} className="rounded-sm border-[#E2E2E0] shadow-sm p-5" data-testid={`kpi-${k.label.toLowerCase().replace(' ','-')}`}>
            <div className="flex items-center justify-between text-neutral-500">
              <span className="text-xs uppercase tracking-widest font-mono-data">{k.label}</span>
              <k.icon className="h-4 w-4" />
            </div>
            <div className="font-heading text-4xl mt-3">{k.val}</div>
          </Card>
        ))}
      </div>

      {/* Pipeline + AI */}
      <div className="grid lg:grid-cols-12 gap-4">
        <Card className="rounded-sm border-[#E2E2E0] shadow-sm p-6 lg:col-span-8">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-xs uppercase tracking-widest font-mono-data text-neutral-500">Pipeline value by stage</div>
              <div className="font-heading text-2xl mt-1">{currency(data.totals.pipeline_value)}</div>
            </div>
            <div className="text-right">
              <div className="text-xs uppercase tracking-widest font-mono-data text-neutral-500">Won</div>
              <div className="font-heading text-2xl mt-1 text-[#10b981]">{currency(data.totals.won_value)}</div>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.pipeline_by_stage}>
                <XAxis dataKey="stage" tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={{ stroke: '#E2E2E0' }} />
                <YAxis tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={{ stroke: '#E2E2E0' }} />
                <Tooltip
                  contentStyle={{ background: '#0A0A0A', border: 'none', borderRadius: 4, color: 'white', fontFamily: 'IBM Plex Mono', fontSize: 12 }}
                  formatter={(v) => currency(v)}
                />
                <Bar dataKey="value" radius={0}>
                  {data.pipeline_by_stage.map((s) => (
                    <Cell key={s.stage} fill={stageColors[s.stage]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="ai-grain rounded-sm border-[#E2E2E0] border-l-4 border-l-[#FF3823] shadow-sm p-6 lg:col-span-4 bg-[#FFF0EE]/40">
          <div className="flex items-center gap-2 text-[#FF3823]">
            <Brain className="h-4 w-4" />
            <span className="text-xs uppercase tracking-widest font-mono-data">AI Sales Forecast</span>
          </div>
          <div className="font-heading text-xl mt-3">Predict Q1 revenue</div>
          <p className="text-sm text-neutral-600 mt-2">
            Claude analyses your current pipeline to project next-quarter revenue.
          </p>
          {forecast ? (
            <div className="mt-4 text-sm bg-white/70 border border-[#E2E2E0] p-3 rounded-sm whitespace-pre-wrap" data-testid="ai-forecast-result">
              {forecast}
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

      {/* Leads by status */}
      <Card className="rounded-sm border-[#E2E2E0] shadow-sm p-6">
        <div className="text-xs uppercase tracking-widest font-mono-data text-neutral-500 mb-4">Leads by status</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {["new","contacted","qualified","unqualified"].map(s => {
            const item = data.leads_by_status.find(x => x.status === s);
            return (
              <div key={s} className="border border-[#E2E2E0] rounded-sm p-4">
                <div className="text-[11px] uppercase font-mono-data text-neutral-500">{s}</div>
                <div className="font-heading text-3xl mt-1">{item?.count || 0}</div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
