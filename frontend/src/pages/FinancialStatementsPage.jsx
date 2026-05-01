import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowRight, FileSpreadsheet, FileWarning, Home, LogOut, Printer, Scale } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ExportReportButtons } from "@/components/ExportReportButtons";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { useAppSettings } from "@/contexts/AppSettingsContext";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

const currentYear = new Date().getFullYear();
const years = Array.from({ length: 16 }, (_, index) => currentYear - 10 + index);

const yearRange = (year) => ({ from_date: `${year}-01-01`, to_date: `${year}-12-31` });
const lineAmount = (line) => Number(line?.amount || 0);
const sectionTotal = (section) => Number(section?.total || 0);

function buildCompareMap(sections = []) {
  const map = new Map();
  sections.forEach((section) => (section?.lines || []).forEach((line) => map.set(`${line.code || ""}-${line.name}`, lineAmount(line))));
  return map;
}

function SignatureStrip({ testId }) {
  return (
    <div className="mt-10 grid grid-cols-1 gap-8 text-center font-extrabold md:grid-cols-3 print:grid-cols-3" data-testid={testId}>
      <div className="min-h-24 border-t border-slate-400 pt-3" data-testid={`${testId}-prepared`}><p>المراجع / المختص</p><p className="mt-4 text-sm">........................</p></div>
      <div className="min-h-24 border-t border-slate-400 pt-3" data-testid={`${testId}-treasurer`}><p>أمين الصندوق</p><p className="mt-4 text-sm">........................</p></div>
      <div className="min-h-24 border-t border-slate-400 pt-3" data-testid={`${testId}-chairman`}><p>رئيس النقابة العامة</p><p className="mt-4 text-sm">........................</p></div>
    </div>
  );
}

function ReportHeader({ title, subtitle, year, dateLabel, testId, unionName, projectName }) {
  return (
    <div className="mb-6 text-center" data-testid={testId}>
      <p className="text-lg font-extrabold" data-testid={`${testId}-organization`}>{unionName}</p>
      <p className="text-base font-bold" data-testid={`${testId}-project`}>{projectName}</p>
      <h2 className="mt-3 text-3xl font-extrabold" data-testid={`${testId}-title`}>{title}</h2>
      <p className="mt-1 text-xl font-extrabold" data-testid={`${testId}-date`}>{dateLabel || `في ${year}`}</p>
      {subtitle && <p className="mt-1 text-sm font-bold text-slate-500" data-testid={`${testId}-subtitle`}>{subtitle}</p>}
    </div>
  );
}

function AnnualRowsTable({ title, rows, compareMap, currentLabel, total, previousTotal, testId }) {
  return (
    <div className="rounded-lg border border-slate-300 bg-white" data-testid={`${testId}-box`}>
      <div className="border-b border-slate-300 bg-slate-100 px-4 py-2 text-center text-lg font-extrabold" data-testid={`${testId}-title`}>{title}</div>
      <Table data-testid={testId}>
        <TableHeader>
          <TableRow className="bg-white hover:bg-white">
            <TableHead className="w-32 border border-slate-300 text-center font-extrabold text-slate-900">مقارن</TableHead>
            <TableHead className="border border-slate-300 text-center font-extrabold text-slate-900">البيان</TableHead>
            <TableHead className="w-36 border border-slate-300 text-center font-extrabold text-slate-900">{currentLabel}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 && <TableRow data-testid={`${testId}-empty-row`}><TableCell colSpan={3} className="border border-slate-300 py-7 text-center font-bold text-slate-500">لا توجد بيانات</TableCell></TableRow>}
          {rows.map((line, index) => <TableRow key={`${line.code || ""}-${line.name}-${index}`} data-testid={`${testId}-row-${index}`}><TableCell className="border border-slate-300 text-center" data-testid={`${testId}-row-${index}-compare`}>{formatCurrency(compareMap.get(`${line.code || ""}-${line.name}`) || 0)}</TableCell><TableCell className="border border-slate-300 font-extrabold" data-testid={`${testId}-row-${index}-name`}>{line.name}</TableCell><TableCell className="border border-slate-300 text-center font-extrabold" data-testid={`${testId}-row-${index}-amount`}>{formatCurrency(lineAmount(line))}</TableCell></TableRow>)}
          <TableRow className="bg-slate-100 font-extrabold" data-testid={`${testId}-total-row`}><TableCell className="border border-slate-300 text-center" data-testid={`${testId}-previous-total`}>{formatCurrency(previousTotal || 0)}</TableCell><TableCell className="border border-slate-300">الإجمالي</TableCell><TableCell className="border border-slate-300 text-center" data-testid={`${testId}-current-total`}>{formatCurrency(total || 0)}</TableCell></TableRow>
        </TableBody>
      </Table>
    </div>
  );
}

