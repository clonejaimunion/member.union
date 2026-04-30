import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Banknote, BarChart3, BookOpenText, Building2, FileCheck2, GitFork, HandCoins, Landmark, LogOut, NotebookPen, PackageCheck, ReceiptText, Scale, SendToBack, ShieldCheck, UsersRound, WalletCards } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { useAppSettings } from "@/contexts/AppSettingsContext";
import { isModuleEnabled } from "@/lib/modules";

export default function ModuleSelection({ accountingOnly = false }) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { settings } = useAppSettings();
  const organizationName = user?.organization_name || settings.system_name;
  const canUseDeposits = isModuleEnabled(user, "deposits") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports);
  const canUseChartAccounts = isModuleEnabled(user, "chart_accounts") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_expenses || user?.permissions?.manage_revenues);
  const canUseTrialBalance = isModuleEnabled(user, "trial_balance") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_expenses || user?.permissions?.manage_revenues);
  const canUseJournalEntries = isModuleEnabled(user, "journal_entries") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_expenses || user?.permissions?.manage_revenues);
  const canUseReconciliation = isModuleEnabled(user, "reconciliations") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_reconciliations);
  const canUseRevenues = isModuleEnabled(user, "revenues") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_revenues);
  const canUseExpenses = isModuleEnabled(user, "expenses") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_expenses);
  const canUseExpensesAnalysis = isModuleEnabled(user, "expenses_analysis") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_expenses);
  const canUseBankingExpenses = isModuleEnabled(user, "banking_expenses") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_expenses || user?.permissions?.manage_revenues);
  const canUseLedger = isModuleEnabled(user, "ledger") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_expenses || user?.permissions?.manage_revenues);
  const canUseElectronicInvoice = isModuleEnabled(user, "electronic_invoice") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_revenues);
  const canUseFixedAssets = isModuleEnabled(user, "fixed_assets") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_expenses || user?.permissions?.manage_revenues);
  const canUseCustodyAdvances = isModuleEnabled(user, "custody_advances") && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_expenses || user?.permissions?.manage_revenues);
  const canUseMembership = isModuleEnabled(user, "membership") && user?.organization_id === "social-solidarity" && (user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_users);
  const showSocialHub = user?.organization_id === "social-solidarity" && !accountingOnly;

  const hubModules = [
    {
      title: "الحسابات",
      description: "كل ما يخص الحسابات داخل قسم مستقل.",
      path: "/accounting",
      icon: BookOpenText,
      testId: "module-accounting-hub-card",
    },
    canUseMembership && {
      title: "العضوية",
      description: "تسجيل وبحث وتصفية عضوية مشروع التكافل الاجتماعي.",
      path: "/membership",
      icon: UsersRound,
      testId: "module-membership-card",
    },
  ].filter(Boolean);

  const accountingModules = [
    canUseFixedAssets && {
      title: "الأصول الثابتة",
      description: "تسجيل الأصول، حساب الإهلاك تلقائياً، وربطه بالقيود اليومية.",
      path: "/fixed-assets",
      icon: PackageCheck,
      testId: "module-fixed-assets-card",
    },
    canUseCustodyAdvances && {
      title: "العهد والسلف",
      description: "صرف عهد وسلف وتسويتها بقيود يومية تلقائية.",
      path: "/custody-advances",
      icon: HandCoins,
      testId: "module-custody-advances-card",
    },
    canUseChartAccounts && {
      title: "شجرة الحسابات",
      description: "حسابات تلقائية لكل جهة وربط مباشر مع القيود اليومية.",
      path: "/chart-accounts",
      icon: GitFork,
      testId: "module-chart-accounts-card",
    },
    canUseDeposits && {
      title: "فوائد الودائع",
      description: "تسجيل الودائع، تقارير العائد الشهري، المستحقات، والكشوف التفريغية.",
      path: "/deposits",
      icon: WalletCards,
      testId: "module-deposits-card",
    },
    canUseReconciliation && {
      title: "التسويات البنكية",
      description: "مذكرات تسوية حسابات البنوك، الشيكات، المطابقة، وطباعة PDF.",
      path: "/reconciliations",
      icon: Landmark,
      testId: "module-reconciliations-card",
    },
    canUseJournalEntries && {
      title: "القيود اليومية",
      description: "عرض القيود التلقائية وإضافة قيود يدوية مع ترقيم تسلسلي لكل جهة.",
      path: "/journal-entries",
      icon: NotebookPen,
      testId: "module-journal-entries-card",
    },
    canUseTrialBalance && {
      title: "ميزان المراجعة",
      description: "تقرير تلقائي بالمجاميع والأرصدة من القيود اليومية وشجرة الحسابات.",
      path: "/trial-balance",
      icon: Scale,
      testId: "module-trial-balance-card",
    },
    canUseRevenues && {
      title: "الإيرادات",
      description: "تسجيل الإيرادات، طرق التحصيل، البحث، التقرير، وطباعة PDF.",
      path: "/revenues",
      icon: ReceiptText,
      testId: "module-revenues-card",
    },
    canUseExpensesAnalysis && {
      title: "المصروفات",
      description: "أذون الصرف، الاستحقاقات، الاستقطاعات، الصافي، والتقرير.",
      path: "/expenses",
      icon: SendToBack,
      testId: "module-expenses-card",
    },
    canUseExpenses && {
      title: "تحليل المصروفات",
      description: "تحليل شهري وسنوي لبنود المصروفات حسب الجهة المسجلة.",
      path: "/expenses-analysis",
      icon: BarChart3,
      testId: "module-expenses-analysis-card",
    },
    canUseBankingExpenses && {
      title: "المصروفات البنكية",
      description: "حساب رسوم وعمولات البنك من الإيرادات والمصروفات المسجلة.",
      path: "/banking-expenses",
      icon: Banknote,
      testId: "module-banking-expenses-card",
    },
    canUseLedger && {
      title: "دفتر الأستاذ",
      description: "تجميع محاسبي للحركات المدينة والدائنة والرصيد المتراكم.",
      path: "/ledger",
      icon: BookOpenText,
      testId: "module-ledger-card",
    },
    canUseElectronicInvoice && {
      title: "الفاتورة الإلكترونية",
      description: "توليد فواتير إلكترونية تلقائياً من الإيرادات المحصلة.",
      path: "/electronic-invoice",
      icon: FileCheck2,
      testId: "module-electronic-invoice-card",
    },
  ].filter(Boolean);

  const modules = showSocialHub ? hubModules : accountingModules;

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="module-selection-page">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur" data-testid="module-selection-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-5 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="module-selection-brand">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="module-selection-brand-icon"><Building2 className="h-5 w-5" /></div>
            <div>
              <p className="text-xs font-extrabold text-emerald-700" data-testid="module-selection-eyebrow">{accountingOnly ? "الحسابات" : "الصفحة الرئيسية"}</p>
              <h1 className="text-2xl font-extrabold" data-testid="module-selection-title">{organizationName}</h1>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3" data-testid="module-selection-actions">
            <Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="module-selection-user-badge">{user?.username}</Badge>
            {user?.role === "admin" && (
              <Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="module-selection-admin-button">
                <Link to="/secure-admin-control-panel"><ShieldCheck className="h-4 w-4" /> لوحة الأدمن</Link>
              </Button>
            )}
            <Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="module-selection-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button>
            <Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="module-selection-logout-button"><LogOut className="h-4 w-4" /> خروج</Button>
          </div>
        </div>
      </header>

      <section className="mx-auto flex min-h-[calc(100vh-88px)] max-w-7xl flex-col justify-center gap-10 px-4 py-10 sm:px-6 lg:px-8" data-testid="module-selection-content">
        <div className="mx-auto max-w-4xl space-y-5 text-center" data-testid="module-selection-intro">
          <h2 className="text-4xl font-extrabold leading-tight sm:text-5xl lg:text-6xl" data-testid="module-selection-heading">{accountingOnly ? "الحسابات" : settings.system_name}</h2>
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6" data-testid="module-cards-grid">
          {modules.map((module) => {
            const Icon = module.icon;
            return (
              <Link key={module.path} to={module.path} className="group flex aspect-square min-h-56 flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm transition-[transform,box-shadow,background-color,border-color] hover:-translate-y-1 hover:border-slate-300 hover:bg-slate-50 hover:shadow-xl" data-testid={module.testId}>
                <div className="mb-5 flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-sm transition-transform group-hover:scale-105" data-testid={`${module.testId}-icon`}><Icon className="h-9 w-9" /></div>
                <h3 className="flex min-h-16 items-center justify-center text-balance text-2xl font-extrabold leading-snug text-slate-950" data-testid={`${module.testId}-title`}>{module.title}</h3>
                <p className="sr-only" data-testid={`${module.testId}-description`}>{module.description}</p>
                <span className="sr-only" data-testid={`${module.testId}-action`}>{module.title}</span>
              </Link>
            );
          })}
        </div>
      </section>
      <footer className="px-4 pb-5" data-testid="module-selection-footer"><CreditLine testId="module-selection-creator-credit" /></footer>
    </main>
  );
}
