import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { toast } from "sonner";
import { Plus, Trash2, LifeBuoy, AlertOctagon, CheckCircle, Clock } from "lucide-react";

const STATUSES = ["open", "in_progress", "waiting", "resolved", "closed"];
const PRIORITIES = ["low", "medium", "high", "urgent"];

const statusColor = {
  open: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  in_progress: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  waiting: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
  resolved: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  closed: "bg-neutral-100 text-neutral-500",
};
const priorityColor = {
  low: "bg-neutral-100 text-neutral-700",
  medium: "bg-blue-100 text-blue-800",
  high: "bg-orange-100 text-orange-800",
  urgent: "bg-red-100 text-red-800",
};

const emptyForm = { subject: "", description: "", priority: "medium", status: "open", customer_id: "" };

export default function Tickets() {
  const [tickets, setTickets] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [stats, setStats] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const [t, c, s] = await Promise.all([
        api.get("/tickets"),
        api.get("/customers"),
        api.get("/tickets/stats/overview"),
      ]);
      setTickets(t.data); setCustomers(c.data); setStats(s.data);
    } catch (e) { toast.error("Failed to load tickets"); }
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    setSaving(true);
    try {
      await api.post("/tickets", { ...form, customer_id: form.customer_id || null });
      toast.success("Ticket created");
      setOpen(false); setForm(emptyForm); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  const updateStatus = async (t, status) => {
    try {
      await api.put(`/tickets/${t.id}`, { ...t, status });
      setTickets((prev) => prev.map((x) => x.id === t.id ? { ...x, status } : x));
      load();
    } catch { toast.error("Update failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this ticket?")) return;
    try { await api.delete(`/tickets/${id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const customerName = (id) => customers.find((c) => c.id === id)?.name || "—";

  return (
    <div className="space-y-6" data-testid="tickets-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-heading text-4xl md:text-5xl">Support Tickets</h1>
          <p className="text-sm text-muted-foreground mt-1 font-mono-data uppercase tracking-widest">{tickets.length} total</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-sm bg-[#0047FF] hover:bg-[#0036CC] text-white" data-testid="new-ticket-btn">
              <Plus className="h-4 w-4 mr-2" /> New ticket
            </Button>
          </DialogTrigger>
          <DialogContent className="rounded-sm max-w-md">
            <DialogHeader><DialogTitle>New ticket</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label>Subject *</Label>
                <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}
                       className="rounded-sm mt-1" data-testid="ticket-subject-input" /></div>
              <div><Label>Description</Label>
                <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                          className="rounded-sm mt-1" data-testid="ticket-description-input" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Priority</Label>
                  <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                    <SelectTrigger className="rounded-sm mt-1" data-testid="ticket-priority-select"><SelectValue /></SelectTrigger>
                    <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                  </Select></div>
                <div><Label>Status</Label>
                  <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                    <SelectTrigger className="rounded-sm mt-1" data-testid="ticket-status-select"><SelectValue /></SelectTrigger>
                    <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{s.replace("_", " ")}</SelectItem>)}</SelectContent>
                  </Select></div>
              </div>
              <div><Label>Customer</Label>
                <Select value={form.customer_id} onValueChange={(v) => setForm({ ...form, customer_id: v })}>
                  <SelectTrigger className="rounded-sm mt-1" data-testid="ticket-customer-select"><SelectValue placeholder="Optional" /></SelectTrigger>
                  <SelectContent>{customers.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                </Select></div>
            </div>
            <DialogFooter>
              <Button onClick={create} disabled={saving || !form.subject}
                      className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="ticket-submit">
                {saving ? "Creating…" : "Create ticket"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Open", val: stats.open, icon: LifeBuoy, color: "text-[#0047FF]" },
            { label: "High priority", val: stats.high_priority, icon: AlertOctagon, color: "text-[#FF3823]" },
            { label: "Resolved", val: stats.resolved, icon: CheckCircle, color: "text-green-600" },
            { label: "Total", val: stats.total, icon: Clock, color: "text-muted-foreground" },
          ].map((k) => (
            <Card key={k.label} className="rounded-sm border-border shadow-sm p-5" data-testid={`ticket-stat-${k.label.toLowerCase().replace(' ','-')}`}>
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-xs uppercase tracking-widest font-mono-data">{k.label}</span>
                <k.icon className={`h-4 w-4 ${k.color}`} />
              </div>
              <div className="font-heading text-4xl mt-3">{k.val}</div>
            </Card>
          ))}
        </div>
      )}

      <Card className="rounded-sm border-border shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-24 font-mono-data text-xs">Number</TableHead>
              <TableHead>Subject</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-16"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tickets.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-10">
                  No tickets yet. Create your first one.
                </TableCell>
              </TableRow>
            )}
            {tickets.map((t) => (
              <TableRow key={t.id} data-testid={`ticket-row-${t.id}`}>
                <TableCell className="font-mono-data text-xs">{t.number}</TableCell>
                <TableCell className="font-medium">
                  {t.subject}
                  {t.description && <div className="text-xs text-muted-foreground mt-0.5 max-w-md truncate">{t.description}</div>}
                </TableCell>
                <TableCell className="text-muted-foreground">{customerName(t.customer_id)}</TableCell>
                <TableCell>
                  <span className={`text-[10px] uppercase font-mono-data px-2 py-1 rounded-sm ${priorityColor[t.priority]}`}>{t.priority}</span>
                </TableCell>
                <TableCell>
                  <Select value={t.status} onValueChange={(v) => updateStatus(t, v)}>
                    <SelectTrigger className={`w-32 h-7 text-xs rounded-sm ${statusColor[t.status]}`} data-testid={`ticket-status-${t.id}`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{s.replace("_", " ")}</SelectItem>)}</SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  <Button size="sm" variant="ghost" onClick={() => remove(t.id)}
                          className="h-8 text-muted-foreground hover:text-[#FF3823]" data-testid={`delete-ticket-${t.id}`}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
