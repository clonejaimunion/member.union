import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, BookOpenText, Home, LogOut, RotateCcw } from "lucide-react";
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
import { formatCurrency, formatNumber } from "@/lib/format";

const today = () => new Date().toISOString().slice(0, 10);
const startOfYear = () => `${new Date().getFullYear()}-01-01`;
const ALL_ACCOUNTS_VALUE = "all";
const accountLabel = (item) => `${item.code} - ${item.name}`;

export default function LedgerPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [filters, setFilters] = useState({ account_id: ALL_ACCOUNTS_VALUE, from_date: startOfYear(), to_date: today() });
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  const selectedAccount = useMemo(() => filters.account_id === ALL_ACCOUNTS_VALUE ? { id: ALL_ACCOUNTS_VALUE, code: "ALL", name: "عرض الكل" } : accounts.find((item) => item.id === filters.account_id) || accounts[0], [accounts, filters.account_id]);

  const loadLedger = useCallback(async () => {
    setLoading(true);
    try {
      const accountsResponse = await api.get("/chart-accounts");
      const postableAccounts = accountsResponse.data.filter((item) => item.is_postable && item.is_active);
      const accountId = filters.account_id || ALL_ACCOUNTS_VALUE;
      setAccounts(postableAccounts);
      if (!accountId) {
        setReport(null);
        return;
      }
      if (filters.from_date && filters.to_date && filters.from_date > filters.to_date) {
        toast.error("تاريخ بداية الفترة يجب أن يكون قبل تاريخ النهاية");
        setReport(null);
        return;
      }
      const params = new URLSearchParams({ account_id: accountId });
      if (filters.from_date) params.set("from_date", filters.from_date);
      if (filters.to_date) params.set("to_date", filters.to_date);
      const response = await api.get(`/ledger?${params.toString()}`);
      setReport(response.data);
    } catch (error) {
      toast.error("تعذر تحميل دفتر الأستاذ من القيود اليومية");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [filters.account_id, filters.from_date, filters.to_date]);

  useEffect(() => { loadLedger(); }, [loadLedger]);

  const rows = report?.rows || [];
  const isAllAccounts = filters.account_id === ALL_ACCOUNTS_VALUE || report?.account_scope === "all";
  const totals = { opening: report?.opening_balance || 0, debit: report?.total_debit || 0, credit: report?.total_credit || 0, balance: report?.closing_balance || 0 };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="ledger-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="ledger-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="ledger-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="ledger-brand-icon"><BookOpenText className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700" data-testid="ledger-eyebrow">دفتر الأستاذ العام</p><h1 className="text-2xl font-extrabold" data-testid="ledger-title">الأستاذ من القيود اليومية</h1></div></div>
          <div className="flex flex-wrap items-center gap-3" data-testid="ledger-header-actions"><Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="ledger-user-badge">{user?.username}</Badge><Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="ledger-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="ledger-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="ledger-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>
      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="ledger-content">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden sm:p-8" data-testid="ledger-filters-section">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between" data-testid="ledger-filters-heading"><h2 className="text-3xl font-extrabold" data-testid="ledger-filters-title">اختيارات دفتر الأستاذ</h2><ExportReportButtons title={`دفتر الأستاذ - ${report?.account?.name || selectedAccount?.name || ""}`} fileName={`دفتر-الأستاذ-${report?.account?.name || selectedAccount?.name || ""}`} selectors={["[data-testid='ledger-report-section']"]} disabled={loading || !report} pdfLabel="طباعة PDF" pdfTestId="print-ledger-report-button" excelTestId="export-ledger-excel-button" wordTestId="export-ledger-word-button" /></div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="ledger-filters-grid">
            <div data-testid="ledger-account-wrapper"><Label data-testid="ledger-account-label">الحساب</Label><select value={filters.account_id} onChange={(event) => setFilters((current) => ({ ...current, account_id: event.target.value }))} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="ledger-account-select"><option value={ALL_ACCOUNTS_VALUE} data-testid="ledger-account-option-all">عرض الكل ضمن الفترة المحددة</option>{accounts.map((item) => <option key={item.id} value={item.id} label={accountLabel(item)} data-testid={`ledger-account-option-${item.id}`} />)}</select></div>
            <div data-testid="ledger-from-date-wrapper"><Label data-testid="ledger-from-date-label">من تاريخ</Label><Input type="date" value={filters.from_date} onChange={(event) => setFilters((current) => ({ ...current, from_date: event.target.value }))} className="mt-2 h-12 rounded-lg bg-slate-50 text-right" data-testid="ledger-from-date-input" /></div>
            <div data-testid="ledger-to-date-wrapper"><Label data-testid="ledger-to-date-label">إلى تاريخ</Label><Input type="date" value={filters.to_date} onChange={(event) => setFilters((current) => ({ ...current, to_date: event.target.value }))} className="mt-2 h-12 rounded-lg bg-slate-50 text-right" data-testid="ledger-to-date-input" /></div>
          </div>
          <Button type="button" onClick={loadLedger} variant="outline" className="mt-4 h-11 rounded-lg bg-white" data-testid="refresh-ledger-button"><RotateCcw className="h-4 w-4" /> تحديث</Button>
        </section>
        <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:border-0 print:shadow-none sm:p-8" data-testid="ledger-report-section">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between" data-testid="ledger-report-heading"><div><p className="text-sm font-extrabold text-emerald-700" data-testid="ledger-report-bank">{isAllAccounts ? "ALL" : report?.account?.code}</p><h2 className="text-3xl font-extrabold" data-testid="ledger-report-title">دفتر الأستاذ - {isAllAccounts ? "عرض الكل" : report?.account?.name || selectedAccount?.name}</h2><p className="mt-1 text-sm font-bold text-slate-500" data-testid="ledger-report-period">رصيد أول المدة + حركة الفترة فقط من {filters.from_date} إلى {filters.to_date}</p></div><div className="grid grid-cols-1 gap-3 sm:grid-cols-4" data-testid="ledger-kpi-grid"><div className="rounded-xl bg-amber-50 p-4 text-amber-900" data-testid="ledger-opening-card"><p className="text-xs font-bold text-amber-700">رصيد أول المدة</p><p className="text-xl font-extrabold" data-testid="ledger-opening-total">{formatCurrency(totals.opening)}</p></div><div className="rounded-xl bg-emerald-50 p-4 text-emerald-900" data-testid="ledger-debit-card"><p className="text-xs font-bold text-emerald-700">حركة مدين</p><p className="text-xl font-extrabold" data-testid="ledger-debit-total">{formatCurrency(totals.debit)}</p></div><div className="rounded-xl bg-red-50 p-4 text-red-900" data-testid="ledger-credit-card"><p className="text-xs font-bold text-red-700">حركة دائن</p><p className="text-xl font-extrabold" data-testid="ledger-credit-total">{formatCurrency(totals.credit)}</p></div><div className="rounded-xl bg-slate-950 p-4 text-white" data-testid="ledger-balance-card"><p className="text-xs font-bold text-slate-300">رصيد آخر المدة</p><p className="text-xl font-extrabold" data-testid="ledger-balance-total">{formatCurrency(totals.balance)}</p></div></div></div>
          <div className="overflow-hidden rounded-xl border border-slate-200" data-testid="ledger-table-wrapper"><Table data-testid="ledger-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950" data-testid="ledger-table-header-row"><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-serial">م</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-date">التاريخ</TableHead>{isAllAccounts && <TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-account">الحساب</TableHead>}<TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-source">المصدر</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-reference">المرجع</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-statement">البيان</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-debit">مدين</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-credit">دائن</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-balance">{isAllAccounts ? "صافي تراكمي" : "الرصيد"}</TableHead></TableRow></TableHeader><TableBody>{rows.length === 0 && <TableRow data-testid="ledger-empty-row"><TableCell colSpan={isAllAccounts ? 9 : 8} className="py-8 text-center font-extrabold text-slate-500" data-testid="ledger-empty-message">لا توجد حركات في الفترة المختارة</TableCell></TableRow>}{rows.map((row) => <TableRow key={`${row.entry_id}-${row.serial}`} data-testid={`ledger-row-${row.serial}`}><TableCell data-testid={`ledger-row-${row.serial}-serial`}>{formatNumber(row.serial)}</TableCell><TableCell data-testid={`ledger-row-${row.serial}-date`}>{row.entry_date}</TableCell>{isAllAccounts && <TableCell className="font-extrabold" data-testid={`ledger-row-${row.serial}-account`}>{row.account_code ? `${row.account_code} - ${row.account_name}` : "—"}</TableCell>}<TableCell data-testid={`ledger-row-${row.serial}-source`}>{row.source_type}</TableCell><TableCell data-testid={`ledger-row-${row.serial}-reference`}>{row.reference || "—"}</TableCell><TableCell className="font-bold" data-testid={`ledger-row-${row.serial}-statement`}>{row.description}</TableCell><TableCell data-testid={`ledger-row-${row.serial}-debit`}>{row.debit ? formatCurrency(row.debit) : "—"}</TableCell><TableCell data-testid={`ledger-row-${row.serial}-credit`}>{row.credit ? formatCurrency(row.credit) : "—"}</TableCell><TableCell className="font-extrabold" data-testid={`ledger-row-${row.serial}-balance`}>{formatCurrency(row.balance)}</TableCell></TableRow>)}<TableRow className="bg-slate-50 font-extrabold hover:bg-slate-50" data-testid="ledger-grand-total-row"><TableCell colSpan={isAllAccounts ? 6 : 5} data-testid="ledger-grand-total-label">الإجمالي داخل الفترة فقط</TableCell><TableCell data-testid="ledger-grand-total-debit">{formatCurrency(totals.debit)}</TableCell><TableCell data-testid="ledger-grand-total-credit">{formatCurrency(totals.credit)}</TableCell><TableCell data-testid="ledger-grand-total-balance">{formatCurrency(totals.balance)}</TableCell></TableRow></TableBody></Table></div>
        </section>
      </section>
      <footer className="px-4 pb-5 print:hidden" data-testid="ledger-footer"><CreditLine testId="ledger-creator-credit" /></footer>
    </main>
  );
}