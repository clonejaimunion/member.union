import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Home, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BankLogo } from "@/components/BankLogo";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { bankPalette, fallbackBanks } from "@/lib/banks";

const heroImage = "https://static.prod-images.emergentagent.com/jobs/4f04fbc5-156c-472b-951d-b7c652b3b7cc/images/36a05283766e2e65b334ee079225dde8ffc0c070fd433ac61be8d002f145fac0.png";

export default function BankSelection({ mode = "deposits" }) {
  const { user, logout } = useAuth();
  const [banks, setBanks] = useState(fallbackBanks);
  const isReconciliation = mode === "reconciliations";
  const canEnterDeposits = user?.role === "admin" || user?.permissions?.enter_deposits;

  const bankPath = (bankId) => {
    if (isReconciliation) return `/bank/${bankId}/reconciliation`;
    return canEnterDeposits ? `/bank/${bankId}/register` : `/bank/${bankId}/current-year`;
  };

  useEffect(() => {
    api.get("/banks").then((response) => setBanks(response.data)).catch(() => setBanks(fallbackBanks));
  }, []);

  const deleteBank = async (bank, event) => {
    event.preventDefault();
    event.stopPropagation();
    const confirmed = window.confirm(`هل أنت متأكد من حذف ${bank.name}؟ سيتم حذف كل الودائع والتسويات الخاصة بهذا البنك بالكامل.`);
    if (!confirmed) return;
    try {
      await api.delete(`/admin/banks/${bank.id}`);
      toast.success("تم حذف البنك وكل بياناته");
      setBanks((current) => current.filter((item) => item.id !== bank.id));
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حذف البنك");
    }
  };

  return (
    <main className="min-h-screen overflow-hidden bg-slate-50 text-slate-950" data-testid="bank-selection-page">
      <header className="absolute left-0 right-0 top-0 z-20" data-testid="bank-selection-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-5 sm:px-6 lg:px-8">
          <Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="bank-selection-user-badge">{user?.username}</Badge>
          <div className="flex flex-wrap gap-3" data-testid="bank-selection-actions">
            {user?.role === "admin" && (
              <Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="bank-selection-admin-button"><Link to="/secure-admin-control-panel">لوحة الأدمن</Link></Button>
            )}
            <Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="bank-selection-modules-button"><Link to="/"><Home className="h-4 w-4" /> القائمة الرئيسية</Link></Button>
            <Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="bank-selection-logout-button">خروج</Button>
          </div>
        </div>
      </header>
      <section className="relative mx-auto grid min-h-screen max-w-7xl grid-cols-1 items-center gap-10 px-4 py-8 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8" data-testid="bank-selection-hero-section">
        <div className="absolute inset-0 -z-10 bg-[linear-gradient(135deg,rgba(15,23,42,0.08)_1px,transparent_1px)] bg-[size:30px_30px]" />
        <div className="order-2 space-y-8 lg:order-1" data-testid="bank-selection-content">
          <Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="bank-system-badge">
            <ShieldCheck className="ml-1 h-4 w-4 text-emerald-600" /> {isReconciliation ? "قسم التسويات البنكية" : "قسم فوائد الودائع"}
          </Badge>
          <div className="space-y-4">
            <h1 className="max-w-3xl text-4xl font-extrabold leading-tight text-slate-950 sm:text-5xl lg:text-6xl" data-testid="bank-selection-title">
              {isReconciliation ? "اختر البنك وابدأ مذكرة التسوية البنكية" : "اختر البنك وابدأ إدارة عوائد الودائع بدقة"}
            </h1>
            <p className="max-w-2xl text-base font-semibold leading-8 text-slate-600 md:text-lg" data-testid="bank-selection-subtitle">
              {isReconciliation ? "كل بنك له مذكرات تسوية منفصلة تشمل الشيكات والمطابقة والطباعة." : "كل بنك له بياناته وتقاريره المستقلة، مع تسجيل الوديعة واستخراج عائد السنة الحالية والسابقة والفوائد المستحقة بشكل منظم."}
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="bank-cards-grid">
            {banks.map((bank) => {
              const palette = bankPalette[bank.id] || bankPalette["industrial-development"];
              return (
                <div
                  key={bank.id}
                  data-testid={`bank-card-${bank.id}`}
                  className="group rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-[transform,box-shadow,background-color] hover:-translate-y-1 hover:bg-slate-50 hover:shadow-lg focus:outline-none focus:ring-4 focus:ring-emerald-100"
                >
                  <Link to={bankPath(bank.id)} className="block" data-testid={`bank-card-${bank.id}-open-link`}>
                    <BankLogo bankId={bank.id} bankName={bank.name} logoUrl={bank.logo_url} className={`mb-5 h-16 w-28 ${palette.ring} ring-2`} testId={`bank-card-${bank.id}-logo`} />
                    <p className="text-xs font-extrabold text-slate-500" data-testid={`bank-card-${bank.id}-code`}>{bank.code}</p>
                    <p className="mt-1 text-xs font-extrabold text-slate-500" data-testid={`bank-card-${bank.id}-swift-code`}>SWIFT CODE: {bank.swift_code || "غير مسجل"}</p>
                    <h2 className="mt-2 min-h-14 text-xl font-extrabold leading-7 text-slate-950" data-testid={`bank-card-${bank.id}-name`}>{bank.name}</h2>
                    <div className="mt-5 inline-flex items-center gap-2 text-sm font-extrabold text-emerald-700" data-testid={`bank-card-${bank.id}-action-text`}>
                      {isReconciliation ? "فتح تسوية البنك" : "فتح ملف البنك"} <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
                    </div>
                  </Link>
                  {user?.role === "admin" && (
                    <button
                      type="button"
                      onClick={(event) => deleteBank(bank, event)}
                      className="mt-5 inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 text-sm font-extrabold text-red-700 transition-colors hover:bg-red-100"
                      data-testid={`delete-bank-button-${bank.id}`}
                    >
                      <Trash2 className="h-4 w-4" /> حذف البنك بالكامل
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        <div className="order-1 lg:order-2" data-testid="bank-selection-image-panel">
          <div className="relative mx-auto aspect-[1.05/1] w-full max-w-xl overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-2xl shadow-slate-200">
            <img src={heroImage} alt="خزينة وبطاقات بنكية" className="h-full w-full object-cover" data-testid="bank-selection-hero-image" />
          </div>
          <Button asChild className="mt-6 h-12 rounded-lg bg-slate-950 px-7 text-white hover:bg-slate-800 md:hidden" data-testid="mobile-start-button">
            <Link to={bankPath(banks[0]?.id || "industrial-development")}>ابدأ الآن</Link>
          </Button>
        </div>
        <div className="absolute bottom-4 left-4 right-4" data-testid="bank-selection-footer-credit">
          <CreditLine className="text-center text-xs font-bold text-slate-500" testId="bank-selection-creator-credit" />
        </div>
      </section>
    </main>
  );
}
