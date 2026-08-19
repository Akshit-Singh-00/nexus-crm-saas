import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { Toaster } from "@/components/ui/sonner";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import Onboarding from "@/pages/Onboarding";
import Dashboard from "@/pages/Dashboard";
import Customers from "@/pages/Customers";
import Leads from "@/pages/Leads";
import Deals from "@/pages/Deals";
import Tasks from "@/pages/Tasks";
import Team from "@/pages/Team";
import Billing from "@/pages/Billing";
import InviteAccept from "@/pages/InviteAccept";
import CustomerDetail from "@/pages/CustomerDetail";
import Landing from "@/pages/Landing";
import Layout from "@/components/Layout";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10 text-sm text-muted-foreground">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function WithWorkspace({ children }) {
  const { user, workspaces, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (!workspaces || workspaces.length === 0) return <Navigate to="/onboarding" replace />;
  return <Layout>{children}</Layout>;
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Toaster position="bottom-right" richColors theme="dark" />
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/invite/:token" element={<InviteAccept />} />
            <Route path="/onboarding" element={<Protected><Onboarding /></Protected>} />
            <Route path="/app" element={<WithWorkspace><Dashboard /></WithWorkspace>} />
            <Route path="/app/customers" element={<WithWorkspace><Customers /></WithWorkspace>} />
            <Route path="/app/customers/:id" element={<WithWorkspace><CustomerDetail /></WithWorkspace>} />
            <Route path="/app/leads" element={<WithWorkspace><Leads /></WithWorkspace>} />
            <Route path="/app/deals" element={<WithWorkspace><Deals /></WithWorkspace>} />
            <Route path="/app/tasks" element={<WithWorkspace><Tasks /></WithWorkspace>} />
            <Route path="/app/team" element={<WithWorkspace><Team /></WithWorkspace>} />
            <Route path="/app/billing" element={<WithWorkspace><Billing /></WithWorkspace>} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
