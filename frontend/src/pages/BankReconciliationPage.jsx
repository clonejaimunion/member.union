import { useEffect, useMemo, useState } from "react";
import { Plus, Printer, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useParams } from "react-router-dom";
import { BankShell } from "@/components/BankShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fallbackBanks } from "@/lib/banks";
import { formatCurrency, formatDateTime, toDateTimeLocal } from "@/lib/format";

const emptyCheck = () => ({ check_number: "", amount: "", check_date: toDateTimeLocal(new Date()) });

export default function BankReconciliationPage() {
  const { bankId } = useParams();
  const [banks, setBanks] = useState(fallbackBanks);
  const [periodLabel, setPeriodLabel] = useState("");
  const [bookBalance, setBookBalance] = useState("");
  const [bankStatementBalance, setBankStatementBalance] = useState("");
  const [outstandingChecks, setOutstandingChecks] = useState([emptyCheck()]);
  const [collectionChecks, setCollectionChecks] = useState([emptyCheck()]);
  const [reconciliations, setReconciliations] = useState([]);
  const [activeReconciliation, setActiveReconciliation] = useState(null);
  const [saving, setSaving] = useState(false);

  const bank = banks.find((item) => item.id === bankId) || fallbackBanks.find((item) => item.id === bankId) || fallbackBanks[0];

  const totals = useMemo(() => {
    const outstanding = outstandingChecks.reduce((sum, item) => sum + Number(item.amount || 0), 0);
    const collection = collectionChecks.reduce((sum, item) => sum + Number(item.amount || 0), 0);
    const calculated = Number(bookBalance || 0) + outstanding - collection;
    const difference = calculated - Number(bankStatementBalance || 0);
    return {
      outstanding,
      collection,
      calculated,
      difference,
      matched: Math.abs(difference) < 0.01,
    };
  }, [bookBalance, bankStatementBalance, outstandingChecks, collectionChecks]);

  const loadReconciliations = () => {
    api.get(`/banks/${bankId}/reconciliations`).then((response) => {
      setReconciliations(response.data);
      setActiveReconciliation(response.data[0] || null);
    }).catch(() => {
      setReconciliations([]);
      setActiveReconciliation(null);
    });
  };

  useEffect(() => {
    api.get("/banks").then((response) => setBanks(response.data)).catch(() => setBanks(fallbackBanks));
    loadReconciliations();
  }, [bankId]);

  const updateCheck = (type, index, field, value) => {
    const setter = type === "outstanding" ? setOutstandingChecks : setCollectionChecks;
    setter((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: value } : item));
  };

  const addCheck = (type) => {
    const setter = type === "outstanding" ? setOutstandingChecks : setCollectionChecks;
    setter((current) => [...current, emptyCheck()]);
  };

  const removeCheck = (type, index) => {
    const setter = type === "outstanding" ? setOutstandingChecks : setCollectionChecks;
    setter((current) => current.filter((_, itemIndex) => itemIndex !== index));
  };

  const cleanChecks = (checks) => checks
    .filter((item) => item.check_number || Number(item.amount || 0) > 0)
    .map((item) => ({ check_number: item.check_number, amount: Number(item.amount || 0), check_date: item.check_date }));

  const saveReconciliation = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = {
        period_label: periodLabel,
        book_balance: Number(bookBalance || 0),
        bank_statement_balance: Number(bankStatementBalance || 0),
        outstanding_checks: cleanChecks(outstandingChecks),
        collection_checks: cleanChecks(collectionChecks),
      };
      const response = await api.post(`/banks/${bankId}/reconciliations`, payload);
      setActiveReconciliation(response.data);
      toast.success("تم حفظ مذكرة التسوية البنكية");
      loadReconciliations();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ التسوية البنكية");
    } finally {
      setSaving(false);
    }
  };

  const printPdf = () => window.print();

  const CheckEditor = ({ title, type, checks }) => (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid={`${type}-checks-section`}>
      <div className="mb-4 flex items-center justify-between gap-3" data-testid={`${type}-checks-heading`}>
        <h3 className="text-xl font-extrabold text-slate-950" data-testid={`${type}-checks-title`}>{title}</h3>
        <Button type="button" onClick={() => addCheck(type)} variant="outline" className="h-10 rounded-lg bg-white print:hidden" data-testid={`add-${type}-check-button`}>
          <Plus className="h-4 w-4" /> إضافة شيك
        </Button>
      </div>
      <div className="space-y-3" data-testid={`${type}-checks-list`}>
        {checks.map((item, index) => (
          <div key={`${type}-${index}`} className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 md:grid-cols-[1fr_1fr_1fr_auto]" data-testid={`${type}-check-row-${index}`}>
            <div className="space-y-2" data-testid={`${type}-check-${index}-number-wrapper`}>
              <Label data-testid={`${type}-check-${index}-number-label`}>رقم الشيك</Label>
              <Input value={item.check_number} onChange={(event) => updateCheck(type, index, "check_number", event.target.value)} className="h-11 rounded-lg bg-white text-right" data-testid={`${type}-check-${index}-number-input`} />
            </div>
            <div className="space-y-2" data-testid={`${type}-check-${index}-amount-wrapper`}>
              <Label data-testid={`${type}-check-${index}-amount-label`}>مبلغ الشيك</Label>
              <Input type="number" step="0.01" min="0" value={item.amount} onChange={(event) => updateCheck(type, index, "amount", event.target.value)} className="h-11 rounded-lg bg-white text-right" data-testid={`${type}-check-${index}-amount-input`} />
            </div>
            <div className="space-y-2" data-testid={`${type}-check-${index}-date-wrapper`}>
              <Label data-testid={`${type}-check-${index}-date-label`}>تاريخ الشيك</Label>
              <Input type="date" value={item.check_date?.slice(0, 10)} onChange={(event) => updateCheck(type, index, "check_date", `${event.target.value}T00:00`)} className="h-11 rounded-lg bg-white text-right" data-testid={`${type}-check-${index}-date-input`} />
            </div>
            <button type="button" onClick={() => removeCheck(type, index)} className="mt-7 inline-flex h-11 items-center justify-center rounded-lg border border-red-200 bg-red-50 px-3 text-red-700 hover:bg-red-100 print:hidden" data-testid={`remove-${type}-check-${index}-button`}>
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </section>
  );

  const ChecksTable = ({ title, rows, testId }) => (
    <section className="space-y-3" data-testid={`${testId}-print-section`}>
      <h3 className="text-xl font-extrabold text-slate-950" data-testid={`${testId}-print-title`}>{title}</h3>
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white" data-testid={`${testId}-table-wrapper`}>
        <Table data-testid={`${testId}-table`}>
          <TableHeader className="bg-slate-950">
            <TableRow className="hover:bg-slate-950" data-testid={`${testId}-header-row`}>
              <TableHead className="text-right font-extrabold text-white">التاريخ</TableHead>
              <TableHead className="text-right font-extrabold text-white">رقم الشيك</TableHead>
              <TableHead className="text-right font-extrabold text-white">المبلغ</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(rows || []).map((row, index) => (
              <TableRow key={`${testId}-${index}`} data-testid={`${testId}-row-${index}`}>
                <TableCell data-testid={`${testId}-row-${index}-date`}>{formatDateTime(row.check_date)}</TableCell>
                <TableCell className="font-extrabold" data-testid={`${testId}-row-${index}-number`}>{row.check_number}</TableCell>
                <TableCell data-testid={`${testId}-row-${index}-amount`}>{formatCurrency(row.amount)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  );

  return (
    <BankShell>
      <div className="space-y-6" data-testid="bank-reconciliation-page">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8" data-testid="reconciliation-heading-section">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm font-extrabold text-emerald-700" data-testid="reconciliation-eyebrow">تسوية بنكية</p>
              <h2 className="text-3xl font-extrabold text-slate-950 sm:text-4xl" data-testid="reconciliation-title">مذكرة تسوية حساب بنك - {bank.name}</h2>
              <p className="mt-3 text-base font-semibold text-slate-600" data-testid="reconciliation-description">الرصيد الدفتري + شيكات لم تقدم للصرف - شيكات تحت التحصيل = الإجمالي المطابق لرصيد كشف حساب البنك.</p>
            </div>
            <Button onClick={printPdf} className="h-12 rounded-lg bg-slate-950 px-6 text-white hover:bg-slate-800 print:hidden" data-testid="print-reconciliation-pdf-button">
              <Printer className="h-4 w-4" /> طباعة PDF
            </Button>
          </div>
        </section>

        <form onSubmit={saveReconciliation} className="space-y-6 print:hidden" data-testid="reconciliation-form">
          <section className="grid grid-cols-1 gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-3" data-testid="reconciliation-balances-section">
            <div className="space-y-2" data-testid="reconciliation-period-wrapper">
              <Label data-testid="reconciliation-period-label">الفترة / الشهر</Label>
              <Input value={periodLabel} onChange={(event) => setPeriodLabel(event.target.value)} placeholder="مثال: يناير 2025" className="h-12 rounded-lg bg-slate-50 text-right" data-testid="reconciliation-period-input" />
            </div>
            <div className="space-y-2" data-testid="book-balance-wrapper">
              <Label data-testid="book-balance-label">الرصيد الدفتري</Label>
              <Input type="number" step="0.01" value={bookBalance} onChange={(event) => setBookBalance(event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="book-balance-input" />
            </div>
            <div className="space-y-2" data-testid="bank-statement-balance-wrapper">
              <Label data-testid="bank-statement-balance-label">الرصيد الشهري من واقع كشف حساب البنك</Label>
              <Input type="number" step="0.01" value={bankStatementBalance} onChange={(event) => setBankStatementBalance(event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="bank-statement-balance-input" />
            </div>
          </section>

          <CheckEditor title="شيكات لم تقدم للصرف" type="outstanding" checks={outstandingChecks} />
          <CheckEditor title="شيكات تحت التحصيل" type="collection" checks={collectionChecks} />

          <section className="grid grid-cols-1 gap-4 md:grid-cols-4" data-testid="reconciliation-live-summary">
            <div className="rounded-xl bg-slate-950 p-5 text-white" data-testid="summary-book-balance-card"><p className="text-xs font-bold text-slate-300">الرصيد الدفتري</p><p className="mt-2 text-xl font-extrabold">{formatCurrency(bookBalance)}</p></div>
            <div className="rounded-xl bg-emerald-50 p-5 text-emerald-900" data-testid="summary-outstanding-card"><p className="text-xs font-bold text-emerald-700">إجمالي شيكات لم تقدم</p><p className="mt-2 text-xl font-extrabold">{formatCurrency(totals.outstanding)}</p></div>
            <div className="rounded-xl bg-amber-50 p-5 text-amber-950" data-testid="summary-collection-card"><p className="text-xs font-bold text-amber-700">إجمالي تحت التحصيل</p><p className="mt-2 text-xl font-extrabold">{formatCurrency(totals.collection)}</p></div>
            <div className={`rounded-xl p-5 ${totals.matched ? "bg-emerald-700 text-white" : "bg-red-700 text-white"}`} data-testid="summary-matched-card"><p className="text-xs font-bold opacity-80">الحالة</p><p className="mt-2 text-xl font-extrabold">{totals.matched ? "الرصيد مطابق" : "الرصيد غير مطابق"}</p></div>
          </section>

          <Button type="submit" disabled={saving} className="h-12 rounded-lg bg-slate-950 px-7 text-white hover:bg-slate-800" data-testid="save-reconciliation-button">
            <Save className="h-4 w-4" /> {saving ? "جاري الحفظ..." : "حفظ مذكرة التسوية"}
          </Button>
        </form>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden" data-testid="reconciliations-history-section">
          <h3 className="mb-4 text-xl font-extrabold text-slate-950" data-testid="reconciliations-history-title">مذكرات محفوظة</h3>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3" data-testid="reconciliations-history-grid">
            {reconciliations.map((item) => (
              <button key={item.id} type="button" onClick={() => setActiveReconciliation(item)} className={`rounded-xl border p-4 text-right transition-transform hover:-translate-y-0.5 ${activeReconciliation?.id === item.id ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-slate-50 text-slate-800 hover:bg-white"}`} data-testid={`reconciliation-history-button-${item.id}`}>
                <p className="text-xs font-bold opacity-70" data-testid={`reconciliation-history-button-${item.id}-period`}>{item.period_label || "بدون فترة"}</p>
                <p className="mt-1 text-lg font-extrabold" data-testid={`reconciliation-history-button-${item.id}-status`}>{item.status_text}</p>
                <p className="mt-1 text-sm font-bold opacity-80" data-testid={`reconciliation-history-button-${item.id}-balance`}>{formatCurrency(item.calculated_balance)}</p>
              </button>
            ))}
          </div>
        </section>

        {activeReconciliation && (
          <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:border-0 print:shadow-none sm:p-8" data-testid="reconciliation-print-report">
            <div className="text-center" data-testid="reconciliation-print-header">
              <p className="text-sm font-bold text-slate-500" data-testid="reconciliation-print-organization">النقابة العامة للزراعة والري - مشروع التكافل الاجتماعي</p>
              <h2 className="mt-2 text-3xl font-extrabold text-slate-950" data-testid="reconciliation-print-title">مذكرة تسوية حساب بنك - {bank.name}</h2>
              <p className="mt-2 text-lg font-bold text-slate-600" data-testid="reconciliation-print-period">{activeReconciliation.period_label || "—"}</p>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4" data-testid="reconciliation-print-kpis">
              <div className="rounded-xl bg-slate-50 p-4" data-testid="print-book-balance"><p className="text-xs font-bold text-slate-500">الرصيد الدفتري</p><p className="text-xl font-extrabold">{formatCurrency(activeReconciliation.book_balance)}</p></div>
              <div className="rounded-xl bg-slate-50 p-4" data-testid="print-statement-balance"><p className="text-xs font-bold text-slate-500">رصيد كشف البنك</p><p className="text-xl font-extrabold">{formatCurrency(activeReconciliation.bank_statement_balance)}</p></div>
              <div className="rounded-xl bg-slate-50 p-4" data-testid="print-calculated-balance"><p className="text-xs font-bold text-slate-500">الإجمالي</p><p className="text-xl font-extrabold">{formatCurrency(activeReconciliation.calculated_balance)}</p></div>
              <div className={`rounded-xl p-4 ${activeReconciliation.is_matched ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`} data-testid="print-status"><p className="text-xs font-bold opacity-80">الحالة</p><p className="text-xl font-extrabold">{activeReconciliation.status_text}</p></div>
            </div>
            <ChecksTable title="يضاف: شيكات لم تقدم للصرف" rows={activeReconciliation.outstanding_checks} testId="outstanding-print" />
            <ChecksTable title="يخصم: شيكات تحت التحصيل" rows={activeReconciliation.collection_checks} testId="collection-print" />
          </section>
        )}
      </div>
    </BankShell>
  );
}
