import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogFooter
} from "@/components/ui/dialog";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell
} from "@/components/ui/table";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Plus, Search, Trash2, ArrowRight } from "lucide-react";

const emptyForm = { name: "", email: "", phone: "", company: "", status: "active", tags: [] };

export default function Customers() {
  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/customers", { params: { search } });
      setRows(data);
    } catch (e) { toast.error("Failed to load customers"); }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [search]);

  const create = async () => {
    setSaving(true);
    try {
      await api.post("/customers", form);
      toast.success("Customer created");
      setOpen(false); setForm(emptyForm); load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    } finally { setSaving(false); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this customer?")) return;
    try { await api.delete(`/customers/${id}`); load(); toast.success("Deleted"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const statusColor = { active: "bg-green-100 text-green-800", churned: "bg-red-100 text-red-800", prospect: "bg-blue-100 text-blue-800" };

  return (
    <div className="space-y-6" data-testid="customers-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-heading text-4xl md:text-5xl">Customers</h1>
          <p className="text-sm text-neutral-500 mt-1 font-mono-data uppercase tracking-widest">{rows.length} records</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-sm bg-[#0047FF] hover:bg-[#0036CC]" data-testid="new-customer-btn">
              <Plus className="h-4 w-4 mr-2" /> New customer
            </Button>
          </DialogTrigger>
          <DialogContent className="rounded-sm max-w-md">
            <DialogHeader><DialogTitle>New customer</DialogTitle></DialogHeader>
            <div className="space-y-3">
              {[
                ["name","Name",true], ["email","Email",false], ["phone","Phone",false], ["company","Company",false]
              ].map(([k,label,req]) => (
                <div key={k}>
                  <Label>{label}{req && " *"}</Label>
                  <Input value={form[k]} onChange={e=>setForm({...form,[k]:e.target.value})}
                         required={req} className="rounded-sm mt-1" data-testid={`customer-${k}-input`} />
                </div>
              ))}
            </div>
            <DialogFooter>
              <Button onClick={create} disabled={saving || !form.name} className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800" data-testid="customer-submit">
                {saving ? "Saving…" : "Create"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="rounded-sm border-[#E2E2E0] shadow-sm">
        <div className="p-4 border-b border-[#E2E2E0] flex items-center gap-2">
          <Search className="h-4 w-4 text-neutral-500" />
          <Input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search customers…"
                 className="border-0 shadow-none focus-visible:ring-0 h-8" data-testid="customer-search" />
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-24"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              <TableRow><TableCell colSpan={5} className="text-center text-sm text-neutral-500 py-10">No customers yet.</TableCell></TableRow>
            )}
            {rows.map(r => (
              <TableRow key={r.id} data-testid={`customer-row-${r.id}`}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell className="text-neutral-600">{r.company || "—"}</TableCell>
                <TableCell className="text-neutral-600 font-mono-data text-xs">{r.email || "—"}</TableCell>
                <TableCell>
                  <Badge className={`${statusColor[r.status]} hover:${statusColor[r.status]} rounded-sm border-0`}>{r.status}</Badge>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center gap-1 justify-end">
                    <Link to={`/app/customers/${r.id}`}>
                      <Button variant="ghost" size="sm" className="h-8" data-testid={`open-customer-${r.id}`}>
                        <ArrowRight className="h-4 w-4" />
                      </Button>
                    </Link>
                    <Button variant="ghost" size="sm" className="h-8 text-[#FF3823] hover:text-[#FF3823] hover:bg-[#FFF0EE]"
                            onClick={() => remove(r.id)} data-testid={`delete-customer-${r.id}`}>
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
