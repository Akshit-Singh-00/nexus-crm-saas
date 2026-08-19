import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { Shield } from "lucide-react";

const actionColor = {
  created: "text-green-600",
  updated: "text-blue-600",
  deleted: "text-[#FF3823]",
  role_changed: "text-purple-600",
  removed: "text-[#FF3823]",
};

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/audit-logs", { params: { limit: 200 } });
        setLogs(data);
      } catch (e) {
        setError(e?.response?.data?.detail || "You don't have permission to view audit logs.");
      } finally { setLoading(false); }
    })();
  }, []);

  if (loading) return <div className="text-sm text-muted-foreground">Loading audit log…</div>;
  if (error) {
    return (
      <div className="max-w-lg">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="h-5 w-5 text-[#FF3823]" />
          <h1 className="font-heading text-3xl">Audit log</h1>
        </div>
        <p className="text-sm text-muted-foreground">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="audit-log-page">
      <div>
        <h1 className="font-heading text-4xl md:text-5xl">Audit log</h1>
        <p className="text-sm text-muted-foreground mt-1 font-mono-data uppercase tracking-widest">
          {logs.length} recent events · admin-only
        </p>
      </div>

      <Card className="rounded-sm border-border shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>When</TableHead>
              <TableHead>User</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Resource</TableHead>
              <TableHead>Changes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {logs.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-10">
                  No audit events yet. Sensitive actions will appear here.
                </TableCell>
              </TableRow>
            )}
            {logs.map((log) => (
              <TableRow key={log.id} data-testid={`audit-row-${log.id}`}>
                <TableCell className="text-xs text-muted-foreground font-mono-data whitespace-nowrap">
                  {formatDistanceToNow(new Date(log.created_at), { addSuffix: true })}
                </TableCell>
                <TableCell className="text-sm">{log.user_email || log.user_id?.slice(0, 8)}</TableCell>
                <TableCell>
                  <span className={`text-xs uppercase font-mono-data ${actionColor[log.action] || "text-foreground"}`}>
                    {log.action}
                  </span>
                </TableCell>
                <TableCell className="text-sm">
                  <span className="font-medium">{log.resource}</span>
                  <span className="text-muted-foreground ml-2 font-mono-data text-xs">{(log.resource_id || "").slice(0, 8)}</span>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground max-w-xs">
                  {log.after && Object.keys(log.after).length > 0 ? (
                    <code className="font-mono-data">{JSON.stringify(log.after)}</code>
                  ) : "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
