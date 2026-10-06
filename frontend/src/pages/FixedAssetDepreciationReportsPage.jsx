import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Home, LogOut, BarChart3, FileBarChart } from "lucide-react";
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

const REPORTS = [
  { id: "furniture_dep", title: "اهلاك الاثاث", type: "dep", cat: "5" },
  { id: "electrical_dep", title: "اهلاك الاجهزة الكهربائية", type: "dep", cat: "155" },
  { id: "office_dep", title: "اهلاك الالات المكتبية", type: "dep", cat: "101" },
  { id: "safes_dep", title: "اهلاك الخزائن", type: "dep", cat: "151" },
  { id: "installments", title: "قسط الاهلاك", type: "simple", source: "installments" },
  { id: "furniture_bal", title: "الاثاث", type: "balance", cat: "5" },
  { id: "safes_bal", title: "الخزائن", type: "balance", cat: "151" },
  { id: "electrical_bal", title: "الاجهزة الكهربائية", type: "balance", cat: "155" },
  { id: "office_bal", title: "الالات المكتبية", type: "balance", cat: "101" },
  { id: "provisions", title: "مخصصات الاهلاك", type: "simple", source: "provisions" },
  { id: "deposit_interest", title: "فوائد ودائع مستحقة", type: "simple", source: "deposit_interest" },
];

