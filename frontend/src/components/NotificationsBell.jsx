import { useEffect, useState } from "react";
import api from "@/lib/api";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Bell, Check, Sparkles } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

export default function NotificationsBell() {
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/notifications");
      setItems(data.items || []);
      setUnread(data.unread || 0);
    } catch (error) {
      console.error("Notifications fetch failed:", error);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, []);

  const markAllRead = async () => {
    await api.post("/notifications/read-all");
    load();
  };

  const markOneRead = async (id) => {
    await api.post(`/notifications/${id}/read`);
    load();
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button className="relative p-2 rounded-sm hover:bg-black/5 dark:hover:bg-white/5 transition-colors" data-testid="notifications-bell">
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 px-1 rounded-full bg-[#FF3823] text-white text-[10px] font-mono-data font-semibold flex items-center justify-center" data-testid="notifications-badge">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 max-h-[440px] overflow-y-auto">
        <div className="flex items-center justify-between px-2 py-1.5">
          <DropdownMenuLabel className="p-0">Notifications</DropdownMenuLabel>
          {unread > 0 && (
            <button onClick={markAllRead} className="text-xs text-[#0047FF] hover:underline" data-testid="mark-all-read-btn">
              Mark all read
            </button>
          )}
        </div>
        <DropdownMenuSeparator />
        {items.length === 0 && (
          <div className="p-8 text-center text-sm text-muted-foreground">
            <Sparkles className="h-5 w-5 mx-auto mb-2 opacity-40" />
            All caught up.
          </div>
        )}
        {items.map(n => (
          <div key={n.id}
               onClick={() => !n.read && markOneRead(n.id)}
               className={`px-3 py-2.5 border-l-2 cursor-pointer hover:bg-black/5 dark:hover:bg-white/5 ${n.read ? "border-transparent opacity-70" : "border-[#0047FF]"}`}
               data-testid={`notification-${n.id}`}>
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{n.title}</div>
                <div className="text-xs text-muted-foreground line-clamp-2">{n.body}</div>
                <div className="text-[10px] text-muted-foreground font-mono-data mt-1">
                  {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
                </div>
              </div>
              {!n.read && <span className="mt-1 h-1.5 w-1.5 rounded-full bg-[#FF3823] shrink-0" />}
            </div>
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
