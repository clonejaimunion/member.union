import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Banknote, Home, LogOut, Plus, Save, Trash2 } from "lucide-react";
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
import { formatCurrency, sanitizeDecimalInput } from "@/lib/format";

const monthOptions = [
  ["01", "يناير"], ["02", "فبراير"], ["03", "مارس"], ["04", "أبريل"], ["05", "مايو"], ["06", "يونيو"],
  ["07", "يوليو"], ["08", "أغسطس"], ["09", "سبتمبر"], ["10", "أكتوبر"], ["11", "نوفمبر"], ["12", "ديسمبر"],
];
const monthLabels = Object.fromEntries(monthOptions);
const months = monthOptions.map(([value]) => value);
const firstReportYear = 2025;
const currentYear = String(Math.max(new Date().getFullYear(), firstReportYear));
const currentMonth = String(new Date().getMonth() + 1).padStart(2, "0");
const yearOptions = Array.from({ length: Math.max(new Date().getFullYear() + 10, 2035) - firstReportYear + 1 }, (_, index) => String(firstReportYear + index));

const createManualRow = (statement = "", count = "1", amount = "") => ({ id: `${Date.now()}-${Math.random()}`, statement, count, amount });

export default function BankingExpensesPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [banks, setBanks] = useState(fallbackBanks);
  const [filters, setFilters] = useState({ bank_id: "industrial-development", period_type: "monthly", year: currentYear, month: currentMonth });
  const [manualRows, setManualRows] = useState([createManualRow()]);
  const [reportRows, setReportRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingManual, setSavingManual] = useState(false);

  const canManage = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.manage_expenses || user?.permissions?.manage_revenues;
  const selectedBank = banks.find((bank) => bank.id === filters.bank_id) || fallbackBanks.find((bank) => bank.id === filters.bank_id) || banks[0];
  const isYearly = filters.period_type === "yearly";
  const periodLabel = isYearly ? `سنة ${filters.year}` : `${monthLabels[filters.month] || filters.month} / ${filters.year}`;

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const manualRequests = isYearly
        ? months.map((month) => api.get(`/banking-expenses/manual?bank_id=${filters.bank_id}&year=${filters.year}&month=${Number(month)}`))
        : [api.get(`/banking-expenses/manual?bank_id=${filters.bank_id}&year=${filters.year}&month=${Number(filters.month)}`)];
      const [banksResponse, ...manualResponses] = await Promise.all([api.get("/banks"), ...manualRequests]);
      setBanks(banksResponse.data);
      if (isYearly) {
        const grouped = manualResponses.flatMap((response) => response.data.items || []).reduce((acc, item) => {
          const statement = String(item.statement || "").trim();
          const count = Number(item.count || 1);
          const amount = Number(item.amount || 0);
          const total = Number(item.total ?? count * amount);
          if (!statement || count <= 0 || amount <= 0) return acc;
          const current = acc[statement] || { statement, count: 0, amount, total: 0 };
          current.count += count;
          current.total += total;
          current.amount = current.count > 0 ? current.total / current.count : amount;
          acc[statement] = current;
          return acc;
        }, {});
        setReportRows(Object.values(grouped).map((item) => ({ ...item, amount: Number(item.amount || 0), total: Number(item.total || 0) })));
        setManualRows([createManualRow()]);
      } else {
        const items = manualResponses[0]?.data?.items || [];
        const rows = items.length ? items.map((item) => createManualRow(item.statement, String(item.count || 1), String(item.amount || ""))) : [createManualRow()];
        setManualRows(rows);
        setReportRows(items.map((item, index) => ({ id: `${index}-${item.statement}`, statement: item.statement, count: Number(item.count || 1), amount: Number(item.amount || 0), total: Number(item.total ?? Number(item.count || 1) * Number(item.amount || 0)) })));
      }
    } catch (error) {
      toast.error("تعذر تحميل بيانات المصروفات البنكية");
      setManualRows([createManualRow()]);
      setReportRows([]);
    } finally {
      setLoading(false);
    }
  }, [filters, isYearly]);

  useEffect(() => { loadData(); }, [loadData]);

  const updateManualRow = (rowId, field, value) => {
    setManualRows((current) => current.map((row) => (row.id === rowId ? { ...row, [field]: field === "amount" || field === "count" ? sanitizeDecimalInput(value) : value } : row)));
  };

  const addManualRow = () => setManualRows((current) => [...current, createManualRow()]);

  const removeManualRow = (rowId) => setManualRows((current) => (current.length > 1 ? current.filter((row) => row.id !== rowId) : [createManualRow()]));

  const saveManual = async () => {
    if (isYearly) {
      toast.error("يتم حفظ البيان والمبلغ من العرض الشهري فقط");
      return;
    }
    const items = manualRows
      .map((row) => ({ statement: row.statement.trim(), count: Number(sanitizeDecimalInput(row.count) || 0), amount: Number(sanitizeDecimalInput(row.amount) || 0) }))
      .filter((row) => row.statement && row.count > 0 && row.amount > 0);
    setSavingManual(true);
    try {
      await api.put("/banking-expenses/manual", { bank_id: filters.bank_id, year: Number(filters.year), month: Number(filters.month), items });
      toast.success("تم حفظ البيان والمبلغ");
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ المصروفات البنكية");
    } finally {
      setSavingManual(false);
    }
  };

  const visibleReportRows = useMemo(() => reportRows.filter((row) => String(row.statement || "").trim() && Number(row.total ?? Number(row.count || 0) * Number(row.amount || 0)) > 0), [reportRows]);
  const totalBankExpenses = useMemo(() => visibleReportRows.reduce((sum, row) => sum + Number(row.total ?? Number(row.count || 0) * Number(row.amount || 0)), 0), [visibleReportRows]);

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
            <Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="banking-expenses-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button>
            <Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="banking-expenses-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button>
            <Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="banking-expenses-logout-button"><LogOut className="h-4 w-4" /> خروج</Button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="banking-expenses-content">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden sm:p-8" data-testid="banking-expenses-filters-section">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between" data-testid="banking-expenses-filters-heading">
            <div><h2 className="text-3xl font-extrabold" data-testid="banking-expenses-filters-title">اختيارات التقرير</h2><p className="mt-1 text-sm font-bold text-slate-500" data-testid="banking-expenses-rules-source">يتم إدخال البيان والعدد والمبلغ يدوياً، والإجمالي يحسب تلقائياً = العدد × المبلغ.</p></div>
            <ExportReportButtons title={`تقرير المصروفات البنكية - ${selectedBank?.name || ""} - ${periodLabel}`} fileName={`تقرير-المصروفات-البنكية-${selectedBank?.name || ""}-${periodLabel}`} selectors={["[data-testid='banking-expenses-report-section']"]} disabled={loading} pdfLabel="طباعة PDF" pdfTestId="print-banking-expenses-report-button" excelTestId="export-banking-expenses-excel-button" wordTestId="export-banking-expenses-word-button" />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4" data-testid="banking-expenses-filters-grid">
            <div data-testid="banking-expenses-bank-wrapper"><Label data-testid="banking-expenses-bank-label">البنك</Label><select value={filters.bank_id} onChange={(event) => setFilters((current) => ({ ...current, bank_id: event.target.value }))} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="banking-expenses-bank-select">{banks.map((bank) => <option key={bank.id} value={bank.id} data-testid={`banking-expenses-bank-option-${bank.id}`}>{bank.name}</option>)}</select></div>
            <div data-testid="banking-expenses-period-type-wrapper"><Label data-testid="banking-expenses-period-type-label">عرض التقرير</Label><select value={filters.period_type} onChange={(event) => setFilters((current) => ({ ...current, period_type: event.target.value }))} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="banking-expenses-period-type-select"><option value="monthly" data-testid="banking-expenses-period-monthly-option">شهري</option><option value="yearly" data-testid="banking-expenses-period-yearly-option">سنوي</option></select></div>
            <div data-testid="banking-expenses-year-wrapper"><Label data-testid="banking-expenses-year-label">السنة</Label><select value={filters.year} onChange={(event) => setFilters((current) => ({ ...current, year: event.target.value }))} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="banking-expenses-year-select">{yearOptions.map((year) => <option key={year} value={year} data-testid={`banking-expenses-year-option-${year}`}>{year}</option>)}</select></div>
            <div data-testid="banking-expenses-month-wrapper"><Label data-testid="banking-expenses-month-label">الشهر</Label><select value={filters.month} onChange={(event) => setFilters((current) => ({ ...current, month: event.target.value }))} disabled={isYearly} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none disabled:opacity-50" data-testid="banking-expenses-month-select">{monthOptions.map(([value, label]) => <option key={value} value={value} data-testid={`banking-expenses-month-option-${value}`}>{label}</option>)}</select></div>
          </div>
        </section>

        {canManage && !isYearly && (
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden sm:p-8" data-testid="banking-expenses-manual-section">
            <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between" data-testid="banking-expenses-manual-heading"><h2 className="text-2xl font-extrabold" data-testid="banking-expenses-manual-title">إدخال البيان والعدد والمبلغ</h2><div className="flex flex-wrap gap-2" data-testid="banking-expenses-manual-actions"><Button type="button" onClick={addManualRow} variant="outline" className="h-11 rounded-lg bg-white" data-testid="add-banking-expense-manual-row-button"><Plus className="h-4 w-4" /> إضافة بيان</Button><Button onClick={saveManual} disabled={savingManual} className="h-11 rounded-lg bg-slate-950 text-white" data-testid="save-banking-expenses-manual-button"><Save className="h-4 w-4" /> {savingManual ? "جاري الحفظ..." : "حفظ"}</Button></div></div>
            <div className="space-y-3" data-testid="banking-expenses-manual-grid">
              {manualRows.map((row, index) => {
                const rowTotal = Number(sanitizeDecimalInput(row.count) || 0) * Number(sanitizeDecimalInput(row.amount) || 0);
                return <div key={row.id} className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 md:grid-cols-[1fr_140px_180px_180px_auto] md:items-end" data-testid={`banking-expenses-manual-row-${index}`}><div data-testid={`banking-expenses-manual-statement-wrapper-${index}`}><Label data-testid={`banking-expenses-manual-statement-label-${index}`}>البيان</Label><Input value={row.statement} onChange={(event) => updateManualRow(row.id, "statement", event.target.value)} className="mt-2 h-12 rounded-lg bg-white text-right" data-testid={`banking-expenses-manual-statement-input-${index}`} /></div><div data-testid={`banking-expenses-manual-count-wrapper-${index}`}><Label data-testid={`banking-expenses-manual-count-label-${index}`}>العدد</Label><Input inputMode="decimal" value={row.count} onChange={(event) => updateManualRow(row.id, "count", event.target.value)} className="mt-2 h-12 rounded-lg bg-white text-right" data-testid={`banking-expenses-manual-count-input-${index}`} /></div><div data-testid={`banking-expenses-manual-amount-wrapper-${index}`}><Label data-testid={`banking-expenses-manual-amount-label-${index}`}>المبلغ</Label><Input inputMode="decimal" value={row.amount} onChange={(event) => updateManualRow(row.id, "amount", event.target.value)} className="mt-2 h-12 rounded-lg bg-white text-right" data-testid={`banking-expenses-manual-amount-input-${index}`} /></div><div data-testid={`banking-expenses-manual-total-wrapper-${index}`}><Label data-testid={`banking-expenses-manual-total-label-${index}`}>الإجمالي</Label><div className="mt-2 flex h-12 items-center rounded-lg border border-slate-200 bg-white px-3 font-extrabold" data-testid={`banking-expenses-manual-total-value-${index}`}>{formatCurrency(rowTotal)}</div></div><Button type="button" onClick={() => removeManualRow(row.id)} variant="outline" className="h-12 rounded-lg border-red-200 bg-red-50 text-red-700 hover:bg-red-100" data-testid={`remove-banking-expense-manual-row-button-${index}`}><Trash2 className="h-4 w-4" /> حذف</Button></div>;
              })}
            </div>
          </section>
        )}

        {canManage && isYearly && <section className="rounded-xl border border-slate-200 bg-white p-5 text-sm font-bold text-slate-600 shadow-sm print:hidden sm:p-8" data-testid="banking-expenses-yearly-manual-note">العرض السنوي يجمع البنود اليدوية المحفوظة في الشهور. للتعديل اختر عرض شهري ثم أدخل البيان والعدد والمبلغ.</section>}

        <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:border-0 print:shadow-none sm:p-8" data-testid="banking-expenses-report-section">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between" data-testid="banking-expenses-report-heading">
            <div data-testid="banking-expenses-report-title-block"><p className="text-sm font-extrabold text-emerald-700" data-testid="banking-expenses-report-eyebrow">{selectedBank?.name}</p><h2 className="text-3xl font-extrabold text-slate-950" data-testid="banking-expenses-report-title">المصروفات البنكية - {periodLabel}</h2></div>
            <div className="rounded-xl bg-slate-950 p-4 text-white" data-testid="banking-expenses-total-card"><p className="text-xs font-bold text-slate-300">إجمالي مصروف البنك</p><p className="text-2xl font-extrabold" data-testid="banking-expenses-total-value">{formatCurrency(totalBankExpenses)}</p></div>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200" data-testid="banking-expenses-table-wrapper">
            <Table data-testid="banking-expenses-table">
              <TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950" data-testid="banking-expenses-table-header-row"><TableHead className="text-right font-extrabold text-white" data-testid="banking-expenses-header-statement">البيان</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="banking-expenses-header-count">العدد</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="banking-expenses-header-bank-expense">المبلغ</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="banking-expenses-header-total">الإجمالي</TableHead></TableRow></TableHeader>
              <TableBody>{visibleReportRows.length === 0 && <TableRow data-testid="banking-expenses-empty-report-row"><TableCell colSpan={4} className="py-8 text-center font-extrabold text-slate-500" data-testid="banking-expenses-empty-report-message">لا توجد بنود مصروفات بنكية لهذه الفترة</TableCell></TableRow>}{visibleReportRows.map((row, index) => <TableRow key={`${row.statement}-${index}`} data-testid={`banking-expenses-row-${index}`}><TableCell className="font-extrabold" data-testid={`banking-expenses-row-${index}-statement`}>{row.statement}</TableCell><TableCell className="font-extrabold" data-testid={`banking-expenses-row-${index}-count`}>{row.count}</TableCell><TableCell className="font-extrabold" data-testid={`banking-expenses-row-${index}-expense`}>{formatCurrency(row.amount)}</TableCell><TableCell className="font-extrabold" data-testid={`banking-expenses-row-${index}-total`}>{formatCurrency(row.total ?? Number(row.count || 0) * Number(row.amount || 0))}</TableCell></TableRow>)}<TableRow className="bg-emerald-50 font-extrabold hover:bg-emerald-50" data-testid="banking-expenses-grand-total-row"><TableCell colSpan={3} data-testid="banking-expenses-grand-total-label">الإجمالي</TableCell><TableCell data-testid="banking-expenses-grand-total-value">{formatCurrency(totalBankExpenses)}</TableCell></TableRow></TableBody>
            </Table>
          </div>
        </section>
      </section>
      <footer className="px-4 pb-5 print:hidden" data-testid="banking-expenses-footer"><CreditLine testId="banking-expenses-creator-credit" /></footer>
    </main>
  );
}