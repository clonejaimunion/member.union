import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Banknote, BarChart3, Building2, Landmark, LogOut, ReceiptText, SendToBack, ShieldCheck, WalletCards } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";

export default function ModuleSelection() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const canUseDeposits = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports;
  const canUseReconciliation = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_reconciliations;
  const canUseRevenues = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_revenues;
  const canUseExpenses = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_expenses;
  const canUseBankingExpenses = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports || user?.permissions?.manage_expenses || user?.permissions?.manage_revenues;

  const modules = [
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
    canUseRevenues && {
      title: "الإيرادات",
      description: "تسجيل الإيرادات، طرق التحصيل، البحث، التقرير، وطباعة PDF.",
      path: "/revenues",
      icon: ReceiptText,
      testId: "module-revenues-card",
    },
    canUseExpenses && {
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
  ].filter(Boolean);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="module-selection-page">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur" data-testid="module-selection-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-5 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="module-selection-brand">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="module-selection-brand-icon"><Building2 className="h-5 w-5" /></div>
            <div>
              <p className="text-xs font-extrabold text-emerald-700" data-testid="module-selection-eyebrow">القائمة الرئيسية</p>
              <h1 className="text-2xl font-extrabold" data-testid="module-selection-title">اختر نوع العمل</h1>
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
          <Badge className="border-emerald-200 bg-emerald-50 px-3 py-1 text-emerald-700 hover:bg-emerald-50" data-testid="module-selection-badge">نظام بنكي منفصل ومنظم</Badge>
          <h2 className="text-4xl font-extrabold leading-tight sm:text-5xl lg:text-6xl" data-testid="module-selection-heading">اختر القسم المطلوب</h2>
          <p className="mx-auto max-w-2xl text-base font-semibold leading-8 text-slate-600 md:text-lg" data-testid="module-selection-description">
            كل قسم مستقل وواضح للوصول السريع بدون تزاحم في العرض.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6" data-testid="module-cards-grid">
          {modules.map((module) => {
            const Icon = module.icon;
            return (
              <Link key={module.path} to={module.path} className="group flex aspect-square min-h-56 flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm transition-[transform,box-shadow,background-color,border-color] hover:-translate-y-1 hover:border-slate-300 hover:bg-slate-50 hover:shadow-xl" data-testid={module.testId}>
                <div className="mb-5 flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-sm transition-transform group-hover:scale-105" data-testid={`${module.testId}-icon`}><Icon className="h-9 w-9" /></div>
                <h3 className="flex min-h-16 items-center justify-center text-balance text-2xl font-extrabold leading-snug text-slate-950" data-testid={`${module.testId}-title`}>{module.title}</h3>
                <p className="sr-only" data-testid={`${module.testId}-description`}>{module.description}</p>
                <div className="mt-5 text-sm font-extrabold text-emerald-700 transition-transform group-hover:-translate-x-1" data-testid={`${module.testId}-action`}>اختيار القسم ←</div>
              </Link>
            );
          })}
        </div>
      </section>
      <footer className="px-4 pb-5" data-testid="module-selection-footer"><CreditLine testId="module-selection-creator-credit" /></footer>
    </main>
  );
}
