import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { FileSpreadsheet, Landmark, Percent, Sigma, WalletCards } from "lucide-react";
import { BankShell } from "@/components/BankShell";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatCurrency, formatNumber } from "@/lib/format";

export default function StatementsPage() {
  const { bankId } = useParams();
  const [detailed, setDetailed] = useState(null);
  const [volume, setVolume] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/banks/${bankId}/statements/detailed`),
      api.get(`/banks/${bankId}/statements/volume`),
    ]).then(([detailedResponse, volumeResponse]) => {
      setDetailed(detailedResponse.data);
      setVolume(volumeResponse.data);
    }).catch(() => {
      setDetailed(null);
      setVolume(null);
    }).finally(() => setLoading(false));
  }, [bankId]);

  return (
    <BankShell>
      <div className="space-y-6" data-testid="statements-page">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8" data-testid="statements-heading-section">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm font-extrabold text-emerald-700" data-testid="statements-eyebrow">كشوف تفريغية مفصلة</p>
              <h2 className="mt-2 text-3xl font-extrabold text-slate-950 sm:text-4xl" data-testid="statements-title">إجماليات الودائع والعوائد لكل وديعة</h2>
              <p className="mt-3 max-w-3xl text-base font-semibold leading-8 text-slate-600" data-testid="statements-description">
                كشف مستقل للبنك الحالي يعرض إجمالي العائد عن السنة الحالية والمستحق عن السنوات السابقة، مع حساب كل شهر من العائد السنوي ÷ 365 × أيام الشهر المستحقة بحد أقصى 30 يومًا للشهر الكامل.
              </p>
            </div>
            <Badge className="w-fit border-slate-200 bg-slate-50 px-4 py-2 text-slate-700 hover:bg-slate-50" data-testid="statements-bank-badge">
              <Landmark className="ml-2 h-4 w-4" /> {detailed?.bank?.name || "—"}
            </Badge>
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
                <p className="mt-2 text-2xl font-extrabold" data-testid="statement-kpi-volume-value">{formatCurrency(detailed.total_deposit_volume)}</p>
              </div>
              <div className="rounded-xl bg-emerald-50 p-5 text-emerald-900" data-testid="statement-kpi-current">
                <Sigma className="mb-3 h-6 w-6" />
                <p className="text-sm font-bold text-emerald-700" data-testid="statement-kpi-current-label">عائد السنة الحالية</p>
                <p className="mt-2 text-2xl font-extrabold" data-testid="statement-kpi-current-value">{formatCurrency(detailed.total_current_year_interest)}</p>
              </div>
              <div className="rounded-xl bg-amber-50 p-5 text-amber-950" data-testid="statement-kpi-previous">
                <FileSpreadsheet className="mb-3 h-6 w-6" />
                <p className="text-sm font-bold text-amber-700" data-testid="statement-kpi-previous-label">مستحق سنوات سابقة</p>
                <p className="mt-2 text-2xl font-extrabold" data-testid="statement-kpi-previous-value">{formatCurrency(detailed.total_previous_years_interest)}</p>
              </div>
              <div className="rounded-xl bg-white p-5 ring-1 ring-slate-200" data-testid="statement-kpi-count">
                <Percent className="mb-3 h-6 w-6 text-slate-700" />
                <p className="text-sm font-bold text-slate-500" data-testid="statement-kpi-count-label">عدد الودائع</p>
                <p className="mt-2 text-2xl font-extrabold text-slate-950" data-testid="statement-kpi-count-value">{formatNumber(detailed.deposits_count)}</p>
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
                    {detailed.rows.map((row) => (
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
              <h3 className="text-2xl font-extrabold text-slate-950" data-testid="volume-statement-title">كشف إجمالي حجم الودائع</h3>
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
                    {(volume?.rows || []).map((row) => (
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
