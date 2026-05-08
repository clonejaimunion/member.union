import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Handshake, Home, LogOut, Save } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { formatCurrency, formatDate, sanitizeDecimalInput } from "@/lib/format";

const today = new Date().toISOString().slice(0, 10);
const movementLabels = { obligation: "إثبات التزام", payment: "سداد" };

export default function MiscCreditorsPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [creditors, setCreditors] = useState([]);
  const [banks, setBanks] = useState([]);
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [filters, setFilters] = useState({ from_date: "", to_date: "", creditor_id: "" });
  const [form, setForm] = useState({ movement_date: today, creditor_id: "", creditor_name: "", movement_type: "obligation", amount: "", bank_id: "", description: "", reference: "" });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.from_date) params.set("from_date", filters.from_date);
      if (filters.to_date) params.set("to_date", filters.to_date);
      if (filters.creditor_id) params.set("creditor_id", filters.creditor_id);
      const [creditorsResponse, movementsResponse, banksResponse] = await Promise.all([api.get("/misc-creditors"), api.get(`/misc-creditors/movements?${params.toString()}`), api.get("/banks")]);
      setCreditors(creditorsResponse.data);
      setMovements(movementsResponse.data);
      setBanks(banksResponse.data);
    } catch (error) {
      toast.error("تعذر تحميل دفتر الدائنين المتنوعين");
    } finally {
      setLoading(false);
    }
  }, [filters.from_date, filters.to_date, filters.creditor_id]);
  useEffect(() => { loadData(); }, [loadData]);
  const totalBalance = useMemo(() => creditors.reduce((sum, item) => sum + Number(item.balance || 0), 0), [creditors]);
  const updateForm = (field, value) => setForm((current) => ({ ...current, [field]: field === "amount" ? sanitizeDecimalInput(value) : value }));

  const saveMovement = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await api.post("/misc-creditors/movements", { ...form, creditor_id: form.creditor_id || null, creditor_name: form.creditor_name || null, bank_id: form.movement_type === "payment" ? form.bank_id : null, amount: Number(form.amount || 0) });
      toast.success("تم حفظ حركة الدائن وإنشاء القيد تلقائياً");
      setForm({ movement_date: today, creditor_id: "", creditor_name: "", movement_type: "obligation", amount: "", bank_id: "", description: "", reference: "" });
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ حركة الدائن");
    } finally {
      setSaving(false);
    }
  };

  return <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="misc-creditors-page"><header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur print:hidden" data-testid="misc-creditors-header"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8"><div className="flex items-center gap-3"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white"><Handshake className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700">تدفق محاسبي تلقائي</p><h1 className="text-2xl font-extrabold" data-testid="misc-creditors-title">دفتر الدائنين المتنوعين</h1></div></div><div className="flex flex-wrap items-center gap-3"><Badge className="bg-white text-slate-700" data-testid="misc-creditors-user-badge">{user?.full_name || user?.username}</Badge><Button asChild variant="outline" className="h-11 bg-white" data-testid="misc-creditors-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="misc-creditors-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 bg-white" data-testid="misc-creditors-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div></div></header><section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 sm:px-6 xl:grid-cols-[0.85fr_1.15fr] lg:px-8"><section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="misc-creditor-form-section"><h2 className="mb-4 text-2xl font-extrabold">إدخال حركة دائن</h2><form onSubmit={saveMovement} className="space-y-4" data-testid="misc-creditor-movement-form"><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><div><Label>التاريخ</Label><Input type="date" value={form.movement_date} onChange={(e) => updateForm("movement_date", e.target.value)} required data-testid="misc-creditor-date-input" /></div><div><Label>نوع الحركة</Label><select value={form.movement_type} onChange={(e) => updateForm("movement_type", e.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 font-bold" data-testid="misc-creditor-type-select"><option value="obligation">إثبات التزام</option><option value="payment">سداد</option></select></div></div><div><Label>الدائن المسجل</Label><select value={form.creditor_id} onChange={(e) => updateForm("creditor_id", e.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 font-bold" data-testid="misc-creditor-select"><option value="">دائن جديد / بدون اختيار</option>{creditors.map((creditor) => <option key={creditor.id} value={creditor.id}>{creditor.creditor_name} — {formatCurrency(creditor.balance)}</option>)}</select></div><Input placeholder="اسم دائن جديد" value={form.creditor_name} onChange={(e) => updateForm("creditor_name", e.target.value)} data-testid="misc-creditor-name-input" /><Input placeholder="المبلغ" inputMode="decimal" value={form.amount} onChange={(e) => updateForm("amount", e.target.value)} required data-testid="misc-creditor-amount-input" />{form.movement_type === "payment" && <div><Label>بنك السداد</Label><select value={form.bank_id} onChange={(e) => updateForm("bank_id", e.target.value)} required className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 font-bold" data-testid="misc-creditor-bank-select"><option value="">اختر البنك</option>{banks.map((bank) => <option key={bank.id} value={bank.id}>{bank.name}</option>)}</select></div>}<Input placeholder="البيان" value={form.description} onChange={(e) => updateForm("description", e.target.value)} required data-testid="misc-creditor-description-input" /><Input placeholder="رقم مستند اختياري" value={form.reference} onChange={(e) => updateForm("reference", e.target.value)} data-testid="misc-creditor-reference-input" /><Button type="submit" disabled={saving} className="h-11 w-full bg-slate-950 text-white" data-testid="misc-creditor-save-button"><Save className="h-4 w-4" /> حفظ الحركة وإنشاء القيد</Button></form></section><section className="space-y-5"><div className="rounded-xl bg-amber-50 p-5 text-amber-950 shadow-sm" data-testid="misc-creditors-total-card"><p className="text-xs font-bold">رصيد الدائنين ضمن الخصوم المتداولة</p><p className="text-2xl font-extrabold">{formatCurrency(totalBalance)}</p></div><div className="rounded-xl border border-slate-200 bg-white p-5"><div className="grid grid-cols-1 gap-2 md:grid-cols-4"><Input type="date" value={filters.from_date} onChange={(e) => setFilters((c) => ({ ...c, from_date: e.target.value }))} data-testid="misc-creditor-filter-from-date" /><Input type="date" value={filters.to_date} onChange={(e) => setFilters((c) => ({ ...c, to_date: e.target.value }))} data-testid="misc-creditor-filter-to-date" /><select value={filters.creditor_id} onChange={(e) => setFilters((c) => ({ ...c, creditor_id: e.target.value }))} className="h-10 rounded-md border border-slate-300 bg-white px-3 font-bold" data-testid="misc-creditor-filter-select"><option value="">كل الدائنين</option>{creditors.map((creditor) => <option key={creditor.id} value={creditor.id}>{creditor.creditor_name}</option>)}</select><Button onClick={loadData} variant="outline" className="h-10 bg-white" data-testid="misc-creditor-filter-apply-button">تطبيق</Button></div></div><div className="overflow-x-auto rounded-xl border border-slate-200 bg-white"><Table data-testid="misc-creditor-movements-table"><TableHeader className="bg-slate-950"><TableRow><TableHead className="text-right text-white">التاريخ</TableHead><TableHead className="text-right text-white">الدائن</TableHead><TableHead className="text-right text-white">الحركة</TableHead><TableHead className="text-right text-white">المبلغ</TableHead><TableHead className="text-right text-white">الرصيد</TableHead><TableHead className="text-right text-white">الترحيل</TableHead></TableRow></TableHeader><TableBody>{loading && <TableRow><TableCell colSpan={6} className="py-8 text-center font-bold">جاري التحميل...</TableCell></TableRow>}{!loading && movements.length === 0 && <TableRow data-testid="misc-creditor-empty-row"><TableCell colSpan={6} className="py-8 text-center font-bold text-slate-500">لا توجد حركات دائنين</TableCell></TableRow>}{movements.map((movement) => <TableRow key={movement.id} data-testid={`misc-creditor-movement-row-${movement.id}`}><TableCell>{formatDate(movement.movement_date)}</TableCell><TableCell className="font-extrabold">{movement.creditor_name}</TableCell><TableCell>{movementLabels[movement.movement_type]}</TableCell><TableCell>{formatCurrency(movement.amount)}</TableCell><TableCell>{formatCurrency(movement.balance_after)}</TableCell><TableCell>{movement.journal_entry_id ? "تم الترحيل" : "غير مرحل"}</TableCell></TableRow>)}</TableBody></Table></div></section></section><footer className="px-4 pb-5 print:hidden"><CreditLine testId="misc-creditors-creator-credit" /></footer></main>;
}