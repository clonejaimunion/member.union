import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Banknote, Eye, Home, Landmark, LogOut, Printer, RotateCcw, Search, ShieldCheck, WalletCards } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { formatCurrency, formatDate, formatNumber } from "@/lib/format";
import { printNow } from "@/lib/printOrientation";

const today = () => new Date().toISOString().slice(0, 10);
const startOfYear = () => `${new Date().getFullYear()}-01-01`;
const emptyReport = { summary: {}, accounts: [], transactions: [] };
const accountKindLabels = { all: "كل الحسابات", bank: "البنوك فقط", cash: "الخزينة فقط" };
const movementOptions = [
  { value: "all", label: "كل الحركات" },
  { value: "revenue", label: "إيرادات / زيادة" },
  { value: "expense", label: "مصروفات / نقص" },
  { value: "opening", label: "رصيد افتتاحي" },
];

const sourceLabels = {
  manual: "قيد يدوي",
  revenue: "إيراد",
  expense: "مصروف",
  banking_expense: "مصروف بنكي",
  deposit: "وديعة",
  deposit_interest: "فائدة وديعة",
  outstanding_check: "شيك لم يُقدَّم للصرف",
  collection_check: "شيك تحت التحصيل",
  prior_year_check: "شيك سنوات سابقة",
  reconciliation: "تسوية بنكية",
  fixed_asset: "أصل ثابت",
  custody_advance: "عهدة/سلفة",
  custody_advance_settlement: "تسوية عهدة/سلفة",
  opening_balance: "رصيد افتتاحي",
  membership_batch_payment: "إذن عضوية جماعي",
  inventory: "مخزون",
  misc_creditor: "دائن متنوع",
};

const buildPrintableHtml = (title, reportHtml) => `<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8" /><title>${title}</title><style>@page{size:A4 landscape;margin:8mm}body{font-family:Tahoma,Arial,sans-serif;color:#0f172a;direction:rtl}h1,h2,h3,p{margin:0 0 8px}.print-shell{padding:8px}table{width:100%;border-collapse:collapse;table-layout:auto;margin-top:10px}th,td{border:1px solid #111827;padding:6px;text-align:right;font-size:11px;vertical-align:top}th{background:#0f172a;color:white}.no-print,button,input,select{display:none!important}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.rounded-2xl,.rounded-xl,.rounded-lg{border-radius:4px}.bg-white,.bg-slate-50{background:#fff}.shadow-sm{box-shadow:none}.border{border:1px solid #cbd5e1}.p-5,.p-6{padding:10px}.text-3xl{font-size:18px}.text-xl{font-size:15px}.text-sm,.text-xs{font-size:11px}</style></head><body><main class="print-shell"><h1>${title}</h1>${reportHtml}</main></body></html>`;

function StatCard({ testId, title, value, tone, Icon }) {
  return (
    <article className={`rounded-2xl border p-5 shadow-sm ${tone}`} data-testid={testId}>
      <div className="flex items-start justify-between gap-3" data-testid={`${testId}-content`}>
        <div data-testid={`${testId}-text`}>
          <p className="text-xs font-extrabold opacity-75" data-testid={`${testId}-title`}>{title}</p>
          <p className="mt-3 text-2xl font-black leading-tight" data-testid={`${testId}-value`}>{formatCurrency(value)}</p>
          <p className="mt-1 text-xs font-bold opacity-70" data-testid={`${testId}-currency`}>جنيه مصري</p>
        </div>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/80 text-slate-950 shadow-sm" data-testid={`${testId}-icon`}><Icon className="h-6 w-6" /></div>
      </div>
    </article>
  );
}

