import { Link, NavLink, useLocation, useParams } from "react-router-dom";
import { ArrowRightLeft, ClipboardPenLine, FileClock, FileSpreadsheet, FileText, Home, Landmark, LogOut, ReceiptText, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { bankPalette, fallbackBanks } from "@/lib/banks";
import { useAuth } from "@/contexts/AuthContext";
import { BankLogo } from "@/components/BankLogo";
import { CreditLine } from "@/components/CreditLine";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

export const BankShell = ({ children }) => {
  const { bankId } = useParams();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [banks, setBanks] = useState(fallbackBanks);
  useEffect(() => {
    api.get("/banks").then((response) => setBanks(response.data)).catch(() => setBanks(fallbackBanks));
  }, []);
  const bank = banks.find((item) => item.id === bankId) || fallbackBanks.find((item) => item.id === bankId) || fallbackBanks[0];
  const palette = bankPalette[bank.id] || bankPalette["industrial-development"];
  const canViewReports = user?.role === "admin" || user?.permissions?.view_reports;
  const canEnterDeposits = user?.role === "admin" || user?.permissions?.enter_deposits;
  const isReconciliationModule = location.pathname.includes("/reconciliation");
  const moduleBankSelectionPath = isReconciliationModule ? "/reconciliations" : "/deposits";

  const depositNavItems = [
    canEnterDeposits && { label: "تسجيل وديعة", path: "register", icon: ClipboardPenLine, testId: "nav-register-link" },
    canViewReports && { label: "عائد السنة الحالية", path: "current-year", icon: FileText, testId: "nav-current-report-link" },
    canViewReports && { label: "عائد السنة السابقة", path: "previous-year", icon: FileClock, testId: "nav-previous-report-link" },
    canViewReports && { label: "تقرير المستحقات", path: "accrued-interest", icon: ReceiptText, testId: "nav-accrued-report-link" },
    canViewReports && { label: "الكشوف التفريغية", path: "statements", icon: FileSpreadsheet, testId: "nav-statements-link" },
  ].filter(Boolean);
  const reconciliationNavItems = [
    (canViewReports || canEnterDeposits) && { label: "التسوية البنكية", path: "reconciliation", icon: Landmark, testId: "nav-reconciliation-link" },
  ].filter(Boolean);
  const navItems = isReconciliationModule ? reconciliationNavItems : depositNavItems;

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900" data-testid="bank-shell">
      <div className="fixed inset-0 pointer-events-none opacity-[0.05] bg-[linear-gradient(135deg,#0f172a_1px,transparent_1px),linear-gradient(45deg,#059669_1px,transparent_1px)] bg-[size:38px_38px]" />
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/85 backdrop-blur-xl" data-testid="bank-header">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-4">
            <BankLogo bankId={bank.id} bankName={bank.name} logoUrl={bank.logo_url} className={`h-14 w-24 ${palette.ring} ring-2`} testId="bank-logo-mark" />
            <div>
              <p className="text-xs font-bold text-slate-500" data-testid="bank-code-label">{bank.code}</p>
              <h1 className="text-xl font-extrabold text-slate-950" data-testid="bank-name-heading">{bank.name}</h1>
            </div>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Badge className="w-fit border-emerald-200 bg-emerald-50 px-3 py-1 text-emerald-700 hover:bg-emerald-50" data-testid="bank-data-separation-badge">
              بيانات البنك منفصلة بالكامل
            </Badge>
            {user?.role === "admin" && (
              <Button asChild variant="outline" className="h-11 rounded-lg border-slate-300 bg-white px-5 text-slate-800" data-testid="admin-panel-button">
                <Link to="/secure-admin-control-panel"><ShieldCheck className="h-4 w-4" /> لوحة الأدمن</Link>
              </Button>
            )}
            <Button asChild variant="outline" className="h-11 rounded-lg border-slate-300 bg-white px-5 text-slate-800 transition-transform hover:-translate-y-0.5" data-testid="switch-bank-button">
              <Link to={moduleBankSelectionPath}><ArrowRightLeft className="h-4 w-4" /> تغيير البنك</Link>
            </Button>
            <Button asChild variant="outline" className="h-11 rounded-lg border-slate-300 bg-white px-5 text-slate-800" data-testid="module-home-button">
              <Link to="/"><Home className="h-4 w-4" /> القائمة الرئيسية</Link>
            </Button>
            <Button onClick={logout} variant="outline" className="h-11 rounded-lg border-slate-300 bg-white px-5 text-slate-800" data-testid="logout-button">
              <LogOut className="h-4 w-4" /> خروج
            </Button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-7xl gap-2 overflow-x-auto px-4 pb-4 sm:px-6 lg:px-8" data-testid="bank-sub-navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={`/bank/${bank.id}/${item.path}`}
                data-testid={item.testId}
                className={({ isActive }) =>
                  `inline-flex min-w-fit items-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-bold transition-[transform,background-color,color] hover:-translate-y-0.5 ${
                    isActive ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-100"
                  }`
                }
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
      </header>
      <section className="relative mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8" data-testid="bank-page-content">
        {children}
        <footer className="mt-10 border-t border-slate-200 pt-5" data-testid="bank-page-footer">
          <CreditLine testId="bank-page-creator-credit" />
        </footer>
      </section>
    </main>
  );
};
