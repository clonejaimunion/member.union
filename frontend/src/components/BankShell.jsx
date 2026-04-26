import { Link, NavLink, useParams } from "react-router-dom";
import { ArrowRightLeft, Building2, ClipboardPenLine, FileClock, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { bankPalette, fallbackBanks } from "@/lib/banks";

export const BankShell = ({ children }) => {
  const { bankId } = useParams();
  const bank = fallbackBanks.find((item) => item.id === bankId) || fallbackBanks[0];
  const palette = bankPalette[bank.id] || bankPalette["industrial-development"];

  const navItems = [
    { label: "تسجيل وديعة", path: "register", icon: ClipboardPenLine, testId: "nav-register-link" },
    { label: "عائد السنة الحالية", path: "current-year", icon: FileText, testId: "nav-current-report-link" },
    { label: "عائد السنة السابقة", path: "previous-year", icon: FileClock, testId: "nav-previous-report-link" },
  ];

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900" data-testid="bank-shell">
      <div className="fixed inset-0 pointer-events-none opacity-[0.05] bg-[linear-gradient(135deg,#0f172a_1px,transparent_1px),linear-gradient(45deg,#059669_1px,transparent_1px)] bg-[size:38px_38px]" />
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/85 backdrop-blur-xl" data-testid="bank-header">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-4">
            <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${palette.tone} shadow-sm`} data-testid="bank-logo-mark">
              <Building2 className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs font-bold text-slate-500" data-testid="bank-code-label">{bank.code}</p>
              <h1 className="text-xl font-extrabold text-slate-950" data-testid="bank-name-heading">{bank.name}</h1>
            </div>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Badge className="w-fit border-emerald-200 bg-emerald-50 px-3 py-1 text-emerald-700 hover:bg-emerald-50" data-testid="bank-data-separation-badge">
              بيانات البنك منفصلة بالكامل
            </Badge>
            <Button asChild variant="outline" className="h-11 rounded-lg border-slate-300 bg-white px-5 text-slate-800 transition-transform hover:-translate-y-0.5" data-testid="switch-bank-button">
              <Link to="/"><ArrowRightLeft className="h-4 w-4" /> تغيير البنك</Link>
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
      </section>
    </main>
  );
};
