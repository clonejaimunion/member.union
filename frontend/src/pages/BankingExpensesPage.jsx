import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Banknote, CheckCircle2, Home, Landmark, LogOut, Save, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreditLine } from "@/components/CreditLine";
import { ExportReportButtons } from "@/components/ExportReportButtons";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { fallbackBanks } from "@/lib/banks";
import { formatCurrency, formatNumber, sanitizeDecimalInput } from "@/lib/format";

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

const manualFields = [
  { key: "stamp", label: "دمغة" },
  { key: "bank_correspondence", label: "مراسلات بنكية" },
  { key: "correspondence_safekeeping", label: "حفظ مراسلات" },
  { key: "internal_transfer_fee", label: "رسوم تحويل داخلي" },
  { key: "external_transfer_fee", label: "رسوم تحويل خارجي" },
];

const emptyManual = () => ({ stamp: "", bank_correspondence: "", correspondence_safekeeping: "", internal_transfer_fee: "", external_transfer_fee: "" });
const currentYear = String(new Date().getFullYear());
const currentMonth = String(new Date().getMonth() + 1).padStart(2, "0");

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const getBankRules = (bankId) => {
  if (bankId === "industrial-development") {
    return {
      source: "تعريفة خدمات بنك التنمية الصناعية - حسابات الشركات",
      monthlyStatementFee: 100,
      paymentOrderFee: 10,
      incomingCheckFee: 20,
      outgoingTransferFee: (amount) => clamp(Number(amount || 0) * 0.003, 50, 500),
      cashFee: (amount) => Number(amount || 0) < 20000 ? 20 : 0,
      issuedCheckFee: () => 0,
      depositLinkFee: () => 0,
    };
  }
  return {
    source: "لم يتم إدخال ملف تعريفة خاص بهذا البنك بعد؛ يتم حساب البنود اليدوية فقط والآلي بقيمة صفر لحين إضافة التعريفة.",
    monthlyStatementFee: 0,
    paymentOrderFee: 0,
    incomingCheckFee: 0,
    outgoingTransferFee: () => 0,
    cashFee: () => 0,
    issuedCheckFee: () => 0,
    depositLinkFee: () => 0,
  };
};

const sumAmounts = (items, field = "amount") => items.reduce((sum, item) => sum + Number(item[field] || 0), 0);
const periodBounds = (year, month) => ({ from: `${year}-${month}-01`, to: `${year}-${month}-${new Date(Number(year), Number(month), 0).getDate()}` });

