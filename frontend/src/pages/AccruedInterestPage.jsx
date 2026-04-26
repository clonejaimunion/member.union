import { useEffect, useMemo, useState } from "react";
import { Printer, ReceiptText, Sigma } from "lucide-react";
import { useParams, useSearchParams } from "react-router-dom";
import { BankShell } from "@/components/BankShell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatCurrency, formatDateTime, formatNumber } from "@/lib/format";

export default function AccruedInterestPage() {
  const { bankId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const selectedYear = searchParams.get("year");

  useEffect(() => {
    setLoading(true);
    const query = selectedYear ? `?year=${selectedYear}` : "";
    api.get(`/banks/${bankId}/accrued-interest${query}`)
      .then((response) => setReport(response.data))
      .catch(() => setReport(null))
      .finally(() => setLoading(false));
  }, [bankId, selectedYear]);

  const years = useMemo(() => report?.available_years || [], [report]);

  const printPdf = () => {
    window.print();
  };

  return (
    <BankShell>
      <div className="space-y-6" data-testid="accrued-interest-page">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:shadow-none sm:p-8" data-testid="accrued-heading-section">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm font-extrabold text-emerald-700" data-testid="accrued-eyebrow">فوائد ودائع مستحقة</p>
              <h2 className="mt-2 text-3xl font-extrabold text-slate-950 sm:text-4xl" data-testid="accrued-title">تقرير المستحقات السنوية</h2>
              <p className="mt-3 max-w-3xl text-base font-semibold leading-8 text-slate-600" data-testid="accrued-description">
                يتم الحساب حسب يوم ربط الوديعة؛ إذا كان يوم الربط 18 فإن آخر صرف في ديسمبر يكون يوم 18، والمستحق حتى نهاية السنة = الأيام المتبقية × العائد اليومي.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row print:hidden" data-testid="accrued-actions">
              <select
                value={report?.year || selectedYear || ""}
                onChange={(event) => setSearchParams({ year: event.target.value })}
                className="h-12 rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold text-slate-800 outline-none focus:border-slate-900"
                data-testid="accrued-year-selector"
              >
                {years.map((year) => (
                  <option key={year} value={year} data-testid={`accrued-year-option-${year}`}>{year}</option>
                ))}
              </select>
              <Button onClick={printPdf} className="h-12 rounded-lg bg-slate-950 px-6 text-white hover:bg-slate-800" data-testid="print-accrued-pdf-button">
                <Printer className="h-4 w-4" /> طباعة PDF
              </Button>
            </div>
          </div>
        </section>

        {loading ? (
          <section className="rounded-xl border border-slate-200 bg-white p-10 text-center font-extrabold" data-testid="accrued-loading-state">جاري تحميل تقرير المستحقات...</section>
        ) : report ? (
          <section className="space-y-5" data-testid="accrued-print-area">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="accrued-kpi-grid">
              <div className="rounded-xl bg-slate-950 p-5 text-white" data-testid="accrued-bank-card">
                <ReceiptText className="mb-3 h-6 w-6" />
                <p className="text-sm font-bold text-slate-300" data-testid="accrued-bank-label">البنك</p>
                <p className="mt-2 text-2xl font-extrabold" data-testid="accrued-bank-value">{report.bank.name}</p>
              </div>
              <div className="rounded-xl bg-emerald-50 p-5 text-emerald-900" data-testid="accrued-year-card">
                <Sigma className="mb-3 h-6 w-6" />
                <p className="text-sm font-bold text-emerald-700" data-testid="accrued-year-label">سنة التقرير</p>
                <p className="mt-2 text-2xl font-extrabold" data-testid="accrued-year-value">{report.year}</p>
              </div>
              <div className="rounded-xl bg-amber-50 p-5 text-amber-950" data-testid="accrued-total-card">
                <Sigma className="mb-3 h-6 w-6" />
                <p className="text-sm font-bold text-amber-700" data-testid="accrued-total-label">إجمالي المستحقات</p>
                <p className="mt-2 text-2xl font-extrabold" data-testid="accrued-total-value">{formatCurrency(report.total_accrued_interest)}</p>
              </div>
            </div>

            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm print:shadow-none" data-testid="accrued-table-wrapper">
              <Table data-testid="accrued-table">
                <TableHeader className="bg-slate-950">
                  <TableRow className="hover:bg-slate-950" data-testid="accrued-table-header-row">
                    {['مسلسل', 'رقم الوديعة', 'رقم الحساب', 'مبلغ الوديعة', 'النسبة السنوية', 'العائد اليومي', 'آخر تاريخ صرف', 'حتى تاريخ', 'أيام مستحقة', 'مبلغ المستحق'].map((title) => (
                      <TableHead key={title} className="text-right font-extrabold text-white" data-testid={`accrued-header-${title}`}>{title}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.rows.map((row) => (
                    <TableRow key={row.deposit_id} data-testid={`accrued-row-${row.deposit_id}`}>
                      <TableCell data-testid={`accrued-row-${row.deposit_id}-serial`}>{row.serial}</TableCell>
                      <TableCell className="font-extrabold" data-testid={`accrued-row-${row.deposit_id}-deposit-number`}>{row.deposit_number}</TableCell>
                      <TableCell data-testid={`accrued-row-${row.deposit_id}-account-number`}>{row.account_number}</TableCell>
                      <TableCell data-testid={`accrued-row-${row.deposit_id}-amount`}>{formatCurrency(row.amount)}</TableCell>
                      <TableCell data-testid={`accrued-row-${row.deposit_id}-rate`}>{formatNumber(row.annual_interest_rate)}%</TableCell>
                      <TableCell data-testid={`accrued-row-${row.deposit_id}-daily-interest`}>{formatCurrency(row.daily_interest_amount)}</TableCell>
                      <TableCell data-testid={`accrued-row-${row.deposit_id}-last-payment`}>{formatDateTime(row.last_payment_date)}</TableCell>
                      <TableCell data-testid={`accrued-row-${row.deposit_id}-until-date`}>{formatDateTime(row.accrued_until_date)}</TableCell>
                      <TableCell className="font-bold" data-testid={`accrued-row-${row.deposit_id}-days`}>{row.accrued_days}</TableCell>
                      <TableCell className="font-extrabold" data-testid={`accrued-row-${row.deposit_id}-amount-due`}>{formatCurrency(row.accrued_interest_amount)}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow className="bg-amber-50 hover:bg-amber-50" data-testid="accrued-total-row">
                    <TableCell colSpan={9} className="text-lg font-extrabold text-slate-950" data-testid="accrued-total-row-label">إجمالي المستحقات</TableCell>
                    <TableCell className="text-lg font-extrabold text-slate-950" data-testid="accrued-total-row-value">{formatCurrency(report.total_accrued_interest)}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </section>
        ) : (
          <section className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center" data-testid="accrued-empty-state">
            <p className="text-2xl font-extrabold text-slate-950" data-testid="accrued-empty-title">لا توجد ودائع لحساب المستحقات</p>
            <p className="mt-3 text-base font-semibold text-slate-500" data-testid="accrued-empty-description">سجل ودائع أولاً حتى يظهر تقرير المستحقات.</p>
          </section>
        )}
      </div>
    </BankShell>
  );
}
