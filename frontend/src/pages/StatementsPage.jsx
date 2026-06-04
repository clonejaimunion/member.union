import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { FileSpreadsheet, Landmark, Percent, Sigma, WalletCards } from "lucide-react";
import { BankShell } from "@/components/BankShell";
import { ExportReportButtons } from "@/components/ExportReportButtons";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatCurrency, formatNumber } from "@/lib/format";
import { useAuth } from "@/contexts/AuthContext";

const monthOptions = [
  ["01", "يناير"],
  ["02", "فبراير"],
  ["03", "مارس"],
  ["04", "أبريل"],
  ["05", "مايو"],
  ["06", "يونيو"],
  ["07", "يوليو"],
  ["08", "أغسطس"],
  ["09", "سبتمبر"],
  ["10", "أكتوبر"],
  ["11", "نوفمبر"],
  ["12", "ديسمبر"],
];
const monthLabels = Object.fromEntries(monthOptions);
const statusLabels = { active: "نشطة", matured: "مستحقة", renewed: "مجددة", closed: "مغلقة" };
const currentDate = new Date();
const firstReportYear = 2025;
const yearOptions = Array.from({ length: Math.max(currentDate.getFullYear() + 10, 2035) - firstReportYear + 1 }, (_, index) => String(firstReportYear + index));
const defaultDetailedFilter = { period_type: "yearly", year: String(Math.max(currentDate.getFullYear(), firstReportYear)), month: String(currentDate.getMonth() + 1).padStart(2, "0") };
const defaultPreviousFilter = { period_type: "yearly", year: String(Math.max(currentDate.getFullYear() - 1, firstReportYear)), month: String(currentDate.getMonth() + 1).padStart(2, "0") };
const yearValues = new Set(yearOptions);
const monthValues = new Set(monthOptions.map(([value]) => value));

const normalizeFilterPreference = (value, fallback) => {
  const periodType = value?.period_type === "monthly" ? "monthly" : "yearly";
  const year = yearValues.has(String(value?.year)) ? String(value.year) : fallback.year;
  const month = monthValues.has(String(value?.month).padStart(2, "0")) ? String(value.month).padStart(2, "0") : fallback.month;
  return { period_type: periodType, year, month };
};

