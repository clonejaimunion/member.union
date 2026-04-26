import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { CalendarDays, Check, ChevronDown, ClipboardPenLine, Printer, Sigma } from "lucide-react";
import { BankShell } from "@/components/BankShell";
import { DepositSummary } from "@/components/DepositSummary";
import { ReportTable } from "@/components/ReportTable";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

export default function ReportPage({ type }) {
  const { bankId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [deposits, setDeposits] = useState([]);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectorOpen, setSelectorOpen] = useState(false);
  const depositId = searchParams.get("deposit_id");

  const title = type === "current-year" ? "العائد الشهري عن السنة الحالية" : "العائد الشهري المستحق عن السنة السابقة";

  const printPdf = () => {
    window.print();
  };

  useEffect(() => {
    api.get(`/banks/${bankId}/deposits`).then((response) => setDeposits(response.data)).catch(() => setDeposits([]));
  }, [bankId]);

  useEffect(() => {
    setLoading(true);
    const query = depositId ? `?deposit_id=${depositId}` : "";
    api.get(`/banks/${bankId}/reports/${type}${query}`).then((response) => setReport(response.data)).catch(() => setReport(null)).finally(() => setLoading(false));
  }, [bankId, type, depositId]);

  const selectedValue = useMemo(() => report?.deposit?.id || depositId || "", [report, depositId]);

  const selectedDepositLabel = useMemo(() => {
    const selected = deposits.find((deposit) => deposit.id === selectedValue) || report?.deposit;
    if (!selected) return "اختر الوديعة";
    return `${selected.deposit_number} - ${selected.account_number}`;
  }, [deposits, selectedValue, report]);

  const changeDeposit = (value) => {
    if (value) {
      setSearchParams({ deposit_id: value });
      setSelectorOpen(false);
    }
  };

  return (
    <BankShell>
      <div className="space-y-6" data-testid={`${type}-report-page`}>
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8" data-testid="report-heading-section">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <p className="text-sm font-extrabold text-emerald-700" data-testid="report-type-label">{report?.year || "—"}</p>
              <h2 className="text-3xl font-extrabold text-slate-950 sm:text-4xl" data-testid="report-title">{title}</h2>
              <p className="max-w-3xl text-base font-semibold leading-8 text-slate-600" data-testid="report-description">
                التقرير يعرض بيانات الوديعة أعلى الجدول ثم العائد الشهري محسوبًا من العائد السنوي ÷ عدد أيام السنة الفعلية × أيام الشهر الفعلية من التقويم.
              </p>
              {type === "current-year" && (
                <div className="print:hidden" data-testid="report-print-actions">
                  <Button onClick={printPdf} className="h-12 rounded-lg bg-slate-950 px-6 text-white hover:bg-slate-800" data-testid="print-current-year-pdf-button">
                    <Printer className="h-4 w-4" /> طباعة PDF
                  </Button>
                </div>
              )}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="report-kpis">
              <div className="rounded-xl bg-slate-950 p-5 text-white" data-testid="report-monthly-interest-card">
                <p className="text-xs font-bold text-slate-300" data-testid="report-monthly-interest-label">العائد السنوي الكامل</p>
                <p className="mt-2 text-2xl font-extrabold" data-testid="report-monthly-interest-value">{formatCurrency(report?.monthly_interest_amount)}</p>
              </div>
              <div className="rounded-xl bg-amber-50 p-5 text-slate-950" data-testid="report-total-interest-card">
                <p className="text-xs font-bold text-amber-700" data-testid="report-total-interest-label">إجمالي السنة</p>
                <p className="mt-2 text-2xl font-extrabold" data-testid="report-total-interest-value">{formatCurrency(report?.total_interest)}</p>
              </div>
            </div>
          </div>
        </section>

        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-10 text-center" data-testid="report-loading-state">جاري تحميل التقرير...</div>
        ) : report ? (
          <>
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8" data-testid="report-deposit-details-section">
              <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-sm font-bold text-slate-500" data-testid="report-deposit-details-label">بيانات الوديعة المسجلة</p>
                  <h3 className="text-2xl font-extrabold text-slate-950" data-testid="report-deposit-details-title">{report.deposit.deposit_number}</h3>
                </div>
                <div className="relative w-full lg:w-80" data-testid="report-deposit-selector-wrapper">
                  <button
                    type="button"
                    onClick={() => setSelectorOpen((current) => !current)}
                    className="flex h-12 w-full items-center justify-between gap-3 rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-bold text-slate-800 outline-none transition-colors hover:bg-white focus:border-slate-900 focus:bg-white"
                    data-testid="report-deposit-selector"
                  >
                    <span className="truncate" data-testid="report-deposit-selector-label">{selectedDepositLabel}</span>
                    <ChevronDown className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${selectorOpen ? "rotate-180" : ""}`} data-testid="report-deposit-selector-icon" />
                  </button>
                  {selectorOpen && (
                    <div className="absolute left-0 right-0 top-14 z-30 max-h-72 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 shadow-xl" data-testid="report-deposit-options-list">
                      {deposits.map((deposit) => {
                        const isSelected = deposit.id === selectedValue;
                        return (
                          <button
                            key={deposit.id}
                            type="button"
                            onClick={() => changeDeposit(deposit.id)}
                            className={`flex w-full items-center justify-between gap-3 rounded-lg px-3 py-3 text-right text-sm font-bold transition-colors ${isSelected ? "bg-slate-950 text-white" : "text-slate-700 hover:bg-slate-100"}`}
                            data-testid={`report-deposit-option-${deposit.id}`}
                          >
                            <span className="truncate" data-testid={`report-deposit-option-${deposit.id}-label`}>{deposit.deposit_number} - {deposit.account_number}</span>
                            {isSelected && <Check className="h-4 w-4 shrink-0" data-testid={`report-deposit-option-${deposit.id}-check`} />}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
              <DepositSummary deposit={report.deposit} />
              <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="report-clickable-deposits-grid">
                {deposits.map((deposit) => (
                  <button
                    key={deposit.id}
                    type="button"
                    onClick={() => changeDeposit(deposit.id)}
                    className={`rounded-xl border p-4 text-right transition-[transform,background-color,border-color] hover:-translate-y-0.5 ${deposit.id === selectedValue ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-slate-50 text-slate-800 hover:bg-white"}`}
                    data-testid={`report-clickable-deposit-${deposit.id}`}
                  >
                    <p className="text-xs font-bold opacity-70" data-testid={`report-clickable-deposit-${deposit.id}-label`}>اختيار الوديعة بالفأرة</p>
                    <p className="mt-1 text-lg font-extrabold" data-testid={`report-clickable-deposit-${deposit.id}-number`}>{deposit.deposit_number}</p>
                  </button>
                ))}
              </div>
            </section>

            <section className="space-y-4" data-testid="monthly-report-section">
              <div className="flex items-center justify-between gap-3" data-testid="monthly-report-header">
                <div className="flex items-center gap-3">
                  <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700" data-testid="monthly-report-icon"><CalendarDays className="h-5 w-5" /></span>
                  <div>
                    <p className="text-sm font-bold text-slate-500" data-testid="monthly-report-label">جدول العائد الشهري</p>
                    <h3 className="text-2xl font-extrabold text-slate-950" data-testid="monthly-report-title">{report.year}</h3>
                  </div>
                </div>
                <div className="hidden items-center gap-2 rounded-lg bg-slate-100 px-4 py-2 text-sm font-extrabold text-slate-700 sm:flex" data-testid="monthly-report-total-chip">
                  <Sigma className="h-4 w-4" /> {formatCurrency(report.total_interest)}
                </div>
              </div>
              <ReportTable rows={report.rows} total={report.total_interest} />
            </section>
          </>
        ) : (
          <section className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center" data-testid="report-empty-state">
            <p className="text-2xl font-extrabold text-slate-950" data-testid="report-empty-title">لا توجد وديعة مسجلة لهذا البنك</p>
            <p className="mt-3 text-base font-semibold text-slate-500" data-testid="report-empty-description">سجل بيانات الوديعة أولاً حتى يتم استخراج التقرير.</p>
            <Button asChild className="mt-6 h-12 rounded-lg bg-slate-950 px-7 text-white" data-testid="go-register-from-empty-report-button">
              <Link to={`/bank/${bankId}/register`}><ClipboardPenLine className="h-4 w-4" /> تسجيل وديعة</Link>
            </Button>
          </section>
        )}
      </div>
    </BankShell>
  );
}
