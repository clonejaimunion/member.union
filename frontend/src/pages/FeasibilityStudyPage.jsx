import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, FileBarChart, Home, LogOut, Printer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { formatCurrency, sanitizeDecimalInput } from "@/lib/format";

const fields = [
  ["project_name", "اسم المشروع", "مشروع جديد"],
  ["investment_cost", "التكاليف الاستثمارية", "0"],
  ["operating_cost", "التكاليف التشغيلية السنوية", "0"],
  ["expected_revenue", "الإيرادات السنوية المتوقعة", "0"],
  ["fixed_cost", "التكاليف الثابتة السنوية", "0"],
  ["variable_cost_ratio", "نسبة التكلفة المتغيرة %", "0"],
];

export default function FeasibilityStudyPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [form, setForm] = useState(Object.fromEntries(fields.map(([key,, value]) => [key, value])));
  const update = (key, value) => setForm((current) => ({ ...current, [key]: key === "project_name" ? value : sanitizeDecimalInput(value) }));
  const result = useMemo(() => {
    const investment = Number(form.investment_cost || 0);
    const operating = Number(form.operating_cost || 0);
    const revenue = Number(form.expected_revenue || 0);
    const fixed = Number(form.fixed_cost || 0);
    const variableRatio = Number(form.variable_cost_ratio || 0) / 100;
    const variableCost = revenue * variableRatio;
    const profit = revenue - operating - variableCost;
    const contributionRatio = revenue > 0 ? Math.max(0, 1 - variableRatio) : 0;
    const breakEven = contributionRatio > 0 ? fixed / contributionRatio : 0;
    const payback = profit > 0 ? investment / profit : 0;
    return { investment, operating, revenue, variableCost, profit, breakEven, payback };
  }, [form]);
  return <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="feasibility-page"><header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur print:hidden"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8"><div className="flex items-center gap-3"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white"><FileBarChart className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700">وحدة تحليلية مستقلة</p><h1 className="text-2xl font-extrabold" data-testid="feasibility-title">دراسة جدوى</h1></div></div><div className="flex flex-wrap items-center gap-3"><Badge className="bg-white text-slate-700" data-testid="feasibility-user-badge">{user?.username}</Badge><Button asChild variant="outline" className="h-11 bg-white" data-testid="feasibility-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="feasibility-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 bg-white" data-testid="feasibility-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div></div></header><section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[0.85fr_1.15fr] lg:px-8"><section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="feasibility-form-section"><h2 className="mb-4 text-2xl font-extrabold">بيانات المشروع</h2><div className="space-y-4">{fields.map(([key, label]) => <div key={key}><Label data-testid={`feasibility-${key}-label`}>{label}</Label><Input value={form[key]} onChange={(e) => update(key, e.target.value)} className="mt-2 text-right" data-testid={`feasibility-${key}-input`} /></div>)}<Button onClick={() => window.print()} className="h-11 w-full bg-slate-950 text-white" data-testid="feasibility-print-button"><Printer className="h-4 w-4" /> طباعة التقرير</Button></div></section><section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="feasibility-report"><h2 className="text-3xl font-extrabold" data-testid="feasibility-report-title">تقرير دراسة جدوى — {form.project_name}</h2><p className="mt-2 text-sm font-bold text-slate-500">هذه الصفحة تحليلية فقط ولا تنشئ قيوداً ولا تؤثر على اليومية أو الأستاذ أو الميزانية.</p><div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-2"><div className="rounded-lg bg-slate-50 p-4"><p className="text-xs font-bold text-slate-500">صافي الربح المتوقع</p><p className="text-2xl font-extrabold" data-testid="feasibility-profit-value">{formatCurrency(result.profit)}</p></div><div className="rounded-lg bg-emerald-50 p-4 text-emerald-900"><p className="text-xs font-bold">نقطة التعادل</p><p className="text-2xl font-extrabold" data-testid="feasibility-break-even-value">{formatCurrency(result.breakEven)}</p></div><div className="rounded-lg bg-amber-50 p-4 text-amber-900"><p className="text-xs font-bold">فترة الاسترداد</p><p className="text-2xl font-extrabold" data-testid="feasibility-payback-value">{result.payback ? `${result.payback.toFixed(2)} سنة` : "غير متاحة"}</p></div><div className="rounded-lg bg-sky-50 p-4 text-sky-900"><p className="text-xs font-bold">إجمالي الإيرادات المتوقعة</p><p className="text-2xl font-extrabold">{formatCurrency(result.revenue)}</p></div></div></section></section><footer className="px-4 pb-5 print:hidden"><CreditLine testId="feasibility-creator-credit" /></footer></main>;
}