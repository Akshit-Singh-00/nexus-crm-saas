import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ChevronLeft, Brain, Sparkles, Send, MessageSquare } from "lucide-react";

export default function CustomerDetail() {
  const { id } = useParams();
  const [customer, setCustomer] = useState(null);
  const [notes, setNotes] = useState([]);
  const [activities, setActivities] = useState([]);
  const [note, setNote] = useState("");
  const [summary, setSummary] = useState("");
  const [aiBusy, setAiBusy] = useState(false);

  const load = async () => {
    try {
      const [c, n, a] = await Promise.all([
        api.get(`/customers/${id}`),
        api.get("/notes", { params: { related_type: "customer", related_id: id } }),
        api.get("/activities", { params: { limit: 20 } }),
      ]);
      setCustomer(c.data); setNotes(n.data);
      setActivities(a.data.filter(x => x.entity_id === id));
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

  return (
    <div className="space-y-6" data-testid="customer-detail-page">
      <div>
        <Link to="/app/customers" className="text-sm text-muted-foreground hover:text-neutral-800 inline-flex items-center gap-1">
          <ChevronLeft className="h-4 w-4" /> All customers
        </Link>
        <div className="flex items-center justify-between mt-2 flex-wrap gap-4">
          <div>
            <h1 className="font-heading text-4xl md:text-5xl">{customer.name}</h1>
            <div className="text-sm text-muted-foreground mt-1 font-mono-data">
              {customer.company || "—"} · {customer.email || "—"}
            </div>
          </div>
          <Badge className="rounded-sm border-0 bg-blue-100 text-blue-800 hover:bg-blue-100">{customer.status}</Badge>
        </div>
      </div>

      <div className="grid lg:grid-cols-12 gap-4">
        <Card className="ai-grain rounded-sm border-border border-l-4 border-l-[#FF3823] shadow-sm p-6 lg:col-span-6 bg-[#FFF0EE]/40">
          <div className="flex items-center gap-2 text-[#FF3823]">
            <Brain className="h-4 w-4" />
            <span className="text-xs uppercase tracking-widest font-mono-data">AI Customer Summary</span>
          </div>
          <div className="font-heading text-xl mt-3">Executive brief</div>
          {summary ? (
            <div className="mt-4 text-sm bg-white/70 border border-border p-4 rounded-sm whitespace-pre-wrap" data-testid="ai-summary-result">
              {summary}
            </div>
          ) : (
            <Button onClick={summarize} disabled={aiBusy}
                    className="mt-4 rounded-sm bg-[#FF3823] hover:bg-[#e02f1c] text-white h-10" data-testid="ai-summarize-btn">
              <Sparkles className="h-4 w-4 mr-2" /> {aiBusy ? "Analysing…" : "Generate summary"}
            </Button>
          )}
        </Card>

        <Card className="rounded-sm border-border shadow-sm p-6 lg:col-span-6">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-[#0047FF]" />
            <span className="text-xs uppercase tracking-widest font-mono-data text-muted-foreground">Notes</span>
          </div>
          <div className="mt-3 space-y-2">
            <Textarea value={note} onChange={e=>setNote(e.target.value)} placeholder="Log a note about this customer…"
                      className="rounded-sm" data-testid="note-input" />
            <Button onClick={addNote} disabled={!note.trim()} className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800" data-testid="note-submit">
              <Send className="h-4 w-4 mr-2" /> Add note
            </Button>
          </div>
          <div className="mt-6 space-y-3 max-h-[300px] overflow-y-auto">
            {notes.length === 0 && <div className="text-sm text-muted-foreground">No notes yet.</div>}
            {notes.map(n => (
              <div key={n.id} className="border-l-2 border-[#0047FF] pl-3 py-1" data-testid={`note-${n.id}`}>
                <div className="text-sm">{n.content}</div>
                <div className="text-[11px] text-muted-foreground mt-1 font-mono-data">
                  {n.author?.name} · {new Date(n.created_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="rounded-sm border-border shadow-sm p-6">
        <div className="text-xs uppercase tracking-widest font-mono-data text-muted-foreground mb-4">Activity timeline</div>
        {activities.length === 0 && <div className="text-sm text-muted-foreground">No activity yet.</div>}
        <div className="space-y-3">
          {activities.map(a => (
            <div key={a.id} className="flex items-start gap-3">
              <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#0047FF]" />
              <div className="text-sm">
                <span className="font-medium">{a.actor?.name}</span>
                <span className="text-muted-foreground"> {a.action} {a.entity_type}</span>
                <div className="text-[11px] text-muted-foreground font-mono-data">{new Date(a.created_at).toLocaleString()}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
