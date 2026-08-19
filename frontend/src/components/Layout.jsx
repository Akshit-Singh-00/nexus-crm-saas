import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Users, Target, Kanban, CheckSquare, UsersRound,
  LogOut, Hexagon, ChevronDown, Search
} from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

const nav = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/app/customers", label: "Customers", icon: Users },
  { to: "/app/leads", label: "Leads", icon: Target },
  { to: "/app/deals", label: "Deals", icon: Kanban },
  { to: "/app/tasks", label: "Tasks", icon: CheckSquare },
  { to: "/app/team", label: "Team", icon: UsersRound },
];

export default function Layout({ children }) {
  const { user, activeWorkspace, workspaces, switchWorkspace, logout } = useAuth();
  const nav_go = useNavigate();

  const doLogout = () => { logout(); nav_go("/login"); };

  const initials = (user?.name || user?.email || "?")
    .split(" ").map(s => s[0]).slice(0,2).join("").toUpperCase();

  return (
    <div className="min-h-screen flex bg-[#f7f7f5]">
      {/* Sidebar */}
      <aside className="w-64 bg-[#0A0A0A] text-[#f7f7f5] flex flex-col shrink-0" data-testid="app-sidebar">
        <div className="px-6 py-6 flex items-center gap-2">
          <Hexagon className="h-6 w-6 text-[#FF3823]" strokeWidth={2.5} />
          <span className="font-heading text-xl">Nexus<span className="text-neutral-400">CRM</span></span>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="mx-3 mb-4 flex items-center justify-between px-3 py-2.5 rounded-sm bg-white/5 hover:bg-white/10 border border-white/10 text-left"
              data-testid="workspace-switcher"
            >
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
            {workspaces.map(w => (
              <DropdownMenuItem
                key={w.id}
                onClick={() => switchWorkspace(w.id)}
                data-testid={`workspace-option-${w.id}`}
              >
                {w.name} <span className="ml-auto text-xs text-neutral-500 uppercase font-mono-data">{w.role}</span>
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => nav_go("/onboarding")} data-testid="create-workspace-btn">
              + New workspace
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <nav className="flex-1 px-3 space-y-0.5">
          {nav.map(({ to, label, icon: Icon, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              data-testid={`nav-${label.toLowerCase()}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-sm text-sm transition-colors ${
                  isActive
                    ? "bg-[#0047FF] text-white"
                    : "text-neutral-300 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </NavLink>
          ))}
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
        <div className="h-14 border-b border-[#E2E2E0] bg-white/70 backdrop-blur-xl px-6 flex items-center gap-3 sticky top-0 z-10">
          <div className="flex items-center gap-2 text-sm text-neutral-500 flex-1">
            <Search className="h-4 w-4" />
            <span>Global search coming soon</span>
          </div>
          <div className="text-xs font-mono-data text-neutral-500 uppercase tracking-widest">
            {activeWorkspace?.role}
          </div>
        </div>
        <div className="flex-1 p-6 md:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