function BalanceSheetPrint({ report, previousReport, year, unionName, projectName }) {
  const currentAssets = report?.balance_sheet?.assets;
  const currentLiabilities = report?.balance_sheet?.liabilities;
  const currentEquity = report?.balance_sheet?.equity;
  const previousAssets = previousReport?.balance_sheet?.assets;
  const previousLiabilities = previousReport?.balance_sheet?.liabilities;
  const previousEquity = previousReport?.balance_sheet?.equity;
  const assetsCompare = buildCompareMap([previousAssets]);
  const liabilitiesCompare = buildCompareMap([previousLiabilities, previousEquity]);
  const rightRows = [...(currentLiabilities?.lines || []), ...(currentEquity?.lines || [])];
  const rightPreviousTotal = sectionTotal(previousLiabilities) + sectionTotal(previousEquity);
  const rightTotal = sectionTotal(currentLiabilities) + sectionTotal(currentEquity);
  return (
    <section className="financial-print-sheet" data-testid="balance-sheet-print-section">
      <ReportHeader title="الميزانية" year={year} unionName={unionName} projectName={projectName} testId="balance-sheet-print-header" />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2 print:grid-cols-2" data-testid="balance-sheet-print-grid">
        <AnnualRowsTable title="الأصول" rows={currentAssets?.lines || []} compareMap={assetsCompare} currentLabel={String(year)} total={sectionTotal(currentAssets)} previousTotal={sectionTotal(previousAssets)} testId="balance-sheet-print-assets-table" />
        <AnnualRowsTable title="المخصصات والفائض" rows={rightRows} compareMap={liabilitiesCompare} currentLabel={String(year)} total={rightTotal} previousTotal={rightPreviousTotal} testId="balance-sheet-print-liabilities-equity-table" />
      </div>
      <div className={`mt-5 border-2 p-3 text-center text-xl font-extrabold ${report?.balance_sheet?.check?.total === 0 ? "border-slate-400" : "border-red-600 text-red-700"}`} data-testid="balance-sheet-print-check">فرق اتزان الميزانية: {formatCurrency(report?.balance_sheet?.check?.total || 0)}</div>
      <SignatureStrip testId="balance-sheet-print-signatures" />
    </section>
  );
}

function IncomeExpensePrint({ report, previousReport, year, unionName, projectName }) {
  const revenues = report?.revenues_expenses?.revenues;
  const expenses = report?.revenues_expenses?.expenses;
  const revenuesCompare = buildCompareMap([previousReport?.revenues_expenses?.revenues]);
  const expensesCompare = buildCompareMap([previousReport?.revenues_expenses?.expenses]);
  return (
    <section className="financial-print-sheet" data-testid="income-expense-print-section">
      <ReportHeader title="حساب الإيرادات والمصروفات" year={year} unionName={unionName} projectName={projectName} testId="income-expense-print-header" />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2 print:grid-cols-2" data-testid="income-expense-print-grid">
        <AnnualRowsTable title="إيرادات النشاط" rows={revenues?.lines || []} compareMap={revenuesCompare} currentLabel={String(year)} total={sectionTotal(revenues)} previousTotal={sectionTotal(previousReport?.revenues_expenses?.revenues)} testId="income-print-revenues-table" />
        <AnnualRowsTable title="المصروفات" rows={expenses?.lines || []} compareMap={expensesCompare} currentLabel={String(year)} total={sectionTotal(expenses)} previousTotal={sectionTotal(previousReport?.revenues_expenses?.expenses)} testId="income-print-expenses-table" />
      </div>
      <div className="mt-5 border border-slate-400 bg-slate-100 p-3 text-center text-xl font-extrabold" data-testid="income-expense-print-result">الفائض / العجز: {formatCurrency(report?.revenues_expenses?.result?.total || 0)}</div>
      <SignatureStrip testId="income-expense-print-signatures" />
    </section>
  );
}

