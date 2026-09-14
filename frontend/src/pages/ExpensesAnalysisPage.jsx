import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, BarChart3, Eye, FileDown, FileSpreadsheet, FileText, Home, LogOut, Printer, RotateCcw, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreditLine } from "@/components/CreditLine";
import { PrintOrientationToggle } from "@/components/PrintOrientationToggle";
import { useAuth } from "@/contexts/AuthContext";
import { useAppSettings } from "@/contexts/AppSettingsContext";
import { api } from "@/lib/api";
import { formatCurrency, formatEgpLabel } from "@/lib/format";
import { usePrintOrientation, printWithOrientation } from "@/lib/printOrientation";

const organizationLabels = {
  general_union: "النقابة العامة",
  social_solidarity_project: "مشروع التكافل الاجتماعي",
};

const monthLabels = {
  "01": "يناير",
  "02": "فبراير",
  "03": "مارس",
  "04": "أبريل",
  "05": "مايو",
  "06": "يونيو",
  "07": "يوليو",
  "08": "أغسطس",
  "09": "سبتمبر",
  "10": "أكتوبر",
  "11": "نوفمبر",
  "12": "ديسمبر",
};

const normalizeArabic = (value) => String(value || "")
  .toLowerCase()
  .replace(/[إأآا]/g, "ا")
  .replace(/ة/g, "ه")
  .replace(/ى/g, "ي")
  .replace(/[ًٌٍَُِّْـ]/g, "")
  .replace(/\s+/g, " ")
  .trim();

const analysisCategories = [
  { key: "wages", label: "أجور ومرتبات", keywords: ["منحة", "منحه", "مرتبات عاملين", "مرتبات", "مكافاة", "مكافأة", "مكافاه"] },
  { key: "board_attendance", label: "بدل حضور جلسات", keywords: ["مجلس الادارة", "مجلس الإدارة"] },
  { key: "transportation", label: "بدل انتقال", keywords: ["بدل انتقال"] },
  { key: "effort", label: "بدل جهد", keywords: ["بدل اعباء", "بدل أعباء"] },
  { key: "maintenance", label: "قطع غيار وصيانة", keywords: ["قطع غيار", "صيانة", "صيانه"] },
  { key: "consulting", label: "إستشارات فنية", keywords: ["اتعاب", "أتعاب", "احمد بدران", "أحمد بدران", "مراجعة ميزانية"] },
  { key: "postage_stamps", label: "طوابع بريد", keywords: ["طوابع بريد", "طوابع بريديه", "طوابع بريدية", "طوابع", "بريد"] },
  { key: "office_supplies", label: "أدوات مكتبية", keywords: ["ادوات مكتبيه", "ادوات مكتبية", "أدوات مكتبية", "أدوات مكتبيه", "ادوات كتابيه", "ادوات كتابية", "أدوات كتابية", "أدوات كتابيه", "قرطاسيه", "قرطاسية", "مهمات مكتبيه", "مهمات مكتبية"] },
];