export default function TreasuryBanksPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [filters, setFilters] = useState({ from_date: startOfYear(), to_date: today(), account_id: "all", account_kind: "all", movement_type: "all", search: "" });
  const [report, setReport] = useState(emptyReport);
  const [accountOptions, setAccountOptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [previewOpen, setPreviewOpen] = useState(false);

  const summary = report.summary || {};
  const transactions = report.transactions || [];

  const loadReport = useCallback(async () => {
    if (filters.from_date && filters.to_date && filters.from_date > filters.to_date) {
      toast.error("تاريخ البداية يجب أن يكون قبل تاريخ النهاية");
      return;
    }
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.from_date) params.set("from_date", filters.from_date);
      if (filters.to_date) params.set("to_date", filters.to_date);
      if (filters.account_id) params.set("account_id", filters.account_id);
      if (filters.account_kind) params.set("account_kind", filters.account_kind);
      if (filters.movement_type) params.set("movement_type", filters.movement_type);
      if (filters.search.trim()) params.set("search", filters.search.trim());
      const response = await api.get(`/treasury-banks?${params.toString()}`);
      setReport(response.data);
      if (!accountOptions.length || filters.account_id === "all") setAccountOptions(response.data.accounts || []);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تحميل الخزينة والبنوك من القيود اليومية");
      setReport(emptyReport);
    } finally {
      setLoading(false);
    }
  }, [accountOptions.length, filters.account_id, filters.account_kind, filters.from_date, filters.movement_type, filters.search, filters.to_date]);

  useEffect(() => { loadReport(); }, [loadReport]);

  const selectedAccountName = useMemo(() => {
    if (filters.account_id === "all") return accountKindLabels[filters.account_kind] || "كل الحسابات";
    const account = accountOptions.find((item) => item.id === filters.account_id);
    return account ? `${account.code || ""} - ${account.name}` : "حساب محدد";
  }, [accountOptions, filters.account_id, filters.account_kind]);

  const openPrintWindow = (printNowAfter = true) => {
    const reportNode = document.querySelector("[data-testid='treasury-banks-print-section']");
    const printWindow = window.open("", "_blank", "width=1200,height=800");
    if (!printWindow || !reportNode) {
      printNow();
      return;
    }
    const title = `الخزينة والبنوك - ${selectedAccountName}`;
    printWindow.document.write(buildPrintableHtml(title, reportNode.outerHTML));
    printWindow.document.close();
    printWindow.focus();
    if (printNowAfter) setTimeout(() => printWindow.print(), 250);
  };

  return (
    <main className="min-h-screen bg-[#f4f8fb] text-slate-950" data-testid="treasury-banks-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/95 backdrop-blur-xl print:hidden" data-testid="treasury-banks-header">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8" data-testid="treasury-banks-header-inner">
          <div className="flex items-center gap-3" data-testid="treasury-banks-brand">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#075985] text-white shadow-sm" data-testid="treasury-banks-brand-icon"><Landmark className="h-6 w-6" /></div>
            <div data-testid="treasury-banks-brand-text">
              <p className="text-xs font-extrabold text-sky-700" data-testid="treasury-banks-eyebrow">مراقبة وتحليل فقط</p>
              <h1 className="text-2xl font-black" data-testid="treasury-banks-title">الخزينة والبنوك</h1>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3" data-testid="treasury-banks-header-actions">
            <Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="treasury-banks-user-badge">{user?.full_name || user?.username}</Badge>
            <Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="treasury-banks-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button>
            <Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="treasury-banks-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button>
            <Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="treasury-banks-logout-button"><LogOut className="h-4 w-4" /> خروج</Button>
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-[1500px] grid-cols-1 gap-6 px-4 py-8 sm:px-6 lg:px-8 xl:grid-cols-[minmax(0,1fr)_330px]" data-testid="treasury-banks-content">
        <div className="space-y-6" data-testid="treasury-banks-main-column">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm print:hidden" data-testid="treasury-banks-filters-section">
            <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between" data-testid="treasury-banks-filters-heading">
              <div data-testid="treasury-banks-filters-title-block">
                <h2 className="text-3xl font-black" data-testid="treasury-banks-filters-title">الفلتر والبحث</h2>
                <p className="mt-1 text-sm font-bold text-slate-500" data-testid="treasury-banks-filters-subtitle">مصدر القراءة الوحيد هو القيود اليومية المرحلة، بدون إنشاء أو تعديل أي بيانات.</p>
              </div>
              <div className="flex flex-wrap gap-2" data-testid="treasury-banks-print-actions">
                <Button type="button" onClick={() => setPreviewOpen(true)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="treasury-banks-preview-button"><Eye className="h-4 w-4" /> معاينة</Button>
                <Button type="button" onClick={() => openPrintWindow(true)} className="h-11 rounded-lg bg-[#075985] text-white" data-testid="treasury-banks-print-pdf-button"><Printer className="h-4 w-4" /> طباعة PDF</Button>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6" data-testid="treasury-banks-filters-grid">
              <div data-testid="treasury-banks-from-wrapper"><Label data-testid="treasury-banks-from-label">من تاريخ</Label><Input type="date" value={filters.from_date} onChange={(event) => setFilters((current) => ({ ...current, from_date: event.target.value }))} className="mt-2 h-12 bg-slate-50 text-right" data-testid="treasury-banks-from-date-input" /></div>
              <div data-testid="treasury-banks-to-wrapper"><Label data-testid="treasury-banks-to-label">إلى تاريخ</Label><Input type="date" value={filters.to_date} onChange={(event) => setFilters((current) => ({ ...current, to_date: event.target.value }))} className="mt-2 h-12 bg-slate-50 text-right" data-testid="treasury-banks-to-date-input" /></div>
              <div data-testid="treasury-banks-kind-wrapper"><Label data-testid="treasury-banks-kind-label">نوع الحساب</Label><select value={filters.account_kind} onChange={(event) => setFilters((current) => ({ ...current, account_kind: event.target.value, account_id: "all" }))} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 text-sm font-extrabold" data-testid="treasury-banks-account-kind-select"><option value="all" label="كل الحسابات" /><option value="bank" label="البنوك فقط" /><option value="cash" label="الخزينة فقط" /></select></div>
              <div data-testid="treasury-banks-account-wrapper"><Label data-testid="treasury-banks-account-label">الحساب</Label><select value={filters.account_id} onChange={(event) => setFilters((current) => ({ ...current, account_id: event.target.value }))} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 text-sm font-extrabold" data-testid="treasury-banks-account-select"><option value="all" label="كل البنوك والخزينة" />{accountOptions.map((item) => <option key={item.id} value={item.id} label={`${item.code || ""} - ${item.name || ""}`} />)}</select></div>
              <div data-testid="treasury-banks-movement-wrapper"><Label data-testid="treasury-banks-movement-label">نوع الحركة</Label><select value={filters.movement_type} onChange={(event) => setFilters((current) => ({ ...current, movement_type: event.target.value }))} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 text-sm font-extrabold" data-testid="treasury-banks-movement-select">{movementOptions.map((item) => <option key={item.value} value={item.value} label={item.label} />)}</select></div>
              <div data-testid="treasury-banks-search-wrapper"><Label data-testid="treasury-banks-search-label">بحث</Label><div className="relative mt-2" data-testid="treasury-banks-search-box"><Search className="pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-slate-400" /><Input value={filters.search} onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))} placeholder="رقم القيد أو البيان أو الحساب" className="h-12 bg-slate-50 pr-9 text-right" data-testid="treasury-banks-search-input" /></div></div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2" data-testid="treasury-banks-filter-buttons">
              <Button type="button" onClick={loadReport} disabled={loading} className="h-11 rounded-lg bg-slate-950 text-white" data-testid="treasury-banks-apply-filter-button"><RotateCcw className="h-4 w-4" /> تطبيق الفلتر</Button>
              <Button type="button" variant="outline" onClick={() => setFilters({ from_date: startOfYear(), to_date: today(), account_id: "all", account_kind: "all", movement_type: "all", search: "" })} className="h-11 rounded-lg bg-white" data-testid="treasury-banks-clear-filter-button">مسح</Button>
            </div>
          </section>

          <section className="space-y-6" data-testid="treasury-banks-print-section">
            <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="treasury-banks-stat-grid">
              <StatCard testId="treasury-banks-total-balance-card" title="إجمالي الرصيد" value={summary.total_balance} tone="border-sky-200 bg-sky-50 text-sky-950" Icon={Landmark} />
              <StatCard testId="treasury-banks-total-revenues-card" title="إجمالي الإيرادات" value={summary.total_revenues} tone="border-emerald-200 bg-emerald-50 text-emerald-950" Icon={WalletCards} />
              <StatCard testId="treasury-banks-total-expenses-card" title="إجمالي المصروفات" value={summary.total_expenses} tone="border-rose-200 bg-rose-50 text-rose-950" Icon={Banknote} />
              <StatCard testId="treasury-banks-net-movement-card" title="صافي الحركة" value={summary.net_movement} tone="border-slate-300 bg-slate-950 text-white" Icon={ShieldCheck} />
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="treasury-banks-table-section">
              <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between" data-testid="treasury-banks-table-heading">
                <div data-testid="treasury-banks-table-title-block">
                  <p className="text-sm font-extrabold text-sky-700" data-testid="treasury-banks-table-eyebrow">{selectedAccountName}</p>
                  <h2 className="text-3xl font-black" data-testid="treasury-banks-table-title">حركات الخزينة والبنوك</h2>
                  <p className="mt-1 text-sm font-bold text-slate-500" data-testid="treasury-banks-table-period">الفترة من {filters.from_date || "البداية"} إلى {filters.to_date || "آخر حركة"} — عدد الحركات: {formatNumber(summary.transactions_count || 0)}</p>
                </div>
                <Badge className="w-fit bg-sky-50 px-3 py-1 text-sky-700 hover:bg-sky-50" data-testid="treasury-banks-readonly-badge">عرض فقط من القيود اليومية</Badge>
              </div>
              <div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="treasury-banks-table-wrapper">
                <Table data-testid="treasury-banks-table">
                  <TableHeader className="bg-[#0f3f5f]" data-testid="treasury-banks-table-header"><TableRow className="hover:bg-[#0f3f5f]" data-testid="treasury-banks-table-header-row"><TableHead className="text-right text-white" data-testid="treasury-banks-header-date">التاريخ</TableHead><TableHead className="text-right text-white" data-testid="treasury-banks-header-entry-number">رقم القيد</TableHead><TableHead className="min-w-[260px] text-right text-white" data-testid="treasury-banks-header-description">البيان</TableHead><TableHead className="text-right text-white" data-testid="treasury-banks-header-movement-type">نوع الحركة</TableHead><TableHead className="text-right text-white" data-testid="treasury-banks-header-account">الحساب</TableHead><TableHead className="text-right text-white" data-testid="treasury-banks-header-amount">المبلغ</TableHead><TableHead className="text-right text-white" data-testid="treasury-banks-header-running-balance">الرصيد التراكمي</TableHead></TableRow></TableHeader>
                  <TableBody data-testid="treasury-banks-table-body">
                    {loading && <TableRow data-testid="treasury-banks-loading-row"><TableCell colSpan={7} className="py-8 text-center font-extrabold text-slate-500" data-testid="treasury-banks-loading-message">جاري تحميل الحركات...</TableCell></TableRow>}
                    {!loading && transactions.length === 0 && <TableRow data-testid="treasury-banks-empty-row"><TableCell colSpan={7} className="py-8 text-center font-extrabold text-slate-500" data-testid="treasury-banks-empty-message">لا توجد حركات مرتبطة بالخزينة أو البنوك في الفترة المحددة</TableCell></TableRow>}
                    {!loading && transactions.map((row) => <TableRow key={`${row.entry_id}-${row.serial}`} className="align-top" data-testid={`treasury-banks-row-${row.serial}`}><TableCell className="font-bold" data-testid={`treasury-banks-row-${row.serial}-date`}>{formatDate(row.entry_date)}</TableCell><TableCell className="font-black" data-testid={`treasury-banks-row-${row.serial}-entry-number`}>{row.entry_number}</TableCell><TableCell data-testid={`treasury-banks-row-${row.serial}-description`}><p className="font-extrabold text-slate-950">{row.description}</p><p className="mt-1 text-xs font-bold text-slate-500">{sourceLabels[row.source_type] || row.source_type}{row.reference ? ` — ${row.reference}` : ""}</p></TableCell><TableCell data-testid={`treasury-banks-row-${row.serial}-movement-type`}><Badge className={`${row.movement_type === "إيراد" ? "bg-emerald-50 text-emerald-700" : row.movement_type === "مصروف" ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-700"} hover:bg-white`}>{row.movement_type}</Badge></TableCell><TableCell className="font-bold" data-testid={`treasury-banks-row-${row.serial}-account`}><p>{row.account_name}</p><p className="mt-1 text-xs text-slate-500">{row.account_kind === "cash" ? "خزينة" : row.bank_name || "بنك"}</p></TableCell><TableCell className="font-black" data-testid={`treasury-banks-row-${row.serial}-amount`}>{formatCurrency(row.amount)}</TableCell><TableCell className="font-black text-sky-800" data-testid={`treasury-banks-row-${row.serial}-running-balance`}>{formatCurrency(row.running_balance)}</TableCell></TableRow>)}
                    {!loading && transactions.length > 0 && <TableRow className="bg-slate-50 font-black hover:bg-slate-50" data-testid="treasury-banks-total-row"><TableCell colSpan={5} data-testid="treasury-banks-total-label">إجمالي الحركة للعرض فقط</TableCell><TableCell data-testid="treasury-banks-total-row-net-movement">{formatCurrency(summary.net_movement)}</TableCell><TableCell data-testid="treasury-banks-total-row-balance">{formatCurrency(summary.total_balance)}</TableCell></TableRow>}
                  </TableBody>
                </Table>
              </div>
            </section>
          </section>
        </div>

        <aside className="space-y-5 print:hidden" data-testid="treasury-banks-sidebar">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="treasury-banks-sidebar-overview">
            <h3 className="text-xl font-black" data-testid="treasury-banks-sidebar-title">ماذا تعرض الصفحة؟</h3>
            <ul className="mt-4 space-y-3 text-sm font-bold text-slate-600" data-testid="treasury-banks-sidebar-list">
              <li data-testid="treasury-banks-sidebar-item-1">ملخص أرصدة الخزينة والبنوك من القيود المرحلة فقط.</li>
              <li data-testid="treasury-banks-sidebar-item-2">تفاصيل الحركة داخل الفترة مع الرصيد التراكمي لكل حساب.</li>
              <li data-testid="treasury-banks-sidebar-item-3">بحث سريع برقم القيد أو البيان أو اسم البنك.</li>
              <li data-testid="treasury-banks-sidebar-item-4">طباعة تقرير مراقبة مستقل بدون ترحيل أو تعديل.</li>
            </ul>
          </section>
          <section className="rounded-2xl border border-sky-200 bg-sky-50 p-5 shadow-sm" data-testid="treasury-banks-flow-card">
            <h3 className="text-xl font-black text-sky-950" data-testid="treasury-banks-flow-title">التدفق المحاسبي</h3>
            <div className="mt-5 space-y-3" data-testid="treasury-banks-flow-steps">
              {["إدخال الحركة في المصدر", "إنشاء قيد يومية تلقائي", "دفتر اليومية", "الخزينة والبنوك للعرض", "القوائم والتقارير"].map((step, index) => <div key={step} className="flex items-center gap-3" data-testid={`treasury-banks-flow-step-${index + 1}`}><span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#075985] text-sm font-black text-white" data-testid={`treasury-banks-flow-step-${index + 1}-number`}>{index + 1}</span><p className="text-sm font-extrabold text-sky-950" data-testid={`treasury-banks-flow-step-${index + 1}-text`}>{step}</p></div>)}
            </div>
          </section>
          <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5 shadow-sm" data-testid="treasury-banks-notes-card">
            <h3 className="text-xl font-black text-amber-950" data-testid="treasury-banks-notes-title">ملاحظات مهمة</h3>
            <div className="mt-4 space-y-3 text-sm font-bold text-amber-900" data-testid="treasury-banks-notes-list"><p data-testid="treasury-banks-note-readonly">لا يوجد تعديل أو حذف أو إنشاء قيود من هذه الصفحة.</p><p data-testid="treasury-banks-note-reconciliation">لا تتدخل الصفحة في التسوية البنكية الحالية.</p><p data-testid="treasury-banks-note-source">كل رقم ظاهر محسوب مباشرة من القيود اليومية المرحلة.</p></div>
          </section>
        </aside>
      </section>

      {previewOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 print:hidden" data-testid="treasury-banks-preview-modal"><section className="max-h-[88vh] w-full max-w-6xl overflow-auto rounded-2xl bg-white p-5 shadow-2xl" data-testid="treasury-banks-preview-dialog"><div className="mb-4 flex flex-wrap items-center justify-between gap-3" data-testid="treasury-banks-preview-heading"><h2 className="text-2xl font-black" data-testid="treasury-banks-preview-title">معاينة تقرير الخزينة والبنوك</h2><div className="flex gap-2" data-testid="treasury-banks-preview-actions"><Button type="button" onClick={() => openPrintWindow(true)} className="h-10 bg-[#075985] text-white" data-testid="treasury-banks-preview-print-button"><Printer className="h-4 w-4" /> طباعة PDF</Button><Button type="button" variant="outline" onClick={() => setPreviewOpen(false)} className="h-10 bg-white" data-testid="treasury-banks-preview-close-button">إغلاق</Button></div></div><div className="rounded-xl border border-slate-200 p-4" data-testid="treasury-banks-preview-content"><h3 className="mb-3 text-xl font-black" data-testid="treasury-banks-preview-report-title">الخزينة والبنوك - {selectedAccountName}</h3><p className="mb-4 text-sm font-bold text-slate-500" data-testid="treasury-banks-preview-report-period">الفترة من {filters.from_date || "البداية"} إلى {filters.to_date || "آخر حركة"}</p><div className="max-h-[58vh] overflow-auto" data-testid="treasury-banks-preview-table-wrapper"><Table data-testid="treasury-banks-preview-table"><TableHeader className="bg-slate-950"><TableRow><TableHead className="text-right text-white">التاريخ</TableHead><TableHead className="text-right text-white">رقم القيد</TableHead><TableHead className="text-right text-white">البيان</TableHead><TableHead className="text-right text-white">الحساب</TableHead><TableHead className="text-right text-white">المبلغ</TableHead><TableHead className="text-right text-white">الرصيد</TableHead></TableRow></TableHeader><TableBody>{transactions.slice(0, 80).map((row) => <TableRow key={`preview-${row.serial}`} data-testid={`treasury-banks-preview-row-${row.serial}`}><TableCell>{formatDate(row.entry_date)}</TableCell><TableCell>{row.entry_number}</TableCell><TableCell>{row.description}</TableCell><TableCell>{row.account_name}</TableCell><TableCell>{formatCurrency(row.amount)}</TableCell><TableCell>{formatCurrency(row.running_balance)}</TableCell></TableRow>)}</TableBody></Table></div></div></section></div>}

      <footer className="px-4 pb-5 print:hidden" data-testid="treasury-banks-footer"><CreditLine testId="treasury-banks-creator-credit" /></footer>
    </main>
  );
}