import "@/App.css";
import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import BankSelection from "@/pages/BankSelection";
import DepositRegistration from "@/pages/DepositRegistration";
import ReportPage from "@/pages/ReportPage";
import LoginPage from "@/pages/LoginPage";
import AdminPage from "@/pages/AdminPage";
import StatementsPage from "@/pages/StatementsPage";
import AccruedInterestPage from "@/pages/AccruedInterestPage";
import BankReconciliationPage from "@/pages/BankReconciliationPage";
import ModuleSelection from "@/pages/ModuleSelection";

function App() {
  useEffect(() => {
    document.documentElement.setAttribute("dir", "rtl");
    document.documentElement.setAttribute("lang", "ar");
  }, []);

  return (
    <div className="App" dir="rtl" data-testid="app-root">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<ProtectedRoute><ModuleSelection /></ProtectedRoute>} />
            <Route path="/deposits" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports"]}><BankSelection mode="deposits" /></ProtectedRoute>} />
            <Route path="/reconciliations" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports"]}><BankSelection mode="reconciliations" /></ProtectedRoute>} />
            <Route path="/secure-admin-control-panel" element={<ProtectedRoute adminOnly><AdminPage /></ProtectedRoute>} />
            <Route path="/bank/:bankId/register" element={<ProtectedRoute permission="enter_deposits"><DepositRegistration /></ProtectedRoute>} />
            <Route path="/bank/:bankId/current-year" element={<ProtectedRoute permission="view_reports"><ReportPage type="current-year" /></ProtectedRoute>} />
            <Route path="/bank/:bankId/previous-year" element={<ProtectedRoute permission="view_reports"><ReportPage type="previous-year" /></ProtectedRoute>} />
            <Route path="/bank/:bankId/accrued-interest" element={<ProtectedRoute permission="view_reports"><AccruedInterestPage /></ProtectedRoute>} />
            <Route path="/bank/:bankId/reconciliation" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports"]}><BankReconciliationPage /></ProtectedRoute>} />
            <Route path="/bank/:bankId/statements" element={<ProtectedRoute permission="view_reports"><StatementsPage /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
      <Toaster richColors position="top-center" />
    </div>
  );
}

export default App;
