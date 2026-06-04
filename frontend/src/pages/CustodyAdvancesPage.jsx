import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, HandCoins, Home, LogOut, Printer, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { formatCurrency, sanitizeDecimalInput } from "@/lib/format";
import { printNow } from "@/lib/printOrientation";

const todayIso = new Date().toISOString().slice(0, 10);
const initialForm = { transaction_type: "custody", recipient_name: "", issue_date: todayIso, amount: "", bank_id: "", purpose: "", due_date: "", notes: "" };
const initialSettlement = { settlement_date: todayIso, settlement_amount: "", settlement_type: "expense", notes: "" };

export default function CustodyAdvancesPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [banks, setBanks] = useState([]);
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [settlementForms, setSettlementForms] = useState({});
  const [filter, setFilter] = useState({ status: "all", transaction_type: "all" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const canManage = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.manage_expenses;

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter.status !== "all") params.set("status", filter.status);
      if (filter.transaction_type !== "all") params.set("transaction_type", filter.transaction_type);
      const [banksResponse, rowsResponse] = await Promise.all([api.get("/banks"), api.get(`/custody-advances?${params.toString()}`)]);
      setBanks(banksResponse.data);
      setRows(rowsResponse.data);
      setForm((current) => ({ ...current, bank_id: current.bank_id || banksResponse.data[0]?.id || "" }));
    } catch (error) {
      toast.error("تعذر تحميل العهد والسلف");
    } finally {
      setLoading(false);
    }
  }, [filter.status, filter.transaction_type]);

  useEffect(() => { loadData(); }, [loadData]);

  const totals = useMemo(() => rows.reduce((acc, item) => ({ amount: acc.amount + Number(item.amount || 0), settled: acc.settled + Number(item.settled_amount || 0), remaining: acc.remaining + Number(item.remaining_amount || 0) }), { amount: 0, settled: 0, remaining: 0 }), [rows]);
  const updateForm = (field, value) => setForm((current) => ({ ...current, [field]: field === "amount" ? sanitizeDecimalInput(value) : value }));
  const updateSettlement = (id, field, value) => setSettlementForms((current) => ({ ...current, [id]: { ...(current[id] || initialSettlement), [field]: field === "settlement_amount" ? sanitizeDecimalInput(value) : value } }));

  const createRow = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await api.post("/custody-advances", { ...form, amount: Number(form.amount || 0), due_date: form.due_date || null, notes: form.notes || null });
      toast.success("تم تسجيل العهدة/السلفة وإنشاء القيد تلقائياً");
      setForm((current) => ({ ...initialForm, bank_id: current.bank_id, issue_date: todayIso }));
      await loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ العهدة/السلفة");
    } finally {
      setSaving(false);
    }
  };

  const settleRow = async (item) => {
    const settlement = settlementForms[item.id] || { ...initialSettlement, settlement_amount: String(item.remaining_amount || item.amount || "") };
    setSaving(true);
    try {
      await api.post(`/custody-advances/${item.id}/settle`, { ...settlement, settlement_amount: Number(settlement.settlement_amount || 0), notes: settlement.notes || null });
      toast.success("تمت التسوية وإنشاء القيد تلقائياً");
      setSettlementForms((current) => ({ ...current, [item.id]: initialSettlement }));
      await loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تسوية العهدة/السلفة");
    } finally {
      setSaving(false);
    }
  };

  const deleteRow = async (item) => {
    if (!window.confirm(`هل تريد حذف ${item.reference_number} وقيوده؟`)) return;
    try {
      await api.delete(`/custody-advances/${item.id}`);
      toast.success("تم الحذف مع القيود التلقائية");
      await loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر الحذف");
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="custody-advances-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="custody-advances-header"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8"><div className="flex items-center gap-3" data-testid="custody-advances-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="custody-advances-brand-icon"><HandCoins className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700" data-testid="custody-advances-eyebrow">الحسابات</p><h1 className="text-2xl font-extrabold" data-testid="custody-advances-title">العهد والسلف</h1></div></div><div className="flex flex-wrap items-center gap-3" data-testid="custody-advances-actions"><Badge className="bg-white text-slate-700" data-testid="custody-advances-organization-badge">{user?.organization_name}</Badge><Button asChild variant="outline" className="h-11 bg-white" data-testid="custody-advances-home-button"><Link to="/"><Home className="h-4 w-4" /> الرئيسية</Link></Button><Button type="button" onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="custody-advances-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button type="button" onClick={logout} variant="outline" className="h-11 bg-white" data-testid="custody-advances-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div></div></header>
      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 sm:px-6 xl:grid-cols-[0.8fr_1.2fr] lg:px-8" data-testid="custody-advances-content">
        {canManage && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="custody-advance-create-section"><h2 className="mb-5 text-2xl font-extrabold" data-testid="custody-advance-create-title">تسجيل عهدة/سلفة</h2><form onSubmit={createRow} className="grid grid-cols-1 gap-4 md:grid-cols-2" data-testid="custody-advance-create-form"><div data-testid="custody-advance-type-wrapper"><Label data-testid="custody-advance-type-label">النوع</Label><select value={form.transaction_type} onChange={(event) => updateForm("transaction_type", event.target.value)} className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="custody-advance-type-select"><option value="custody">عهدة</option><option value="advance">سلفة</option></select></div><div data-testid="custody-advance-recipient-wrapper"><Label data-testid="custody-advance-recipient-label">اسم المستلم</Label><Input value={form.recipient_name} onChange={(event) => updateForm("recipient_name", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="custody-advance-recipient-input" /></div><div data-testid="custody-advance-date-wrapper"><Label data-testid="custody-advance-date-label">تاريخ الصرف</Label><Input type="text" value={form.issue_date} onChange={(event) => updateForm("issue_date", event.target.value)} pattern="\d{4}-\d{2}-\d{2}" placeholder="YYYY-MM-DD" required className="mt-2 h-11 bg-slate-50 text-right" data-testid="custody-advance-issue-date-input" /></div><div data-testid="custody-advance-amount-wrapper"><Label data-testid="custody-advance-amount-label">القيمة</Label><Input value={form.amount} onChange={(event) => updateForm("amount", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="custody-advance-amount-input" /></div><div data-testid="custody-advance-bank-wrapper"><Label data-testid="custody-advance-bank-label">البنك</Label><select value={form.bank_id} onChange={(event) => updateForm("bank_id", event.target.value)} required className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="custody-advance-bank-select">{banks.map((bank) => <option key={bank.id} value={bank.id}>{bank.name}</option>)}</select></div><div data-testid="custody-advance-due-date-wrapper"><Label data-testid="custody-advance-due-date-label">تاريخ الاستحقاق</Label><Input type="text" value={form.due_date} onChange={(event) => updateForm("due_date", event.target.value)} pattern="\d{4}-\d{2}-\d{2}" placeholder="YYYY-MM-DD" className="mt-2 h-11 bg-slate-50 text-right" data-testid="custody-advance-due-date-input" /></div><div className="md:col-span-2" data-testid="custody-advance-purpose-wrapper"><Label data-testid="custody-advance-purpose-label">الغرض</Label><Input value={form.purpose} onChange={(event) => updateForm("purpose", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="custody-advance-purpose-input" /></div><div className="md:col-span-2" data-testid="custody-advance-notes-wrapper"><Label data-testid="custody-advance-notes-label">ملاحظات</Label><Input value={form.notes} onChange={(event) => updateForm("notes", event.target.value)} className="mt-2 h-11 bg-slate-50 text-right" data-testid="custody-advance-notes-input" /></div><Button type="submit" disabled={saving} className="h-11 bg-slate-950 text-white md:col-span-2" data-testid="save-custody-advance-button"><Save className="h-4 w-4" /> حفظ وإنشاء القيد تلقائياً</Button></form></section>}
        <section className="space-y-6" data-testid="custody-advances-report-column"><section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="custody-advances-filter-section"><div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><h2 className="text-2xl font-extrabold" data-testid="custody-advances-filter-title">تقرير العهد والسلف</h2><Button type="button" onClick={() => printNow()} variant="outline" className="h-10 bg-white" data-testid="print-custody-advances-report-button"><Printer className="h-4 w-4" /> طباعة التقرير</Button></div><div className="grid grid-cols-1 gap-3 md:grid-cols-3" data-testid="custody-advances-filter-controls"><select value={filter.transaction_type} onChange={(event) => setFilter((current) => ({ ...current, transaction_type: event.target.value }))} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="custody-advances-type-filter"><option value="all">كل الأنواع</option><option value="custody">عهدة</option><option value="advance">سلفة</option></select><select value={filter.status} onChange={(event) => setFilter((current) => ({ ...current, status: event.target.value }))} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="custody-advances-status-filter"><option value="all">كل الحالات</option><option value="open">مفتوحة</option><option value="partial">جزئية</option><option value="settled">مسددة</option></select><Button type="button" onClick={loadData} className="h-11 bg-slate-950 text-white" data-testid="apply-custody-advances-filter-button">تطبيق</Button></div></section><section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="custody-advances-list-section"><div className="mb-5 grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="custody-advances-kpis"><div className="rounded-xl bg-slate-950 p-4 text-white" data-testid="custody-advances-total-card"><p className="text-xs font-bold text-slate-300">إجمالي المصروف</p><p className="text-xl font-extrabold" data-testid="custody-advances-total-value">{formatCurrency(totals.amount)}</p></div><div className="rounded-xl bg-emerald-50 p-4" data-testid="custody-advances-settled-card"><p className="text-xs font-bold text-emerald-700">المسدد</p><p className="text-xl font-extrabold" data-testid="custody-advances-settled-value">{formatCurrency(totals.settled)}</p></div><div className="rounded-xl bg-amber-50 p-4" data-testid="custody-advances-remaining-card"><p className="text-xs font-bold text-amber-700">المتبقي</p><p className="text-xl font-extrabold" data-testid="custody-advances-remaining-value">{formatCurrency(totals.remaining)}</p></div></div><div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="custody-advances-table-wrapper"><Table data-testid="custody-advances-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">المرجع</TableHead><TableHead className="text-right text-white">النوع/المستلم</TableHead><TableHead className="text-right text-white">القيمة</TableHead><TableHead className="text-right text-white">المسدد</TableHead><TableHead className="text-right text-white">المتبقي</TableHead><TableHead className="text-right text-white">الحالة</TableHead><TableHead className="text-right text-white print:hidden">تسوية</TableHead></TableRow></TableHeader><TableBody>{loading && <TableRow data-testid="custody-advances-loading-row"><TableCell colSpan={7} className="py-8 text-center font-bold">جاري التحميل...</TableCell></TableRow>}{!loading && rows.length === 0 && <TableRow data-testid="custody-advances-empty-row"><TableCell colSpan={7} className="py-8 text-center font-bold text-slate-500">لا توجد عهد أو سلف</TableCell></TableRow>}{rows.map((item) => { const settlement = settlementForms[item.id] || { ...initialSettlement, settlement_amount: String(item.remaining_amount || "") }; return <TableRow key={item.id} data-testid={`custody-advance-row-${item.id}`}><TableCell className="font-extrabold" data-testid={`custody-advance-${item.id}-reference`}>{item.reference_number}<p className="text-xs text-slate-500" data-testid={`custody-advance-${item.id}-issue-date`}>{item.issue_date}</p></TableCell><TableCell data-testid={`custody-advance-${item.id}-recipient`}><span className="font-extrabold">{item.transaction_type === "custody" ? "عهدة" : "سلفة"}</span><p className="text-sm font-bold text-slate-600">{item.recipient_name}</p><p className="text-xs text-slate-500">{item.purpose}</p></TableCell><TableCell data-testid={`custody-advance-${item.id}-amount`}>{formatCurrency(item.amount)}</TableCell><TableCell data-testid={`custody-advance-${item.id}-settled`}>{formatCurrency(item.settled_amount)}</TableCell><TableCell className="font-extrabold" data-testid={`custody-advance-${item.id}-remaining`}>{formatCurrency(item.remaining_amount)}</TableCell><TableCell data-testid={`custody-advance-${item.id}-status`}>{item.status === "settled" ? "مسددة" : item.status === "partial" ? "جزئية" : "مفتوحة"}</TableCell><TableCell className="min-w-72 print:hidden" data-testid={`custody-advance-${item.id}-settlement-cell`}>{item.status !== "settled" && canManage ? <div className="grid grid-cols-1 gap-2"><Input value={settlement.settlement_amount} onChange={(event) => updateSettlement(item.id, "settlement_amount", event.target.value)} className="h-9 bg-white text-right" data-testid={`custody-advance-${item.id}-settlement-amount-input`} /><Input value={settlement.settlement_date} onChange={(event) => updateSettlement(item.id, "settlement_date", event.target.value)} pattern="\d{4}-\d{2}-\d{2}" className="h-9 bg-white text-right" data-testid={`custody-advance-${item.id}-settlement-date-input`} /><select value={settlement.settlement_type} onChange={(event) => updateSettlement(item.id, "settlement_type", event.target.value)} className="h-9 rounded-md border border-slate-300 bg-white px-2 font-bold" data-testid={`custody-advance-${item.id}-settlement-type-select`}><option value="expense">تسوية كمصروف</option><option value="bank_return">رد للبنك</option></select><Button type="button" onClick={() => settleRow(item)} disabled={saving} className="h-9 bg-slate-950 text-white" data-testid={`custody-advance-${item.id}-settle-button`}>تسوية تلقائية</Button></div> : <span className="font-bold text-emerald-700">تمت التسوية</span>}{user?.role === "admin" && <Button type="button" onClick={() => deleteRow(item)} variant="outline" className="mt-2 h-9 bg-white text-red-700" data-testid={`custody-advance-${item.id}-delete-button`}><Trash2 className="h-4 w-4" /> حذف</Button>}</TableCell></TableRow>; })}</TableBody></Table></div></section></section>
      </section><footer className="px-4 pb-5 print:hidden" data-testid="custody-advances-footer"><CreditLine testId="custody-advances-creator-credit" /></footer>
    </main>
  );
}