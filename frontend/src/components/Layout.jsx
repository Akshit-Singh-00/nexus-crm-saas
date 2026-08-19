import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import {
  LayoutDashboard, Users, Target, Kanban, CheckSquare, UsersRound, Receipt,
  LifeBuoy, Settings2, Shield, LogOut, Hexagon, ChevronDown, Search, Sun, Moon, Brain,
} from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import CommandPalette from "@/components/CommandPalette";
import NotificationsBell from "@/components/NotificationsBell";
import CopilotDrawer from "@/components/CopilotDrawer";

const NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, exact: true, resource: null },
  { to: "/app/customers", label: "Customers", icon: Users, resource: "customer" },
  { to: "/app/leads", label: "Leads", icon: Target, resource: "lead" },
  { to: "/app/deals", label: "Deals", icon: Kanban, resource: "deal" },
  { to: "/app/tasks", label: "Tasks", icon: CheckSquare, resource: "task" },
  { to: "/app/tickets", label: "Tickets", icon: LifeBuoy, resource: "ticket" },
  { to: "/app/team", label: "Team", icon: UsersRound, resource: null },
];

const ADMIN_NAV = [
  { to: "/app/settings", label: "Settings", icon: Settings2, roles: ["owner", "admin"] },
  { to: "/app/audit", label: "Audit log", icon: Shield, roles: ["owner", "admin"] },
  { to: "/app/billing", label: "Billing", icon: Receipt, roles: ["owner", "admin"] },
];

export default function Layout({ children }) {
  const { user, activeWorkspace, workspaces, switchWorkspace, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const nav_go = useNavigate();
  const [cmdOpen, setCmdOpen] = useState(false);
  const [copilotOpen, setCopilotOpen] = useState(false);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); setCmdOpen((o) => !o); }
      if ((e.metaKey || e.ctrlKey) && e.key === "j") { e.preventDefault(); setCopilotOpen((o) => !o); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const doLogout = () => { logout(); nav_go("/login"); };
  const initials = (user?.name || user?.email || "?")
    .split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();

  const isAdmin = ["owner", "admin"].includes(activeWorkspace?.role);
  const adminItems = ADMIN_NAV.filter((n) => n.roles.includes(activeWorkspace?.role));

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} />
      <CopilotDrawer open={copilotOpen} onOpenChange={setCopilotOpen} />

      {/* Sidebar */}
      <aside className="w-64 bg-[#0A0A0A] text-[#f7f7f5] flex flex-col shrink-0" data-testid="app-sidebar">
        <div className="px-6 py-6 flex items-center gap-2">
          {activeWorkspace?.logo_url ? (
            <img src={activeWorkspace.logo_url} alt="logo" className="h-7 w-7 rounded-sm object-cover" />
          ) : (
            <Hexagon className="h-6 w-6 text-[#FF3823]" strokeWidth={2.5} />
          )}
          <span className="font-heading text-xl">Nexus<span className="text-neutral-400">CRM</span></span>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="mx-3 mb-4 flex items-center justify-between px-3 py-2.5 rounded-sm bg-white/5 hover:bg-white/10 border border-white/10 text-left"
                    data-testid="workspace-switcher">
              <div className="min-w-0">
                <div className="text-[10px] uppercase tracking-widest text-neutral-500 font-mono-data">Workspace</div>
                <div className="truncate text-sm">{activeWorkspace?.name || "—"}</div>
              </div>
              <ChevronDown className="h-4 w-4 text-neutral-400 shrink-0" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuLabel>Your workspaces</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {workspaces.map((w) => (
              <DropdownMenuItem key={w.id} onClick={() => switchWorkspace(w.id)} data-testid={`workspace-option-${w.id}`}>
                {w.name} <span className="ml-auto text-xs text-muted-foreground uppercase font-mono-data">{w.role}</span>
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => nav_go("/onboarding")} data-testid="create-workspace-btn">
              + New workspace
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <nav className="flex-1 px-3 space-y-0.5 overflow-y-auto">
          {NAV.map(({ to, label, icon: Icon, exact }) => (
            <NavLink key={to} to={to} end={exact} data-testid={`nav-${label.toLowerCase()}`}
              className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-sm text-sm transition-colors ${
                isActive ? "bg-[#0047FF] text-white" : "text-neutral-300 hover:bg-white/5 hover:text-white"
              }`}>
              <Icon className="h-4 w-4" /><span>{label}</span>
            </NavLink>
          ))}
          {adminItems.length > 0 && (
            <>
              <div className="pt-4 px-3 text-[10px] uppercase tracking-widest text-neutral-500 font-mono-data">Admin</div>
              {adminItems.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to} data-testid={`nav-${label.toLowerCase().replace(' ','-')}`}
                  className={({ isActive }) => `flex items-center gap-3 px-3 py-2 rounded-sm text-sm transition-colors ${
                    isActive ? "bg-[#0047FF] text-white" : "text-neutral-300 hover:bg-white/5 hover:text-white"
                  }`}>
                  <Icon className="h-4 w-4" /><span>{label}</span>
                </NavLink>
              ))}
            </>
          )}
        </nav>

        <div className="p-3 border-t border-white/10">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="w-full flex items-center gap-3 px-2 py-2 rounded-sm hover:bg-white/5" data-testid="user-menu">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="bg-[#0047FF] text-white text-xs">{initials}</AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1 text-left">
                  <div className="text-sm truncate">{user?.name}</div>
                  <div className="text-[11px] text-neutral-500 truncate font-mono-data">{user?.email}</div>
                </div>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={doLogout} data-testid="logout-btn">
                <LogOut className="h-4 w-4 mr-2" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0 flex flex-col">
        <div className="h-14 border-b border-border bg-background/70 backdrop-blur-xl px-6 flex items-center gap-3 sticky top-0 z-10">
          <button onClick={() => setCmdOpen(true)}
                  className="flex items-center gap-2 text-sm text-muted-foreground flex-1 max-w-md px-3 py-1.5 rounded-sm border border-border hover:border-primary/40 transition-colors"
                  data-testid="global-search-trigger">
            <Search className="h-4 w-4" />
            <span className="hidden sm:inline">Search customers, leads, deals…</span>
            <span className="sm:hidden">Search</span>
            <span className="ml-auto font-mono-data text-[10px] border border-border px-1.5 py-0.5 rounded-sm">⌘K</span>
          </button>

          <div className="flex-1 hidden md:block" />

          <button onClick={() => setCopilotOpen(true)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-sm bg-[#FF3823] hover:bg-[#e02f1c] text-white text-sm transition-colors"
                  data-testid="copilot-open-btn">
            <Brain className="h-4 w-4" />
            <span className="hidden sm:inline">Copilot</span>
            <span className="ml-2 font-mono-data text-[10px] border border-white/30 px-1.5 py-0.5 rounded-sm hidden sm:inline">⌘J</span>
          </button>

          <button onClick={toggle} className="p-2 rounded-sm hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                  aria-label="Toggle theme" data-testid="theme-toggle">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          <NotificationsBell />

          <div className="text-xs font-mono-data text-muted-foreground uppercase tracking-widest ml-2 hidden md:block">
            {activeWorkspace?.role}
          </div>
        </div>
        <div className="flex-1 p-4 md:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
