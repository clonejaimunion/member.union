import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { FileSpreadsheet, Landmark, Percent, Sigma, WalletCards } from "lucide-react";
import { BankShell } from "@/components/BankShell";
import { ExportReportButtons } from "@/components/ExportReportButtons";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatCurrency, formatNumber } from "@/lib/format";

export default function StatementsPage() {
  const { bankId } = useParams();
  const [detailed, setDetailed] = useState(null);
  const [volume, setVolume] = useState(null);
  const [deposits, setDeposits] = useState([]);
  const [selectedDepositId, setSelectedDepositId] = useState("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/banks/${bankId}/statements/detailed`),
      api.get(`/banks/${bankId}/statements/volume`),
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
  }, [bankId]);

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

  return (
    <BankShell>
      <div className="space-y-6" data-testid="statements-page">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8" data-testid="statements-heading-section">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm font-extrabold text-emerald-700" data-testid="statements-eyebrow">كشوف تفريغية مفصلة</p>
              <h2 className="mt-2 text-3xl font-extrabold text-slate-950 sm:text-4xl" data-testid="statements-title">إجماليات الودائع والعوائد لكل وديعة</h2>
              <p className="mt-3 max-w-3xl text-base font-semibold leading-8 text-slate-600" data-testid="statements-description">
                كشف مستقل للبنك الحالي يعرض إجمالي العائد عن السنة الحالية والمستحق عن السنوات السابقة، مع حساب كل شهر من العائد السنوي ÷ عدد أيام السنة الفعلية × أيام الشهر من التقويم.
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
                <p className="text-sm font-bold text-emerald-700" data-testid="statement-kpi-current-label">عائد السنة الحالية</p>
                <p className="mt-2 text-2xl font-extrabold" data-testid="statement-kpi-current-value">{formatCurrency(filteredTotals.current)}</p>
              </div>
              <div className="rounded-xl bg-amber-50 p-5 text-amber-950" data-testid="statement-kpi-previous">
                <FileSpreadsheet className="mb-3 h-6 w-6" />
                <p className="text-sm font-bold text-amber-700" data-testid="statement-kpi-previous-label">مستحق سنوات سابقة</p>
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
              <h3 className="text-2xl font-extrabold text-slate-950" data-testid="detailed-interest-statement-title">كشف العوائد التفريغي</h3>
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="detailed-interest-table-wrapper">
                <Table data-testid="detailed-interest-table">
                  <TableHeader className="bg-slate-950">
                    <TableRow className="hover:bg-slate-950" data-testid="detailed-interest-header-row">
                      {['مسلسل', 'رقم الوديعة', 'رقم الحساب', 'مبلغ الوديعة', 'العائد السنوي', 'عائد السنة الحالية', 'مستحق سنوات سابقة', 'الإجمالي المستحق'].map((title) => (
                        <TableHead key={title} className="text-right font-extrabold text-white" data-testid={`detailed-interest-header-${title}`}>{title}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredDetailedRows.map((row) => (
                      <TableRow key={row.deposit_id} data-testid={`detailed-interest-row-${row.deposit_id}`}>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-serial`}>{row.serial}</TableCell>
                        <TableCell className="font-extrabold" data-testid={`detailed-interest-row-${row.deposit_id}-deposit-number`}>{row.deposit_number}</TableCell>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-account-number`}>{row.account_number}</TableCell>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-amount`}>{formatCurrency(row.amount)}</TableCell>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-monthly-interest`}>{formatCurrency(row.monthly_interest_amount)}</TableCell>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-current-interest`}>{formatCurrency(row.current_year_interest)}</TableCell>
                        <TableCell data-testid={`detailed-interest-row-${row.deposit_id}-previous-interest`}>{formatCurrency(row.previous_years_interest)}</TableCell>
                        <TableCell className="font-extrabold" data-testid={`detailed-interest-row-${row.deposit_id}-total-due`}>{formatCurrency(row.total_due_interest)}</TableCell>
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
                      {['مسلسل', 'رقم الوديعة', 'رقم الحساب', 'مبلغ الوديعة', 'نسبة الفائدة السنوية', 'العائد السنوي'].map((title) => (
                        <TableHead key={title} className="text-right font-extrabold text-white" data-testid={`volume-header-${title}`}>{title}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredVolumeRows.map((row) => (
                      <TableRow key={row.deposit_id} data-testid={`volume-row-${row.deposit_id}`}>
                        <TableCell data-testid={`volume-row-${row.deposit_id}-serial`}>{row.serial}</TableCell>
                        <TableCell className="font-extrabold" data-testid={`volume-row-${row.deposit_id}-deposit-number`}>{row.deposit_number}</TableCell>
                        <TableCell data-testid={`volume-row-${row.deposit_id}-account-number`}>{row.account_number}</TableCell>
                        <TableCell className="font-extrabold" data-testid={`volume-row-${row.deposit_id}-amount`}>{formatCurrency(row.amount)}</TableCell>
                        <TableCell data-testid={`volume-row-${row.deposit_id}-rate`}>{formatNumber(row.monthly_interest_rate)}%</TableCell>
                        <TableCell data-testid={`volume-row-${row.deposit_id}-monthly-interest`}>{formatCurrency(row.monthly_interest_amount)}</TableCell>
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
