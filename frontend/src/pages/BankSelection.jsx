import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, BadgeCheck, Building2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { bankPalette, fallbackBanks } from "@/lib/banks";

const heroImage = "https://static.prod-images.emergentagent.com/jobs/4f04fbc5-156c-472b-951d-b7c652b3b7cc/images/36a05283766e2e65b334ee079225dde8ffc0c070fd433ac61be8d002f145fac0.png";

export default function BankSelection() {
  const { user, logout } = useAuth();
  const [banks, setBanks] = useState(fallbackBanks);

  useEffect(() => {
    api.get("/banks").then((response) => setBanks(response.data)).catch(() => setBanks(fallbackBanks));
  }, []);

  return (
    <main className="min-h-screen overflow-hidden bg-slate-50 text-slate-950" data-testid="bank-selection-page">
      <header className="absolute left-0 right-0 top-0 z-20" data-testid="bank-selection-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-5 sm:px-6 lg:px-8">
          <Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="bank-selection-user-badge">{user?.username}</Badge>
          <div className="flex flex-wrap gap-3" data-testid="bank-selection-actions">
            {user?.role === "admin" && (
              <Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="bank-selection-admin-button"><Link to="/secure-admin-control-panel">لوحة الأدمن</Link></Button>
            )}
            <Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="bank-selection-logout-button">خروج</Button>
          </div>
        </div>
      </header>
      <section className="relative mx-auto grid min-h-screen max-w-7xl grid-cols-1 items-center gap-10 px-4 py-8 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8" data-testid="bank-selection-hero-section">
        <div className="absolute inset-0 -z-10 bg-[linear-gradient(135deg,rgba(15,23,42,0.08)_1px,transparent_1px)] bg-[size:30px_30px]" />
        <div className="order-2 space-y-8 lg:order-1" data-testid="bank-selection-content">
          <Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="bank-system-badge">
            <ShieldCheck className="ml-1 h-4 w-4 text-emerald-600" /> نظام عوائد الودائع البنكية
          </Badge>
          <div className="space-y-4">
            <h1 className="max-w-3xl text-4xl font-extrabold leading-tight text-slate-950 sm:text-5xl lg:text-6xl" data-testid="bank-selection-title">
              اختر البنك وابدأ إدارة عوائد الودائع بدقة
            </h1>
            <p className="max-w-2xl text-base font-semibold leading-8 text-slate-600 md:text-lg" data-testid="bank-selection-subtitle">
              كل بنك له بياناته وتقاريره المستقلة، مع تسجيل الوديعة واستخراج عائد السنة الحالية والسابقة بشكل منظم.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="bank-cards-grid">
            {banks.map((bank) => {
              const palette = bankPalette[bank.id] || bankPalette["industrial-development"];
              return (
                <Link
                  key={bank.id}
                  to={`/bank/${bank.id}/register`}
                  data-testid={`bank-card-${bank.id}`}
                  className="group rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-[transform,box-shadow,background-color] hover:-translate-y-1 hover:bg-slate-50 hover:shadow-lg focus:outline-none focus:ring-4 focus:ring-emerald-100"
                >
                  <div className={`mb-5 flex h-12 w-12 items-center justify-center rounded-lg ${palette.tone}`} data-testid={`bank-card-${bank.id}-icon`}>
                    <Building2 className="h-6 w-6" />
                  </div>
                  <p className="text-xs font-extrabold text-slate-500" data-testid={`bank-card-${bank.id}-code`}>{bank.code}</p>
                  <h2 className="mt-2 min-h-14 text-xl font-extrabold leading-7 text-slate-950" data-testid={`bank-card-${bank.id}-name`}>{bank.name}</h2>
                  <div className="mt-5 inline-flex items-center gap-2 text-sm font-extrabold text-emerald-700" data-testid={`bank-card-${bank.id}-action-text`}>
                    فتح ملف البنك <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
        <div className="order-1 lg:order-2" data-testid="bank-selection-image-panel">
          <div className="relative mx-auto aspect-[1.05/1] w-full max-w-xl overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-2xl shadow-slate-200">
            <img src={heroImage} alt="خزينة وبطاقات بنكية" className="h-full w-full object-cover" data-testid="bank-selection-hero-image" />
            <div className="absolute bottom-5 right-5 rounded-xl border border-white/60 bg-white/90 p-4 shadow-lg backdrop-blur" data-testid="bank-selection-hero-metric">
              <div className="flex items-center gap-3">
                <BadgeCheck className="h-7 w-7 text-emerald-600" />
                <div>
                  <p className="text-xs font-bold text-slate-500" data-testid="hero-metric-label">تقارير منفصلة</p>
                  <p className="text-xl font-extrabold text-slate-950" data-testid="hero-metric-value">٣ بنوك</p>
                </div>
              </div>
            </div>
          </div>
          <Button asChild className="mt-6 h-12 rounded-lg bg-slate-950 px-7 text-white hover:bg-slate-800 md:hidden" data-testid="mobile-start-button">
            <Link to={`/bank/${banks[0]?.id || "industrial-development"}/register`}>ابدأ الآن</Link>
          </Button>
        </div>
      </section>
    </main>
  );
}
