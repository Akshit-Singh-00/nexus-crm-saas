import { useEffect, useState, useMemo } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Trash2, AlertTriangle, User } from "lucide-react";

const priorityColor = { low: "bg-neutral-200 text-neutral-700", medium: "bg-blue-100 text-blue-800", high: "bg-red-100 text-red-800" };
const money = (n) => `$${Number(n || 0).toLocaleString()}`;

const emptyForm = {
  title: "", value: 0, stage: "lead", customer_id: "", assignee_id: "",
  close_date: "", probability: 25, priority: "medium", tags: "", description: ""
};

export default function Deals() {
  const [deals, setDeals] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [members, setMembers] = useState([]);
  const [stages, setStages] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [dragId, setDragId] = useState(null);
  const [editingId, setEditingId] = useState(null);

  const load = async () => {
    try {
      const [d, c, m, s] = await Promise.all([
        api.get("/deals"),
        api.get("/customers"),
        api.get("/workspaces/members"),
        api.get("/workspaces/settings").catch(() => ({ data: null })),
      ]);
      setDeals(d.data); setCustomers(c.data); setMembers(m.data);
      const workspaceStages = s.data?.pipeline_stages || null;
      // fall back to inferring stages from deals if not admin
      const fallback = [
        { id: "lead", label: "Lead", color: "#94a3b8", probability: 10 },
        { id: "qualified", label: "Qualified", color: "#0047FF", probability: 25 },
        { id: "demo", label: "Demo", color: "#7c3aed", probability: 40 },
        { id: "proposal", label: "Proposal", color: "#0036CC", probability: 60 },
        { id: "negotiation", label: "Negotiation", color: "#0A0A0A", probability: 80 },
        { id: "won", label: "Won", color: "#10b981", probability: 100 },
        { id: "lost", label: "Lost", color: "#FF3823", probability: 0 },
      ];
      setStages(workspaceStages || fallback);
    } catch { toast.error("Failed to load deals"); }
  };
  useEffect(() => { load(); }, []);

  const openEdit = (deal) => {
    setEditingId(deal.id);
    setForm({
      title: deal.title || "", value: deal.value || 0, stage: deal.stage || "lead",
      customer_id: deal.customer_id || "", assignee_id: deal.assignee_id || "",
      close_date: (deal.close_date || "").slice(0, 10), probability: deal.probability ?? 25,
      priority: deal.priority || "medium", tags: (deal.tags || []).join(", "),
      description: deal.description || "",
    });
    setOpen(true);
  };
  const openNew = () => { setEditingId(null); setForm(emptyForm); setOpen(true); };

  const save = async () => {
    setSaving(true);
    const payload = {
      ...form,
      value: Number(form.value) || 0,
      probability: Number(form.probability) || 0,
      customer_id: form.customer_id || null,
      assignee_id: form.assignee_id || null,
      close_date: form.close_date || null,
      tags: form.tags.split(",").map((s) => s.trim()).filter(Boolean),
    };
    try {
      if (editingId) await api.put(`/deals/${editingId}`, payload);
      else await api.post("/deals", payload);
      toast.success(editingId ? "Deal updated" : "Deal created");
      setOpen(false); setForm(emptyForm); setEditingId(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  const move = async (id, stage) => {
    try {
      await api.patch(`/deals/${id}/stage`, { stage });
      setDeals((prev) => prev.map((d) => d.id === id ? { ...d, stage } : d));
    } catch { toast.error("Move failed"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this deal?")) return;
    try { await api.delete(`/deals/${id}`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const memberName = (id) => members.find((x) => x.id === id)?.name || "Unassigned";
  const customerName = (id) => customers.find((x) => x.id === id)?.name || "—";

  const totals = useMemo(() => {
    const sum = (stage) => deals.filter((d) => d.stage === stage).reduce((a, b) => a + (b.value || 0), 0);
    const total = deals.filter((d) => !["won", "lost"].includes(d.stage)).reduce((a, b) => a + (b.value || 0), 0);
    const weighted = deals.filter((d) => !["won", "lost"].includes(d.stage))
      .reduce((a, b) => a + (b.value || 0) * ((b.probability ?? 50) / 100), 0);
    const won = sum("won");
    return { total, weighted, won };
  }, [deals]);

  return (
    <div className="space-y-6" data-testid="deals-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-heading text-4xl md:text-5xl">Sales Pipeline</h1>
          <p className="text-sm text-muted-foreground mt-1 font-mono-data uppercase tracking-widest">
            {deals.length} deals · {money(totals.total)} open · weighted {money(totals.weighted)} · won {money(totals.won)}
          </p>
        </div>
        <Button onClick={openNew} className="rounded-sm bg-[#0047FF] hover:bg-[#0036CC] text-white" data-testid="new-deal-btn">
          <Plus className="h-4 w-4 mr-2" /> New deal
        </Button>
      </div>

      <Dialog open={open} onOpenChange={(o) => { if (!o) setEditingId(null); setOpen(o); }}>
        <DialogContent className="rounded-sm max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editingId ? "Edit deal" : "New deal"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Title *</Label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="rounded-sm mt-1" data-testid="deal-title-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Value (USD)</Label>
                <Input type="number" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} className="rounded-sm mt-1 font-mono-data" data-testid="deal-value-input" /></div>
              <div><Label>Probability %</Label>
                <Input type="number" min={0} max={100} value={form.probability} onChange={(e) => setForm({ ...form, probability: e.target.value })} className="rounded-sm mt-1 font-mono-data" data-testid="deal-probability-input" /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Stage</Label>
                <Select value={form.stage} onValueChange={(v) => setForm({ ...form, stage: v })}>
                  <SelectTrigger className="rounded-sm mt-1" data-testid="deal-stage-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{stages.map((s) => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}</SelectContent>
                </Select></div>
              <div><Label>Priority</Label>
                <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                  <SelectTrigger className="rounded-sm mt-1" data-testid="deal-priority-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{["low", "medium", "high"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Customer</Label>
                <Select value={form.customer_id} onValueChange={(v) => setForm({ ...form, customer_id: v })}>
                  <SelectTrigger className="rounded-sm mt-1" data-testid="deal-customer-select"><SelectValue placeholder="Select customer" /></SelectTrigger>
                  <SelectContent>{customers.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                </Select></div>
              <div><Label>Owner</Label>
                <Select value={form.assignee_id} onValueChange={(v) => setForm({ ...form, assignee_id: v })}>
                  <SelectTrigger className="rounded-sm mt-1" data-testid="deal-assignee-select"><SelectValue placeholder="Assign to…" /></SelectTrigger>
                  <SelectContent>{members.map((m) => <SelectItem key={m.id} value={m.id}>{m.name || m.email}</SelectItem>)}</SelectContent>
                </Select></div>
            </div>
            <div><Label>Expected close date</Label>
              <Input type="date" value={form.close_date} onChange={(e) => setForm({ ...form, close_date: e.target.value })} className="rounded-sm mt-1" data-testid="deal-close-input" /></div>
            <div><Label>Tags (comma-separated)</Label>
              <Input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} placeholder="enterprise, urgent" className="rounded-sm mt-1" data-testid="deal-tags-input" /></div>
            <div><Label>Description</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="rounded-sm mt-1" data-testid="deal-description-input" /></div>
          </div>
          <DialogFooter>
            <Button onClick={save} disabled={saving || !form.title}
                    className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="deal-submit">
              {saving ? "Saving…" : editingId ? "Save changes" : "Create deal"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="flex gap-4 overflow-x-auto kanban-scroll pb-4">
        {stages.map((stage) => {
          const items = deals.filter((d) => d.stage === stage.id);
          const total = items.reduce((a, b) => a + (b.value || 0), 0);
          return (
            <div key={stage.id}
                 className="w-80 shrink-0 bg-card border border-border rounded-sm"
                 onDragOver={(e) => e.preventDefault()}
                 onDrop={() => dragId && move(dragId, stage.id)}
                 data-testid={`kanban-column-${stage.id}`}>
              <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: stage.color }} />
                  <span className="font-medium text-sm">{stage.label}</span>
                  <span className="text-xs text-muted-foreground font-mono-data">{items.length}</span>
                </div>
                <span className="font-mono-data text-xs text-muted-foreground">{money(total)}</span>
              </div>
              <div className="p-3 space-y-2 min-h-[300px]">
                {items.map((d) => (
                  <div key={d.id} draggable
                       onDragStart={() => setDragId(d.id)}
                       onDragEnd={() => setDragId(null)}
                       onClick={() => openEdit(d)}
                       className={`bg-card border rounded-sm p-3 hover:border-[#0047FF] cursor-grab active:cursor-grabbing group ${
                         d.risk?.level === "high" ? "border-[#FF3823] border-l-4" :
                         d.risk?.level === "medium" ? "border-amber-500 border-l-4" : "border-border"
                       }`}
                       data-testid={`deal-card-${d.id}`}>
                    <div className="flex justify-between items-start gap-2">
                      <div className="font-medium text-sm truncate flex-1">{d.title}</div>
                      <button onClick={(e) => { e.stopPropagation(); remove(d.id); }} className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-[#FF3823]" data-testid={`delete-deal-${d.id}`}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 truncate">{customerName(d.customer_id)}</div>
                    <div className="flex items-center justify-between mt-2 gap-2">
                      <span className="font-mono-data text-sm">{money(d.value)}</span>
                      <span className={`text-[9px] uppercase font-mono-data px-1.5 py-0.5 rounded-sm ${priorityColor[d.priority || "medium"]}`}>{d.priority || "med"}</span>
                    </div>
                    {(d.probability != null || d.tags?.length > 0) && (
                      <div className="mt-2 flex items-center flex-wrap gap-1">
                        {d.probability != null && (
                          <span className="text-[10px] font-mono-data text-muted-foreground bg-secondary rounded-sm px-1.5 py-0.5">{d.probability}%</span>
                        )}
                        {(d.tags || []).slice(0, 3).map((t) => (
                          <span key={t} className="text-[10px] font-mono-data bg-[#0047FF]/10 text-[#0047FF] rounded-sm px-1.5 py-0.5">{t}</span>
                        ))}
                      </div>
                    )}
                    <div className="flex items-center justify-between mt-2 text-[10px] text-muted-foreground font-mono-data">
                      <span className="flex items-center gap-1 truncate">
                        <User className="h-3 w-3" /> {d.assignee_id ? memberName(d.assignee_id) : "—"}
                      </span>
                      {d.close_date && <span>{d.close_date.slice(0, 10)}</span>}
                    </div>
                    {d.risk && d.risk.level !== "none" && (
                      <div className={`mt-2 flex items-start gap-1 text-[10px] ${d.risk.level === "high" ? "text-[#FF3823]" : "text-amber-600"}`}>
                        <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" />
                        <span className="line-clamp-2">{d.risk.reasons.join(" · ")}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
