import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, FileClock, Home, LogOut, PrinterCheck } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BankLogo } from "@/components/BankLogo";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { bankPalette, fallbackBanks } from "@/lib/banks";

export default function BankPrintsPortalPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [banks, setBanks] = useState(fallbackBanks);

  useEffect(() => {
    api.get("/banks").then((response) => setBanks(response.data)).catch(() => {
      toast.error("تعذر تحميل البنوك المسجلة");
      setBanks(fallbackBanks);
    });
  }, []);

  return (
    <main className="min-h-screen bg-[#f4f8fb] text-slate-950" data-testid="bank-prints-portal-page">
      <header className="border-b border-slate-200 bg-white/95 backdrop-blur-xl" data-testid="bank-prints-portal-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-5 sm:px-6 lg:px-8" data-testid="bank-prints-portal-header-inner">
          <div className="flex items-center gap-3" data-testid="bank-prints-portal-brand">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-800 text-white" data-testid="bank-prints-portal-brand-icon"><PrinterCheck className="h-6 w-6" /></div>
            <div data-testid="bank-prints-portal-brand-text"><p className="text-xs font-extrabold text-sky-700" data-testid="bank-prints-portal-eyebrow">محدثة لحظياً</p><h1 className="text-2xl font-black" data-testid="bank-prints-portal-title">مطبوعات بنكية</h1></div>
          </div>
          <div className="flex flex-wrap gap-3" data-testid="bank-prints-portal-actions">
            <Badge className="bg-white text-slate-700" data-testid="bank-prints-portal-user-badge">{user?.username}</Badge>
            <Button asChild variant="outline" className="h-11 bg-white" data-testid="bank-prints-portal-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button>
            <Button onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="bank-prints-portal-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button>
            <Button onClick={logout} variant="outline" className="h-11 bg-white" data-testid="bank-prints-portal-logout-button"><LogOut className="h-4 w-4" /> خروج</Button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8" data-testid="bank-prints-portal-content">
        <div className="mb-8 max-w-3xl" data-testid="bank-prints-portal-intro">
          <h2 className="text-4xl font-black leading-tight sm:text-5xl lg:text-6xl" data-testid="bank-prints-portal-heading">البنوك الموجودة بالبرنامج</h2>
          <p className="mt-4 text-base font-bold leading-8 text-slate-600 md:text-lg" data-testid="bank-prints-portal-subtitle">اختَر البنك لإنشاء مطبوعة خارجية مستقلة. المطبوعات لا تعدل القيود اليومية ولا التسويات البنكية ولا أرصدة النظام.</p>
        </div>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3" data-testid="bank-prints-bank-cards-grid">
          {banks.map((bank) => {
            const palette = bankPalette[bank.id] || bankPalette["industrial-development"];
            const isBanqueMisr = bank.id === "banque-misr";
            return (
              <article key={bank.id} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-[transform,box-shadow] hover:-translate-y-1 hover:shadow-xl" data-testid={`bank-prints-bank-card-${bank.id}`}>
                <BankLogo bankId={bank.id} bankName={bank.name} logoUrl={bank.logo_url} className={`mb-5 h-16 w-28 ${palette.ring} ring-2`} testId={`bank-prints-bank-card-${bank.id}-logo`} />
                <p className="text-xs font-extrabold text-slate-500" data-testid={`bank-prints-bank-card-${bank.id}-code`}>{bank.code}</p>
                <h3 className="mt-2 min-h-14 text-2xl font-black leading-8" data-testid={`bank-prints-bank-card-${bank.id}-name`}>{bank.name}</h3>
                <p className="mt-2 text-sm font-bold leading-6 text-slate-500" data-testid={`bank-prints-bank-card-${bank.id}-description`}>{isBanqueMisr ? "وحدة طباعة تعتمد على بيانات بنك مصر الخارجية مع نموذج إدخال وأرشيف طلبات." : "سيتم ربط وحدة المطبوعات الخارجية لهذا البنك لاحقاً."}</p>
                {isBanqueMisr ? (
                  <Button asChild className="mt-5 h-11 w-full rounded-lg bg-sky-800 text-white" data-testid="bank-prints-open-banque-misr-button"><Link to="/bank-prints/banque-misr">فتح مطبوعات بنك مصر <ArrowLeft className="h-4 w-4" /></Link></Button>
                ) : (
                  <Badge className="mt-5 bg-slate-100 px-3 py-2 text-slate-600 hover:bg-slate-100" data-testid={`bank-prints-bank-card-${bank.id}-coming-soon`}><FileClock className="ml-1 h-4 w-4" /> غير مفعل حالياً</Badge>
                )}
              </article>
            );
          })}
        </div>
      </section>
      <footer className="px-4 pb-5" data-testid="bank-prints-portal-footer"><CreditLine testId="bank-prints-portal-creator-credit" /></footer>
    </main>
  );
}