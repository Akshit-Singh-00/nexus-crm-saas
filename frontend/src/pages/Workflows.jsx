import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Trash2, Zap, ArrowRight, Cog } from "lucide-react";

const TRIGGERS = [
  { id: "lead_created", label: "Lead is created", fields: ["score", "value", "status", "source", "company"] },
  { id: "lead_scored", label: "Lead is scored by AI", fields: ["score", "classification", "value", "status"] },
  { id: "customer_created", label: "Customer is created", fields: ["status", "company"] },
  { id: "deal_created", label: "Deal is created", fields: ["value", "stage", "priority", "probability"] },
  { id: "deal_stage_changed", label: "Deal stage changes", fields: ["value", "stage", "priority", "probability"] },
];

const OPS = [
  { id: "eq", label: "equals" }, { id: "neq", label: "not equals" },
  { id: "gt", label: ">" }, { id: "gte", label: "≥" },
  { id: "lt", label: "<" }, { id: "lte", label: "≤" },
  { id: "contains", label: "contains" },
];

const ACTION_TYPES = [
  { id: "create_task", label: "Create a task" },
  { id: "assign_user", label: "Assign to user" },
  { id: "notify_user", label: "Notify user" },
  { id: "add_tag", label: "Add tag" },
];

const emptyForm = {
  name: "", description: "", trigger: "lead_created", enabled: true,
  conditions: [], actions: [{ type: "create_task", params: { title: "", priority: "medium" } }],
};

