import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { ChevronLeft, Brain, Sparkles, Send, MessageSquare, Mail, Phone, Building2, User as UserIcon, DollarSign } from "lucide-react";

const money = (n) => `$${Number(n || 0).toLocaleString()}`;

export default function CustomerDetail() {
  const { id } = useParams();
  const [customer, setCustomer] = useState(null);
  const [notes, setNotes] = useState([]);
  const [activities, setActivities] = useState([]);
  const [deals, setDeals] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [note, setNote] = useState("");
  const [summary, setSummary] = useState("");
  const [aiBusy, setAiBusy] = useState(false);

  const load = async () => {
    try {
      const [c, n, a, d, t] = await Promise.all([
        api.get(`/customers/${id}`),
        api.get("/notes", { params: { related_type: "customer", related_id: id } }),
        api.get("/activities", { params: { limit: 100 } }),
        api.get("/deals"),
        api.get("/tasks"),
      ]);
      setCustomer(c.data);
      setNotes(n.data);
      setActivities(a.data.filter((x) => x.entity_id === id));
      setDeals(d.data.filter((x) => x.customer_id === id));
      setTasks(t.data.filter((x) => x.related_type === "customer" && x.related_id === id));
    } catch { toast.error("Failed to load"); }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [id]);

  const addNote = async () => {
    if (!note.trim()) return;
    try {
      await api.post("/notes", { content: note, related_type: "customer", related_id: id });
      setNote(""); load();
    } catch { toast.error("Failed"); }
  };

  const summarize = async () => {
    setAiBusy(true);
    try {
      const { data } = await api.post(`/ai/summarize-customer/${id}`);
      setSummary(data.summary || "");
    } catch (e) { toast.error(e?.response?.data?.detail || "AI failed"); }
    finally { setAiBusy(false); }
  };

  if (!customer) return <div className="text-sm text-muted-foreground">Loading…</div>;

  const openDeals = deals.filter((d) => !["won", "lost"].includes(d.stage));
  const totalValue = deals.reduce((a, b) => a + (b.value || 0), 0);
  const healthy = customer.status === "active" && openDeals.length > 0;
  const health = customer.status === "churned" ? "at-risk" : healthy ? "healthy" : "neutral";
  const healthColor = { healthy: "bg-green-500", "at-risk": "bg-[#FF3823]", neutral: "bg-neutral-400" }[health];

  return (
    <div className="space-y-6" data-testid="customer-detail-page">
      <div>
        <Link to="/app/customers" className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
          <ChevronLeft className="h-4 w-4" /> All customers
        </Link>
      </div>

      {/* Header card */}
      <Card className="rounded-sm border-border shadow-sm p-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <div className={`h-2 w-2 rounded-full ${healthColor}`} title={health} />
              <h1 className="font-heading text-3xl md:text-4xl truncate">{customer.name}</h1>
            </div>
            <div className="flex flex-wrap items-center gap-4 mt-3 text-sm text-muted-foreground">
              {customer.company && <span className="flex items-center gap-1.5"><Building2 className="h-3.5 w-3.5" />{customer.company}</span>}
              {customer.email && <span className="flex items-center gap-1.5"><Mail className="h-3.5 w-3.5" /><a href={`mailto:${customer.email}`} className="hover:text-foreground">{customer.email}</a></span>}
              {customer.phone && <span className="flex items-center gap-1.5"><Phone className="h-3.5 w-3.5" />{customer.phone}</span>}
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-right">
              <div className="text-[10px] uppercase font-mono-data text-muted-foreground">Total value</div>
              <div className="font-heading text-2xl">{money(totalValue)}</div>
            </div>
            <div className="text-right">
              <div className="text-[10px] uppercase font-mono-data text-muted-foreground">Status</div>
              <Badge className="mt-1 rounded-sm border-0 bg-blue-100 text-blue-800 hover:bg-blue-100 capitalize">{customer.status}</Badge>
            </div>
          </div>
        </div>
      </Card>

      {/* AI Summary */}
      <Card className="ai-grain rounded-sm border-border border-l-4 border-l-[#FF3823] shadow-sm p-6 bg-[#FFF0EE]/40 dark:bg-[#FF3823]/5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[#FF3823]">
              <Brain className="h-4 w-4" />
              <span className="text-xs uppercase tracking-widest font-mono-data">AI Customer Summary</span>
            </div>
            <div className="font-heading text-xl mt-2">Executive brief</div>
          </div>
          {!summary && (
            <Button onClick={summarize} disabled={aiBusy}
                    className="rounded-sm bg-[#FF3823] hover:bg-[#e02f1c] text-white h-10" data-testid="ai-summarize-btn">
              <Sparkles className="h-4 w-4 mr-2" /> {aiBusy ? "Analysing…" : "Generate summary"}
            </Button>
          )}
        </div>
        {summary && (
          <div className="mt-4 text-sm bg-card/70 border border-border p-4 rounded-sm whitespace-pre-wrap" data-testid="ai-summary-result">
            {summary}
          </div>
        )}
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList className="rounded-sm">
          <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="deals" data-testid="tab-deals">Deals · {deals.length}</TabsTrigger>
          <TabsTrigger value="tasks" data-testid="tab-tasks">Tasks · {tasks.length}</TabsTrigger>
          <TabsTrigger value="notes" data-testid="tab-notes">Notes · {notes.length}</TabsTrigger>
          <TabsTrigger value="activity" data-testid="tab-activity">Activity · {activities.length}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <div className="grid md:grid-cols-3 gap-4">
            <Card className="rounded-sm border-border shadow-sm p-5">
              <div className="text-xs uppercase font-mono-data text-muted-foreground">Open deals</div>
              <div className="font-heading text-3xl mt-2">{openDeals.length}</div>
              <div className="text-sm text-muted-foreground mt-1">{money(openDeals.reduce((a, b) => a + (b.value || 0), 0))}</div>
            </Card>
            <Card className="rounded-sm border-border shadow-sm p-5">
              <div className="text-xs uppercase font-mono-data text-muted-foreground">Open tasks</div>
              <div className="font-heading text-3xl mt-2">{tasks.filter((t) => t.status !== "done").length}</div>
            </Card>
            <Card className="rounded-sm border-border shadow-sm p-5">
              <div className="text-xs uppercase font-mono-data text-muted-foreground">Notes</div>
              <div className="font-heading text-3xl mt-2">{notes.length}</div>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="deals" className="mt-6 space-y-2">
          {deals.length === 0 && <div className="text-sm text-muted-foreground">No deals for this customer yet.</div>}
          {deals.map((d) => (
            <Card key={d.id} className="rounded-sm border-border shadow-sm p-4 flex items-center justify-between" data-testid={`customer-deal-${d.id}`}>
              <div>
                <div className="font-medium">{d.title}</div>
                <div className="text-xs text-muted-foreground mt-1 font-mono-data">Stage: {d.stage} · Probability: {d.probability ?? "—"}%</div>
              </div>
              <div className="font-mono-data text-lg"><DollarSign className="inline h-3.5 w-3.5" />{Number(d.value || 0).toLocaleString()}</div>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="tasks" className="mt-6 space-y-2">
          {tasks.length === 0 && <div className="text-sm text-muted-foreground">No tasks linked to this customer yet.</div>}
          {tasks.map((t) => (
            <Card key={t.id} className="rounded-sm border-border shadow-sm p-4 flex items-center justify-between" data-testid={`customer-task-${t.id}`}>
              <div>
                <div className={`font-medium ${t.status === "done" ? "line-through text-muted-foreground" : ""}`}>{t.title}</div>
                {t.description && <div className="text-xs text-muted-foreground mt-1">{t.description}</div>}
              </div>
              <span className="text-[10px] uppercase font-mono-data text-muted-foreground">{t.priority} · {t.status}</span>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="notes" className="mt-6 space-y-4">
          <Card className="rounded-sm border-border shadow-sm p-4">
            <Textarea value={note} onChange={(e) => setNote(e.target.value)}
                      placeholder="Log a note. Use @teammate to mention (coming soon)."
                      className="rounded-sm" data-testid="note-input" />
            <Button onClick={addNote} disabled={!note.trim()}
                    className="mt-3 rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="note-submit">
              <Send className="h-4 w-4 mr-2" /> Add note
            </Button>
          </Card>
          <div className="space-y-3">
            {notes.length === 0 && <div className="text-sm text-muted-foreground">No notes yet.</div>}
            {notes.map((n) => (
              <div key={n.id} className="border-l-2 border-[#0047FF] pl-3 py-1" data-testid={`note-${n.id}`}>
                <div className="text-sm">{n.content}</div>
                <div className="text-[11px] text-muted-foreground mt-1 font-mono-data">
                  {n.author?.name || "Unknown"} · {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
                </div>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="activity" className="mt-6">
          <Card className="rounded-sm border-border shadow-sm p-6">
            {activities.length === 0 && <div className="text-sm text-muted-foreground">No activity yet.</div>}
            <div className="space-y-3">
              {activities.map((a) => (
                <div key={a.id} className="flex items-start gap-3">
                  <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#0047FF]" />
                  <div className="text-sm">
                    <span className="font-medium">{a.actor?.name || "System"}</span>
                    <span className="text-muted-foreground"> {a.action} {a.entity_type}</span>
                    <div className="text-[11px] text-muted-foreground font-mono-data">
                      {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