export default function BankingExpensesPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [banks, setBanks] = useState(fallbackBanks);
  const [filters, setFilters] = useState({ bank_id: "industrial-development", year: currentYear, month: currentMonth });
  const [revenues, setRevenues] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [deposits, setDeposits] = useState([]);
  const [manual, setManual] = useState(emptyManual);
  const [loading, setLoading] = useState(true);
  const [savingManual, setSavingManual] = useState(false);

  const canManage = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.manage_expenses || user?.permissions?.manage_revenues;
  const selectedBank = banks.find((bank) => bank.id === filters.bank_id) || fallbackBanks.find((bank) => bank.id === filters.bank_id) || banks[0];
  const rules = useMemo(() => getBankRules(filters.bank_id), [filters.bank_id]);
  const periodLabel = `${monthLabels[filters.month] || filters.month} / ${filters.year}`;

  const loadData = useCallback(async () => {
    setLoading(true);
    const { from, to } = periodBounds(filters.year, filters.month);
    try {
      const [banksResponse, revenuesResponse, expensesResponse, depositsResponse, manualResponse] = await Promise.all([
        api.get("/banks"),
        api.get(`/revenues?bank_id=${filters.bank_id}&from_date=${from}&to_date=${to}`),
        api.get(`/expenses?bank_id=${filters.bank_id}&from_date=${from}&to_date=${to}`),
        api.get(`/banks/${filters.bank_id}/deposits`),
        api.get(`/banking-expenses/manual?bank_id=${filters.bank_id}&year=${filters.year}&month=${Number(filters.month)}`),
      ]);
      setBanks(banksResponse.data);
      setRevenues(revenuesResponse.data);
      setExpenses(expensesResponse.data);
      setDeposits(depositsResponse.data);
      setManual(manualFields.reduce((acc, field) => ({ ...acc, [field.key]: String(manualResponse.data[field.key] || "") }), {}));
    } catch (error) {
      toast.error("تعذر تحميل بيانات المصروفات البنكية");
      setRevenues([]);
      setExpenses([]);
      setDeposits([]);
      setManual(emptyManual());
    } finally {
      setLoading(false);
    }
  }, [filters.bank_id, filters.month, filters.year]);

  useEffect(() => { loadData(); }, [loadData]);

  const updateRevenueStatus = async (item, status) => {
    try {
      await api.patch(`/revenues/${item.id}/banking-status`, { bank_collection_status: status });
      toast.success("تم تحديث حالة التحصيل");
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تحديث حالة التحصيل");
    }
  };

  const updateExpenseStatus = async (item, status) => {
    try {
      await api.patch(`/expenses/${item.id}/banking-status`, { bank_payment_status: status });
      toast.success("تم تحديث حالة الشيك");
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تحديث حالة الشيك");
    }
  };

  const saveManual = async () => {
    setSavingManual(true);
    try {
      await api.put("/banking-expenses/manual", {
        bank_id: filters.bank_id,
        year: Number(filters.year),
        month: Number(filters.month),
        ...manualFields.reduce((acc, field) => ({ ...acc, [field.key]: Number(sanitizeDecimalInput(manual[field.key]) || 0) }), {}),
      });
      toast.success("تم حفظ البنود اليدوية");
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ البنود اليدوية");
    } finally {
      setSavingManual(false);
    }
  };

  const reportRows = useMemo(() => {
    const paymentOrdersCollected = revenues.filter((item) => item.collection_method === "payment_order" && (item.bank_collection_status || "under_collection") === "collected");
    const paymentOrdersUnderCollection = revenues.filter((item) => item.collection_method === "payment_order" && (item.bank_collection_status || "under_collection") === "under_collection");
    const checksCollected = revenues.filter((item) => item.collection_method === "check" && (item.bank_collection_status || "under_collection") === "collected");
    const checksUnderCollection = revenues.filter((item) => item.collection_method === "check" && (item.bank_collection_status || "under_collection") === "under_collection");
    const paidChecks = expenses.filter((item) => item.payment_method === "check" && (item.bank_payment_status || "not_presented") === "paid");
    const notPresentedChecks = expenses.filter((item) => item.payment_method === "check" && (item.bank_payment_status || "not_presented") === "not_presented");
    const transfers = expenses.filter((item) => item.payment_method === "bank_transfer");
    const cashExpenses = expenses.filter((item) => item.payment_method === "cash");
    const depositLinks = deposits.filter((item) => String(item.creation_datetime || item.created_at || "").startsWith(`${filters.year}-${filters.month}`));

    return [
      { key: "payment-orders-collected", statement: "أوامر دفع إلكتروني محصلة", count: paymentOrdersCollected.length, bankExpense: paymentOrdersCollected.length * rules.paymentOrderFee },
      { key: "payment-orders-under", statement: "أوامر دفع إلكتروني تحت التحصيل", count: paymentOrdersUnderCollection.length, bankExpense: 0 },
      { key: "checks-collected", statement: "شيكات محصلة", count: checksCollected.length, bankExpense: checksCollected.length * rules.incomingCheckFee },
      { key: "checks-under", statement: "شيكات تحت التحصيل", count: checksUnderCollection.length, bankExpense: 0 },
      { key: "monthly-statement", statement: "رسوم كشف الحساب الشهري", count: 1, bankExpense: rules.monthlyStatementFee },
      ...manualFields.map((field) => ({ key: field.key, statement: field.label, count: manual[field.key] ? 1 : 0, bankExpense: Number(sanitizeDecimalInput(manual[field.key]) || 0) })),
      { key: "paid-checks", statement: "شيكات تم الصرف", count: paidChecks.length, bankExpense: paidChecks.reduce((sum, item) => sum + rules.issuedCheckFee(item.net_amount), 0) },
      { key: "not-presented-checks", statement: "شيكات لم تقدم للصرف", count: notPresentedChecks.length, bankExpense: 0 },
      { key: "bank-transfer-beneficiary", statement: "تحويل بنكي لمستفيد", count: transfers.length, bankExpense: transfers.reduce((sum, item) => sum + rules.outgoingTransferFee(item.net_amount), 0) },
      { key: "cash", statement: "نقدي", count: cashExpenses.length, bankExpense: cashExpenses.reduce((sum, item) => sum + rules.cashFee(item.net_amount), 0) },
      { key: "deposit-link", statement: "ربط وديعة", count: depositLinks.length, bankExpense: depositLinks.reduce((sum, item) => sum + rules.depositLinkFee(item.amount), 0) },
    ];
  }, [deposits, expenses, filters.month, filters.year, manual, revenues, rules]);

  const totalBankExpenses = useMemo(() => reportRows.reduce((sum, row) => sum + Number(row.bankExpense || 0), 0), [reportRows]);
  const revenueStatusRows = useMemo(() => revenues.filter((item) => ["check", "payment_order"].includes(item.collection_method)), [revenues]);
  const expenseCheckRows = useMemo(() => expenses.filter((item) => item.payment_method === "check"), [expenses]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="banking-expenses-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="banking-expenses-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="banking-expenses-brand">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="banking-expenses-brand-icon"><Banknote className="h-5 w-5" /></div>
            <div><p className="text-xs font-extrabold text-emerald-700" data-testid="banking-expenses-eyebrow">المصروفات البنكية</p><h1 className="text-2xl font-extrabold" data-testid="banking-expenses-title">تقرير رسوم وعمولات البنك</h1></div>
          </div>
          <div className="flex flex-wrap items-center gap-3" data-testid="banking-expenses-header-actions">
            <Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="banking-expenses-user-badge">{user?.username}</Badge>
            <Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="banking-expenses-home-button"><Link to="/"><Home className="h-4 w-4" /> القائمة الرئيسية</Link></Button>
            <Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="banking-expenses-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button>
            <Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="banking-expenses-logout-button"><LogOut className="h-4 w-4" /> خروج</Button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="banking-expenses-content">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden sm:p-8" data-testid="banking-expenses-filters-section">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between" data-testid="banking-expenses-filters-heading">
            <div><h2 className="text-3xl font-extrabold" data-testid="banking-expenses-filters-title">اختيارات التقرير</h2><p className="mt-1 text-sm font-bold text-slate-500" data-testid="banking-expenses-rules-source">{rules.source}</p></div>
            <ExportReportButtons title={`تقرير المصروفات البنكية - ${selectedBank?.name || ""} - ${periodLabel}`} fileName={`تقرير-المصروفات-البنكية-${selectedBank?.name || ""}-${periodLabel}`} selectors={["[data-testid='banking-expenses-report-section']"]} disabled={loading} pdfTestId="print-banking-expenses-report-button" excelTestId="export-banking-expenses-excel-button" wordTestId="export-banking-expenses-word-button" />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="banking-expenses-filters-grid">
            <div data-testid="banking-expenses-bank-wrapper"><Label data-testid="banking-expenses-bank-label">البنك</Label><select value={filters.bank_id} onChange={(event) => setFilters((current) => ({ ...current, bank_id: event.target.value }))} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="banking-expenses-bank-select">{banks.map((bank) => <option key={bank.id} value={bank.id} data-testid={`banking-expenses-bank-option-${bank.id}`}>{bank.name}</option>)}</select></div>
            <div data-testid="banking-expenses-year-wrapper"><Label data-testid="banking-expenses-year-label">السنة</Label><Input value={filters.year} onChange={(event) => setFilters((current) => ({ ...current, year: event.target.value.replace(/[^0-9]/g, "").slice(0, 4) || current.year }))} className="mt-2 h-12 rounded-lg bg-slate-50 text-right" data-testid="banking-expenses-year-input" /></div>
            <div data-testid="banking-expenses-month-wrapper"><Label data-testid="banking-expenses-month-label">الشهر</Label><select value={filters.month} onChange={(event) => setFilters((current) => ({ ...current, month: event.target.value }))} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="banking-expenses-month-select">{Object.entries(monthLabels).map(([value, label]) => <option key={value} value={value} data-testid={`banking-expenses-month-option-${value}`}>{label}</option>)}</select></div>
          </div>
        </section>

        {canManage && (
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden sm:p-8" data-testid="banking-expenses-manual-section">
            <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between" data-testid="banking-expenses-manual-heading"><h2 className="text-2xl font-extrabold" data-testid="banking-expenses-manual-title">بنود يدوية للشهر</h2><Button onClick={saveManual} disabled={savingManual} className="h-11 rounded-lg bg-slate-950 text-white" data-testid="save-banking-expenses-manual-button"><Save className="h-4 w-4" /> {savingManual ? "جاري الحفظ..." : "حفظ البنود"}</Button></div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-5" data-testid="banking-expenses-manual-grid">
              {manualFields.map((field) => <div key={field.key} data-testid={`banking-expenses-manual-${field.key}-wrapper`}><Label data-testid={`banking-expenses-manual-${field.key}-label`}>{field.label}</Label><Input inputMode="decimal" value={manual[field.key] || ""} onChange={(event) => setManual((current) => ({ ...current, [field.key]: sanitizeDecimalInput(event.target.value) }))} className="mt-2 h-12 rounded-lg bg-slate-50 text-right" data-testid={`banking-expenses-manual-${field.key}-input`} /></div>)}
            </div>
          </section>
        )}

        {canManage && (
          <section className="grid grid-cols-1 gap-6 xl:grid-cols-2 print:hidden" data-testid="banking-expenses-status-sections">
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="banking-expenses-revenue-status-section">
              <h2 className="text-2xl font-extrabold" data-testid="banking-expenses-revenue-status-title">تحديد حالة إيرادات الشيكات وأوامر الدفع</h2>
              <div className="mt-4 space-y-3" data-testid="banking-expenses-revenue-status-list">
                {revenueStatusRows.length === 0 ? <p className="rounded-lg border border-dashed border-slate-300 p-5 text-center font-bold text-slate-500" data-testid="banking-expenses-revenue-status-empty">لا توجد شيكات أو أوامر دفع لهذا الشهر</p> : revenueStatusRows.map((item) => <article key={item.id} className="rounded-lg border border-slate-200 p-4" data-testid={`banking-revenue-status-${item.id}`}><div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"><div><p className="font-extrabold" data-testid={`banking-revenue-status-${item.id}-title`}>{item.collection_method === "check" ? `شيك رقم ${item.check_number}` : `أمر دفع رقم ${item.payment_order_number}`}</p><p className="mt-1 text-sm font-bold text-slate-500" data-testid={`banking-revenue-status-${item.id}-amount`}>{formatCurrency(item.amount)} — إذن {item.receipt_number}</p></div><div className="flex flex-wrap gap-2" data-testid={`banking-revenue-status-${item.id}-actions`}><Button type="button" onClick={() => updateRevenueStatus(item, "collected")} variant={(item.bank_collection_status || "under_collection") === "collected" ? "default" : "outline"} className="h-10 rounded-lg" data-testid={`mark-revenue-collected-button-${item.id}`}><CheckCircle2 className="h-4 w-4" /> تم التحصيل</Button><Button type="button" onClick={() => updateRevenueStatus(item, "under_collection")} variant={(item.bank_collection_status || "under_collection") === "under_collection" ? "default" : "outline"} className="h-10 rounded-lg" data-testid={`mark-revenue-under-collection-button-${item.id}`}><XCircle className="h-4 w-4" /> تحت التحصيل</Button></div></div></article>)}
              </div>
            </section>
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="banking-expenses-expense-status-section">
              <h2 className="text-2xl font-extrabold" data-testid="banking-expenses-expense-status-title">تحديد حالة شيكات المصروفات</h2>
              <div className="mt-4 space-y-3" data-testid="banking-expenses-expense-status-list">
                {expenseCheckRows.length === 0 ? <p className="rounded-lg border border-dashed border-slate-300 p-5 text-center font-bold text-slate-500" data-testid="banking-expenses-expense-status-empty">لا توجد شيكات مصروفات لهذا الشهر</p> : expenseCheckRows.map((item) => <article key={item.id} className="rounded-lg border border-slate-200 p-4" data-testid={`banking-expense-status-${item.id}`}><div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"><div><p className="font-extrabold" data-testid={`banking-expense-status-${item.id}-title`}>شيك مصروف رقم {item.check_number}</p><p className="mt-1 text-sm font-bold text-slate-500" data-testid={`banking-expense-status-${item.id}-amount`}>{formatCurrency(item.net_amount)} — إذن {item.expense_number}</p></div><div className="flex flex-wrap gap-2" data-testid={`banking-expense-status-${item.id}-actions`}><Button type="button" onClick={() => updateExpenseStatus(item, "paid")} variant={(item.bank_payment_status || "not_presented") === "paid" ? "default" : "outline"} className="h-10 rounded-lg" data-testid={`mark-expense-paid-button-${item.id}`}><CheckCircle2 className="h-4 w-4" /> تم الصرف</Button><Button type="button" onClick={() => updateExpenseStatus(item, "not_presented")} variant={(item.bank_payment_status || "not_presented") === "not_presented" ? "default" : "outline"} className="h-10 rounded-lg" data-testid={`mark-expense-not-presented-button-${item.id}`}><XCircle className="h-4 w-4" /> لم يقدم للصرف</Button></div></div></article>)}
              </div>
            </section>
          </section>
        )}

        <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:border-0 print:shadow-none sm:p-8" data-testid="banking-expenses-report-section">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between" data-testid="banking-expenses-report-heading">
            <div data-testid="banking-expenses-report-title-block"><p className="text-sm font-extrabold text-emerald-700" data-testid="banking-expenses-report-eyebrow">{selectedBank?.name}</p><h2 className="text-3xl font-extrabold text-slate-950" data-testid="banking-expenses-report-title">المصروفات البنكية - {periodLabel}</h2></div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3" data-testid="banking-expenses-report-kpis"><div className="rounded-xl bg-slate-950 p-4 text-white" data-testid="banking-expenses-total-card"><p className="text-xs font-bold text-slate-300">إجمالي مصروف البنك</p><p className="text-2xl font-extrabold" data-testid="banking-expenses-total-value">{formatCurrency(totalBankExpenses)}</p></div><div className="rounded-xl bg-emerald-50 p-4 text-emerald-900" data-testid="banking-expenses-revenue-count-card"><p className="text-xs font-bold text-emerald-700">حركات الإيرادات</p><p className="text-2xl font-extrabold" data-testid="banking-expenses-revenue-count-value">{formatNumber(revenues.length)}</p></div><div className="rounded-xl bg-amber-50 p-4 text-amber-900" data-testid="banking-expenses-expense-count-card"><p className="text-xs font-bold text-amber-700">حركات المصروفات</p><p className="text-2xl font-extrabold" data-testid="banking-expenses-expense-count-value">{formatNumber(expenses.length)}</p></div></div>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200" data-testid="banking-expenses-table-wrapper">
            <Table data-testid="banking-expenses-table">
              <TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950" data-testid="banking-expenses-table-header-row"><TableHead className="text-right font-extrabold text-white" data-testid="banking-expenses-header-statement">بيان</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="banking-expenses-header-count">العدد</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="banking-expenses-header-bank-expense">مصروف البنك</TableHead></TableRow></TableHeader>
              <TableBody>{reportRows.map((row) => <TableRow key={row.key} data-testid={`banking-expenses-row-${row.key}`}><TableCell className="font-extrabold" data-testid={`banking-expenses-row-${row.key}-statement`}>{row.statement}</TableCell><TableCell data-testid={`banking-expenses-row-${row.key}-count`}>{formatNumber(row.count)}</TableCell><TableCell className="font-extrabold" data-testid={`banking-expenses-row-${row.key}-expense`}>{formatCurrency(row.bankExpense)}</TableCell></TableRow>)}<TableRow className="bg-emerald-50 font-extrabold hover:bg-emerald-50" data-testid="banking-expenses-grand-total-row"><TableCell data-testid="banking-expenses-grand-total-label">الإجمالي</TableCell><TableCell data-testid="banking-expenses-grand-total-count">—</TableCell><TableCell data-testid="banking-expenses-grand-total-value">{formatCurrency(totalBankExpenses)}</TableCell></TableRow></TableBody>
            </Table>
          </div>
        </section>
      </section>
      <footer className="px-4 pb-5 print:hidden" data-testid="banking-expenses-footer"><CreditLine testId="banking-expenses-creator-credit" /></footer>
    </main>
  );
}