const formatAmount = (value) => {
  const num = Number(value || 0);
  if (Math.abs(num) < 0.005) return "-";
  return num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const AmountCell = ({ value, bold }) => (
  <TableCell className={`text-center tabular-nums ${bold ? "font-extrabold" : ""}`} dir="ltr">{formatAmount(value)}</TableCell>
);

const formatArabicDate = (iso) => {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
};

export default function FixedAssetDepreciationReportsPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const currentYear = new Date().getFullYear();
  const [filters, setFilters] = useState({ from_date: `${currentYear}-01-01`, to_date: `${currentYear}-12-31` });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeReportId, setActiveReportId] = useState(null);

  const loadData = useCallback(async () => {
    if (!filters.from_date || !filters.to_date) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ from_date: filters.from_date, to_date: filters.to_date });
      const response = await api.get(`/fixed-assets/depreciation-reports?${params.toString()}`);
      setData(response.data);
    } catch (error) {
      toast.error("تعذر تحميل تقارير الإهلاك");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { loadData(); }, [loadData]);

  const activeReport = useMemo(() => REPORTS.find((r) => r.id === activeReportId) || null, [activeReportId]);
  const periodLabel = `من ${formatArabicDate(filters.from_date)} إلى ${formatArabicDate(filters.to_date)}`;
  const toLabel = formatArabicDate(filters.to_date);

  const renderDepreciation = (report) => {
    const section = (data?.categories || []).find((c) => String(c.code) === String(report.cat));
    const rows = section?.assets || [];
    const totals = section?.totals || {};
    return (
      <div className="overflow-x-auto rounded-xl border border-slate-300" data-testid="depreciation-report-table-wrapper">
        <Table className="text-sm">
          <TableHeader>
            <TableRow className="bg-slate-950 hover:bg-slate-950">
              <TableHead className="border border-slate-300 text-center align-middle text-white">البيان</TableHead>
              <TableHead className="border border-slate-300 text-center text-white">القيمة</TableHead>
              <TableHead className="border border-slate-300 text-center text-white">صافي الأصل في {toLabel}</TableHead>
              <TableHead className="border border-slate-300 text-center text-white">مجمع الإهلاك في {toLabel}</TableHead>
              <TableHead className="border border-slate-300 text-center text-white">الإهلاك خلال الفترة</TableHead>
              <TableHead className="border border-slate-300 text-center text-white">مجمع الإهلاك في {formatArabicDate(filters.from_date)}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && <TableRow><TableCell colSpan={6} className="py-6 text-center font-bold text-slate-500">لا توجد أصول في هذه الفئة خلال الفترة</TableCell></TableRow>}
            {rows.map((row, idx) => (
              <TableRow key={idx} data-testid={`depreciation-row-${idx}`}>
                <TableCell className="border border-slate-200 font-bold">{row.name}</TableCell>
                <AmountCell value={row.value} />
                <AmountCell value={row.net} />
                <AmountCell value={row.closing_accum} />
                <AmountCell value={row.year_depreciation} />
                <AmountCell value={row.opening_accum} />
              </TableRow>
            ))}
            {rows.length > 0 && (
              <TableRow className="bg-emerald-50 font-extrabold hover:bg-emerald-50" data-testid="depreciation-total-row">
                <TableCell className="border border-slate-200 font-extrabold">الإجمالي</TableCell>
                <AmountCell value={totals.value} bold />
                <AmountCell value={totals.net} bold />
                <AmountCell value={totals.closing_accum} bold />
                <AmountCell value={totals.year_depreciation} bold />
                <AmountCell value={totals.opening_accum} bold />
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    );
  };

  const renderSimple = (rows, total, valueKey) => (
    <div className="overflow-x-auto rounded-xl border border-slate-300" data-testid="simple-report-table-wrapper">
      <Table className="text-sm">
        <TableHeader>
          <TableRow className="bg-slate-950 hover:bg-slate-950">
            <TableHead className="border border-slate-300 text-center align-middle text-white">البيان</TableHead>
            <TableHead className="border border-slate-300 text-center text-white">المبلغ</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 && <TableRow><TableCell colSpan={2} className="py-6 text-center font-bold text-slate-500">لا توجد بيانات خلال الفترة</TableCell></TableRow>}
          {rows.map((row, idx) => (
            <TableRow key={idx} data-testid={`simple-row-${idx}`}>
              <TableCell className="border border-slate-200 font-bold">{row.name}</TableCell>
              <AmountCell value={row[valueKey]} />
            </TableRow>
          ))}
          {rows.length > 0 && (
            <TableRow className="bg-emerald-50 font-extrabold hover:bg-emerald-50" data-testid="simple-total-row">
              <TableCell className="border border-slate-200 font-extrabold">الإجمالي</TableCell>
              <AmountCell value={total} bold />
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );

  const renderActiveReport = (report) => {
    if (report.type === "dep") return renderDepreciation(report);
    if (report.type === "balance") {
      const section = data?.balances?.[report.cat];
      return renderSimple(section?.rows || [], section?.total || 0, "value");
    }
    const source = data?.[report.source];
    return renderSimple(source?.rows || [], source?.total || 0, "amount");
  };

  const reportTitle = (report) => report.type === "balance" ? `${report.title} في ${toLabel}` : report.title;

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="depreciation-reports-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="depreciation-reports-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white"><BarChart3 className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700">تقارير تلقائية</p><h1 className="text-2xl font-extrabold" data-testid="depreciation-reports-title">تقارير اهلاك الاصول الثابتة</h1></div></div>
          <div className="flex flex-wrap items-center gap-3"><Badge className="bg-white text-slate-700">{user?.organization_name}</Badge><Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="depreciation-home-button"><Link to="/"><Home className="h-4 w-4" /> الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="depreciation-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="depreciation-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="depreciation-reports-content">
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="depreciation-filters-section">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div><Label>من تاريخ</Label><Input type="date" value={filters.from_date} onChange={(e) => setFilters((c) => ({ ...c, from_date: e.target.value }))} className="mt-2 h-11 bg-slate-50" data-testid="depreciation-from-date-input" /></div>
            <div><Label>إلى تاريخ</Label><Input type="date" value={filters.to_date} onChange={(e) => setFilters((c) => ({ ...c, to_date: e.target.value }))} className="mt-2 h-11 bg-slate-50" data-testid="depreciation-to-date-input" /></div>
            <div className="flex items-end"><Button onClick={loadData} className="h-11 w-full bg-slate-950 text-white" data-testid="depreciation-apply-button">تحديث التقارير</Button></div>
          </div>
          <p className="mt-3 text-sm font-bold text-slate-500">الفترة الحالية: {periodLabel}{loading ? " — جاري التحميل..." : ""}</p>
        </section>

        {!activeReport && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="depreciation-reports-grid">
            {REPORTS.map((report) => (
              <button key={report.id} type="button" onClick={() => setActiveReportId(report.id)} className="group flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5 text-right shadow-sm transition-all hover:-translate-y-1 hover:border-slate-300 hover:shadow-xl" data-testid={`depreciation-card-${report.id}`}>
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-slate-950 text-white transition-transform group-hover:scale-105"><FileBarChart className="h-6 w-6" /></div>
                <div><h3 className="text-lg font-extrabold">{reportTitle(report)}</h3><p className="text-xs font-bold text-slate-500">توليد تلقائي حسب الفترة</p></div>
              </button>
            ))}
          </div>
        )}

        {activeReport && (
          <section className="space-y-4" data-testid="depreciation-active-report">
            <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
              <Button onClick={() => setActiveReportId(null)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="depreciation-report-back-list-button"><ArrowRight className="h-4 w-4" /> كل التقارير</Button>
              <ExportReportButtons title={`${reportTitle(activeReport)} - ${periodLabel}`} fileName={`${reportTitle(activeReport)}-${filters.from_date}-${filters.to_date}`} selectors={["[data-testid='depreciation-report-section']"]} disabled={loading} pdfLabel="طباعة PDF" pdfTestId="depreciation-print-button" excelTestId="depreciation-export-excel-button" wordTestId="depreciation-export-word-button" />
            </div>
            <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="depreciation-report-section">
              <div className="mb-4 text-center">
                <h2 className="text-xl font-extrabold text-slate-950" data-testid="depreciation-report-heading">{reportTitle(activeReport)}</h2>
                <p className="text-sm font-bold text-slate-600">{periodLabel}</p>
              </div>
              {renderActiveReport(activeReport)}
            </section>
          </section>
        )}
      </section>

      <footer className="px-4 pb-5 print:hidden"><CreditLine testId="depreciation-reports-creator-credit" /></footer>
    </main>
  );
}
