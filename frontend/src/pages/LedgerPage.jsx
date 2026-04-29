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
import { fallbackBanks } from "@/lib/banks";
import { formatCurrency, formatNumber } from "@/lib/format";

const today = () => new Date().toISOString().slice(0, 10);
const startOfYear = () => `${new Date().getFullYear()}-01-01`;
const accountOptions = [
  { value: "bank", label: "حساب البنك", balance: (row) => row.debit - row.credit },
  { value: "revenues", label: "الإيرادات", balance: (row) => row.credit - row.debit },
  { value: "expenses", label: "المصروفات", balance: (row) => row.debit - row.credit },
  { value: "banking_expenses", label: "المصروفات البنكية", balance: (row) => row.debit - row.credit },
];

const monthRange = (fromDate, toDate) => {
  const months = [];
  const cursor = new Date(`${fromDate.slice(0, 7)}-01T00:00:00`);
  const end = new Date(`${toDate.slice(0, 7)}-01T00:00:00`);
  while (cursor <= end) {
    const year = cursor.getFullYear();
    const month = String(cursor.getMonth() + 1).padStart(2, "0");
    months.push({ year, month, lastDay: new Date(year, cursor.getMonth() + 1, 0).toISOString().slice(0, 10) });
    cursor.setMonth(cursor.getMonth() + 1);
  }
  return months;
};

const cappedFee = (amount, percent, min, max) => {
  const raw = Number(amount || 0) * (Number(percent || 0) / 100);
  const withMin = Math.max(raw, Number(min || 0));
  return Number(max || 0) > 0 ? Math.min(withMin, Number(max || 0)) : withMin;
};

const feeRules = (tariff) => {
  const rule = tariff?.rules || {};
  return {
    monthlyStatementFee: Number(rule.monthly_statement_fee || 0),
    paymentOrderFee: Number(rule.payment_order_fee || 0),
    incomingCheckFee: Number(rule.incoming_check_internal_fee || 0),
    incomingExternalCheckFee: (amount) => cappedFee(amount, rule.incoming_check_external_percent, rule.incoming_check_external_min, rule.incoming_check_external_max),
    issuedCheckFee: Number(rule.issued_check_internal_fee || 0),
    issuedExternalCheckFee: (amount) => cappedFee(amount, rule.issued_check_external_percent, rule.issued_check_external_min, rule.issued_check_external_max),
    outgoingTransferFee: (amount) => cappedFee(amount, rule.outgoing_transfer_percent, rule.outgoing_transfer_min, rule.outgoing_transfer_max),
    cashDepositFee: (amount) => Number(amount || 0) > 0 ? Math.max(Number(amount || 0) * (Number(rule.cash_deposit_percent || 0) / 100), Number(rule.cash_deposit_min || 0)) : 0,
    depositLinkFee: () => Number(rule.deposit_link_fee || 0),
  };
};

