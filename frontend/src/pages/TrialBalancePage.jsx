import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Home, LogOut, Scale } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ExportReportButtons } from "@/components/ExportReportButtons";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

const accountTypes = { all: "كل الحسابات", asset: "أصول", liability: "التزامات", equity: "حقوق الملكية", revenue: "إيرادات", expense: "مصروفات" };

export default function TrialBalancePage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ from_date: "", to_date: "", account_type: "all", non_zero_only: true });

  const loadReport = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ non_zero_only: String(filters.non_zero_only) });
      if (filters.from_date) params.set("from_date", filters.from_date);
      if (filters.to_date) params.set("to_date", filters.to_date);
      if (filters.account_type !== "all") params.set("account_type", filters.account_type);
      const response = await api.get(`/trial-balance?${params.toString()}`);
      setReport(response.data);
    } catch (error) {
      toast.error("تعذر تحميل ميزان المراجعة");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { loadReport(); }, [loadReport]);

  const periodLabel = filters.from_date || filters.to_date ? `من ${filters.from_date || "البداية"} إلى ${filters.to_date || "اليوم"}` : "كل الفترات";

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="trial-balance-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="trial-balance-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="trial-balance-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white"><Scale className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700">التقارير المحاسبية</p><h1 className="text-2xl font-extrabold" data-testid="trial-balance-title">ميزان المراجعة</h1></div></div>
          <div className="flex flex-wrap items-center gap-3" data-testid="trial-balance-actions"><Badge className="bg-white text-slate-700" data-testid="trial-balance-user-badge">{user?.organization_name}</Badge><Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="trial-balance-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="trial-balance-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="trial-balance-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="trial-balance-content">
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="trial-balance-filters-section">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><div><h2 className="text-2xl font-extrabold" data-testid="trial-balance-filters-title">اختيارات التقرير</h2><p className="text-sm font-bold text-slate-500">يُحسب تلقائياً من القيود اليومية المعتمدة وشجرة الحسابات.</p></div><ExportReportButtons title={`ميزان المراجعة - ${periodLabel}`} fileName={`ميزان-المراجعة-${periodLabel}`} selectors={["[data-testid='trial-balance-report-section']"]} disabled={loading || !report} pdfLabel="طباعة PDF" pdfTestId="print-trial-balance-button" excelTestId="export-trial-balance-excel-button" wordTestId="export-trial-balance-word-button" /></div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-5" data-testid="trial-balance-filters-grid"><div><Label>من تاريخ</Label><Input type="date" value={filters.from_date} onChange={(e) => setFilters((c) => ({ ...c, from_date: e.target.value }))} className="mt-2 h-11 bg-slate-50" data-testid="trial-balance-from-date-input" /></div><div><Label>إلى تاريخ</Label><Input type="date" value={filters.to_date} onChange={(e) => setFilters((c) => ({ ...c, to_date: e.target.value }))} className="mt-2 h-11 bg-slate-50" data-testid="trial-balance-to-date-input" /></div><div><Label>نوع الحساب</Label><select value={filters.account_type} onChange={(e) => setFilters((c) => ({ ...c, account_type: e.target.value }))} className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="trial-balance-account-type-select">{Object.entries(accountTypes).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div><label className="mt-7 flex h-11 items-center gap-2 rounded-md bg-slate-50 px-3 font-bold"><input type="checkbox" checked={filters.non_zero_only} onChange={(e) => setFilters((c) => ({ ...c, non_zero_only: e.target.checked }))} data-testid="trial-balance-non-zero-checkbox" /> إظهار الحسابات ذات الحركة فقط</label><Button type="button" onClick={loadReport} className="mt-7 h-11 bg-slate-950 text-white" data-testid="apply-trial-balance-filter-button">تطبيق</Button></div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="trial-balance-report-section">
          <div className="mb-5 grid grid-cols-1 gap-4 md:grid-cols-5" data-testid="trial-balance-kpi-grid"><div className="rounded-xl bg-slate-950 p-4 text-white"><p className="text-xs font-bold text-slate-300">حالة الميزان</p><p className="text-xl font-extrabold" data-testid="trial-balance-status-value">{report?.is_balanced ? "متوازن" : "غير متوازن"}</p></div><div className="rounded-xl bg-emerald-50 p-4"><p className="text-xs font-bold text-emerald-700">إجمالي مدين</p><p className="text-xl font-extrabold" data-testid="trial-balance-total-debit">{formatCurrency(report?.total_debit || 0)}</p></div><div className="rounded-xl bg-emerald-50 p-4"><p className="text-xs font-bold text-emerald-700">إجمالي دائن</p><p className="text-xl font-extrabold" data-testid="trial-balance-total-credit">{formatCurrency(report?.total_credit || 0)}</p></div><div className="rounded-xl bg-amber-50 p-4"><p className="text-xs font-bold text-amber-700">أرصدة مدينة</p><p className="text-xl font-extrabold" data-testid="trial-balance-total-balance-debit">{formatCurrency(report?.total_balance_debit || 0)}</p></div><div className="rounded-xl bg-amber-50 p-4"><p className="text-xs font-bold text-amber-700">أرصدة دائنة</p><p className="text-xl font-extrabold" data-testid="trial-balance-total-balance-credit">{formatCurrency(report?.total_balance_credit || 0)}</p></div></div>
          <div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="trial-balance-table-wrapper"><Table data-testid="trial-balance-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">كود الحساب</TableHead><TableHead className="text-right text-white">اسم الحساب</TableHead><TableHead className="text-right text-white">النوع</TableHead><TableHead className="text-right text-white">إجمالي مدين</TableHead><TableHead className="text-right text-white">إجمالي دائن</TableHead><TableHead className="text-right text-white">رصيد مدين</TableHead><TableHead className="text-right text-white">رصيد دائن</TableHead></TableRow></TableHeader><TableBody>{loading && <TableRow><TableCell colSpan={7} className="py-8 text-center font-bold">جاري التحميل...</TableCell></TableRow>}{!loading && (report?.rows || []).length === 0 && <TableRow data-testid="trial-balance-empty-row"><TableCell colSpan={7} className="py-8 text-center font-bold text-slate-500">لا توجد حركات</TableCell></TableRow>}{!loading && (report?.rows || []).map((row) => <TableRow key={row.account_id || row.account_code || row.account_name} data-testid={`trial-balance-row-${row.account_code || row.account_name}`}><TableCell className="font-extrabold">{row.account_code || "-"}</TableCell><TableCell className="font-extrabold">{row.account_name}</TableCell><TableCell>{accountTypes[row.account_type] || row.account_type || "-"}</TableCell><TableCell>{formatCurrency(row.total_debit)}</TableCell><TableCell>{formatCurrency(row.total_credit)}</TableCell><TableCell>{formatCurrency(row.balance_debit)}</TableCell><TableCell>{formatCurrency(row.balance_credit)}</TableCell></TableRow>)}{!loading && report && <TableRow className="bg-emerald-50 font-extrabold hover:bg-emerald-50" data-testid="trial-balance-grand-total-row"><TableCell colSpan={3}>الإجمالي</TableCell><TableCell>{formatCurrency(report.total_debit)}</TableCell><TableCell>{formatCurrency(report.total_credit)}</TableCell><TableCell>{formatCurrency(report.total_balance_debit)}</TableCell><TableCell>{formatCurrency(report.total_balance_credit)}</TableCell></TableRow>}</TableBody></Table></div>
        </section>
      </section>
      <footer className="px-4 pb-5 print:hidden"><CreditLine testId="trial-balance-creator-credit" /></footer>
    </main>
  );
}