import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Home, LineChart, LogOut, Printer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { formatCurrency, sanitizeDecimalInput } from "@/lib/format";

const fields = [["members", "عدد الأعضاء", "0"], ["monthly_subscription", "متوسط الاشتراك الشهري", "0"], ["annual_commitments", "الالتزامات السنوية المتوقعة", "0"], ["growth_rate", "معدل نمو العضوية %", "0"], ["years", "عدد سنوات التقدير", "5"]];

export default function ActuarialStudyPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [form, setForm] = useState(Object.fromEntries(fields.map(([key,, value]) => [key, value])));
  const update = (key, value) => setForm((current) => ({ ...current, [key]: sanitizeDecimalInput(value) }));
  const result = useMemo(() => {
    const members = Number(form.members || 0);
    const monthly = Number(form.monthly_subscription || 0);
    const commitments = Number(form.annual_commitments || 0);
    const growth = Number(form.growth_rate || 0) / 100;
    const years = Math.max(1, Number(form.years || 1));
    const rows = Array.from({ length: years }, (_, index) => {
      const projectedMembers = Math.round(members * ((1 + growth) ** index));
      const inflow = projectedMembers * monthly * 12;
      const outflow = commitments * ((1 + growth) ** index);
      return { year: index + 1, projectedMembers, inflow, outflow, adequacy: outflow > 0 ? inflow / outflow : 0 };
    });
    const totalInflow = rows.reduce((sum, row) => sum + row.inflow, 0);
    const totalOutflow = rows.reduce((sum, row) => sum + row.outflow, 0);
    return { rows, totalInflow, totalOutflow, adequacy: totalOutflow > 0 ? totalInflow / totalOutflow : 0 };
  }, [form]);
  return <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="actuarial-page"><header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur print:hidden"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8"><div className="flex items-center gap-3"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white"><LineChart className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700">وحدة تحليلية مستقلة</p><h1 className="text-2xl font-extrabold" data-testid="actuarial-title">دراسة اكتوارية</h1></div></div><div className="flex flex-wrap items-center gap-3"><Badge className="bg-white text-slate-700" data-testid="actuarial-user-badge">{user?.username}</Badge><Button asChild variant="outline" className="h-11 bg-white" data-testid="actuarial-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="actuarial-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 bg-white" data-testid="actuarial-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div></div></header><section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[0.85fr_1.15fr] lg:px-8"><section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="actuarial-form-section"><h2 className="mb-4 text-2xl font-extrabold">مدخلات الدراسة</h2><div className="space-y-4">{fields.map(([key, label]) => <div key={key}><Label data-testid={`actuarial-${key}-label`}>{label}</Label><Input value={form[key]} onChange={(e) => update(key, e.target.value)} className="mt-2 text-right" data-testid={`actuarial-${key}-input`} /></div>)}<Button onClick={() => window.print()} className="h-11 w-full bg-slate-950 text-white" data-testid="actuarial-print-button"><Printer className="h-4 w-4" /> طباعة التقرير</Button></div></section><section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="actuarial-report"><h2 className="text-3xl font-extrabold">التقرير الاكتواري المتوقع</h2><p className="mt-2 text-sm font-bold text-slate-500">تحليل مستقل لا ينشئ قيوداً ولا يؤثر على القوائم المالية.</p><div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-3"><div className="rounded-lg bg-emerald-50 p-4 text-emerald-900"><p className="text-xs font-bold">إجمالي التدفقات الداخلة</p><p className="text-xl font-extrabold">{formatCurrency(result.totalInflow)}</p></div><div className="rounded-lg bg-red-50 p-4 text-red-900"><p className="text-xs font-bold">إجمالي الالتزامات</p><p className="text-xl font-extrabold">{formatCurrency(result.totalOutflow)}</p></div><div className="rounded-lg bg-slate-50 p-4"><p className="text-xs font-bold text-slate-500">معدل كفاية الصندوق</p><p className="text-xl font-extrabold" data-testid="actuarial-adequacy-value">{(result.adequacy * 100).toFixed(2)}%</p></div></div><div className="mt-5 overflow-x-auto rounded-xl border"><table className="w-full text-right text-sm" data-testid="actuarial-report-table"><thead className="bg-slate-950 text-white"><tr><th className="p-3">السنة</th><th className="p-3">الأعضاء المتوقعون</th><th className="p-3">التدفقات</th><th className="p-3">الالتزامات</th><th className="p-3">الكفاية</th></tr></thead><tbody>{result.rows.map((row) => <tr key={row.year} className="border-t"><td className="p-3 font-extrabold">{row.year}</td><td className="p-3">{row.projectedMembers}</td><td className="p-3">{formatCurrency(row.inflow)}</td><td className="p-3">{formatCurrency(row.outflow)}</td><td className="p-3">{(row.adequacy * 100).toFixed(2)}%</td></tr>)}</tbody></table></div></section></section><footer className="px-4 pb-5 print:hidden"><CreditLine testId="actuarial-creator-credit" /></footer></main>;
}