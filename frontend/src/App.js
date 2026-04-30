import "@/App.css";
import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
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
import JournalEntriesPage from "@/pages/JournalEntriesPage";
import ChartAccountsPage from "@/pages/ChartAccountsPage";
import TrialBalancePage from "@/pages/TrialBalancePage";
import FixedAssetsPage from "@/pages/FixedAssetsPage";
import CustodyAdvancesPage from "@/pages/CustodyAdvancesPage";
import MembershipPage from "@/pages/MembershipPage";
import ElectronicInvoicePage from "@/pages/ElectronicInvoicePage";
import { isModuleEnabled } from "@/lib/modules";

const defaultAppTitle = "نظام محاسبي متكامل";

const buildSectionTitles = (appTitle) => [
  { test: (path) => path === "/", title: appTitle },
  { test: (path) => path === "/login", title: appTitle },
  { test: (path) => path === "/accounting", title: `الحسابات - ${appTitle}` },
  { test: (path) => path === "/membership", title: `العضوية - ${appTitle}` },
  { test: (path) => path === "/custody-advances", title: `العهد والسلف - ${appTitle}` },
  { test: (path) => path === "/deposits", title: `فوائد الودائع - ${appTitle}` },
  { test: (path) => path === "/reconciliations", title: `التسويات البنكية - ${appTitle}` },
  { test: (path) => path === "/revenues", title: `الإيرادات - ${appTitle}` },
  { test: (path) => path === "/expenses", title: `المصروفات - ${appTitle}` },
  { test: (path) => path === "/expenses-analysis", title: `تحليل المصروفات - ${appTitle}` },
  { test: (path) => path === "/banking-expenses", title: `المصروفات البنكية - ${appTitle}` },
  { test: (path) => path === "/ledger", title: `دفتر الأستاذ - ${appTitle}` },
  { test: (path) => path === "/fixed-assets", title: `الأصول الثابتة - ${appTitle}` },
  { test: (path) => path === "/chart-accounts", title: `شجرة الحسابات - ${appTitle}` },
  { test: (path) => path === "/trial-balance", title: `ميزان المراجعة - ${appTitle}` },
  { test: (path) => path === "/journal-entries", title: `القيود اليومية - ${appTitle}` },
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

function PrintOrganizationHeading() {
  const { user } = useAuth();
  const { settings } = useAppSettings();
  if (!user?.organization_name) return null;
  return (
    <div className="hidden print:block print:p-4 print:text-center print:font-bold" data-testid="print-organization-heading">
      <div>{user.organization_name}</div>
      <div>{settings.system_name}</div>
    </div>
  );
}

function ModuleRoute({ moduleKey, children }) {
  const { user } = useAuth();
  if (!isModuleEnabled(user, moduleKey)) return <Navigate to="/" replace />;
  return children;
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
            <PrintOrganizationHeading />
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/" element={<ProtectedRoute><ModuleSelection /></ProtectedRoute>} />
              <Route path="/accounting" element={<ProtectedRoute><ModuleSelection accountingOnly /></ProtectedRoute>} />
              <Route path="/membership" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_users"]}><ModuleRoute moduleKey="membership"><MembershipPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/custody-advances" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]}><ModuleRoute moduleKey="custody_advances"><CustodyAdvancesPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/deposits" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports"]}><ModuleRoute moduleKey="deposits"><BankSelection mode="deposits" /></ModuleRoute></ProtectedRoute>} />
              <Route path="/reconciliations" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_reconciliations"]}><ModuleRoute moduleKey="reconciliations"><BankSelection mode="reconciliations" /></ModuleRoute></ProtectedRoute>} />
              <Route path="/revenues" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_revenues"]}><ModuleRoute moduleKey="revenues"><RevenuesPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/expenses" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses"]}><ModuleRoute moduleKey="expenses"><ExpensesPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/expenses-analysis" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses"]}><ModuleRoute moduleKey="expenses_analysis"><ExpensesAnalysisPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/banking-expenses" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]}><ModuleRoute moduleKey="banking_expenses"><BankingExpensesPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/ledger" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]}><ModuleRoute moduleKey="ledger"><LedgerPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/fixed-assets" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]}><ModuleRoute moduleKey="fixed_assets"><FixedAssetsPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/chart-accounts" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]}><ModuleRoute moduleKey="chart_accounts"><ChartAccountsPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/trial-balance" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]}><ModuleRoute moduleKey="trial_balance"><TrialBalancePage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/journal-entries" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]}><ModuleRoute moduleKey="journal_entries"><JournalEntriesPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/electronic-invoice" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_revenues"]}><ModuleRoute moduleKey="electronic_invoice"><ElectronicInvoicePage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/secure-admin-control-panel" element={<ProtectedRoute adminOnly><AdminPage /></ProtectedRoute>} />
              <Route path="/bank/:bankId/register" element={<ProtectedRoute permission="enter_deposits"><ModuleRoute moduleKey="deposits"><DepositRegistration /></ModuleRoute></ProtectedRoute>} />
              <Route path="/bank/:bankId/current-year" element={<ProtectedRoute permission="view_reports"><ModuleRoute moduleKey="deposits"><ReportPage type="current-year" /></ModuleRoute></ProtectedRoute>} />
              <Route path="/bank/:bankId/previous-year" element={<ProtectedRoute permission="view_reports"><ModuleRoute moduleKey="deposits"><ReportPage type="previous-year" /></ModuleRoute></ProtectedRoute>} />
              <Route path="/bank/:bankId/accrued-interest" element={<ProtectedRoute permission="view_reports"><ModuleRoute moduleKey="deposits"><AccruedInterestPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/bank/:bankId/reconciliation" element={<ProtectedRoute anyPermissions={["enter_deposits", "view_reports", "manage_reconciliations"]}><ModuleRoute moduleKey="reconciliations"><BankReconciliationPage /></ModuleRoute></ProtectedRoute>} />
              <Route path="/bank/:bankId/statements" element={<ProtectedRoute permission="view_reports"><ModuleRoute moduleKey="deposits"><StatementsPage /></ModuleRoute></ProtectedRoute>} />
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