const escapeHtml = (value) => String(value ?? "")
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;")
  .replace(/'/g, "&#039;");

const makeSafeFileName = (value) => String(value || "expenses-analysis")
  .replace(/[\\/:*?"<>|]/g, "-")
  .replace(/\s+/g, "-")
  .slice(0, 120);

const triggerDownload = (content, filename, type) => {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

const classifyExpense = (expense) => {
  const searchText = normalizeArabic([
    expense.gross_statement,
    ...(expense.deductions || []).map((deduction) => deduction.statement),
  ].filter(Boolean).join(" "));
  return analysisCategories.filter((category) => category.keywords.some((keyword) => searchText.includes(normalizeArabic(keyword))));
};

const arabicToWesternDigits = (value) => String(value || "")
  .replace(/[٠-٩]/g, (digit) => String("٠١٢٣٤٥٦٧٨٩".indexOf(digit)))
  .replace(/[۰-۹]/g, (digit) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit)));

const prepForAmount = (value) => arabicToWesternDigits(String(value || ""))
  .replace(/[ًٌٍَُِّْـ]/g, "")
  .replace(/٫/g, ".")
  .replace(/[,٬]/g, "");

const statementHasItemizedAmounts = (statement) => /بمبلغ/.test(prepForAmount(statement));

const extractSegmentAmount = (segment) => {
  const match = prepForAmount(segment).match(/بمبلغ\D*?(\d+(?:\.\d+)?)/);
  return match ? Number(match[1]) : null;
};

const buildCategoryAmounts = (expense) => {
  const statement = String(expense.gross_statement || "");
  const base = analysisCategories.reduce((acc, category) => ({ ...acc, [category.key]: 0 }), {});
  if (statementHasItemizedAmounts(statement)) {
    statement.split("/").forEach((segment) => {
      const amount = extractSegmentAmount(segment);
      if (amount == null) return;
      const searchText = normalizeArabic(segment);
      analysisCategories.forEach((category) => {
        if (category.keywords.some((keyword) => searchText.includes(normalizeArabic(keyword)))) {
          base[category.key] += amount;
        }
      });
    });
    return base;
  }
  const matchedCategories = classifyExpense(expense);
  return analysisCategories.reduce((acc, category) => ({
    ...acc,
    [category.key]: matchedCategories.some((item) => item.key === category.key) ? Number(expense.gross_amount || 0) : 0,
  }), {});
};

export default function ExpensesAnalysisPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { settings } = useAppSettings();
  const dynamicOrganizationLabels = useMemo(() => ({
    general_union: settings.organizations?.["general-union"]?.login_label || organizationLabels.general_union,
    social_solidarity_project: settings.organizations?.["social-solidarity"]?.login_label || organizationLabels.social_solidarity_project,
  }), [settings.organizations]);
  const [expenses, setExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ organization_scope: "social_solidarity_project", period_type: "monthly", year: "", month: "" });
  const [previewOpen, setPreviewOpen] = useState(false);
  const [orientation, setOrientation] = usePrintOrientation("landscape");

  const loadExpenses = useCallback(() => {
    setLoading(true);
    api.get("/expenses")
      .then((response) => setExpenses(response.data))
      .catch(() => setExpenses([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadExpenses();
  }, [loadExpenses]);

  const years = useMemo(() => [...new Set(expenses.map((item) => String(item.issued_at || "").slice(0, 4)).filter(Boolean))].sort((a, b) => Number(b) - Number(a)), [expenses]);
  const months = useMemo(() => {
    if (!filters.year) return [];
    return [...new Set(expenses
      .filter((item) => String(item.issued_at || "").slice(0, 4) === filters.year)
      .map((item) => String(item.issued_at || "").slice(5, 7))
      .filter(Boolean))].sort();
  }, [expenses, filters.year]);

  const selectedExpenses = useMemo(() => expenses.filter((item) => {
    const issuedAt = String(item.issued_at || "");
    const organization = item.organization_scope || "social_solidarity_project";
    if (organization !== filters.organization_scope) return false;
    if (!filters.year) return false;
    if (!issuedAt.startsWith(filters.year)) return false;
    if (filters.period_type === "monthly") return Boolean(filters.month) && issuedAt.slice(5, 7) === filters.month;
    return true;
  }), [expenses, filters]);

  const analysisRows = useMemo(() => selectedExpenses.map((expense) => {
    const categoryAmounts = buildCategoryAmounts(expense);
    return {
      ...expense,
      categoryAmounts,
      analysis_total: Object.values(categoryAmounts).reduce((sum, value) => sum + value, 0),
    };
  }), [selectedExpenses]);

  const categoryTotals = useMemo(() => analysisCategories.reduce((acc, category) => ({
    ...acc,
    [category.key]: analysisRows.reduce((sum, row) => sum + Number(row.categoryAmounts[category.key] || 0), 0),
  }), {}), [analysisRows]);

  const grandTotal = useMemo(() => analysisCategories.reduce((sum, category) => sum + Number(categoryTotals[category.key] || 0), 0), [categoryTotals]);
  const visibleAnalysisRows = useMemo(() => analysisRows.filter((row) => Number(row.analysis_total || 0) > 0), [analysisRows]);
  const hasCompletePeriod = filters.period_type === "yearly" ? Boolean(filters.year) : Boolean(filters.year && filters.month);
  const periodLabel = filters.period_type === "yearly" ? `سنة ${filters.year || "—"}` : `${monthLabels[filters.month] || "—"} / ${filters.year || "—"}`;

  const exportFileBaseName = useMemo(() => makeSafeFileName(`تحليل-المصروفات-${dynamicOrganizationLabels[filters.organization_scope]}-${periodLabel}`), [dynamicOrganizationLabels, filters.organization_scope, periodLabel]);

  const buildExportTableHtml = useCallback((forExcel = false) => {
    const headers = ["التاريخ", "البيان بالكامل من المصروفات", ...analysisCategories.map((category) => category.label), "إجمالي الصف"];
    const rows = visibleAnalysisRows.map((row) => [
      row.issued_at,
      `${row.gross_statement || ""}${row.expense_number ? `\nإذن رقم ${row.expense_number}` : ""}${row.bank_name ? ` — ${row.bank_name}` : ""}`,
      ...analysisCategories.map((category) => row.categoryAmounts[category.key] ? Number(row.categoryAmounts[category.key]).toFixed(2) : ""),
      Number(row.analysis_total || 0).toFixed(2),
    ]);
    const totalRow = [
      "—",
      "الإجمالي العام",
      ...analysisCategories.map((category) => Number(categoryTotals[category.key] || 0).toFixed(2)),
      Number(grandTotal || 0).toFixed(2),
    ];
    const tableRows = [...rows, totalRow];
    const emptyRow = `<tr><td colspan="${headers.length}">لا توجد مصروفات مطابقة لهذه الاختيارات</td></tr>`;
    const tableBody = tableRows.length > 1 ? tableRows.map((row, rowIndex) => `<tr>${row.map((cell) => `<td${rowIndex === tableRows.length - 1 ? " style='font-weight:700;background:#fef2f2;'" : ""}>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("") : emptyRow;
    const workbookMeta = forExcel ? `<xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet><x:Name>تحليل المصروفات</x:Name><x:WorksheetOptions><x:DisplayRightToLeft/><x:PageSetup><x:Layout x:Orientation="${orientation === "landscape" ? "Landscape" : "Portrait"}"/></x:PageSetup></x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml>` : "";

    return `<!doctype html>
<html dir="rtl" lang="ar">
<head>
  <meta charset="utf-8" />
  ${workbookMeta}
  <style>
    @page { size: A4 ${orientation}; margin: 7mm; }
    body { font-family: Tahoma, Arial, sans-serif; direction: rtl; color: #111827; }
    h1 { font-size: 20px; margin: 0 0 6px; }
    p { margin: 0 0 12px; font-weight: 700; }
    table { border-collapse: collapse; width: 100%; table-layout: fixed; }
    th, td { border: 1px solid #111827; padding: 6px; text-align: right; vertical-align: top; white-space: pre-line; }
    th { background: #111827; color: #ffffff; font-weight: 700; }
  </style>
</head>
<body>
  <h1>${escapeHtml(`تحليل المصروفات - ${periodLabel}`)}</h1>
  <p>${escapeHtml(dynamicOrganizationLabels[filters.organization_scope])}</p>
  <table>
    <thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead>
    <tbody>${tableBody}</tbody>
  </table>
</body>
</html>`;
  }, [categoryTotals, dynamicOrganizationLabels, filters.organization_scope, grandTotal, orientation, periodLabel, visibleAnalysisRows]);

  const exportToPdf = () => printWithOrientation(orientation);
  const exportToExcel = () => triggerDownload(buildExportTableHtml(true), `${exportFileBaseName}.xls`, "application/vnd.ms-excel;charset=utf-8");
  const exportToWord = () => triggerDownload(buildExportTableHtml(false), `${exportFileBaseName}.doc`, "application/msword;charset=utf-8");

  const updateFilter = (field, value) => {
    setFilters((current) => {
      if (field === "period_type") return { ...current, period_type: value, month: value === "yearly" ? "" : current.month };
      if (field === "year") return { ...current, year: value, month: "" };
      return { ...current, [field]: value };
    });
  };

  const ReportBody = ({ preview = false }) => (
    <section className={`space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:border-0 print:shadow-none sm:p-8 ${preview ? "max-h-[78vh] overflow-y-auto" : ""}`} data-testid={preview ? "expenses-analysis-preview-report-section" : "expenses-analysis-report-section"}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between" data-testid={preview ? "expenses-analysis-preview-report-heading" : "expenses-analysis-report-heading"}>
        <div><p className="text-sm font-extrabold text-red-700" data-testid={preview ? "expenses-analysis-preview-report-eyebrow" : "expenses-analysis-report-eyebrow"}>{dynamicOrganizationLabels[filters.organization_scope]}</p><h2 className="text-3xl font-extrabold text-slate-950" data-testid={preview ? "expenses-analysis-preview-report-title" : "expenses-analysis-report-title"}>تحليل المصروفات - {periodLabel}</h2></div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid={preview ? "expenses-analysis-preview-report-kpis" : "expenses-analysis-report-kpis"}><div className="rounded-xl bg-slate-950 p-4 text-white" data-testid={preview ? "expenses-analysis-preview-count-card" : "expenses-analysis-count-card"}><p className="text-xs font-bold text-slate-300">عدد المصروفات</p><p className="text-2xl font-extrabold" data-testid={preview ? "expenses-analysis-preview-count-value" : "expenses-analysis-count-value"}>{hasCompletePeriod ? visibleAnalysisRows.length : 0}</p></div><div className="rounded-xl bg-red-50 p-4 text-red-900" data-testid={preview ? "expenses-analysis-preview-grand-total-card" : "expenses-analysis-grand-total-card"}><p className="text-xs font-bold text-red-700">الإجمالي العام للخانات</p><p className="text-2xl font-extrabold" data-testid={preview ? "expenses-analysis-preview-grand-total-value" : "expenses-analysis-grand-total-value"}>{hasCompletePeriod ? formatEgpLabel(grandTotal) : formatEgpLabel(0)}</p></div></div>
      </div>

      {!hasCompletePeriod ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center" data-testid={preview ? "expenses-analysis-preview-required-state" : "expenses-analysis-required-state"}><p className="text-xl font-extrabold text-slate-950" data-testid={preview ? "expenses-analysis-preview-required-title" : "expenses-analysis-required-title"}>اختر الفترة أولاً</p><p className="mt-2 text-sm font-semibold text-slate-500" data-testid={preview ? "expenses-analysis-preview-required-description" : "expenses-analysis-required-description"}>اختر الجهة والسنة، واختر الشهر عند العرض الشهري، لعرض التحليل.</p></div>
      ) : loading ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center" data-testid={preview ? "expenses-analysis-preview-loading-state" : "expenses-analysis-loading-state"}><p className="text-xl font-extrabold text-slate-950">جاري تحميل المصروفات...</p></div>
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-slate-200" data-testid={preview ? "expenses-analysis-preview-table-wrapper" : "expenses-analysis-table-wrapper"}>
            <Table data-testid={preview ? "expenses-analysis-preview-table" : "expenses-analysis-table"}>
              <TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950" data-testid={preview ? "expenses-analysis-preview-table-header-row" : "expenses-analysis-table-header-row"}><TableHead className="text-right font-extrabold text-white" data-testid={preview ? "expenses-analysis-preview-header-date" : "expenses-analysis-header-date"}>التاريخ</TableHead><TableHead className="text-right font-extrabold text-white" data-testid={preview ? "expenses-analysis-preview-header-statement" : "expenses-analysis-header-statement"}>البيان بالكامل من المصروفات</TableHead>{analysisCategories.map((category) => <TableHead key={category.key} className="text-right font-extrabold text-white" data-testid={`${preview ? "expenses-analysis-preview-header" : "expenses-analysis-header"}-${category.key}`}>{category.label}</TableHead>)}<TableHead className="text-right font-extrabold text-white" data-testid={preview ? "expenses-analysis-preview-header-row-total" : "expenses-analysis-header-row-total"}>إجمالي الصف</TableHead></TableRow></TableHeader>
              <TableBody>
                {visibleAnalysisRows.map((row) => <TableRow key={row.id} data-testid={`${preview ? "expenses-analysis-preview-row" : "expenses-analysis-row"}-${row.id}`}><TableCell className="font-bold" data-testid={`${preview ? "expenses-analysis-preview-row" : "expenses-analysis-row"}-${row.id}-date`}>{row.issued_at}</TableCell><TableCell className="min-w-72 font-bold" data-testid={`${preview ? "expenses-analysis-preview-row" : "expenses-analysis-row"}-${row.id}-statement`}><p>{row.gross_statement}</p><p className="mt-1 text-xs text-slate-500">إذن رقم {row.expense_number} — {row.bank_name}</p></TableCell>{analysisCategories.map((category) => <TableCell key={category.key} data-testid={`${preview ? "expenses-analysis-preview-row" : "expenses-analysis-row"}-${row.id}-${category.key}`}>{row.categoryAmounts[category.key] ? formatCurrency(row.categoryAmounts[category.key]) : "—"}</TableCell>)}<TableCell className="font-extrabold" data-testid={`${preview ? "expenses-analysis-preview-row" : "expenses-analysis-row"}-${row.id}-total`}>{formatCurrency(row.analysis_total)}</TableCell></TableRow>)}
                <TableRow className="bg-red-50 font-extrabold hover:bg-red-50" data-testid={preview ? "expenses-analysis-preview-grand-total-row" : "expenses-analysis-grand-total-row"}>
                  <TableCell data-testid={preview ? "expenses-analysis-preview-grand-total-date" : "expenses-analysis-grand-total-date"}>—</TableCell>
                  <TableCell className="text-lg" data-testid={preview ? "expenses-analysis-preview-grand-total-label" : "expenses-analysis-grand-total-label"}>الإجمالي العام</TableCell>
                  {analysisCategories.map((category) => <TableCell key={category.key} className="text-lg" data-testid={`${preview ? "expenses-analysis-preview-grand-total" : "expenses-analysis-grand-total"}-${category.key}`}>{formatEgpLabel(categoryTotals[category.key] || 0)}</TableCell>)}
                  <TableCell className="text-lg" data-testid={preview ? "expenses-analysis-preview-grand-total-row-total" : "expenses-analysis-grand-total-row-total"}>{formatEgpLabel(grandTotal)}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
          {visibleAnalysisRows.length === 0 && <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center" data-testid={preview ? "expenses-analysis-preview-empty-state" : "expenses-analysis-empty-state"}><p className="text-xl font-extrabold text-slate-950" data-testid={preview ? "expenses-analysis-preview-empty-title" : "expenses-analysis-empty-title"}>لا توجد مصروفات مطابقة لهذه الاختيارات</p></div>}
        </>
      )}
    </section>
  );

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="expenses-analysis-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="expenses-analysis-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="expenses-analysis-brand">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="expenses-analysis-brand-icon"><BarChart3 className="h-5 w-5" /></div>
            <div><p className="text-xs font-extrabold text-red-700" data-testid="expenses-analysis-eyebrow">تحليل المصروفات</p><h1 className="text-2xl font-extrabold" data-testid="expenses-analysis-title">تقرير تحليلي شهري وسنوي</h1></div>
          </div>
          <div className="flex flex-wrap items-center gap-3" data-testid="expenses-analysis-header-actions">
            <Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="expenses-analysis-user-badge">{user?.username}</Badge>
            <Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="expenses-analysis-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button>
            <Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="expenses-analysis-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button>
            <Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="expenses-analysis-logout-button"><LogOut className="h-4 w-4" /> خروج</Button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="expenses-analysis-content">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden" data-testid="expenses-analysis-filters-section">
          <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between" data-testid="expenses-analysis-filters-heading">
            <div><h2 className="text-3xl font-extrabold" data-testid="expenses-analysis-filters-title">اختيارات التقرير</h2><p className="mt-1 text-sm font-bold text-slate-500" data-testid="expenses-analysis-filters-description">التقرير يعتمد فقط على المصروفات المسجلة ولا يحتوي على إدخال بيانات.</p></div>
            <div className="flex flex-wrap items-center gap-2" data-testid="expenses-analysis-filter-actions">
              <PrintOrientationToggle orientation={orientation} onChange={setOrientation} testIdPrefix="expenses-analysis-orientation" />
              <Button type="button" onClick={loadExpenses} variant="outline" className="h-11 rounded-lg bg-white" data-testid="refresh-expenses-analysis-button"><RotateCcw className="h-4 w-4" /> تحديث</Button>
              <Button type="button" onClick={() => setPreviewOpen(true)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="preview-expenses-analysis-button"><Eye className="h-4 w-4" /> معاينة التقرير</Button>
              <Button type="button" onClick={exportToPdf} disabled={!hasCompletePeriod || loading} className="h-11 rounded-lg bg-slate-950 text-white disabled:opacity-50" data-testid="export-expenses-analysis-pdf-button"><FileDown className="h-4 w-4" /> PDF</Button>
              <Button type="button" onClick={exportToExcel} disabled={!hasCompletePeriod || loading} variant="outline" className="h-11 rounded-lg bg-white disabled:opacity-50" data-testid="export-expenses-analysis-excel-button"><FileSpreadsheet className="h-4 w-4" /> Excel</Button>
              <Button type="button" onClick={exportToWord} disabled={!hasCompletePeriod || loading} variant="outline" className="h-11 rounded-lg bg-white disabled:opacity-50" data-testid="export-expenses-analysis-word-button"><FileText className="h-4 w-4" /> Word</Button>
              <Button type="button" onClick={exportToPdf} className="h-11 rounded-lg bg-slate-950 text-white" data-testid="print-expenses-analysis-button"><Printer className="h-4 w-4" /> طباعة PDF</Button>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4" data-testid="expenses-analysis-filters-grid">
            <div data-testid="expenses-analysis-organization-wrapper"><Label data-testid="expenses-analysis-organization-label">الجهة</Label><select value={filters.organization_scope} onChange={(event) => updateFilter("organization_scope", event.target.value)} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="expenses-analysis-organization-select"><option value="general_union" data-testid="expenses-analysis-organization-general-option">{dynamicOrganizationLabels.general_union}</option><option value="social_solidarity_project" data-testid="expenses-analysis-organization-social-option">{dynamicOrganizationLabels.social_solidarity_project}</option></select></div>
            <div data-testid="expenses-analysis-period-wrapper"><Label data-testid="expenses-analysis-period-label">نوع العرض</Label><select value={filters.period_type} onChange={(event) => updateFilter("period_type", event.target.value)} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="expenses-analysis-period-select"><option value="monthly" data-testid="expenses-analysis-period-monthly-option">شهري</option><option value="yearly" data-testid="expenses-analysis-period-yearly-option">سنوي</option></select></div>
            <div data-testid="expenses-analysis-year-wrapper"><Label data-testid="expenses-analysis-year-label">السنة</Label><select value={filters.year} onChange={(event) => updateFilter("year", event.target.value)} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="expenses-analysis-year-select"><option value="" data-testid="expenses-analysis-year-placeholder-option">اختر السنة</option>{years.map((year) => <option key={year} value={year} data-testid={`expenses-analysis-year-option-${year}`}>{year}</option>)}</select></div>
            <div data-testid="expenses-analysis-month-wrapper"><Label data-testid="expenses-analysis-month-label">الشهر</Label><select value={filters.month} onChange={(event) => updateFilter("month", event.target.value)} disabled={filters.period_type === "yearly" || !filters.year} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold disabled:opacity-50" data-testid="expenses-analysis-month-select"><option value="" data-testid="expenses-analysis-month-placeholder-option">اختر الشهر</option>{months.map((month) => <option key={month} value={month} data-testid={`expenses-analysis-month-option-${month}`}>{monthLabels[month] || month}</option>)}</select></div>
          </div>
        </section>

        <ReportBody />
      </section>
      {previewOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 print:hidden" data-testid="expenses-analysis-preview-modal-overlay">
          <section className="w-full max-w-7xl rounded-xl bg-white p-4 shadow-2xl" role="dialog" aria-modal="true" data-testid="expenses-analysis-preview-modal">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3" data-testid="expenses-analysis-preview-modal-actions">
              <h3 className="text-2xl font-extrabold text-slate-950" data-testid="expenses-analysis-preview-modal-title">معاينة تقرير تحليل المصروفات</h3>
              <div className="flex flex-wrap items-center gap-2" data-testid="expenses-analysis-preview-modal-buttons">
                <PrintOrientationToggle orientation={orientation} onChange={setOrientation} testIdPrefix="expenses-analysis-preview-orientation" />
                <Button type="button" onClick={exportToPdf} className="h-11 rounded-lg bg-slate-950 text-white" data-testid="print-expenses-analysis-preview-button"><Printer className="h-4 w-4" /> طباعة PDF</Button>
                <Button type="button" onClick={exportToExcel} variant="outline" className="h-11 rounded-lg bg-white" data-testid="export-expenses-analysis-preview-excel-button"><FileSpreadsheet className="h-4 w-4" /> Excel</Button>
                <Button type="button" onClick={exportToWord} variant="outline" className="h-11 rounded-lg bg-white" data-testid="export-expenses-analysis-preview-word-button"><FileText className="h-4 w-4" /> Word</Button>
                <Button type="button" onClick={() => setPreviewOpen(false)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="close-expenses-analysis-preview-button"><X className="h-4 w-4" /> خروج من المعاينة</Button>
              </div>
            </div>
            <ReportBody preview />
          </section>
        </div>
      )}
      <footer className="px-4 pb-5 print:hidden" data-testid="expenses-analysis-footer"><CreditLine testId="expenses-analysis-creator-credit" /></footer>
    </main>
  );
}