export default function StatementsPage() {
  const { bankId } = useParams();
  const { user } = useAuth();
  const [detailed, setDetailed] = useState(null);
  const [volume, setVolume] = useState(null);
  const [deposits, setDeposits] = useState([]);
  const [selectedDepositId, setSelectedDepositId] = useState("all");
  const [detailedFilter, setDetailedFilter] = useState(defaultDetailedFilter);
  const [draftDetailedFilter, setDraftDetailedFilter] = useState(defaultDetailedFilter);
  const [previousFilter, setPreviousFilter] = useState(defaultPreviousFilter);
  const [draftPreviousFilter, setDraftPreviousFilter] = useState(defaultPreviousFilter);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const filterStorageKey = useMemo(() => user?.id ? `bank-statement-filters:${user.id}:${bankId}` : null, [user?.id, bankId]);

  useEffect(() => {
    setPreferencesLoaded(false);
    if (!filterStorageKey) return;
    try {
      const saved = JSON.parse(window.localStorage.getItem(filterStorageKey) || "{}");
      const nextDetailed = normalizeFilterPreference(saved.detailedFilter, defaultDetailedFilter);
      const nextPrevious = normalizeFilterPreference(saved.previousFilter, defaultPreviousFilter);
      setDetailedFilter(nextDetailed);
      setDraftDetailedFilter(nextDetailed);
      setPreviousFilter(nextPrevious);
      setDraftPreviousFilter(nextPrevious);
    } catch {
      setDetailedFilter(defaultDetailedFilter);
      setDraftDetailedFilter(defaultDetailedFilter);
      setPreviousFilter(defaultPreviousFilter);
      setDraftPreviousFilter(defaultPreviousFilter);
    } finally {
      setPreferencesLoaded(true);
    }
  }, [filterStorageKey]);

  useEffect(() => {
    if (!filterStorageKey || !preferencesLoaded) return;
    window.localStorage.setItem(filterStorageKey, JSON.stringify({ detailedFilter, previousFilter }));
  }, [filterStorageKey, preferencesLoaded, detailedFilter, previousFilter]);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({
      period_type: detailedFilter.period_type,
      year: detailedFilter.year,
      previous_period_type: previousFilter.period_type,
      previous_year: previousFilter.year,
    });
    if (detailedFilter.period_type === "monthly") params.set("month", String(Number(detailedFilter.month)));
    if (previousFilter.period_type === "monthly") params.set("previous_month", String(Number(previousFilter.month)));
    Promise.all([
      api.get(`/banks/${bankId}/statements/detailed?${params.toString()}`),
      api.get(`/banks/${bankId}/statements/volume?${new URLSearchParams({ period_type: detailedFilter.period_type, year: detailedFilter.year, ...(detailedFilter.period_type === "monthly" ? { month: String(Number(detailedFilter.month)) } : {}) }).toString()}`),
      api.get(`/banks/${bankId}/deposits`),
    ]).then(([detailedResponse, volumeResponse, depositsResponse]) => {
      setDetailed(detailedResponse.data);
      setVolume(volumeResponse.data);
      setDeposits(depositsResponse.data);
    }).catch(() => {
      setDetailed(null);
      setVolume(null);
      setDeposits([]);
    }).finally(() => setLoading(false));
  }, [bankId, detailedFilter, previousFilter]);

  const filteredDetailedRows = useMemo(() => {
    const rows = detailed?.rows || [];
    return selectedDepositId === "all" ? rows : rows.filter((row) => row.deposit_id === selectedDepositId);
  }, [detailed, selectedDepositId]);

  const filteredVolumeRows = useMemo(() => {
    const rows = volume?.rows || [];
    return selectedDepositId === "all" ? rows : rows.filter((row) => row.deposit_id === selectedDepositId);
  }, [volume, selectedDepositId]);

  const filteredTotals = useMemo(() => ({
    volume: filteredDetailedRows.reduce((sum, row) => sum + row.amount, 0),
    current: filteredDetailedRows.reduce((sum, row) => sum + row.current_year_interest, 0),
    previous: filteredDetailedRows.reduce((sum, row) => sum + row.previous_years_interest, 0),
    count: filteredDetailedRows.length,
  }), [filteredDetailedRows]);

  const detailedPeriodLabel = detailedFilter.period_type === "monthly" ? `${monthLabels[detailedFilter.month]} / ${detailedFilter.year}` : `سنة ${detailedFilter.year}`;
  const previousPeriodLabel = previousFilter.period_type === "monthly" ? `${monthLabels[previousFilter.month]} / ${previousFilter.year}` : `سنة ${previousFilter.year}`;
  const combinedPeriodLabel = `عائد الفترة: ${detailedPeriodLabel} — مستحق سنوات سابقة: ${previousPeriodLabel}`;
  const totalCurrentInterest = useMemo(() => filteredDetailedRows.reduce((sum, row) => sum + Number(row.current_year_interest || 0), 0), [filteredDetailedRows]);
  const formatActiveStatus = (row) => {
    const baseLabel = statusLabels[row.status] || "نشطة";
    if (row.status === "active" && row.maturity_date) return `${baseLabel} حتى ${row.maturity_date}`;
    return baseLabel;
  };

  return (
    <BankShell>
      <div className="space-y-6" data-testid="statements-page">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8" data-testid="statements-heading-section">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm font-extrabold text-emerald-700" data-testid="statements-eyebrow">كشوف تفريغية مفصلة</p>
              <h2 className="mt-2 text-3xl font-extrabold text-slate-950 sm:text-4xl" data-testid="statements-title">إجماليات الودائع والعوائد لكل وديعة</h2>
              <p className="mt-3 max-w-3xl text-base font-semibold leading-8 text-slate-600" data-testid="statements-description">
                كشف مستقل للبنك الحالي يعرض إجمالي العائد حسب الشهر أو السنة، مع حساب كل شهر من العائد السنوي ÷ 365 × أيام الشهر من التقويم.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2" data-testid="statements-heading-actions">
              <Badge className="w-fit border-slate-200 bg-slate-50 px-4 py-2 text-slate-700 hover:bg-slate-50" data-testid="statements-bank-badge">
                <Landmark className="ml-2 h-4 w-4" /> {detailed?.bank?.name || "—"}
              </Badge>
              <ExportReportButtons
                title={`الكشوف التفريغية - ${detailed?.bank?.name || bankId}`}
                fileName={`الكشوف-التفريغية-${detailed?.bank?.name || bankId}`}
                selectors={["[data-testid='statements-heading-section']", "[data-testid='statements-kpi-grid']", "[data-testid='detailed-interest-statement-section']", "[data-testid='volume-statement-section']"]}
                disabled={!detailed || loading}
                pdfTestId="print-statements-pdf-button"
                excelTestId="export-statements-excel-button"
                wordTestId="export-statements-word-button"
              />
            </div>
          </div>
        </section>

        {loading ? (
          <section className="rounded-xl border border-slate-200 bg-white p-10 text-center font-extrabold" data-testid="statements-loading-state">جاري تحميل الكشوف...</section>
        ) : detailed ? (
          <>
            <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="statements-kpi-grid">
              <div className="rounded-xl bg-slate-950 p-5 text-white" data-testid="statement-kpi-volume">
                <WalletCards className="mb-3 h-6 w-6" />
                <p className="text-sm font-bold text-slate-300" data-testid="statement-kpi-volume-label">إجمالي حجم الودائع</p>
                <p className="mt-2 text-2xl font-extrabold" data-testid="statement-kpi-volume-value">{formatCurrency(filteredTotals.volume)}</p>
              </div>
              <div className="rounded-xl bg-emerald-50 p-5 text-emerald-900" data-testid="statement-kpi-current">
                <Sigma className="mb-3 h-6 w-6" />
                <p className="text-sm font-bold text-emerald-700" data-testid="statement-kpi-current-label">عائد الفترة المختارة</p>
                <p className="mt-1 text-xs font-extrabold text-emerald-700" data-testid="statement-kpi-current-period">{detailedPeriodLabel}</p>
                <p className="mt-2 text-2xl font-extrabold" data-testid="statement-kpi-current-value">{formatCurrency(filteredTotals.current)}</p>
              </div>
              <div className="rounded-xl bg-amber-50 p-5 text-amber-950" data-testid="statement-kpi-previous">
                <FileSpreadsheet className="mb-3 h-6 w-6" />
                <p className="text-sm font-bold text-amber-700" data-testid="statement-kpi-previous-label">مستحق سنوات سابقة</p>
                <p className="mt-1 text-xs font-extrabold text-amber-700" data-testid="statement-kpi-previous-period">{previousPeriodLabel}</p>
                <p className="mt-2 text-2xl font-extrabold" data-testid="statement-kpi-previous-value">{formatCurrency(filteredTotals.previous)}</p>
              </div>
              <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200" data-testid="statement-kpi-count">
                <Percent className="mb-3 h-6 w-6 text-slate-700" />
                <p className="text-sm font-bold text-slate-500" data-testid="statement-kpi-count-label">عدد الودائع</p>
                <p className="mt-2 text-2xl font-extrabold text-slate-950" data-testid="statement-kpi-count-value">{formatNumber(filteredTotals.count)}</p>
              </div>
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="statements-deposit-picker-section">
              <h3 className="mb-4 text-xl font-extrabold text-slate-950" data-testid="statements-deposit-picker-title">اختيار الوديعة بالفأرة</h3>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4" data-testid="statements-deposit-picker-grid">
                <button type="button" onClick={() => setSelectedDepositId("all")} className={`rounded-xl border p-4 text-right font-extrabold ${selectedDepositId === "all" ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-slate-50 text-slate-800"}`} data-testid="statements-deposit-all-button">كل الودائع</button>
                {deposits.map((deposit) => (
                  <button key={deposit.id} type="button" onClick={() => setSelectedDepositId(deposit.id)} className={`rounded-xl border p-4 text-right transition-transform hover:-translate-y-0.5 ${selectedDepositId === deposit.id ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-slate-50 text-slate-800 hover:bg-white"}`} data-testid={`statements-deposit-button-${deposit.id}`}>
                    <p className="text-xs font-bold opacity-70" data-testid={`statements-deposit-button-${deposit.id}-label`}>رقم الوديعة</p>
                    <p className="mt-1 text-lg font-extrabold" data-testid={`statements-deposit-button-${deposit.id}-number`}>{deposit.deposit_number}</p>
                  </button>
                ))}
              </div>
            </section>

            <section className="space-y-4" data-testid="detailed-interest-statement-section">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between" data-testid="detailed-interest-statement-heading">
                <div data-testid="detailed-interest-title-block">
                  <h3 className="text-2xl font-extrabold text-slate-950" data-testid="detailed-interest-statement-title">كشف العوائد التفريغي</h3>
                  <p className="mt-1 text-sm font-bold text-slate-500" data-testid="detailed-interest-period-label">عائد الفترة: {detailedPeriodLabel}</p>
                </div>
                <div className="flex flex-wrap items-end gap-3 print:hidden" data-testid="detailed-interest-actions">
                  <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 p-3" data-testid="current-interest-filter-panel">
                    <p className="mb-2 text-xs font-extrabold text-emerald-700" data-testid="current-interest-filter-title">تصفية عائد الفترة</p>
                    <div className="flex flex-wrap items-end gap-2" data-testid="current-interest-filter-controls">
                      <div data-testid="detailed-interest-period-type-wrapper">
                        <label className="mb-1 block text-xs font-extrabold text-slate-500" data-testid="detailed-interest-period-type-label">عرض العائد</label>
                        <select value={draftDetailedFilter.period_type} onChange={(event) => setDraftDetailedFilter((current) => ({ ...current, period_type: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-extrabold" data-testid="detailed-interest-period-type-select"><option value="yearly" data-testid="detailed-interest-period-yearly-option">سنوي</option><option value="monthly" data-testid="detailed-interest-period-monthly-option">شهري</option></select>
                      </div>
                      <div data-testid="detailed-interest-year-wrapper">
                        <label className="mb-1 block text-xs font-extrabold text-slate-500" data-testid="detailed-interest-year-label">السنة</label>
                        <select value={draftDetailedFilter.year} onChange={(event) => setDraftDetailedFilter((current) => ({ ...current, year: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-extrabold" data-testid="detailed-interest-year-select">{yearOptions.map((year) => <option key={year} value={year} data-testid={`detailed-interest-year-option-${year}`}>{year}</option>)}</select>
                      </div>
                      <div data-testid="detailed-interest-month-wrapper">
                        <label className="mb-1 block text-xs font-extrabold text-slate-500" data-testid="detailed-interest-month-label">الشهر</label>
                        <select value={draftDetailedFilter.month} onChange={(event) => setDraftDetailedFilter((current) => ({ ...current, month: event.target.value }))} disabled={draftDetailedFilter.period_type === "yearly"} className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-extrabold disabled:opacity-50" data-testid="detailed-interest-month-select">{monthOptions.map(([value, label]) => <option key={value} value={value} data-testid={`detailed-interest-month-option-${value}`}>{label}</option>)}</select>
                      </div>
                      <button type="button" onClick={() => setDetailedFilter(draftDetailedFilter)} className="h-11 rounded-lg bg-emerald-700 px-4 text-sm font-extrabold text-white transition-transform hover:-translate-y-0.5" data-testid="apply-current-interest-filter-button">تطبيق العائد</button>
                    </div>
                  </div>
                  <div className="rounded-xl border border-amber-100 bg-amber-50/70 p-3" data-testid="previous-interest-filter-panel">
                    <p className="mb-2 text-xs font-extrabold text-amber-700" data-testid="previous-interest-filter-title">تصفية مستحق سنوات سابقة</p>
                    <div className="flex flex-wrap items-end gap-2" data-testid="previous-interest-filter-controls">
                      <div data-testid="previous-interest-period-type-wrapper">
                        <label className="mb-1 block text-xs font-extrabold text-slate-500" data-testid="previous-interest-period-type-label">عرض المستحق</label>
                        <select value={draftPreviousFilter.period_type} onChange={(event) => setDraftPreviousFilter((current) => ({ ...current, period_type: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-extrabold" data-testid="previous-interest-period-type-select"><option value="yearly" data-testid="previous-interest-period-yearly-option">سنوي</option><option value="monthly" data-testid="previous-interest-period-monthly-option">شهري</option></select>
                      </div>
                      <div data-testid="previous-interest-year-wrapper">
                        <label className="mb-1 block text-xs font-extrabold text-slate-500" data-testid="previous-interest-year-label">السنة</label>
                        <select value={draftPreviousFilter.year} onChange={(event) => setDraftPreviousFilter((current) => ({ ...current, year: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-extrabold" data-testid="previous-interest-year-select">{yearOptions.map((year) => <option key={year} value={year} data-testid={`previous-interest-year-option-${year}`}>{year}</option>)}</select>
                      </div>
                      <div data-testid="previous-interest-month-wrapper">
                        <label className="mb-1 block text-xs font-extrabold text-slate-500" data-testid="previous-interest-month-label">الشهر</label>
                        <select value={draftPreviousFilter.month} onChange={(event) => setDraftPreviousFilter((current) => ({ ...current, month: event.target.value }))} disabled={draftPreviousFilter.period_type === "yearly"} className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm font-extrabold disabled:opacity-50" data-testid="previous-interest-month-select">{monthOptions.map(([value, label]) => <option key={value} value={value} data-testid={`previous-interest-month-option-${value}`}>{label}</option>)}</select>
                      </div>
                      <button type="button" onClick={() => setPreviousFilter(draftPreviousFilter)} className="h-11 rounded-lg bg-amber-600 px-4 text-sm font-extrabold text-white transition-transform hover:-translate-y-0.5" data-testid="apply-previous-interest-filter-button">تطبيق المستحق</button>
                    </div>
                  </div>
                  <ExportReportButtons
                    title={`كشف العوائد التفريغي - ${detailed?.bank?.name || bankId} - ${detailedPeriodLabel}${selectedDepositId === "all" ? "" : ` - وديعة رقم ${deposits.find((deposit) => deposit.id === selectedDepositId)?.deposit_number || ""}`}`}
                    fileName={`كشف-العوائد-التفريغي-${detailed?.bank?.name || bankId}-${detailedPeriodLabel}`}
                    selectors={["[data-testid='detailed-interest-print-report']"]}
                    printSelectors={["[data-testid='detailed-interest-print-report']"]}
                    disabled={!detailed || loading}
                    pdfLabel="طباعة PDF"
                    pdfTestId="print-detailed-interest-pdf-button"
                    excelTestId="export-detailed-interest-excel-button"
                    wordTestId="export-detailed-interest-word-button"
                  />
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:border-0 print:shadow-none" data-testid="detailed-interest-print-report">
                <div className="mb-4 flex flex-col gap-2 border-b border-slate-200 pb-3 sm:flex-row sm:items-center sm:justify-between" data-testid="detailed-interest-print-header">
                  <div>
                    <p className="text-xs font-extrabold text-emerald-700" data-testid="detailed-interest-print-eyebrow">كشف العوائد التفريغي</p>
                    <h3 className="text-2xl font-extrabold text-slate-950" data-testid="detailed-interest-print-title">{detailed?.bank?.name || "—"} — {selectedDepositId === "all" ? "كل الودائع" : `وديعة رقم ${deposits.find((deposit) => deposit.id === selectedDepositId)?.deposit_number || ""}`}</h3>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-sm font-extrabold text-slate-700" data-testid="detailed-interest-print-meta">
                    <span data-testid="detailed-interest-print-period">{detailedPeriodLabel}</span>
                    <span data-testid="detailed-interest-print-rows-count">عدد الودائع: {filteredDetailedRows.length}</span>
                  </div>
                </div>
                <div className="overflow-hidden rounded-xl border border-slate-200" data-testid="detailed-interest-print-table-wrapper">
                  <Table data-testid="detailed-interest-print-table">
                    <TableHeader className="bg-slate-950">
                      <TableRow className="hover:bg-slate-950" data-testid="detailed-interest-print-header-row">
                        <TableHead className="text-right font-extrabold text-white" data-testid="detailed-interest-print-header-serial">مسلسل</TableHead>
                        <TableHead className="text-right font-extrabold text-white" data-testid="detailed-interest-print-header-deposit">رقم الوديعة</TableHead>
                        <TableHead className="text-right font-extrabold text-white" data-testid="detailed-interest-print-header-status">الحالة</TableHead>
                        <TableHead className="text-right font-extrabold text-white" data-testid="detailed-interest-print-header-amount">مبلغ الوديعة</TableHead>
                        <TableHead className="text-right font-extrabold text-white" data-testid="detailed-interest-print-header-interest">عائد {detailedPeriodLabel}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredDetailedRows.length === 0 && (
                        <TableRow data-testid="detailed-interest-print-empty-row"><TableCell colSpan={5} className="py-6 text-center font-extrabold text-slate-500">لا توجد ودائع مطابقة للفلتر</TableCell></TableRow>
                      )}
                      {filteredDetailedRows.map((row) => (
                        <TableRow key={row.deposit_id} data-testid={`detailed-interest-print-row-${row.deposit_id}`}>
                          <TableCell data-testid={`detailed-interest-print-row-${row.deposit_id}-serial`}>{row.serial}</TableCell>
                          <TableCell className="font-extrabold" data-testid={`detailed-interest-print-row-${row.deposit_id}-deposit`}>{row.deposit_number}</TableCell>
                          <TableCell className="font-bold" data-testid={`detailed-interest-print-row-${row.deposit_id}-status`}>{formatActiveStatus(row)}</TableCell>
                          <TableCell data-testid={`detailed-interest-print-row-${row.deposit_id}-amount`}>{formatCurrency(row.amount)}</TableCell>
                          <TableCell className="font-extrabold text-emerald-800" data-testid={`detailed-interest-print-row-${row.deposit_id}-interest`}>{formatCurrency(row.current_year_interest)}</TableCell>
                        </TableRow>
                      ))}
                      <TableRow className="border-t-2 border-slate-300 bg-emerald-50 hover:bg-emerald-50" data-testid="detailed-interest-print-grand-total-row">
                        <TableCell colSpan={4} className="text-lg font-extrabold text-slate-950" data-testid="detailed-interest-print-grand-total-label">إجمالي العائد عن {detailedPeriodLabel}</TableCell>
                        <TableCell className="text-lg font-extrabold text-slate-950" data-testid="detailed-interest-print-grand-total-value">{formatCurrency(totalCurrentInterest)}</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </div>
              </div>

              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm print:hidden" data-testid="detailed-interest-table-wrapper">
                <Table data-testid="detailed-interest-table">
                  <TableHeader className="bg-slate-950">
                    <TableRow className="hover:bg-slate-950" data-testid="detailed-interest-header-row">
                      {['مسلسل', 'رقم الوديعة', 'الحالة', 'رقم الحساب', 'مبلغ الوديعة', 'العائد السنوي', `عائد ${detailedPeriodLabel}`, `مستحق ${previousPeriodLabel}`, 'الإجمالي المستحق للفترات المختارة', 'ملاحظات'].map((title) => (
                        <TableHead key={title} className="text-right font-extrabold text-white" data-testid={`detailed-interest-header-${title}`}>{title}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredDetailedRows.map((row) => (
                      <TableRow key={row.deposit_id} data-testid={`detailed-interest-row-${row.deposit_id}`}>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-serial`}>{row.serial}</TableCell>
                        <TableCell className="font-extrabold" data-testid={`detailed-interest-row-${row.deposit_id}-deposit-number`}>{row.deposit_number}</TableCell>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-status`}>{statusLabels[row.status] || "نشطة"}</TableCell>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-account-number`}>{row.account_number}</TableCell>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-amount`}>{formatCurrency(row.amount)}</TableCell>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-monthly-interest`}>{formatCurrency(row.monthly_interest_amount)}</TableCell>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-current-interest`}>{formatCurrency(row.current_year_interest)}</TableCell>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-previous-interest`}>{formatCurrency(row.previous_years_interest)}</TableCell>
                        <TableCell className="font-extrabold" data-testid={`detailed-interest-row-${row.deposit_id}-total-due`}>{formatCurrency(row.total_due_interest)}</TableCell>
                        <TableCell className="max-w-xs whitespace-pre-wrap text-xs font-bold" data-testid={`detailed-interest-row-${row.deposit_id}-notes`}>{row.renewal_notes || "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </section>

            <section className="space-y-4" data-testid="volume-statement-section">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" data-testid="volume-statement-heading">
                <h3 className="text-2xl font-extrabold text-slate-950" data-testid="volume-statement-title">كشف إجمالي حجم الودائع</h3>
                <ExportReportButtons
                  title={`كشف إجمالي حجم الودائع - ${volume?.bank?.name || detailed?.bank?.name || bankId}`}
                  fileName={`كشف-إجمالي-حجم-الودائع-${volume?.bank?.name || detailed?.bank?.name || bankId}`}
                  selectors={["[data-testid='volume-statement-section']"]}
                  printSelectors={["[data-testid='volume-statement-section']"]}
                  disabled={!volume || loading}
                  pdfLabel="طباعة PDF"
                  pdfTestId="print-volume-statement-pdf-button"
                  excelTestId="export-volume-statement-excel-button"
                  wordTestId="export-volume-statement-word-button"
                />
              </div>
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="volume-table-wrapper">
                <Table data-testid="volume-table">
                  <TableHeader className="bg-emerald-700">
                    <TableRow className="hover:bg-emerald-700" data-testid="volume-header-row">
                      {['مسلسل', 'رقم الوديعة', 'الحالة', 'رقم الحساب', 'مبلغ الوديعة', 'نسبة الفائدة السنوية', 'العائد السنوي', 'ملاحظات'].map((title) => (
                        <TableHead key={title} className="text-right font-extrabold text-white" data-testid={`volume-header-${title}`}>{title}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredVolumeRows.map((row) => (
                      <TableRow key={row.deposit_id} data-testid={`volume-row-${row.deposit_id}`}>
                        <TableCell data-testid={`volume-row-${row.deposit_id}-serial`}>{row.serial}</TableCell>
                        <TableCell className="font-extrabold" data-testid={`volume-row-${row.deposit_id}-deposit-number`}>{row.deposit_number}</TableCell>
                        <TableCell data-testid={`volume-row-${row.deposit_id}-status`}>{row.status === "active" && row.maturity_date ? `نشطة حتى ${row.maturity_date}` : (statusLabels[row.status] || "نشطة")}</TableCell>
                        <TableCell data-testid={`volume-row-${row.deposit_id}-account-number`}>{row.account_number}</TableCell>
                        <TableCell className="font-extrabold" data-testid={`volume-row-${row.deposit_id}-amount`}>{formatCurrency(row.amount)}</TableCell>
                        <TableCell data-testid={`volume-row-${row.deposit_id}-rate`}>{formatNumber(row.monthly_interest_rate)}%</TableCell>
                        <TableCell data-testid={`volume-row-${row.deposit_id}-monthly-interest`}>{formatCurrency(row.monthly_interest_amount)}</TableCell>
                        <TableCell className="max-w-xs whitespace-pre-wrap text-xs font-bold" data-testid={`volume-row-${row.deposit_id}-notes`}>{row.renewal_notes || "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </section>
          </>
        ) : (
          <section className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center" data-testid="statements-empty-state">
            <p className="text-2xl font-extrabold text-slate-950" data-testid="statements-empty-title">لا توجد بيانات كافية للكشوف</p>
            <p className="mt-3 text-base font-semibold text-slate-500" data-testid="statements-empty-description">سجل ودائع لهذا البنك أولاً حتى تظهر الكشوف التفريغية.</p>
          </section>
        )}
      </div>
    </BankShell>
  );
}
