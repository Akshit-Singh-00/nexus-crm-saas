import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput,
  CommandItem, CommandList, CommandSeparator,
} from "@/components/ui/command";
import { Users, Target, Kanban, LayoutDashboard, CheckSquare, UsersRound, Receipt } from "lucide-react";
import api from "@/lib/api";

const NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard },
  { to: "/app/customers", label: "Customers", icon: Users },
  { to: "/app/leads", label: "Leads", icon: Target },
  { to: "/app/deals", label: "Deals", icon: Kanban },
  { to: "/app/tasks", label: "Tasks", icon: CheckSquare },
  { to: "/app/team", label: "Team", icon: UsersRound },
  { to: "/app/billing", label: "Billing", icon: Receipt },
];

export default function CommandPalette({ open, onOpenChange }) {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState({ customers: [], leads: [], deals: [] });

  useEffect(() => {
    if (!q || q.length < 2) { setResults({ customers: [], leads: [], deals: [] }); return; }
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get("/search", { params: { q } });
        setResults(data);
      } catch (_) { /* ignore */ }
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  const go = useCallback((path) => { onOpenChange(false); setQ(""); nav(path); }, [nav, onOpenChange]);

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <Command shouldFilter={false}>
        <CommandInput placeholder="Search customers, leads, deals or jump to a page…" value={q} onValueChange={setQ} data-testid="command-palette-input" />
        <CommandList>
          <CommandEmpty>No results. Try a different search.</CommandEmpty>

          {results.customers.length > 0 && (
            <CommandGroup heading="Customers">
              {results.customers.map(c => (
                <CommandItem key={c.id} onSelect={() => go(`/app/customers/${c.id}`)} data-testid={`cmd-customer-${c.id}`}>
                  <Users className="h-4 w-4 mr-2" /> {c.name} <span className="ml-2 text-xs text-muted-foreground">{c.company}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          {results.leads.length > 0 && (
            <CommandGroup heading="Leads">
              {results.leads.map(l => (
                <CommandItem key={l.id} onSelect={() => go("/app/leads")} data-testid={`cmd-lead-${l.id}`}>
                  <Target className="h-4 w-4 mr-2" /> {l.name} <span className="ml-2 text-xs text-muted-foreground">{l.company}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          {results.deals.length > 0 && (
            <CommandGroup heading="Deals">
              {results.deals.map(d => (
                <CommandItem key={d.id} onSelect={() => go("/app/deals")} data-testid={`cmd-deal-${d.id}`}>
                  <Kanban className="h-4 w-4 mr-2" /> {d.title} <span className="ml-2 text-xs font-mono-data text-muted-foreground">${d.value}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}

          <CommandSeparator />
          <CommandGroup heading="Jump to">
            {NAV.map(n => (
              <CommandItem key={n.to} onSelect={() => go(n.to)} data-testid={`cmd-nav-${n.label.toLowerCase()}`}>
                <n.icon className="h-4 w-4 mr-2" /> {n.label}
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
