import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Plus, Sparkles, Trash2, Search } from "lucide-react";

const emptyForm = { name: "", email: "", phone: "", company: "", source: "manual", status: "new", value: 0 };

const statusColors = {
  new: "bg-neutral-100 text-neutral-800",
  contacted: "bg-blue-100 text-blue-800",
  qualified: "bg-green-100 text-green-800",
  unqualified: "bg-red-100 text-red-800",
};

function ScoreBadge({ score }) {
  if (score == null) return <span className="text-xs text-neutral-400 font-mono-data">—</span>;
  const color = score >= 75 ? "text-green-700 bg-green-100" : score >= 50 ? "text-amber-700 bg-amber-100" : "text-red-700 bg-red-100";
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-mono-data ${color}`}>{score}</span>;
}

export default function Leads() {
  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [scoringId, setScoringId] = useState(null);

  const load = async () => {
    try { const { data } = await api.get("/leads", { params: { search } }); setRows(data); }
    catch { toast.error("Failed to load leads"); }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [search]);

  const create = async () => {
    setSaving(true);
    try {
      await api.post("/leads", { ...form, value: Number(form.value) || 0 });
      toast.success("Lead created");
      setOpen(false); setForm(emptyForm); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this lead?")) return;
    await api.delete(`/leads/${id}`); load(); toast.success("Deleted");
  };

  const score = async (id) => {
    setScoringId(id);
    try {
      const { data } = await api.post(`/ai/score-lead/${id}`);
      toast.success(`Scored ${data.score}/100`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Scoring failed");
    } finally { setScoringId(null); }
  };

  return (
    <div className="space-y-6" data-testid="leads-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-heading text-4xl md:text-5xl">Leads</h1>
          <p className="text-sm text-muted-foreground mt-1 font-mono-data uppercase tracking-widest">{rows.length} records · AI scoring</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-sm bg-[#0047FF] hover:bg-[#0036CC]" data-testid="new-lead-btn">
              <Plus className="h-4 w-4 mr-2" /> New lead
            </Button>
          </DialogTrigger>
          <DialogContent className="rounded-sm max-w-md">
            <DialogHeader><DialogTitle>New lead</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label>Name *</Label>
                <Input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} className="rounded-sm mt-1" data-testid="lead-name-input" /></div>
              <div><Label>Email</Label>
                <Input value={form.email} onChange={e=>setForm({...form,email:e.target.value})} className="rounded-sm mt-1" data-testid="lead-email-input" /></div>
              <div><Label>Company</Label>
                <Input value={form.company} onChange={e=>setForm({...form,company:e.target.value})} className="rounded-sm mt-1" data-testid="lead-company-input" /></div>
              <div><Label>Source</Label>
                <Input value={form.source} onChange={e=>setForm({...form,source:e.target.value})} className="rounded-sm mt-1" data-testid="lead-source-input" /></div>
              <div><Label>Est. value (USD)</Label>
                <Input type="number" value={form.value} onChange={e=>setForm({...form,value:e.target.value})} className="rounded-sm mt-1" data-testid="lead-value-input" /></div>
              <div><Label>Status</Label>
                <Select value={form.status} onValueChange={v=>setForm({...form,status:v})}>
                  <SelectTrigger className="rounded-sm mt-1" data-testid="lead-status-select"><SelectValue/></SelectTrigger>
                  <SelectContent>
                    {["new","contacted","qualified","unqualified"].map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={create} disabled={saving || !form.name} className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800" data-testid="lead-submit">
                {saving ? "Saving…" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="rounded-sm border-border shadow-sm">
        <div className="p-4 border-b border-border flex items-center gap-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search leads…"
                 className="border-0 shadow-none focus-visible:ring-0 h-8" data-testid="lead-search" />
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>AI Score</TableHead>
              <TableHead className="w-24"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow><TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-10">No leads yet.</TableCell></TableRow>
            )}
            {rows.map(r => (
              <TableRow key={r.id} data-testid={`lead-row-${r.id}`}>
                <TableCell className="font-medium">
                  {r.name}
                  {r.score_reason && <div className="text-[11px] text-muted-foreground mt-0.5 max-w-md truncate">{r.score_reason}</div>}
                </TableCell>
                <TableCell className="text-muted-foreground">{r.company || "—"}</TableCell>
                <TableCell><Badge className={`${statusColors[r.status]} hover:${statusColors[r.status]} rounded-sm border-0`}>{r.status}</Badge></TableCell>
                <TableCell className="font-mono-data text-xs">${Number(r.value||0).toLocaleString()}</TableCell>
                <TableCell><ScoreBadge score={r.score} /></TableCell>
                <TableCell>
                  <div className="flex items-center gap-1 justify-end">
                    <Button size="sm" variant="ghost" onClick={() => score(r.id)} disabled={scoringId === r.id}
                            className="h-8 text-[#FF3823] hover:bg-[#FFF0EE]" data-testid={`score-lead-${r.id}`}>
                      <Sparkles className="h-4 w-4" />
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => remove(r.id)}
                            className="h-8 text-muted-foreground hover:text-[#FF3823]" data-testid={`delete-lead-${r.id}`}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
