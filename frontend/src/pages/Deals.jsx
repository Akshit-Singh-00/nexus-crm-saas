import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";

const STAGES = [
  { id: "lead", label: "Lead", color: "#94a3b8" },
  { id: "qualified", label: "Qualified", color: "#0047FF" },
  { id: "proposal", label: "Proposal", color: "#0036CC" },
  { id: "negotiation", label: "Negotiation", color: "#0A0A0A" },
  { id: "won", label: "Won", color: "#10b981" },
  { id: "lost", label: "Lost", color: "#FF3823" },
];

const emptyForm = { title: "", value: 0, stage: "lead", close_date: "", customer_id: "" };

export default function Deals() {
  const [deals, setDeals] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [dragId, setDragId] = useState(null);

  const load = async () => {
    try {
      const [d, c] = await Promise.all([api.get("/deals"), api.get("/customers")]);
      setDeals(d.data); setCustomers(c.data);
    } catch { toast.error("Failed to load deals"); }
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    setSaving(true);
    try {
      await api.post("/deals", { ...form, value: Number(form.value)||0, customer_id: form.customer_id || null });
      toast.success("Deal created");
      setOpen(false); setForm(emptyForm); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  const move = async (id, stage) => {
    try {
      await api.patch(`/deals/${id}/stage`, { stage });
      setDeals(prev => prev.map(d => d.id === id ? { ...d, stage } : d));
    } catch (e) { toast.error("Move failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this deal?")) return;
    await api.delete(`/deals/${id}`); load();
  };

  const totalByStage = (s) => deals.filter(d => d.stage === s).reduce((a, b) => a + (b.value || 0), 0);
  const customerName = (id) => customers.find(c => c.id === id)?.name || "—";

  return (
    <div className="space-y-6" data-testid="deals-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-heading text-4xl md:text-5xl">Deal Pipeline</h1>
          <p className="text-sm text-neutral-500 mt-1 font-mono-data uppercase tracking-widest">{deals.length} deals · drag to move</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-sm bg-[#0047FF] hover:bg-[#0036CC]" data-testid="new-deal-btn">
              <Plus className="h-4 w-4 mr-2" /> New deal
            </Button>
          </DialogTrigger>
          <DialogContent className="rounded-sm max-w-md">
            <DialogHeader><DialogTitle>New deal</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label>Title *</Label>
                <Input value={form.title} onChange={e=>setForm({...form,title:e.target.value})} className="rounded-sm mt-1" data-testid="deal-title-input" /></div>
              <div><Label>Value (USD)</Label>
                <Input type="number" value={form.value} onChange={e=>setForm({...form,value:e.target.value})} className="rounded-sm mt-1" data-testid="deal-value-input" /></div>
              <div><Label>Stage</Label>
                <Select value={form.stage} onValueChange={v=>setForm({...form,stage:v})}>
                  <SelectTrigger className="rounded-sm mt-1" data-testid="deal-stage-select"><SelectValue/></SelectTrigger>
                  <SelectContent>{STAGES.map(s => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}</SelectContent>
                </Select></div>
              <div><Label>Customer</Label>
                <Select value={form.customer_id} onValueChange={v=>setForm({...form,customer_id:v})}>
                  <SelectTrigger className="rounded-sm mt-1" data-testid="deal-customer-select"><SelectValue placeholder="Select customer"/></SelectTrigger>
                  <SelectContent>{customers.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                </Select></div>
            </div>
            <DialogFooter>
              <Button onClick={create} disabled={saving || !form.title} className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800" data-testid="deal-submit">
                {saving ? "Saving…" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex gap-4 overflow-x-auto kanban-scroll pb-4">
        {STAGES.map(stage => {
          const items = deals.filter(d => d.stage === stage.id);
          return (
            <div key={stage.id}
                 className="w-80 shrink-0 bg-white border border-[#E2E2E0] rounded-sm"
                 onDragOver={(e) => e.preventDefault()}
                 onDrop={() => dragId && move(dragId, stage.id)}
                 data-testid={`kanban-column-${stage.id}`}>
              <div className="px-4 py-3 border-b border-[#E2E2E0] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: stage.color }} />
                  <span className="font-medium text-sm">{stage.label}</span>
                  <span className="text-xs text-neutral-500 font-mono-data">{items.length}</span>
                </div>
                <span className="font-mono-data text-xs text-neutral-500">${totalByStage(stage.id).toLocaleString()}</span>
              </div>
              <div className="p-3 space-y-2 min-h-[300px]">
                {items.map(d => (
                  <div key={d.id}
                       draggable
                       onDragStart={() => setDragId(d.id)}
                       onDragEnd={() => setDragId(null)}
                       className="bg-white border border-[#E2E2E0] rounded-sm p-3 hover:border-[#0047FF] cursor-grab active:cursor-grabbing group"
                       data-testid={`deal-card-${d.id}`}>
                    <div className="flex justify-between items-start gap-2">
                      <div className="font-medium text-sm truncate">{d.title}</div>
                      <button onClick={() => remove(d.id)} className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-[#FF3823]" data-testid={`delete-deal-${d.id}`}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className="text-xs text-neutral-500 mt-1">{customerName(d.customer_id)}</div>
                    <div className="font-mono-data text-sm mt-2">${Number(d.value||0).toLocaleString()}</div>
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
