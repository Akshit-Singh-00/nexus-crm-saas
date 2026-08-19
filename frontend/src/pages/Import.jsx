import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@/components/ui/table";
import { toast } from "sonner";
import { Upload, FileText, ArrowRight, Check, Users, Target, X } from "lucide-react";

const STEPS = ["Upload", "Map columns", "Confirm"];

export default function Import() {
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [entity, setEntity] = useState("lead");
  const [csvText, setCsvText] = useState("");
  const [fileName, setFileName] = useState("");
  const [preview, setPreview] = useState(null);
  const [mapping, setMapping] = useState({});
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);

  const onFile = (file) => {
    if (!file) return;
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (e) => setCsvText(e.target.result);
    reader.readAsText(file);
  };

  const goPreview = async () => {
    if (!csvText.trim()) { toast.error("Please choose a CSV file"); return; }
    try {
      const { data } = await api.post("/import/preview", { csv_text: csvText, entity });
      setPreview(data);
      setMapping(data.suggested_mapping || {});
      setStep(1);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to parse CSV"); }
  };

  const execute = async () => {
    setImporting(true);
    try {
      const { data } = await api.post("/import/execute", { csv_text: csvText, entity, mapping });
      setResult(data);
      setStep(2);
      if (data.inserted > 0) toast.success(`Imported ${data.inserted} ${entity}s`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Import failed"); }
    finally { setImporting(false); }
  };

  const requiredMapped = useMemo(() => Object.values(mapping).includes("name"), [mapping]);

  return (
    <div className="space-y-6 max-w-4xl" data-testid="import-page">
      <div>
        <h1 className="font-heading text-4xl md:text-5xl">CSV Import</h1>
        <p className="text-sm text-muted-foreground mt-1 font-mono-data uppercase tracking-widest">
          Bulk import leads or customers · step {step + 1} of {STEPS.length}
        </p>
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-2">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-mono-data ${
              i <= step ? "bg-[#0047FF] text-white" : "bg-secondary text-muted-foreground"
            }`}>
              {i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}
            </div>
            <span className={`text-sm ${i === step ? "font-medium" : "text-muted-foreground"}`}>{s}</span>
            {i < STEPS.length - 1 && <ArrowRight className="h-3 w-3 text-muted-foreground mx-2" />}
          </div>
        ))}
      </div>

      {step === 0 && (
        <Card className="rounded-sm border-border shadow-sm p-6 space-y-5">
          <div>
            <Label>Import into</Label>
            <div className="flex gap-3 mt-2">
              {[{ id: "lead", label: "Leads", icon: Target }, { id: "customer", label: "Customers", icon: Users }].map((o) => (
                <button key={o.id} onClick={() => setEntity(o.id)}
                        className={`flex-1 border rounded-sm p-4 text-left transition-colors ${
                          entity === o.id ? "border-[#0047FF] bg-[#0047FF]/5" : "border-border hover:border-primary/40"
                        }`}
                        data-testid={`import-entity-${o.id}`}>
                  <o.icon className={`h-5 w-5 ${entity === o.id ? "text-[#0047FF]" : "text-muted-foreground"}`} />
                  <div className="font-medium mt-2">{o.label}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    Fields: {(o.id === "lead" ? "name, email, phone, company, source, status, value" : "name, email, phone, company, status")}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <Label>Upload CSV file</Label>
            <label className="mt-2 border-2 border-dashed border-border rounded-sm p-8 flex flex-col items-center justify-center cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-colors"
                   data-testid="import-dropzone">
              <Upload className="h-8 w-8 text-muted-foreground" />
              <div className="mt-3 text-sm font-medium">{fileName || "Choose a .csv file"}</div>
              <div className="text-xs text-muted-foreground mt-1">First row is treated as headers</div>
              <input type="file" accept=".csv,text/csv" className="hidden"
                     onChange={(e) => onFile(e.target.files?.[0])} data-testid="import-file-input" />
            </label>
          </div>

          <div className="flex justify-end">
            <Button onClick={goPreview} disabled={!csvText}
                    className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="import-next-btn">
              Continue <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </div>
        </Card>
      )}

      {step === 1 && preview && (
        <>
          <Card className="rounded-sm border-border shadow-sm p-6 space-y-4">
            <div>
              <div className="text-xs uppercase tracking-widest font-mono-data text-muted-foreground">Column mapping</div>
              <p className="text-sm mt-1">Match each CSV column to a {entity} field. Leave blank to skip.</p>
            </div>
            <div className="space-y-2">
              {preview.headers.map((h) => (
                <div key={h} className="flex items-center gap-3" data-testid={`mapping-row-${h}`}>
                  <div className="flex-1 text-sm font-mono-data truncate">{h}</div>
                  <ArrowRight className="h-3 w-3 text-muted-foreground" />
                  <div className="flex-1">
                    <Select value={mapping[h] || "__skip"} onValueChange={(v) => setMapping({ ...mapping, [h]: v === "__skip" ? undefined : v })}>
                      <SelectTrigger className="rounded-sm" data-testid={`mapping-select-${h}`}><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__skip">— Skip this column —</SelectItem>
                        {preview.target_fields.map((f) => (
                          <SelectItem key={f} value={f}>{f}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              ))}
            </div>
            {!requiredMapped && (
              <div className="text-xs text-[#FF3823] font-mono-data">⚠ You must map at least one column to &quot;name&quot;</div>
            )}
          </Card>

          <Card className="rounded-sm border-border shadow-sm">
            <div className="p-4 border-b border-border text-xs uppercase tracking-widest font-mono-data text-muted-foreground">
              Preview · {preview.total_rows} total row{preview.total_rows !== 1 ? "s" : ""}
            </div>
            <Table>
              <TableHeader>
                <TableRow>{preview.headers.map((h) => <TableHead key={h} className="text-xs font-mono-data">{h}</TableHead>)}</TableRow>
              </TableHeader>
              <TableBody>
                {preview.sample_rows.map((row, i) => (
                  <TableRow key={i}>
                    {preview.headers.map((h) => <TableCell key={h} className="text-xs">{row[h] || "—"}</TableCell>)}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep(0)} className="rounded-sm" data-testid="import-back-btn">Back</Button>
            <Button onClick={execute} disabled={!requiredMapped || importing}
                    className="rounded-sm bg-[#0047FF] hover:bg-[#0036CC] text-white" data-testid="import-execute-btn">
              {importing ? "Importing…" : `Import ${preview.total_rows} row${preview.total_rows !== 1 ? "s" : ""}`}
            </Button>
          </div>
        </>
      )}

      {step === 2 && result && (
        <Card className="rounded-sm border-border shadow-sm p-8 text-center space-y-4">
          <div className="mx-auto h-14 w-14 rounded-full bg-green-100 flex items-center justify-center">
            <Check className="h-7 w-7 text-green-600" />
          </div>
          <div>
            <div className="font-heading text-3xl">Import complete</div>
            <div className="text-muted-foreground mt-2">
              {result.inserted} {entity}{result.inserted !== 1 ? "s" : ""} imported successfully · {result.errors.length} row{result.errors.length !== 1 ? "s" : ""} skipped
            </div>
          </div>
          {result.errors.length > 0 && (
            <div className="text-left max-w-md mx-auto text-xs text-muted-foreground font-mono-data max-h-32 overflow-y-auto border border-border rounded-sm p-3">
              {result.errors.slice(0, 10).map((e, i) => <div key={i}>Row {e.row}: {e.error}</div>)}
            </div>
          )}
          <div className="flex gap-3 justify-center pt-2">
            <Button variant="outline" onClick={() => { setStep(0); setCsvText(""); setFileName(""); setPreview(null); setResult(null); }} className="rounded-sm" data-testid="import-again-btn">
              Import another file
            </Button>
            <Button onClick={() => nav(`/app/${entity}s`)}
                    className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="import-view-btn">
              View {entity}s
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
