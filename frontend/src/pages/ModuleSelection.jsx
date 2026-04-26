import { Link } from "react-router-dom";
import { Building2, Landmark, LogOut, ShieldCheck, WalletCards } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";

export default function ModuleSelection() {
  const { user, logout } = useAuth();
  const canUseDeposits = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports;
  const canUseReconciliation = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.view_reports;

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
            <Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="module-selection-logout-button"><LogOut className="h-4 w-4" /> خروج</Button>
          </div>
        </div>
      </header>

      <section className="mx-auto grid min-h-[calc(100vh-88px)] max-w-7xl grid-cols-1 items-center gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[0.85fr_1.15fr] lg:px-8" data-testid="module-selection-content">
        <div className="space-y-5" data-testid="module-selection-intro">
          <Badge className="border-emerald-200 bg-emerald-50 px-3 py-1 text-emerald-700 hover:bg-emerald-50" data-testid="module-selection-badge">نظام بنكي منفصل ومنظم</Badge>
          <h2 className="text-4xl font-extrabold leading-tight sm:text-5xl lg:text-6xl" data-testid="module-selection-heading">كل جزء في مكانه: الودائع وحدها، والتسويات وحدها</h2>
          <p className="max-w-xl text-base font-semibold leading-8 text-slate-600 md:text-lg" data-testid="module-selection-description">
            اختار القسم المطلوب أولًا، ثم اختار البنك لتفتح الصفحات الخاصة بهذا القسم فقط بدون خلط بين الودائع والتسويات.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2" data-testid="module-cards-grid">
          {modules.map((module) => {
            const Icon = module.icon;
            return (
              <Link key={module.path} to={module.path} className="group rounded-2xl border border-slate-200 bg-white p-7 shadow-sm transition-[transform,box-shadow,background-color] hover:-translate-y-1 hover:bg-slate-50 hover:shadow-xl" data-testid={module.testId}>
                <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid={`${module.testId}-icon`}><Icon className="h-7 w-7" /></div>
                <h3 className="text-3xl font-extrabold text-slate-950" data-testid={`${module.testId}-title`}>{module.title}</h3>
                <p className="mt-4 min-h-20 text-base font-semibold leading-8 text-slate-600" data-testid={`${module.testId}-description`}>{module.description}</p>
                <div className="mt-6 text-sm font-extrabold text-emerald-700 transition-transform group-hover:-translate-x-1" data-testid={`${module.testId}-action`}>اختيار القسم ←</div>
              </Link>
            );
          })}
        </div>
      </section>
      <footer className="px-4 pb-5" data-testid="module-selection-footer"><CreditLine testId="module-selection-creator-credit" /></footer>
    </main>
  );
}