function ReceiptsPaymentsPrint({ report, previousReport, year, unionName, projectName }) {
  const receipts = report?.receipts_payments?.receipts;
  const payments = report?.receipts_payments?.payments;
  const receiptsCompare = buildCompareMap([previousReport?.receipts_payments?.receipts]);
  const paymentsCompare = buildCompareMap([previousReport?.receipts_payments?.payments]);
  return (
    <section className="financial-print-sheet" data-testid="receipts-payments-print-section">
      <ReportHeader title="حساب المقبوضات والمدفوعات" year={year} dateLabel={`في 31 ديسمبر ${year}`} unionName={unionName} projectName={projectName} testId="receipts-payments-print-header" />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2 print:grid-cols-2" data-testid="receipts-payments-print-grid">
        <AnnualRowsTable title="مقبوضات النشاط" rows={receipts?.lines || []} compareMap={receiptsCompare} currentLabel="رصيد آخر المدة" total={sectionTotal(receipts)} previousTotal={sectionTotal(previousReport?.receipts_payments?.receipts)} testId="receipts-print-table" />
        <AnnualRowsTable title="مصروفات النشاط" rows={payments?.lines || []} compareMap={paymentsCompare} currentLabel="رصيد آخر المدة" total={sectionTotal(payments)} previousTotal={sectionTotal(previousReport?.receipts_payments?.payments)} testId="payments-print-table" />
      </div>
      <div className="mt-5 border border-slate-400 bg-slate-100 p-3 text-center text-xl font-extrabold" data-testid="receipts-payments-print-net">صافي المقبوضات والمدفوعات: {formatCurrency(report?.receipts_payments?.net_cash_flow?.total || 0)}</div>
      <SignatureStrip testId="receipts-payments-print-signatures" />
    </section>
  );
}

function AccountingErrorsPrint({ report }) {
  return (
    <section className="financial-print-sheet" data-testid="accounting-errors-print-section">
      <div className="mb-5 flex items-center gap-3"><FileWarning className="h-7 w-7 text-red-700" /><h2 className="text-3xl font-extrabold" data-testid="accounting-errors-print-title">تقرير الأخطاء المحاسبية</h2></div>
      <div className="overflow-x-auto rounded-lg border border-red-200" data-testid="accounting-errors-print-table-wrapper">
        <Table data-testid="accounting-errors-print-table"><TableHeader className="bg-red-900"><TableRow className="hover:bg-red-900"><TableHead className="text-right text-white">الخطورة</TableHead><TableHead className="text-right text-white">نوع الخطأ</TableHead><TableHead className="text-right text-white">مكان الخطأ</TableHead><TableHead className="text-right text-white">التفاصيل</TableHead><TableHead className="text-right text-white">الإجراء المقترح</TableHead></TableRow></TableHeader><TableBody>{(report?.accounting_errors || []).length === 0 && <TableRow data-testid="accounting-errors-print-empty-row"><TableCell colSpan={5} className="py-8 text-center font-extrabold text-emerald-700">لا توجد أخطاء محاسبية مكتشفة</TableCell></TableRow>}{(report?.accounting_errors || []).map((error, index) => <TableRow key={`${error.error_type}-${index}`} data-testid={`accounting-errors-print-row-${index}`}><TableCell className="font-extrabold">{error.severity === "critical" ? "حرج" : error.severity === "warning" ? "تنبيه" : "معلومة"}</TableCell><TableCell>{error.error_type}</TableCell><TableCell className="font-extrabold">{error.location}</TableCell><TableCell>{error.details}</TableCell><TableCell>{error.suggested_fix || "-"}</TableCell></TableRow>)}</TableBody></Table>
      </div>
    </section>
  );
}

