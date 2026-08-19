import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";

const emptyForm = { title: "", description: "", priority: "medium", status: "todo", due_date: "" };

const priorityColor = { low: "bg-neutral-100 text-neutral-700", medium: "bg-blue-100 text-blue-800", high: "bg-red-100 text-red-800" };

export default function Tasks() {
  const [tasks, setTasks] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try { const { data } = await api.get("/tasks"); setTasks(data); }
    catch { toast.error("Failed to load tasks"); }
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    setSaving(true);
    try {
      await api.post("/tasks", form);
      toast.success("Task created");
      setOpen(false); setForm(emptyForm); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  const toggle = async (t) => {
    const status = t.status === "done" ? "todo" : "done";
    try {
      await api.put(`/tasks/${t.id}`, { ...t, status });
      setTasks(prev => prev.map(x => x.id === t.id ? { ...x, status } : x));
    } catch { toast.error("Failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete task?")) return;
    await api.delete(`/tasks/${id}`); load();
  };

  return (
    <div className="space-y-6" data-testid="tasks-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-heading text-4xl md:text-5xl">Tasks</h1>
          <p className="text-sm text-neutral-500 mt-1 font-mono-data uppercase tracking-widest">{tasks.filter(t=>t.status!=='done').length} open</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-sm bg-[#0047FF] hover:bg-[#0036CC]" data-testid="new-task-btn">
              <Plus className="h-4 w-4 mr-2" /> New task
            </Button>
          </DialogTrigger>
          <DialogContent className="rounded-sm max-w-md">
            <DialogHeader><DialogTitle>New task</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label>Title *</Label>
                <Input value={form.title} onChange={e=>setForm({...form,title:e.target.value})} className="rounded-sm mt-1" data-testid="task-title-input" /></div>
              <div><Label>Description</Label>
                <Textarea value={form.description} onChange={e=>setForm({...form,description:e.target.value})} className="rounded-sm mt-1" data-testid="task-description-input" /></div>
              <div><Label>Due date</Label>
                <Input type="date" value={form.due_date} onChange={e=>setForm({...form,due_date:e.target.value})} className="rounded-sm mt-1" data-testid="task-due-input" /></div>
              <div><Label>Priority</Label>
                <Select value={form.priority} onValueChange={v=>setForm({...form,priority:v})}>
                  <SelectTrigger className="rounded-sm mt-1" data-testid="task-priority-select"><SelectValue/></SelectTrigger>
                  <SelectContent>{["low","medium","high"].map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select></div>
            </div>
            <DialogFooter>
              <Button onClick={create} disabled={saving || !form.title} className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800" data-testid="task-submit">
                {saving ? "Saving…" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="rounded-sm border-[#E2E2E0] shadow-sm divide-y divide-[#E2E2E0]">
        {tasks.length === 0 && <div className="text-center text-sm text-neutral-500 py-10">No tasks yet.</div>}
        {tasks.map(t => (
          <div key={t.id} className="flex items-center gap-4 p-4" data-testid={`task-row-${t.id}`}>
            <Checkbox checked={t.status === "done"} onCheckedChange={() => toggle(t)} data-testid={`task-toggle-${t.id}`} />
            <div className="flex-1 min-w-0">
              <div className={`text-sm ${t.status === "done" ? "line-through text-neutral-400" : ""}`}>{t.title}</div>
              {t.description && <div className="text-xs text-neutral-500 mt-0.5">{t.description}</div>}
            </div>
            <span className={`text-[10px] uppercase font-mono-data px-2 py-0.5 rounded-sm ${priorityColor[t.priority]}`}>{t.priority}</span>
            {t.due_date && <span className="text-xs text-neutral-500 font-mono-data">{t.due_date}</span>}
            <button onClick={() => remove(t.id)} className="text-neutral-400 hover:text-[#FF3823]" data-testid={`delete-task-${t.id}`}>
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </Card>
    </div>
  );
}
