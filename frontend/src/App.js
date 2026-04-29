import "@/App.css";
import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/contexts/AuthContext";
import { AppSettingsProvider, useAppSettings } from "@/contexts/AppSettingsContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { applyEasternArabicNumeralsToDocument } from "@/lib/format";
import BankSelection from "@/pages/BankSelection";
import DepositRegistration from "@/pages/DepositRegistration";
import ReportPage from "@/pages/ReportPage";
import LoginPage from "@/pages/LoginPage";
import AdminPage from "@/pages/AdminPage";
import StatementsPage from "@/pages/StatementsPage";
import AccruedInterestPage from "@/pages/AccruedInterestPage";
import BankReconciliationPage from "@/pages/BankReconciliationPage";
import ModuleSelection from "@/pages/ModuleSelection";
import RevenuesPage from "@/pages/RevenuesPage";
import ExpensesPage from "@/pages/ExpensesPage";
import ExpensesAnalysisPage from "@/pages/ExpensesAnalysisPage";
import BankingExpensesPage from "@/pages/BankingExpensesPage";
import LedgerPage from "@/pages/LedgerPage";
import ElectronicInvoicePage from "@/pages/ElectronicInvoicePage";

const defaultAppTitle = "نظام محاسبي متكامل";

const buildSectionTitles = (appTitle) => [
  { test: (path) => path === "/", title: appTitle },
  { test: (path) => path === "/login", title: appTitle },
  { test: (path) => path === "/deposits", title: `فوائد الودائع - ${appTitle}` },
  { test: (path) => path === "/reconciliations", title: `التسويات البنكية - ${appTitle}` },
  { test: (path) => path === "/revenues", title: `الإيرادات - ${appTitle}` },
  { test: (path) => path === "/expenses", title: `المصروفات - ${appTitle}` },
  { test: (path) => path === "/expenses-analysis", title: `تحليل المصروفات - ${appTitle}` },
  { test: (path) => path === "/banking-expenses", title: `المصروفات البنكية - ${appTitle}` },
  { test: (path) => path === "/ledger", title: `دفتر الأستاذ - ${appTitle}` },
  { test: (path) => path === "/electronic-invoice", title: `الفاتورة الإلكترونية - ${appTitle}` },
  { test: (path) => path === "/secure-admin-control-panel", title: `لوحة الأدمن - ${appTitle}` },
  { test: (path) => path.endsWith("/register"), title: `تسجيل الودائع - ${appTitle}` },
  { test: (path) => path.endsWith("/current-year"), title: `تقرير السنة الحالية - ${appTitle}` },
  { test: (path) => path.endsWith("/previous-year"), title: `تقرير السنوات السابقة - ${appTitle}` },
  { test: (path) => path.endsWith("/accrued-interest"), title: `المستحقات السنوية - ${appTitle}` },
  { test: (path) => path.endsWith("/reconciliation"), title: `مذكرة التسوية البنكية - ${appTitle}` },
  { test: (path) => path.endsWith("/statements"), title: `الكشوف التفريغية - ${appTitle}` },
];

function PageTitleManager() {
  const location = useLocation();
  const { settings } = useAppSettings();
  const appTitle = settings.system_name || defaultAppTitle;

  useEffect(() => {
    const sectionTitles = buildSectionTitles(appTitle);
    const matched = sectionTitles.find((item) => item.test(location.pathname));
    document.title = matched?.title || appTitle;
  }, [location.pathname, appTitle]);

  return null;
}

function App() {
  useEffect(() => {
    document.documentElement.setAttribute("dir", "rtl");
    document.documentElement.setAttribute("lang", "ar");
    return applyEasternArabicNumeralsToDocument();
  }, []);

  return (
    <div className="App" dir="rtl" data-testid="app-root">
      <AppSettingsProvider>
        <AuthProvider>
          <BrowserRouter>
            <PageTitleManager />
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/" element={<ProtectedRoute><ModuleSelection /></ProtectedRoute>} />
              <Route path="/deposits" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports"]}><BankSelection mode="deposits" /></ProtectedRoute>} />
              <Route path="/reconciliations" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_reconciliations"]}><BankSelection mode="reconciliations" /></ProtectedRoute>} />
              <Route path="/revenues" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_revenues"]}><RevenuesPage /></ProtectedRoute>} />
              <Route path="/expenses" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses"]}><ExpensesPage /></ProtectedRoute>} />
              <Route path="/expenses-analysis" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses"]}><ExpensesAnalysisPage /></ProtectedRoute>} />
              <Route path="/banking-expenses" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]}><BankingExpensesPage /></ProtectedRoute>} />
              <Route path="/ledger" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]}><LedgerPage /></ProtectedRoute>} />
              <Route path="/electronic-invoice" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_revenues"]}><ElectronicInvoicePage /></ProtectedRoute>} />
              <Route path="/secure-admin-control-panel" element={<ProtectedRoute adminOnly><AdminPage /></ProtectedRoute>} />
              <Route path="/bank/:bankId/register" element={<ProtectedRoute permission="enter_deposits"><DepositRegistration /></ProtectedRoute>} />
              <Route path="/bank/:bankId/current-year" element={<ProtectedRoute permission="view_reports"><ReportPage type="current-year" /></ProtectedRoute>} />
              <Route path="/bank/:bankId/previous-year" element={<ProtectedRoute permission="view_reports"><ReportPage type="previous-year" /></ProtectedRoute>} />
              <Route path="/bank/:bankId/accrued-interest" element={<ProtectedRoute permission="view_reports"><AccruedInterestPage /></ProtectedRoute>} />
              <Route path="/bank/:bankId/reconciliation" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_reconciliations"]}><BankReconciliationPage /></ProtectedRoute>} />
              <Route path="/bank/:bankId/statements" element={<ProtectedRoute permission="view_reports"><StatementsPage /></ProtectedRoute>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </AppSettingsProvider>
      <Toaster richColors position="top-center" />
    </div>
  );
}

export default App;
