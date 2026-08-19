import { useEffect, useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { formatDistanceToNow, format } from "date-fns";
import {
  ChevronLeft, Brain, Sparkles, Send, Mail, Phone, Building2, DollarSign, Calendar,
  FileText, MessageSquare, Upload, User as UserIcon, Zap, ArrowUpRight, ArrowDownLeft,
  CheckCircle2, PhoneCall, Paperclip, StickyNote, Activity as ActivityIcon, Trash2,
} from "lucide-react";

const money = (n) => `$${Number(n || 0).toLocaleString()}`;
const nowIso = () => new Date().toISOString();

const KIND_ICON = {
  email_sent: ArrowUpRight, email_received: ArrowDownLeft,
  call_logged: PhoneCall, meeting_scheduled: Calendar, meeting_completed: CheckCircle2,
  file_uploaded: Paperclip, note_added: StickyNote,
  created: Sparkles, updated: ActivityIcon, deleted: Trash2,
  stage_changed: Zap, ai_scored: Brain,
};
const iconFor = (t) => KIND_ICON[t] || ActivityIcon;

export default function CustomerDetail() {
  const { id } = useParams();
  const [customer, setCustomer] = useState(null);
  const [summary360, setSummary360] = useState(null);
  const [notes, setNotes] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [deals, setDeals] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [emails, setEmails] = useState([]);
  const [calls, setCalls] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [files, setFiles] = useState([]);
  const [integrations, setIntegrations] = useState([]);
  const [note, setNote] = useState("");
  const [summary, setSummary] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [dialog, setDialog] = useState(null); // "email" | "call" | "meeting" | "task" | null

  const load = async () => {
    try {
      const [s, n, tl, d, t, tk, em, ca, mt, fl, ig] = await Promise.all([
        api.get(`/customers/${id}/summary`),
        api.get("/notes", { params: { related_type: "customer", related_id: id } }),
        api.get(`/customers/${id}/timeline`, { params: { limit: 200 } }),
        api.get("/deals"),
        api.get("/tasks"),
        api.get("/tickets"),
        api.get("/emails", { params: { customer_id: id } }),
        api.get("/calls", { params: { customer_id: id } }),
        api.get("/meetings", { params: { customer_id: id } }),
        api.get("/files", { params: { customer_id: id } }),
        api.get("/integrations"),
      ]);
      setSummary360(s.data);
      setCustomer(s.data.customer);
      setNotes(n.data);
      setTimeline(tl.data);
      setDeals(d.data.filter((x) => x.customer_id === id));
      setTasks(t.data.filter((x) => x.related_type === "customer" && x.related_id === id));
      setTickets(tk.data.filter((x) => x.customer_id === id));
      setEmails(em.data); setCalls(ca.data); setMeetings(mt.data); setFiles(fl.data);
      setIntegrations(ig.data);
    } catch { toast.error("Failed to load customer"); }
  };
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

  const totals = summary360?.totals || {};
  const owner = summary360?.owner;
  const nextMeeting = summary360?.next_meeting;
  const lastActivity = summary360?.last_activity;
  const leadScore = summary360?.lead_score;

  const health = customer.status === "churned" ? "at-risk" :
                 (customer.status === "active" && totals.open_deals > 0) ? "healthy" : "neutral";
  const healthColor = { healthy: "bg-green-500", "at-risk": "bg-[#FF3823]", neutral: "bg-neutral-400" }[health];
  const integ = (p) => integrations.find((i) => i.provider === p) || { status: "not_connected" };

  return (
    <div className="space-y-6" data-testid="customer-detail-page">
      <div>
        <Link to="/app/customers" className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
          <ChevronLeft className="h-4 w-4" /> All customers
        </Link>
      </div>

      {/* Header */}
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
              {owner && <span className="flex items-center gap-1.5" data-testid="customer-owner"><UserIcon className="h-3.5 w-3.5" />Owner: {owner.name}</span>}
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <HeaderStat label="Status" value={<Badge className="rounded-sm border-0 bg-blue-100 text-blue-800 hover:bg-blue-100 capitalize">{customer.status}</Badge>} testid="header-status" />
            <HeaderStat label="Total value" value={<span className="font-heading text-xl" data-testid="header-total-value">{money(totals.total_value)}</span>} />
            <HeaderStat label="Lead score" value={<span className="font-heading text-xl" data-testid="header-lead-score">{leadScore ?? "—"}</span>} />
            <HeaderStat label="Last activity" value={
              <span className="text-xs font-mono-data text-muted-foreground" data-testid="header-last-activity">
                {lastActivity ? formatDistanceToNow(new Date(lastActivity.created_at), { addSuffix: true }) : "—"}
              </span>} />
          </div>
        </div>

        {nextMeeting && (
          <div className="mt-4 border-t border-border pt-4 flex items-center justify-between flex-wrap gap-2" data-testid="header-next-meeting">
            <div className="text-sm">
              <span className="text-[10px] uppercase font-mono-data text-muted-foreground mr-2">Next meeting</span>
              <span className="font-medium">{nextMeeting.title}</span>
              <span className="text-muted-foreground ml-2">· {format(new Date(nextMeeting.scheduled_at), "PPp")}</span>
            </div>
          </div>
        )}

        {/* Quick actions */}
        <div className="mt-5 flex flex-wrap gap-2" data-testid="quick-actions">
          <QuickBtn onClick={() => setDialog("email")} icon={Mail} label="Email" testid="qa-email" />
          <QuickBtn onClick={() => setDialog("call")} icon={PhoneCall} label="Call" testid="qa-call" />
          <QuickBtn onClick={() => setDialog("meeting")} icon={Calendar} label="Meeting" testid="qa-meeting" />
          <QuickBtn onClick={() => setDialog("task")} icon={CheckCircle2} label="Task" testid="qa-task" />
          <QuickBtn onClick={() => document.getElementById("note-textarea")?.focus()} icon={StickyNote} label="Note" testid="qa-note" />
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
        <TabsList className="rounded-sm flex-wrap h-auto">
          <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="deals" data-testid="tab-deals">Deals · {deals.length}</TabsTrigger>
          <TabsTrigger value="tasks" data-testid="tab-tasks">Tasks · {tasks.length}</TabsTrigger>
          <TabsTrigger value="emails" data-testid="tab-emails">Emails · {emails.length}</TabsTrigger>
          <TabsTrigger value="meetings" data-testid="tab-meetings">Meetings · {meetings.length}</TabsTrigger>
          <TabsTrigger value="calls" data-testid="tab-calls">Calls · {calls.length}</TabsTrigger>
          <TabsTrigger value="tickets" data-testid="tab-tickets">Tickets · {tickets.length}</TabsTrigger>
          <TabsTrigger value="notes" data-testid="tab-notes">Notes · {notes.length}</TabsTrigger>
          <TabsTrigger value="files" data-testid="tab-files">Files · {files.length}</TabsTrigger>
          <TabsTrigger value="activity" data-testid="tab-activity">Activity · {timeline.length}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6 space-y-4">
          <div className="grid md:grid-cols-4 gap-4">
            <OverviewStat label="Open deals" main={totals.open_deals} sub={money(totals.open_value)} />
            <OverviewStat label="Open tasks" main={totals.open_tasks} />
            <OverviewStat label="Open tickets" main={totals.open_tickets} sub={`${totals.tickets} total`} />
            <OverviewStat label="Notes" main={notes.length} />
          </div>
          <TimelineList events={timeline.slice(0, 10)} empty="No activity yet. Try Email / Call / Meeting above." />
        </TabsContent>

        <TabsContent value="deals" className="mt-6 space-y-2">
          {deals.length === 0 && <Empty msg="No deals for this customer yet." />}
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
          {tasks.length === 0 && <Empty msg="No tasks linked yet." />}
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

        <TabsContent value="emails" className="mt-6 space-y-3" data-testid="emails-panel">
          <IntegrationHint provider="gmail" status={integ("gmail").status} onConnect={() => connectProvider("gmail")} />
          <Button onClick={() => setDialog("email")} className="rounded-sm bg-[#0A0A0A] text-white hover:bg-neutral-800" data-testid="log-email-btn">
            <Mail className="h-4 w-4 mr-2" /> Log an email
          </Button>
          {emails.length === 0 && <Empty msg="No emails logged for this customer yet." />}
          {emails.map((e) => (
            <Card key={e.id} className="rounded-sm border-border p-4" data-testid={`email-${e.id}`}>
              <div className="flex items-center gap-2 text-xs font-mono-data text-muted-foreground">
                {e.direction === "outbound" ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownLeft className="h-3 w-3" />}
                {e.direction} · {formatDistanceToNow(new Date(e.created_at), { addSuffix: true })}
              </div>
              <div className="font-medium mt-1">{e.subject}</div>
              {e.body && <div className="text-sm text-muted-foreground mt-1 line-clamp-3 whitespace-pre-wrap">{e.body}</div>}
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="meetings" className="mt-6 space-y-3" data-testid="meetings-panel">
          <IntegrationHint provider="google_calendar" status={integ("google_calendar").status} onConnect={() => connectProvider("google_calendar")} />
          <Button onClick={() => setDialog("meeting")} className="rounded-sm bg-[#0A0A0A] text-white hover:bg-neutral-800" data-testid="new-meeting-btn">
            <Calendar className="h-4 w-4 mr-2" /> Schedule meeting
          </Button>
          {meetings.length === 0 && <Empty msg="No meetings yet." />}
          {meetings.map((m) => (
            <Card key={m.id} className="rounded-sm border-border p-4 flex items-center justify-between" data-testid={`meeting-${m.id}`}>
              <div>
                <div className="font-medium">{m.title}</div>
                <div className="text-xs text-muted-foreground mt-1 font-mono-data">
                  {format(new Date(m.scheduled_at), "PPp")} · {m.duration_minutes}m · {m.status}
                </div>
              </div>
              {m.status === "scheduled" && (
                <Button size="sm" variant="outline" className="rounded-sm" onClick={() => markMeeting(m.id, "completed")}
                        data-testid={`meeting-complete-${m.id}`}>
                  <CheckCircle2 className="h-3.5 w-3.5 mr-1" /> Mark done
                </Button>
              )}
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="calls" className="mt-6 space-y-3" data-testid="calls-panel">
          <Button onClick={() => setDialog("call")} className="rounded-sm bg-[#0A0A0A] text-white hover:bg-neutral-800" data-testid="log-call-btn">
            <PhoneCall className="h-4 w-4 mr-2" /> Log a call
          </Button>
          {calls.length === 0 && <Empty msg="No calls logged yet." />}
          {calls.map((c) => (
            <Card key={c.id} className="rounded-sm border-border p-4" data-testid={`call-${c.id}`}>
              <div className="text-xs font-mono-data text-muted-foreground">
                {c.outcome} · {Math.round((c.duration_seconds || 0) / 60)}m · {formatDistanceToNow(new Date(c.created_at), { addSuffix: true })}
              </div>
              {c.summary && <div className="text-sm mt-1">{c.summary}</div>}
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="tickets" className="mt-6 space-y-2">
          {tickets.length === 0 && <Empty msg="No tickets for this customer." />}
          {tickets.map((t) => (
            <Card key={t.id} className="rounded-sm border-border p-4 flex items-center justify-between" data-testid={`ticket-${t.id}`}>
              <div>
                <div className="font-medium">{t.number} · {t.subject}</div>
                <div className="text-xs font-mono-data text-muted-foreground mt-1">{t.priority} · {t.status}</div>
              </div>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="notes" className="mt-6 space-y-4">
          <Card className="rounded-sm border-border shadow-sm p-4">
            <Textarea id="note-textarea" value={note} onChange={(e) => setNote(e.target.value)}
                      placeholder="Log a note. Use @teammate to mention (coming soon)."
                      className="rounded-sm" data-testid="note-input" />
            <Button onClick={addNote} disabled={!note.trim()}
                    className="mt-3 rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="note-submit">
              <Send className="h-4 w-4 mr-2" /> Add note
            </Button>
          </Card>
          {notes.length === 0 && <Empty msg="No notes yet." />}
          {notes.map((n) => (
            <div key={n.id} className="border-l-2 border-[#0047FF] pl-3 py-1" data-testid={`note-${n.id}`}>
              <div className="text-sm whitespace-pre-wrap">{n.content}</div>
              <div className="text-[11px] text-muted-foreground mt-1 font-mono-data">
                {n.author?.name || "Unknown"} · {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
              </div>
            </div>
          ))}
        </TabsContent>

        <TabsContent value="files" className="mt-6 space-y-3" data-testid="files-panel">
          <FileUploader customerId={id} onUploaded={load} />
          {files.length === 0 && <Empty msg="No files yet." />}
          {files.map((f) => (
            <Card key={f.id} className="rounded-sm border-border p-4 flex items-center justify-between" data-testid={`file-${f.id}`}>
              <div className="flex items-center gap-3">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="font-medium">{f.filename}</div>
                  <div className="text-[11px] font-mono-data text-muted-foreground">
                    {Math.round((f.size_bytes || 0) / 1024)} KB · {formatDistanceToNow(new Date(f.created_at), { addSuffix: true })}
                  </div>
                </div>
              </div>
              <Button size="sm" variant="outline" className="rounded-sm"
                      onClick={() => downloadFile(f.id, f.filename)}
                      data-testid={`file-download-${f.id}`}>Download</Button>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="activity" className="mt-6">
          <TimelineList events={timeline} empty="No activity recorded yet." />
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      <QuickDialog kind={dialog} customerId={id} onClose={() => setDialog(null)} onSaved={load} />
    </div>
  );

  async function connectProvider(provider) {
    try {
      await api.post("/integrations/connect", { provider });
      toast.success(`${provider} marked as pending. Complete OAuth to finish.`);
      load();
    } catch { toast.error("Could not start connection"); }
  }

  async function markMeeting(mid, status) {
    try {
      await api.patch(`/meetings/${mid}/status`, { status });
      toast.success("Meeting updated"); load();
    } catch { toast.error("Failed"); }
  }

  async function downloadFile(fid, fname) {
    try {
      const { data } = await api.get(`/files/${fid}`);
      const a = document.createElement("a");
      a.href = data.data_url;
      a.download = fname || "download";
      document.body.appendChild(a); a.click(); a.remove();
    } catch { toast.error("Failed to download"); }
  }
}

/* -------- small presentational bits -------- */
function HeaderStat({ label, value, testid }) {
  return (
    <div className="text-right" data-testid={testid}>
      <div className="text-[10px] uppercase font-mono-data text-muted-foreground">{label}</div>
      <div className="mt-1">{value}</div>
    </div>
  );
}
function OverviewStat({ label, main, sub }) {
  return (
    <Card className="rounded-sm border-border shadow-sm p-5">
      <div className="text-xs uppercase font-mono-data text-muted-foreground">{label}</div>
      <div className="font-heading text-3xl mt-2">{main ?? 0}</div>
      {sub && <div className="text-sm text-muted-foreground mt-1">{sub}</div>}
    </Card>
  );
}
function QuickBtn({ onClick, icon: Icon, label, testid }) {
  return (
    <Button onClick={onClick} variant="outline" className="rounded-sm h-9" data-testid={testid}>
      <Icon className="h-4 w-4 mr-2" /> {label}
    </Button>
  );
}
function Empty({ msg }) {
  return <div className="text-sm text-muted-foreground">{msg}</div>;
}

function IntegrationHint({ provider, status, onConnect }) {
  const label = { gmail: "Gmail", outlook: "Outlook", google_calendar: "Google Calendar" }[provider] || provider;
  if (status === "connected") return null;
  return (
    <Card className="rounded-sm border-dashed border-border p-4 flex items-center justify-between" data-testid={`integ-hint-${provider}`}>
      <div className="text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground ml-2">
          {status === "pending" ? "Connection pending — finish OAuth to sync live."
                                : "Not connected. Emails/meetings you log stay in NexusCRM only."}
        </span>
      </div>
      <Button size="sm" variant="outline" className="rounded-sm" onClick={onConnect} data-testid={`integ-connect-${provider}`}>
        {status === "pending" ? "Retry" : "Connect"}
      </Button>
    </Card>
  );
}

function TimelineList({ events, empty }) {
  const grouped = useMemo(() => {
    const g = {};
    for (const e of events) {
      const day = format(new Date(e.created_at), "PP");
      (g[day] = g[day] || []).push(e);
    }
    return g;
  }, [events]);

  if (!events.length) return <Card className="rounded-sm border-border p-6"><Empty msg={empty} /></Card>;

  return (
    <Card className="rounded-sm border-border p-6" data-testid="timeline">
      <div className="space-y-5">
        {Object.entries(grouped).map(([day, evs]) => (
          <div key={day}>
            <div className="text-[10px] uppercase font-mono-data text-muted-foreground mb-2">{day}</div>
            <ul className="space-y-3 border-l border-border pl-4">
              {evs.map((e) => {
                const Icon = iconFor(e.type);
                return (
                  <li key={e.id} className="relative" data-testid={`timeline-item-${e.id}`}>
                    <span className="absolute -left-[22px] top-1 h-3 w-3 rounded-full bg-background border-2 border-[#0047FF]" />
                    <div className="flex items-start gap-2">
                      <Icon className="h-3.5 w-3.5 mt-1 text-muted-foreground shrink-0" />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm">
                          <span className="font-medium">{e.actor?.name || "System"}</span>
                          <span className="text-muted-foreground"> · {e.type?.replace(/_/g, " ")}</span>
                        </div>
                        {e.description && <div className="text-sm text-muted-foreground truncate">{e.description}</div>}
                        <div className="text-[10px] font-mono-data text-muted-foreground">
                          {format(new Date(e.created_at), "p")}
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  );
}

function QuickDialog({ kind, customerId, onClose, onSaved }) {
  const [form, setForm] = useState({});
  useEffect(() => { setForm({}); }, [kind]);
  if (!kind) return null;

  const save = async () => {
    try {
      if (kind === "email") {
        await api.post("/emails", {
          customer_id: customerId, direction: "outbound",
          to_email: form.to_email || undefined,
          subject: form.subject || "(no subject)", body: form.body || "",
        });
      } else if (kind === "call") {
        await api.post("/calls", {
          customer_id: customerId, outcome: form.outcome || "connected",
          duration_seconds: Number(form.duration_minutes || 0) * 60, summary: form.summary || "",
        });
      } else if (kind === "meeting") {
        if (!form.scheduled_at) return toast.error("Pick a date & time");
        await api.post("/meetings", {
          customer_id: customerId, title: form.title || "Meeting",
          scheduled_at: new Date(form.scheduled_at).toISOString(),
          duration_minutes: Number(form.duration_minutes || 30),
          description: form.description || "",
          reminder_minutes: Number(form.reminder_minutes || 15),
        });
      } else if (kind === "task") {
        await api.post("/tasks", {
          title: form.title || "Follow up",
          description: form.description || "",
          priority: form.priority || "medium", status: "todo",
          due_date: form.due_date || null,
          related_type: "customer", related_id: customerId,
        });
      }
      toast.success("Saved"); onSaved(); onClose();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
  };

  const titles = { email: "Log email", call: "Log call", meeting: "Schedule meeting", task: "Create task" };

  return (
    <Dialog open={!!kind} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="rounded-sm" data-testid={`dialog-${kind}`}>
        <DialogHeader><DialogTitle>{titles[kind]}</DialogTitle></DialogHeader>
        <div className="space-y-3">
          {kind === "email" && (<>
            <Input placeholder="To (email)" value={form.to_email || ""} onChange={(e) => setForm({ ...form, to_email: e.target.value })} className="rounded-sm" data-testid="email-to" />
            <Input placeholder="Subject" value={form.subject || ""} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="rounded-sm" data-testid="email-subject" />
            <Textarea placeholder="Body" value={form.body || ""} onChange={(e) => setForm({ ...form, body: e.target.value })} rows={6} className="rounded-sm" data-testid="email-body" />
          </>)}
          {kind === "call" && (<>
            <select value={form.outcome || "connected"} onChange={(e) => setForm({ ...form, outcome: e.target.value })} className="w-full h-10 border border-border rounded-sm bg-background px-3 text-sm" data-testid="call-outcome">
              <option value="connected">Connected</option><option value="voicemail">Voicemail</option>
              <option value="no_answer">No answer</option><option value="busy">Busy</option>
            </select>
            <Input type="number" min="0" placeholder="Duration (minutes)" value={form.duration_minutes || ""} onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })} className="rounded-sm" data-testid="call-duration" />
            <Textarea placeholder="Summary / notes" value={form.summary || ""} onChange={(e) => setForm({ ...form, summary: e.target.value })} rows={4} className="rounded-sm" data-testid="call-summary" />
          </>)}
          {kind === "meeting" && (<>
            <Input placeholder="Title" value={form.title || ""} onChange={(e) => setForm({ ...form, title: e.target.value })} className="rounded-sm" data-testid="meeting-title" />
            <Input type="datetime-local" value={form.scheduled_at || ""} onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })} className="rounded-sm" data-testid="meeting-when" />
            <Input type="number" min="5" placeholder="Duration (minutes)" value={form.duration_minutes || 30} onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })} className="rounded-sm" data-testid="meeting-duration" />
            <Input type="number" min="0" placeholder="Reminder minutes before" value={form.reminder_minutes || 15} onChange={(e) => setForm({ ...form, reminder_minutes: e.target.value })} className="rounded-sm" data-testid="meeting-reminder" />
            <Textarea placeholder="Agenda / description" value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} className="rounded-sm" data-testid="meeting-description" />
          </>)}
          {kind === "task" && (<>
            <Input placeholder="Title" value={form.title || ""} onChange={(e) => setForm({ ...form, title: e.target.value })} className="rounded-sm" data-testid="task-title" />
            <Input type="datetime-local" value={form.due_date || ""} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="rounded-sm" data-testid="task-due" />
            <select value={form.priority || "medium"} onChange={(e) => setForm({ ...form, priority: e.target.value })} className="w-full h-10 border border-border rounded-sm bg-background px-3 text-sm" data-testid="task-priority">
              <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option>
            </select>
            <Textarea placeholder="Description" value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} className="rounded-sm" data-testid="task-description" />
          </>)}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="rounded-sm">Cancel</Button>
          <Button onClick={save} className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="dialog-save">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FileUploader({ customerId, onUploaded }) {
  const [busy, setBusy] = useState(false);
  const onPick = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 5 * 1024 * 1024) return toast.error("File too large (max 5 MB)");
    setBusy(true);
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        await api.post("/files", {
          customer_id: customerId, filename: f.name, mime_type: f.type || "application/octet-stream",
          size_bytes: f.size, data_url: reader.result,
        });
        toast.success("Uploaded"); onUploaded();
      } catch (err) { toast.error(err?.response?.data?.detail || "Upload failed"); }
      finally { setBusy(false); e.target.value = ""; }
    };
    reader.readAsDataURL(f);
  };
  return (
    <label className="inline-flex items-center gap-2 rounded-sm border border-border bg-card px-3 h-9 cursor-pointer hover:bg-accent text-sm" data-testid="file-uploader">
      <Upload className="h-4 w-4" />
      {busy ? "Uploading…" : "Upload file"}
      <input type="file" className="hidden" onChange={onPick} disabled={busy} />
    </label>
  );
}