export default function LedgerPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [banks, setBanks] = useState(fallbackBanks);
  const [filters, setFilters] = useState({ bank_id: "industrial-development", account_type: "bank", from_date: startOfYear(), to_date: today() });
  const [revenues, setRevenues] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [deposits, setDeposits] = useState([]);
  const [manualCharges, setManualCharges] = useState([]);
  const [tariff, setTariff] = useState(null);
  const [loading, setLoading] = useState(true);

  const selectedBank = banks.find((bank) => bank.id === filters.bank_id) || fallbackBanks.find((bank) => bank.id === filters.bank_id) || banks[0];
  const selectedAccount = accountOptions.find((item) => item.value === filters.account_type) || accountOptions[0];

  const loadLedger = useCallback(async () => {
    setLoading(true);
    try {
      const months = monthRange(filters.from_date, filters.to_date);
      const [banksResponse, tariffResponse, revenuesResponse, expensesResponse, depositsResponse, ...manualResponses] = await Promise.all([
        api.get("/banks"),
        api.get(`/banking-tariffs/${filters.bank_id}`),
        api.get(`/revenues?bank_id=${filters.bank_id}&from_date=${filters.from_date}&to_date=${filters.to_date}`),
        api.get(`/expenses?bank_id=${filters.bank_id}&from_date=${filters.from_date}&to_date=${filters.to_date}`),
        api.get(`/banks/${filters.bank_id}/deposits`),
        ...months.map((item) => api.get(`/banking-expenses/manual?bank_id=${filters.bank_id}&year=${item.year}&month=${Number(item.month)}`)),
      ]);
      setBanks(banksResponse.data);
      setTariff(tariffResponse.data);
      setRevenues(revenuesResponse.data);
      setExpenses(expensesResponse.data);
      setDeposits(depositsResponse.data);
      setManualCharges(manualResponses.map((response, index) => ({ ...response.data, period: months[index] })));
    } catch (error) {
      toast.error("تعذر تحميل دفتر الأستاذ");
      setRevenues([]);
      setExpenses([]);
      setDeposits([]);
      setManualCharges([]);
    } finally {
      setLoading(false);
    }
  }, [filters.bank_id, filters.from_date, filters.to_date]);

  useEffect(() => { loadLedger(); }, [loadLedger]);

  const ledgerRows = useMemo(() => {
    const rules = feeRules(tariff);
    const rows = [];
    const pushRow = (row) => {
      if (Number(row.debit || 0) === 0 && Number(row.credit || 0) === 0) return;
      rows.push({ ...row, debit: Number(row.debit || 0), credit: Number(row.credit || 0) });
    };

    if (filters.account_type === "bank" && Number(selectedBank?.opening_balance || 0) !== 0) {
      const openingBalance = Number(selectedBank.opening_balance || 0);
      pushRow({
        date: filters.from_date,
        source: "رصيد افتتاحي",
        reference: "—",
        statement: `الرصيد الافتتاحي - ${selectedBank.name}`,
        debit: openingBalance > 0 ? openingBalance : 0,
        credit: openingBalance < 0 ? Math.abs(openingBalance) : 0,
      });
    }

    revenues.filter((item) => (item.bank_collection_status || "under_collection") === "collected").forEach((item) => {
      const statement = `إيراد محصل - ${item.collection_method === "check" ? `شيك رقم ${item.check_number}` : item.collection_method === "payment_order" ? `أمر دفع رقم ${item.payment_order_number}` : "نقدي"}`;
      if (["bank", "revenues"].includes(filters.account_type)) pushRow({ date: item.issued_at || item.dated, source: "الإيرادات", reference: item.receipt_number, statement, debit: filters.account_type === "bank" ? item.amount : 0, credit: filters.account_type === "revenues" ? item.amount : 0 });

      if (["bank", "banking_expenses"].includes(filters.account_type)) {
        let fee = 0;
        let feeStatement = "";
        if (item.collection_method === "payment_order") { fee = rules.paymentOrderFee; feeStatement = `عمولة أمر دفع رقم ${item.payment_order_number}`; }
        if (item.collection_method === "check") { fee = (item.check_clearing_type || "internal") === "internal" ? rules.incomingCheckFee : rules.incomingExternalCheckFee(item.amount); feeStatement = `عمولة تحصيل شيك رقم ${item.check_number}`; }
        if (item.collection_method === "cash") { fee = rules.cashDepositFee(item.amount); feeStatement = "عمولة إيداع نقدي"; }
        pushRow({ date: item.issued_at || item.dated, source: "المصروفات البنكية", reference: item.receipt_number, statement: feeStatement, debit: filters.account_type === "banking_expenses" ? fee : 0, credit: filters.account_type === "bank" ? fee : 0 });
      }
    });

    expenses.filter((item) => (item.bank_payment_status || "not_presented") === "paid").forEach((item) => {
      const statement = `مصروف منفذ - ${item.payment_method === "check" ? `شيك رقم ${item.check_number}` : item.payment_method === "bank_transfer" ? `تحويل رقم ${item.transfer_number}` : "نقدي"}`;
      if (["bank", "expenses"].includes(filters.account_type)) pushRow({ date: item.issued_at, source: "المصروفات", reference: item.expense_number, statement, debit: filters.account_type === "expenses" ? item.net_amount : 0, credit: filters.account_type === "bank" ? item.net_amount : 0 });

      if (["bank", "banking_expenses"].includes(filters.account_type)) {
        let fee = 0;
        let feeStatement = "";
        if (item.payment_method === "check") { fee = (item.check_clearing_type || "internal") === "internal" ? rules.issuedCheckFee : rules.issuedExternalCheckFee(item.net_amount); feeStatement = `عمولة صرف شيك رقم ${item.check_number}`; }
        if (item.payment_method === "bank_transfer") { fee = rules.outgoingTransferFee(item.net_amount); feeStatement = `عمولة تحويل لمستفيد رقم ${item.transfer_number}`; }
        pushRow({ date: item.issued_at, source: "المصروفات البنكية", reference: item.expense_number, statement: feeStatement, debit: filters.account_type === "banking_expenses" ? fee : 0, credit: filters.account_type === "bank" ? fee : 0 });
      }
    });

    if (["bank", "banking_expenses"].includes(filters.account_type)) {
      manualCharges.forEach((item) => {
        const monthDate = item.period.lastDay;
        pushRow({ date: monthDate, source: "المصروفات البنكية", reference: `${item.year}/${String(item.month).padStart(2, "0")}`, statement: "رسوم كشف الحساب الشهري", debit: filters.account_type === "banking_expenses" ? rules.monthlyStatementFee : 0, credit: filters.account_type === "bank" ? rules.monthlyStatementFee : 0 });
        [
          ["stamp", "دمغة"],
          ["bank_correspondence", "مراسلات بنكية"],
          ["correspondence_safekeeping", "حفظ مراسلات"],
          ["internal_transfer_fee", "رسوم تحويل داخلي"],
          ["external_transfer_fee", "رسوم تحويل خارجي"],
        ].forEach(([key, label]) => {
          const amount = Number(item[key] || 0);
          pushRow({ date: monthDate, source: "المصروفات البنكية", reference: `${item.year}/${String(item.month).padStart(2, "0")}`, statement: label, debit: filters.account_type === "banking_expenses" ? amount : 0, credit: filters.account_type === "bank" ? amount : 0 });
        });
      });
      deposits.filter((item) => String(item.creation_datetime || "").slice(0, 10) >= filters.from_date && String(item.creation_datetime || "").slice(0, 10) <= filters.to_date).forEach((item) => {
        const fee = rules.depositLinkFee(item.amount);
        pushRow({ date: String(item.creation_datetime).slice(0, 10), source: "المصروفات البنكية", reference: item.deposit_number, statement: "رسوم ربط وديعة", debit: filters.account_type === "banking_expenses" ? fee : 0, credit: filters.account_type === "bank" ? fee : 0 });
      });
    }

    let balance = 0;
    return rows.sort((a, b) => `${a.date}-${a.source}`.localeCompare(`${b.date}-${b.source}`)).map((row, index) => {
      balance += selectedAccount.balance(row);
      return { ...row, serial: index + 1, balance };
    });
  }, [deposits, expenses, filters.account_type, filters.from_date, filters.to_date, manualCharges, revenues, selectedAccount, selectedBank, tariff]);

  const totals = useMemo(() => ledgerRows.reduce((acc, row) => ({ debit: acc.debit + row.debit, credit: acc.credit + row.credit, balance: row.balance }), { debit: 0, credit: 0, balance: 0 }), [ledgerRows]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="ledger-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="ledger-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="ledger-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="ledger-brand-icon"><BookOpenText className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700" data-testid="ledger-eyebrow">دفتر الأستاذ</p><h1 className="text-2xl font-extrabold" data-testid="ledger-title">دفتر الأستاذ</h1></div></div>
          <div className="flex flex-wrap items-center gap-3" data-testid="ledger-header-actions"><Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="ledger-user-badge">{user?.username}</Badge><Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="ledger-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="ledger-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="ledger-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>
      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="ledger-content">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden sm:p-8" data-testid="ledger-filters-section">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between" data-testid="ledger-filters-heading"><h2 className="text-3xl font-extrabold" data-testid="ledger-filters-title">اختيارات دفتر الأستاذ</h2><ExportReportButtons title={`دفتر الأستاذ - ${selectedAccount.label} - ${selectedBank?.name || ""}`} fileName={`دفتر-الأستاذ-${selectedAccount.label}-${selectedBank?.name || ""}`} selectors={["[data-testid='ledger-report-section']"]} disabled={loading} pdfLabel="طباعة PDF" pdfTestId="print-ledger-report-button" excelTestId="export-ledger-excel-button" wordTestId="export-ledger-word-button" /></div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4" data-testid="ledger-filters-grid">
            <div data-testid="ledger-bank-wrapper"><Label data-testid="ledger-bank-label">البنك</Label><select value={filters.bank_id} onChange={(event) => setFilters((current) => ({ ...current, bank_id: event.target.value }))} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="ledger-bank-select">{banks.map((bank) => <option key={bank.id} value={bank.id} data-testid={`ledger-bank-option-${bank.id}`}>{bank.name}</option>)}</select></div>
            <div data-testid="ledger-account-wrapper"><Label data-testid="ledger-account-label">الحساب</Label><select value={filters.account_type} onChange={(event) => setFilters((current) => ({ ...current, account_type: event.target.value }))} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="ledger-account-select">{accountOptions.map((item) => <option key={item.value} value={item.value} data-testid={`ledger-account-option-${item.value}`}>{item.label}</option>)}</select></div>
            <div data-testid="ledger-from-date-wrapper"><Label data-testid="ledger-from-date-label">من تاريخ</Label><Input type="date" value={filters.from_date} onChange={(event) => setFilters((current) => ({ ...current, from_date: event.target.value }))} className="mt-2 h-12 rounded-lg bg-slate-50 text-right" data-testid="ledger-from-date-input" /></div>
            <div data-testid="ledger-to-date-wrapper"><Label data-testid="ledger-to-date-label">إلى تاريخ</Label><Input type="date" value={filters.to_date} onChange={(event) => setFilters((current) => ({ ...current, to_date: event.target.value }))} className="mt-2 h-12 rounded-lg bg-slate-50 text-right" data-testid="ledger-to-date-input" /></div>
          </div>
          <Button type="button" onClick={loadLedger} variant="outline" className="mt-4 h-11 rounded-lg bg-white" data-testid="refresh-ledger-button"><RotateCcw className="h-4 w-4" /> تحديث</Button>
        </section>
        <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:border-0 print:shadow-none sm:p-8" data-testid="ledger-report-section">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between" data-testid="ledger-report-heading"><div><p className="text-sm font-extrabold text-emerald-700" data-testid="ledger-report-bank">{selectedBank?.name}</p><h2 className="text-3xl font-extrabold" data-testid="ledger-report-title">دفتر الأستاذ - {selectedAccount.label}</h2><p className="mt-1 text-sm font-bold text-slate-500" data-testid="ledger-report-period">من {filters.from_date} إلى {filters.to_date}</p></div><div className="grid grid-cols-1 gap-3 sm:grid-cols-3" data-testid="ledger-kpi-grid"><div className="rounded-xl bg-emerald-50 p-4 text-emerald-900" data-testid="ledger-debit-card"><p className="text-xs font-bold text-emerald-700">إجمالي مدين</p><p className="text-xl font-extrabold" data-testid="ledger-debit-total">{formatCurrency(totals.debit)}</p></div><div className="rounded-xl bg-red-50 p-4 text-red-900" data-testid="ledger-credit-card"><p className="text-xs font-bold text-red-700">إجمالي دائن</p><p className="text-xl font-extrabold" data-testid="ledger-credit-total">{formatCurrency(totals.credit)}</p></div><div className="rounded-xl bg-slate-950 p-4 text-white" data-testid="ledger-balance-card"><p className="text-xs font-bold text-slate-300">الرصيد</p><p className="text-xl font-extrabold" data-testid="ledger-balance-total">{formatCurrency(totals.balance)}</p></div></div></div>
          <div className="overflow-hidden rounded-xl border border-slate-200" data-testid="ledger-table-wrapper"><Table data-testid="ledger-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950" data-testid="ledger-table-header-row"><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-serial">م</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-date">التاريخ</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-source">المصدر</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-reference">المرجع</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-statement">البيان</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-debit">مدين</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-credit">دائن</TableHead><TableHead className="text-right font-extrabold text-white" data-testid="ledger-header-balance">الرصيد</TableHead></TableRow></TableHeader><TableBody>{ledgerRows.length === 0 && <TableRow data-testid="ledger-empty-row"><TableCell colSpan={8} className="py-8 text-center font-extrabold text-slate-500" data-testid="ledger-empty-message">لا توجد حركات في الفترة المختارة</TableCell></TableRow>}{ledgerRows.map((row) => <TableRow key={`${row.serial}-${row.date}-${row.reference}-${row.statement}`} data-testid={`ledger-row-${row.serial}`}><TableCell data-testid={`ledger-row-${row.serial}-serial`}>{formatNumber(row.serial)}</TableCell><TableCell data-testid={`ledger-row-${row.serial}-date`}>{row.date}</TableCell><TableCell data-testid={`ledger-row-${row.serial}-source`}>{row.source}</TableCell><TableCell data-testid={`ledger-row-${row.serial}-reference`}>{row.reference}</TableCell><TableCell className="font-bold" data-testid={`ledger-row-${row.serial}-statement`}>{row.statement}</TableCell><TableCell data-testid={`ledger-row-${row.serial}-debit`}>{row.debit ? formatCurrency(row.debit) : "—"}</TableCell><TableCell data-testid={`ledger-row-${row.serial}-credit`}>{row.credit ? formatCurrency(row.credit) : "—"}</TableCell><TableCell className="font-extrabold" data-testid={`ledger-row-${row.serial}-balance`}>{formatCurrency(row.balance)}</TableCell></TableRow>)}<TableRow className="bg-slate-50 font-extrabold hover:bg-slate-50" data-testid="ledger-grand-total-row"><TableCell colSpan={5} data-testid="ledger-grand-total-label">الإجمالي</TableCell><TableCell data-testid="ledger-grand-total-debit">{formatCurrency(totals.debit)}</TableCell><TableCell data-testid="ledger-grand-total-credit">{formatCurrency(totals.credit)}</TableCell><TableCell data-testid="ledger-grand-total-balance">{formatCurrency(totals.balance)}</TableCell></TableRow></TableBody></Table></div>
        </section>
      </section>
      <footer className="px-4 pb-5 print:hidden" data-testid="ledger-footer"><CreditLine testId="ledger-creator-credit" /></footer>
    </main>
  );
}