export default function FinancialStatementsPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { settings } = useAppSettings();
  const unionName = settings.organizations?.["general-union"]?.name || "النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الأراضي";
  const projectName = settings.organizations?.["social-solidarity"]?.login_label || settings.organizations?.["social-solidarity"]?.name || "مشروع التكافل الاجتماعي";
  const [year, setYear] = useState(String(currentYear));
  const [report, setReport] = useState(null);
  const [previousReport, setPreviousReport] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadReports = useCallback(async () => {
    setLoading(true);
    try {
      const selectedYear = Number(year);
      const currentRange = yearRange(selectedYear);
      const previousRange = yearRange(selectedYear - 1);
      const [currentResponse, previousResponse] = await Promise.all([
        api.get(`/financial-statements?from_date=${currentRange.from_date}&to_date=${currentRange.to_date}`),
        api.get(`/financial-statements?from_date=${previousRange.from_date}&to_date=${previousRange.to_date}`),
      ]);
      setReport(currentResponse.data);
      setPreviousReport(previousResponse.data);
      if (currentResponse.data.accounting_errors?.length) toast.warning("تم اكتشاف ملاحظات محاسبية في التقرير");
    } catch (error) {
      toast.error("تعذر تحميل القوائم المالية");
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => { loadReports(); }, [loadReports]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="financial-statements-page">
      <style>{`@media print {.print\\:hidden{display:none!important}.financial-print-sheet{break-after:page;box-shadow:none!important;border:0!important;margin:0!important;padding:12mm!important}.financial-print-sheet:last-child{break-after:auto}body{background:white!important}.financial-report-actions{display:none!important}} .financial-print-sheet{background:white;border:1px solid #d6d3d1;border-radius:10px;padding:24px;box-shadow:0 1px 2px rgba(0,0,0,.04)} .financial-print-sheet table{border-collapse:collapse!important} .financial-print-sheet th,.financial-print-sheet td{font-size:13px}`}</style>
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="financial-statements-header"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8"><div className="flex items-center gap-3" data-testid="financial-statements-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white"><Scale className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700">القوائم المالية السنوية</p><h1 className="text-2xl font-extrabold" data-testid="financial-statements-title">الميزانية والحسابات الختامية</h1></div></div><div className="flex flex-wrap items-center gap-3" data-testid="financial-statements-actions"><Badge className="bg-white text-slate-700" data-testid="financial-statements-organization-badge">{user?.organization_name}</Badge><Button asChild variant="outline" className="h-11 bg-white" data-testid="financial-statements-home-button"><Link to="/"><Home className="h-4 w-4" /> الرئيسية</Link></Button><Button type="button" onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="financial-statements-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button type="button" onClick={logout} variant="outline" className="h-11 bg-white" data-testid="financial-statements-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div></div></header>
      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="financial-statements-content">
        <section className="financial-report-actions rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="financial-statements-year-section"><div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><div><h2 className="text-2xl font-extrabold" data-testid="financial-statements-year-title">تقارير سنوية فقط</h2><p className="text-sm font-bold text-slate-500" data-testid="financial-statements-year-subtitle">كل الحسابات الختامية تطبع في نهاية السنة المختارة بنفس شكل النماذج.</p></div><ExportReportButtons title={`الحسابات الختامية في ${year}`} fileName={`الحسابات-الختامية-${year}`} selectors={["[data-testid='balance-sheet-print-section']", "[data-testid='income-expense-print-section']", "[data-testid='receipts-payments-print-section']", "[data-testid='accounting-errors-print-section']"]} disabled={loading || !report} pdfLabel="طباعة PDF" pdfTestId="print-financial-statements-button" excelTestId="export-financial-statements-excel-button" wordTestId="export-financial-statements-word-button" /></div><div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_auto_auto]" data-testid="financial-statements-year-controls"><select value={year} onChange={(event) => setYear(event.target.value)} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="financial-statements-year-select">{years.map((item) => <option key={item} value={item} label={String(item)} />)}</select><Button type="button" onClick={loadReports} className="h-11 bg-slate-950 text-white" data-testid="generate-financial-statements-button"><FileSpreadsheet className="h-4 w-4" /> توليد تلقائي</Button><Button type="button" onClick={() => window.print()} variant="outline" className="h-11 bg-white" data-testid="print-annual-financial-statements-button"><Printer className="h-4 w-4" /> طباعة الحسابات الختامية</Button></div></section>
        <section className="grid grid-cols-1 gap-4 md:grid-cols-4 print:hidden" data-testid="financial-statements-kpi-grid"><div className="rounded-xl bg-slate-950 p-4 text-white"><p className="text-xs font-bold text-slate-300">حالة القوائم</p><p className="text-xl font-extrabold" data-testid="financial-statements-valid-value">{report?.is_accounting_valid ? "سليمة" : "بها أخطاء"}</p></div><div className="rounded-xl bg-emerald-50 p-4"><p className="text-xs font-bold text-emerald-700">إجمالي الأصول</p><p className="text-xl font-extrabold" data-testid="financial-statements-assets-value">{formatCurrency(report?.balance_sheet?.assets?.total || 0)}</p></div><div className="rounded-xl bg-amber-50 p-4"><p className="text-xs font-bold text-amber-700">نتيجة السنة</p><p className="text-xl font-extrabold" data-testid="financial-statements-result-value">{formatCurrency(report?.revenues_expenses?.result?.total || 0)}</p></div><div className="rounded-xl bg-red-50 p-4"><p className="text-xs font-bold text-red-700">الأخطاء المكتشفة</p><p className="text-xl font-extrabold" data-testid="financial-statements-errors-value">{report?.accounting_errors?.length || 0}</p></div></section>
        <BalanceSheetPrint report={report} previousReport={previousReport} year={year} unionName={unionName} projectName={projectName} />
        <IncomeExpensePrint report={report} previousReport={previousReport} year={year} unionName={unionName} projectName={projectName} />
        <ReceiptsPaymentsPrint report={report} previousReport={previousReport} year={year} unionName={unionName} projectName={projectName} />
        <AccountingErrorsPrint report={report} />
      </section>
      <footer className="px-4 pb-5 print:hidden"><CreditLine testId="financial-statements-creator-credit" /></footer>
    </main>
  );
}