export default function Workflows() {
  const [workflows, setWorkflows] = useState([]);
  const [members, setMembers] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const [w, m] = await Promise.all([api.get("/workflows"), api.get("/workspaces/members")]);
      setWorkflows(w.data); setMembers(m.data);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to load workflows"); }
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditingId(null); setForm(emptyForm); setOpen(true); };
  const openEdit = (wf) => {
    setEditingId(wf.id);
    setForm({
      name: wf.name || "", description: wf.description || "",
      trigger: wf.trigger, enabled: wf.enabled !== false,
      conditions: wf.conditions || [], actions: wf.actions || [],
    });
    setOpen(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      if (editingId) await api.put(`/workflows/${editingId}`, form);
      else await api.post("/workflows", form);
      toast.success(editingId ? "Workflow updated" : "Workflow created");
      setOpen(false); setForm(emptyForm); setEditingId(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this workflow?")) return;
    try { await api.delete(`/workflows/${id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const toggleEnabled = async (wf) => {
    try {
      await api.put(`/workflows/${wf.id}`, { ...wf, enabled: !wf.enabled });
      load();
    } catch (e) { toast.error("Failed"); }
  };

  const triggerFields = TRIGGERS.find((t) => t.id === form.trigger)?.fields || [];

  const setCond = (i, k, v) =>
    setForm({ ...form, conditions: form.conditions.map((c, idx) => idx === i ? { ...c, [k]: v } : c) });
  const addCond = () => setForm({ ...form, conditions: [...form.conditions, { field: triggerFields[0], op: "gt", value: "" }] });
  const removeCond = (i) => setForm({ ...form, conditions: form.conditions.filter((_, idx) => idx !== i) });

  const setAction = (i, patch) =>
    setForm({ ...form, actions: form.actions.map((a, idx) => idx === i ? { ...a, ...patch } : a) });
  const setActionParam = (i, k, v) =>
    setForm({ ...form, actions: form.actions.map((a, idx) => idx === i ? { ...a, params: { ...a.params, [k]: v } } : a) });
  const addAction = () => setForm({ ...form, actions: [...form.actions, { type: "create_task", params: {} }] });
  const removeAction = (i) => setForm({ ...form, actions: form.actions.filter((_, idx) => idx !== i) });

  return (
    <div className="space-y-6" data-testid="workflows-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-heading text-4xl md:text-5xl">Workflows</h1>
          <p className="text-sm text-muted-foreground mt-1 font-mono-data uppercase tracking-widest">
            {workflows.length} automation{workflows.length !== 1 ? "s" : ""} · trigger → conditions → actions
          </p>
        </div>
        <Button onClick={openNew} className="rounded-sm bg-[#0047FF] hover:bg-[#0036CC] text-white" data-testid="new-workflow-btn">
          <Plus className="h-4 w-4 mr-2" /> New workflow
        </Button>
      </div>

      {workflows.length === 0 ? (
        <Card className="rounded-sm border-border border-dashed shadow-sm p-10 text-center">
          <Zap className="h-8 w-8 text-[#FF3823] mx-auto mb-3" />
          <div className="font-heading text-xl">No workflows yet</div>
          <p className="text-sm text-muted-foreground mt-2 max-w-md mx-auto">
            Automate repetitive work. Example: when a lead scores &gt; 80, assign it to your best rep and create a follow-up task.
          </p>
          <Button onClick={openNew} className="mt-4 rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="empty-new-workflow-btn">
            Create your first workflow
          </Button>
        </Card>
      ) : (
        <div className="space-y-3">
          {workflows.map((wf) => (
            <Card key={wf.id} className="rounded-sm border-border shadow-sm p-5" data-testid={`workflow-row-${wf.id}`}>
              <div className="flex items-start gap-4 flex-wrap">
                <div className={`h-9 w-9 rounded-sm flex items-center justify-center shrink-0 ${wf.enabled ? "bg-[#FF3823]" : "bg-secondary"}`}>
                  <Zap className={`h-4 w-4 ${wf.enabled ? "text-white" : "text-muted-foreground"}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="font-medium">{wf.name}</div>
                    <span className="text-[10px] uppercase font-mono-data bg-secondary text-muted-foreground px-1.5 py-0.5 rounded-sm">
                      {TRIGGERS.find((t) => t.id === wf.trigger)?.label || wf.trigger}
                    </span>
                  </div>
                  {wf.description && <div className="text-sm text-muted-foreground mt-1">{wf.description}</div>}
                  <div className="text-xs text-muted-foreground mt-2 font-mono-data flex items-center gap-2 flex-wrap">
                    <span>{(wf.conditions || []).length} condition{wf.conditions?.length !== 1 ? "s" : ""}</span>
                    <ArrowRight className="h-3 w-3" />
                    <span>{wf.actions.length} action{wf.actions.length !== 1 ? "s" : ""}</span>
                    {wf.run_count > 0 && <span>· ran {wf.run_count}×</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Switch checked={wf.enabled} onCheckedChange={() => toggleEnabled(wf)} data-testid={`workflow-toggle-${wf.id}`} />
                  <Button variant="ghost" size="sm" onClick={() => openEdit(wf)} className="h-8" data-testid={`workflow-edit-${wf.id}`}>
                    <Cog className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => remove(wf.id)}
                          className="h-8 text-muted-foreground hover:text-[#FF3823]" data-testid={`workflow-delete-${wf.id}`}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={(o) => { if (!o) setEditingId(null); setOpen(o); }}>
        <DialogContent className="rounded-sm max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingId ? "Edit workflow" : "New workflow"}</DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Define a trigger, optional conditions, and one or more actions.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div><Label>Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-sm mt-1" data-testid="workflow-name-input" /></div>
            <div><Label>Description</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="rounded-sm mt-1" data-testid="workflow-description-input" /></div>

            {/* Trigger */}
            <div>
              <div className="text-xs uppercase font-mono-data text-muted-foreground mb-2">1. When (trigger)</div>
              <Select value={form.trigger} onValueChange={(v) => setForm({ ...form, trigger: v, conditions: [] })}>
                <SelectTrigger className="rounded-sm" data-testid="workflow-trigger-select"><SelectValue /></SelectTrigger>
                <SelectContent>{TRIGGERS.map((t) => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>

            {/* Conditions */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs uppercase font-mono-data text-muted-foreground">2. If (conditions, all must match)</div>
                <Button variant="outline" size="sm" onClick={addCond} className="rounded-sm h-7" data-testid="add-condition-btn">
                  <Plus className="h-3.5 w-3.5 mr-1" /> Condition
                </Button>
              </div>
              {form.conditions.length === 0 && <div className="text-xs text-muted-foreground">No conditions — always runs on trigger.</div>}
              <div className="space-y-2">
                {form.conditions.map((c, i) => (
                  <div key={i} className="flex items-center gap-2" data-testid={`condition-row-${i}`}>
                    <Select value={c.field} onValueChange={(v) => setCond(i, "field", v)}>
                      <SelectTrigger className="rounded-sm w-40"><SelectValue /></SelectTrigger>
                      <SelectContent>{triggerFields.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}</SelectContent>
                    </Select>
                    <Select value={c.op} onValueChange={(v) => setCond(i, "op", v)}>
                      <SelectTrigger className="rounded-sm w-32"><SelectValue /></SelectTrigger>
                      <SelectContent>{OPS.map((o) => <SelectItem key={o.id} value={o.id}>{o.label}</SelectItem>)}</SelectContent>
                    </Select>
                    <Input value={c.value ?? ""} onChange={(e) => setCond(i, "value", e.target.value)}
                           className="rounded-sm flex-1" placeholder="value" data-testid={`condition-value-${i}`} />
                    <Button variant="ghost" size="sm" onClick={() => removeCond(i)} className="h-8 text-muted-foreground hover:text-[#FF3823]">
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs uppercase font-mono-data text-muted-foreground">3. Then (actions)</div>
                <Button variant="outline" size="sm" onClick={addAction} className="rounded-sm h-7" data-testid="add-action-btn">
                  <Plus className="h-3.5 w-3.5 mr-1" /> Action
                </Button>
              </div>
              <div className="space-y-2">
                {form.actions.map((a, i) => (
                  <div key={i} className="border border-border rounded-sm p-3 bg-card" data-testid={`action-row-${i}`}>
                    <div className="flex items-center gap-2">
                      <Select value={a.type} onValueChange={(v) => setAction(i, { type: v, params: {} })}>
                        <SelectTrigger className="rounded-sm w-48"><SelectValue /></SelectTrigger>
                        <SelectContent>{ACTION_TYPES.map((t) => <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>)}</SelectContent>
                      </Select>
                      <div className="flex-1" />
                      <Button variant="ghost" size="sm" onClick={() => removeAction(i)} className="h-8 text-muted-foreground hover:text-[#FF3823]">
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      {a.type === "create_task" && (
                        <>
                          <Input placeholder="Task title" value={a.params.title || ""} onChange={(e) => setActionParam(i, "title", e.target.value)}
                                 className="rounded-sm col-span-2" data-testid={`action-task-title-${i}`} />
                          <Select value={a.params.priority || "medium"} onValueChange={(v) => setActionParam(i, "priority", v)}>
                            <SelectTrigger className="rounded-sm"><SelectValue placeholder="Priority" /></SelectTrigger>
                            <SelectContent>{["low", "medium", "high"].map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                          </Select>
                          <Select value={a.params.assignee_id || ""} onValueChange={(v) => setActionParam(i, "assignee_id", v)}>
                            <SelectTrigger className="rounded-sm"><SelectValue placeholder="Assign to…" /></SelectTrigger>
                            <SelectContent>{members.map((m) => <SelectItem key={m.id} value={m.id}>{m.name || m.email}</SelectItem>)}</SelectContent>
                          </Select>
                        </>
                      )}
                      {a.type === "assign_user" && (
                        <Select value={a.params.user_id || ""} onValueChange={(v) => setActionParam(i, "user_id", v)}>
                          <SelectTrigger className="rounded-sm col-span-2"><SelectValue placeholder="User" /></SelectTrigger>
                          <SelectContent>{members.map((m) => <SelectItem key={m.id} value={m.id}>{m.name || m.email}</SelectItem>)}</SelectContent>
                        </Select>
                      )}
                      {a.type === "notify_user" && (
                        <>
                          <Select value={a.params.user_id || ""} onValueChange={(v) => setActionParam(i, "user_id", v)}>
                            <SelectTrigger className="rounded-sm"><SelectValue placeholder="User" /></SelectTrigger>
                            <SelectContent>{members.map((m) => <SelectItem key={m.id} value={m.id}>{m.name || m.email}</SelectItem>)}</SelectContent>
                          </Select>
                          <Input placeholder="Message" value={a.params.body || ""} onChange={(e) => setActionParam(i, "body", e.target.value)} className="rounded-sm" />
                        </>
                      )}
                      {a.type === "add_tag" && (
                        <Input placeholder="Tag name" value={a.params.tag || ""} onChange={(e) => setActionParam(i, "tag", e.target.value)}
                               className="rounded-sm col-span-2" data-testid={`action-tag-${i}`} />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2 pt-2 border-t border-border">
              <Switch checked={form.enabled} onCheckedChange={(v) => setForm({ ...form, enabled: v })} data-testid="workflow-enabled-switch" />
              <Label className="cursor-pointer">Enabled</Label>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={save} disabled={saving || !form.name || form.actions.length === 0}
                    className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="workflow-submit">
              {saving ? "Saving…" : editingId ? "Save changes" : "Create workflow"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
