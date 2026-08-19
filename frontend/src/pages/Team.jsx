import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { UserPlus, Copy, Check } from "lucide-react";

const roleColor = {
  owner: "bg-[#0A0A0A] text-white",
  admin: "bg-[#0047FF] text-white",
  member: "bg-secondary text-secondary-foreground",
  viewer: "bg-muted text-muted-foreground",
};

export default function Team() {
  const { activeWorkspace } = useAuth();
  const [members, setMembers] = useState([]);
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [sendEmail, setSendEmail] = useState(true);
  const [saving, setSaving] = useState(false);
  const [inviteLink, setInviteLink] = useState("");
  const [copied, setCopied] = useState(false);

  const load = async () => {
    try { const { data } = await api.get("/workspaces/members"); setMembers(data); }
    catch { toast.error("Failed to load team"); }
  };
  useEffect(() => { load(); }, []);

  const canInvite = ["owner", "admin"].includes(activeWorkspace?.role);

  const invite = async () => {
    setSaving(true);
    try {
      const { data } = await api.post("/workspaces/invite", { email, role, send_email: sendEmail });
      setInviteLink(data.invite_link);
      if (data.email_sent) toast.success("Invite email sent");
      else toast.success("Invite created — copy the link below");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };

  const copyLink = async () => {
    await navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const closeAndReset = () => {
    setOpen(false);
    setEmail(""); setRole("member"); setInviteLink(""); setSendEmail(true);
  };

  return (
    <div className="space-y-6" data-testid="team-page">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-heading text-4xl md:text-5xl">Team</h1>
          <p className="text-sm text-muted-foreground mt-1 font-mono-data uppercase tracking-widest">{members.length} members</p>
        </div>
        {canInvite && (
          <Dialog open={open} onOpenChange={(o) => { if (!o) closeAndReset(); else setOpen(true); }}>
            <DialogTrigger asChild>
              <Button className="rounded-sm bg-[#0047FF] hover:bg-[#0036CC] text-white" data-testid="invite-member-btn">
                <UserPlus className="h-4 w-4 mr-2" /> Invite member
              </Button>
            </DialogTrigger>
            <DialogContent className="rounded-sm max-w-md">
              <DialogHeader><DialogTitle>Invite team member</DialogTitle></DialogHeader>
              {!inviteLink ? (
                <>
                  <div className="space-y-3">
                    <div>
                      <Label>Email *</Label>
                      <Input value={email} onChange={e => setEmail(e.target.value)} type="email" className="rounded-sm mt-1" data-testid="invite-email-input" />
                    </div>
                    <div>
                      <Label>Role</Label>
                      <Select value={role} onValueChange={setRole}>
                        <SelectTrigger className="rounded-sm mt-1" data-testid="invite-role-select"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="admin">Admin</SelectItem>
                          <SelectItem value="member">Member</SelectItem>
                          <SelectItem value="viewer">Viewer</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center gap-2 pt-2">
                      <Checkbox id="send" checked={sendEmail} onCheckedChange={setSendEmail} data-testid="invite-send-email-check" />
                      <Label htmlFor="send" className="text-sm cursor-pointer">Send invite email</Label>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button onClick={invite} disabled={saving || !email} className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="invite-submit">
                      {saving ? "Creating…" : "Send invitation"}
                    </Button>
                  </DialogFooter>
                </>
              ) : (
                <>
                  <div className="space-y-3">
                    <p className="text-sm text-muted-foreground">Share this link with the invitee. It expires in 7 days.</p>
                    <div className="flex items-center gap-2">
                      <Input readOnly value={inviteLink} className="rounded-sm font-mono-data text-xs" data-testid="invite-link-display" />
                      <Button onClick={copyLink} variant="outline" className="rounded-sm" data-testid="copy-invite-link">
                        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button onClick={closeAndReset} className="rounded-sm bg-[#0A0A0A] hover:bg-neutral-800 text-white" data-testid="invite-done-btn">Done</Button>
                  </DialogFooter>
                </>
              )}
            </DialogContent>
          </Dialog>
        )}
      </div>

      <Card className="rounded-sm border-border shadow-sm divide-y divide-border">
        {members.map(m => {
          const initials = (m.name || m.email || "?").split(" ").map(s => s[0]).slice(0, 2).join("").toUpperCase();
          return (
            <div key={m.membership_id || m.id} className="flex items-center gap-4 p-4" data-testid={`member-row-${m.id}`}>
              <Avatar className="h-10 w-10">
                <AvatarFallback className="bg-[#0047FF] text-white text-xs">{initials}</AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">{m.name || m.email}</div>
                <div className="text-xs text-muted-foreground font-mono-data">{m.email}</div>
              </div>
              <span className={`text-[10px] uppercase font-mono-data px-2 py-1 rounded-sm ${roleColor[m.role]}`}>{m.role}</span>
            </div>
          );
        })}
      </Card>
    </div>
  );
}
