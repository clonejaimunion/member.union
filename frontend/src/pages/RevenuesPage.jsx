import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Banknote, FileSearch, Home, LogOut, Pencil, Printer, ReceiptText, RotateCcw, Save, Search, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { fallbackBanks } from "@/lib/banks";
import { formatCurrency, sanitizeDecimalInput, sanitizeDigitsInput } from "@/lib/format";

const today = () => new Date().toISOString().slice(0, 10);

const defaultForm = () => ({
  receipt_number: "",
  amount: "",
  collection_method: "cash",
  supplier_name: "",
  check_number: "",
  payment_order_number: "",
  bank_id: "industrial-development",
  dated: today(),
  value: "",
  issued_at: today(),
  responsible_employee: "يوسف عبدالغني",
});

const methodLabels = {
  cash: "نقداً",
  check: "شيك",
  payment_order: "أمر دفع",
};

const employeeOptions = ["يوسف عبدالغني", "دعاء علي"];

export default function RevenuesPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [banks, setBanks] = useState(fallbackBanks);
  const [revenues, setRevenues] = useState([]);
  const [form, setForm] = useState(defaultForm);
  const [filters, setFilters] = useState({ bank_id: "all", collection_method: "all", from_date: "", to_date: "" });
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searchOpen, setSearchOpen] = useState(false);

  const canManage = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.manage_revenues;
  const totalAmount = useMemo(() => revenues.reduce((sum, item) => sum + Number(item.amount || 0), 0), [revenues]);

  const loadBanks = useCallback(() => {
    api.get("/banks").then((response) => setBanks(response.data)).catch(() => setBanks(fallbackBanks));
  }, []);

  const loadRevenues = useCallback(() => {
    const params = new URLSearchParams();
    if (filters.bank_id !== "all") params.set("bank_id", filters.bank_id);
    if (filters.collection_method !== "all") params.set("collection_method", filters.collection_method);
    if (filters.from_date) params.set("from_date", filters.from_date);
    if (filters.to_date) params.set("to_date", filters.to_date);
    const query = params.toString() ? `?${params.toString()}` : "";
    api.get(`/revenues${query}`).then((response) => setRevenues(response.data)).catch(() => setRevenues([]));
  }, [filters]);

  useEffect(() => {
    loadBanks();
  }, [loadBanks]);

  useEffect(() => {
    loadRevenues();
  }, [loadRevenues]);

  const updateForm = (field, value) => {
    const nextValue = ["receipt_number", "check_number", "payment_order_number"].includes(field)
      ? sanitizeDigitsInput(value)
      : field === "amount"
        ? sanitizeDecimalInput(value)
        : value;
    setForm((current) => ({ ...current, [field]: nextValue }));
  };

  const resetForm = () => {
    setEditingId(null);
    setForm(defaultForm());
  };

  const payloadFromForm = () => ({
    ...form,
    amount: Number(sanitizeDecimalInput(form.amount) || 0),
    receipt_number: sanitizeDigitsInput(form.receipt_number),
    check_number: form.collection_method === "check" ? sanitizeDigitsInput(form.check_number) : null,
    payment_order_number: form.collection_method === "payment_order" ? sanitizeDigitsInput(form.payment_order_number) : null,
    supplier_name: form.collection_method === "cash" ? form.supplier_name.trim() : null,
  });

  const submitRevenue = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = payloadFromForm();
      const response = editingId ? await api.put(`/revenues/${editingId}`, payload) : await api.post("/revenues", payload);
      toast.success(editingId ? "تم تعديل الإيراد" : "تم حفظ الإيراد");
      setEditingId(null);
      setForm({ ...defaultForm(), bank_id: response.data.bank_id });
      loadRevenues();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ الإيراد");
    } finally {
      setSaving(false);
    }
  };

  const editRevenue = (item) => {
    setEditingId(item.id);
    setForm({
      receipt_number: item.receipt_number || "",
      amount: String(item.amount ?? ""),
      collection_method: item.collection_method || "cash",
      supplier_name: item.supplier_name || "",
      check_number: item.check_number || "",
      payment_order_number: item.payment_order_number || "",
      bank_id: item.bank_id || "industrial-development",
      dated: item.dated || today(),
      value: item.value || "",
      issued_at: item.issued_at || today(),
      responsible_employee: item.responsible_employee || "يوسف عبدالغني",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const deleteRevenue = async (item) => {
    if (!window.confirm(`هل تريد حذف الإيراد رقم ${item.receipt_number}؟`)) return;
    try {
      await api.delete(`/revenues/${item.id}`);
      toast.success("تم حذف الإيراد");
      if (editingId === item.id) resetForm();
      loadRevenues();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حذف الإيراد");
    }
  };

  const searchRevenue = async (event) => {
    event.preventDefault();
    if (!searchQuery.trim()) {
      toast.error("اكتب رقم الشيك أو رقم أمر الدفع أو اسم المورد");
      return;
    }
    try {
      const response = await api.get(`/revenues/search?query=${encodeURIComponent(searchQuery.trim())}`);
      setSearchResults(response.data);
      setSearchOpen(true);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر البحث عن الإيراد");
    }
  };

  const detailValue = (item) => {
    if (item.collection_method === "cash") return item.supplier_name || "—";
    if (item.collection_method === "check") return item.check_number || "—";
    return item.payment_order_number || "—";
  };

  const DetailGrid = ({ item, prefix }) => (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid={`${prefix}-details-grid`}>
      {[
        ["رقم الإذن", item.receipt_number],
        ["المبلغ", formatCurrency(item.amount)],
        ["طريقة التحصيل", methodLabels[item.collection_method]],
        [item.collection_method === "cash" ? "اسم المورد" : item.collection_method === "check" ? "رقم الشيك" : "رقم أمر الدفع", detailValue(item)],
        ["البنك", item.bank_name],
        ["بتاريخ", item.dated],
        ["قيمة", item.value],
        ["تحريراً في", item.issued_at],
        ["الموظف المختص", item.responsible_employee],
      ].map(([label, value], index) => (
        <div key={`${prefix}-${label}`} className={index === 6 ? "rounded-lg bg-slate-50 p-3 md:col-span-2" : "rounded-lg bg-slate-50 p-3"} data-testid={`${prefix}-detail-${index}`}>
          <p className="text-xs font-bold text-slate-500" data-testid={`${prefix}-detail-${index}-label`}>{label}</p>
          <p className="mt-1 break-words text-base font-extrabold text-slate-950" data-testid={`${prefix}-detail-${index}-value`}>{value || "—"}</p>
        </div>
      ))}
    </div>
  );

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="revenues-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="revenues-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="revenues-brand">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="revenues-brand-icon"><ReceiptText className="h-5 w-5" /></div>
            <div>
              <p className="text-xs font-extrabold text-emerald-700" data-testid="revenues-eyebrow">الإيرادات</p>
              <h1 className="text-2xl font-extrabold" data-testid="revenues-title">تسجيل وتقرير الإيرادات</h1>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3" data-testid="revenues-header-actions">
            <Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="revenues-user-badge">{user?.username}</Badge>
            <Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="revenues-home-button"><Link to="/"><Home className="h-4 w-4" /> القائمة الرئيسية</Link></Button>
            <Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="revenues-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button>
            <Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="revenues-logout-button"><LogOut className="h-4 w-4" /> خروج</Button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="revenues-content">
        {canManage && (
          <form onSubmit={submitRevenue} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden sm:p-8" data-testid="revenue-form">
            <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" data-testid="revenue-form-heading">
              <div>
                <p className="text-sm font-extrabold text-emerald-700" data-testid="revenue-form-eyebrow">{editingId ? "تعديل بيانات الإيراد" : "إضافة إيراد جديد"}</p>
                <h2 className="text-3xl font-extrabold text-slate-950" data-testid="revenue-form-title">بيانات الإيراد</h2>
              </div>
              {editingId && <Button type="button" onClick={resetForm} variant="outline" className="h-11 rounded-lg bg-white" data-testid="cancel-edit-revenue-button"><RotateCcw className="h-4 w-4" /> إلغاء التعديل</Button>}
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="revenue-form-grid">
              <div className="space-y-2" data-testid="revenue-receipt-wrapper"><Label data-testid="revenue-receipt-label">رقم الإذن</Label><Input required inputMode="numeric" value={form.receipt_number} onChange={(event) => updateForm("receipt_number", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="revenue-receipt-input" /></div>
              <div className="space-y-2" data-testid="revenue-amount-wrapper"><Label data-testid="revenue-amount-label">المبلغ بالجنيه المصري</Label><Input required inputMode="decimal" value={form.amount} onChange={(event) => updateForm("amount", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="revenue-amount-input" /></div>
              <div className="space-y-2" data-testid="revenue-method-wrapper"><Label data-testid="revenue-method-label">طريقة التحصيل</Label><select value={form.collection_method} onChange={(event) => updateForm("collection_method", event.target.value)} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="revenue-method-select"><option value="cash" data-testid="revenue-method-cash-option">نقداً</option><option value="check" data-testid="revenue-method-check-option">شيك</option><option value="payment_order" data-testid="revenue-method-payment-order-option">أمر دفع</option></select></div>
              {form.collection_method === "cash" && <div className="space-y-2" data-testid="revenue-supplier-wrapper"><Label data-testid="revenue-supplier-label">اسم الشخص الذي قام بالتوريد</Label><Input required value={form.supplier_name} onChange={(event) => updateForm("supplier_name", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="revenue-supplier-input" /></div>}
              {form.collection_method === "check" && <div className="space-y-2" data-testid="revenue-check-wrapper"><Label data-testid="revenue-check-label">رقم الشيك</Label><Input required inputMode="numeric" value={form.check_number} onChange={(event) => updateForm("check_number", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="revenue-check-input" /></div>}
              {form.collection_method === "payment_order" && <div className="space-y-2" data-testid="revenue-payment-order-wrapper"><Label data-testid="revenue-payment-order-label">رقم أمر الدفع</Label><Input required inputMode="numeric" value={form.payment_order_number} onChange={(event) => updateForm("payment_order_number", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="revenue-payment-order-input" /></div>}
              <div className="space-y-2" data-testid="revenue-bank-wrapper"><Label data-testid="revenue-bank-label">اسم البنك</Label><select value={form.bank_id} onChange={(event) => updateForm("bank_id", event.target.value)} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="revenue-bank-select">{banks.map((bank) => <option key={bank.id} value={bank.id} data-testid={`revenue-bank-option-${bank.id}`}>{bank.name}</option>)}</select></div>
              <div className="space-y-2" data-testid="revenue-dated-wrapper"><Label data-testid="revenue-dated-label">بتاريخ</Label><Input required type="date" value={form.dated} onChange={(event) => updateForm("dated", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="revenue-dated-input" /></div>
              <div className="space-y-2" data-testid="revenue-issued-wrapper"><Label data-testid="revenue-issued-label">تحريراً في</Label><Input required type="date" value={form.issued_at} onChange={(event) => updateForm("issued_at", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="revenue-issued-input" /></div>
              <div className="space-y-2" data-testid="revenue-employee-wrapper"><Label data-testid="revenue-employee-label">الموظف المختص</Label><select value={form.responsible_employee} onChange={(event) => updateForm("responsible_employee", event.target.value)} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="revenue-employee-select">{employeeOptions.map((name) => <option key={name} value={name} data-testid={`revenue-employee-option-${name}`}>{name}</option>)}</select></div>
              <div className="space-y-2 md:col-span-3" data-testid="revenue-value-wrapper"><Label data-testid="revenue-value-label">قيمة</Label><textarea required value={form.value} onChange={(event) => updateForm("value", event.target.value)} className="min-h-28 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 text-right text-sm font-bold outline-none focus:border-slate-900" data-testid="revenue-value-textarea" /></div>
            </div>
            <Button type="submit" disabled={saving} className="mt-6 h-12 rounded-lg bg-slate-950 px-7 text-white" data-testid="save-revenue-button"><Save className="h-4 w-4" /> {saving ? "جاري الحفظ..." : editingId ? "حفظ تعديل الإيراد" : "حفظ الإيراد"}</Button>
          </form>
        )}

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden" data-testid="revenues-tools-section">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto]" data-testid="revenues-tools-grid">
            <form onSubmit={searchRevenue} className="flex flex-col gap-3 sm:flex-row" data-testid="revenue-search-form">
              <Input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="بحث برقم الشيك أو أمر الدفع أو اسم المورد" className="h-12 rounded-lg bg-slate-50 text-right" data-testid="revenue-search-input" />
              <Button type="submit" className="h-12 rounded-lg bg-emerald-700 px-6 text-white hover:bg-emerald-800" data-testid="revenue-search-button"><Search className="h-4 w-4" /> بحث</Button>
            </form>
            <Button type="button" onClick={() => window.print()} className="h-12 rounded-lg bg-slate-950 px-6 text-white" data-testid="print-revenues-report-button"><Printer className="h-4 w-4" /> طباعة PDF</Button>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-4" data-testid="revenues-filters-grid">
            <select value={filters.bank_id} onChange={(event) => setFilters((current) => ({ ...current, bank_id: event.target.value }))} className="h-12 rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="revenues-filter-bank-select"><option value="all" data-testid="revenues-filter-bank-all-option">كل البنوك</option>{banks.map((bank) => <option key={bank.id} value={bank.id} data-testid={`revenues-filter-bank-${bank.id}`}>{bank.name}</option>)}</select>
            <select value={filters.collection_method} onChange={(event) => setFilters((current) => ({ ...current, collection_method: event.target.value }))} className="h-12 rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="revenues-filter-method-select"><option value="all" data-testid="revenues-filter-method-all-option">كل طرق التحصيل</option><option value="cash" data-testid="revenues-filter-method-cash-option">نقداً</option><option value="check" data-testid="revenues-filter-method-check-option">شيك</option><option value="payment_order" data-testid="revenues-filter-method-payment-option">أمر دفع</option></select>
            <Input type="date" value={filters.from_date} onChange={(event) => setFilters((current) => ({ ...current, from_date: event.target.value }))} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="revenues-filter-from-date-input" />
            <Input type="date" value={filters.to_date} onChange={(event) => setFilters((current) => ({ ...current, to_date: event.target.value }))} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="revenues-filter-to-date-input" />
          </div>
        </section>

        <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:border-0 print:shadow-none sm:p-8" data-testid="revenues-report-section">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between" data-testid="revenues-report-heading">
            <div><p className="text-sm font-extrabold text-emerald-700" data-testid="revenues-report-eyebrow">تقرير الإيرادات</p><h2 className="text-3xl font-extrabold text-slate-950" data-testid="revenues-report-title">بيان الإيرادات المسجلة</h2></div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="revenues-report-kpis"><div className="rounded-xl bg-slate-950 p-4 text-white" data-testid="revenues-count-card"><p className="text-xs font-bold text-slate-300">عدد الإيرادات</p><p className="text-2xl font-extrabold" data-testid="revenues-count-value">{revenues.length}</p></div><div className="rounded-xl bg-emerald-50 p-4 text-emerald-900" data-testid="revenues-total-card"><p className="text-xs font-bold text-emerald-700">إجمالي الإيرادات</p><p className="text-2xl font-extrabold" data-testid="revenues-total-value">{formatCurrency(totalAmount)}</p></div></div>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200" data-testid="revenues-table-wrapper">
            <Table data-testid="revenues-table">
              <TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950" data-testid="revenues-table-header-row">{["رقم الإذن", "المبلغ", "طريقة التحصيل", "بيان التحصيل", "البنك", "بتاريخ", "قيمة", "تحريراً في", "الموظف"].map((title) => <TableHead key={title} className="text-right font-extrabold text-white" data-testid={`revenues-header-${title}`}>{title}</TableHead>)}{canManage && <TableHead className="text-right font-extrabold text-white print:hidden" data-testid="revenues-header-actions">إجراءات</TableHead>}</TableRow></TableHeader>
              <TableBody>{revenues.map((item) => <TableRow key={item.id} data-testid={`revenue-row-${item.id}`}><TableCell className="font-extrabold" data-testid={`revenue-row-${item.id}-receipt`}>{item.receipt_number}</TableCell><TableCell data-testid={`revenue-row-${item.id}-amount`}>{formatCurrency(item.amount)}</TableCell><TableCell data-testid={`revenue-row-${item.id}-method`}>{methodLabels[item.collection_method]}</TableCell><TableCell data-testid={`revenue-row-${item.id}-detail`}>{detailValue(item)}</TableCell><TableCell data-testid={`revenue-row-${item.id}-bank`}>{item.bank_name}</TableCell><TableCell data-testid={`revenue-row-${item.id}-dated`}>{item.dated}</TableCell><TableCell className="max-w-xs break-words" data-testid={`revenue-row-${item.id}-value`}>{item.value}</TableCell><TableCell data-testid={`revenue-row-${item.id}-issued`}>{item.issued_at}</TableCell><TableCell data-testid={`revenue-row-${item.id}-employee`}>{item.responsible_employee}</TableCell>{canManage && <TableCell className="print:hidden" data-testid={`revenue-row-${item.id}-actions`}><div className="flex flex-col gap-2" data-testid={`revenue-row-${item.id}-manage-actions`}><button type="button" onClick={() => editRevenue(item)} className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 text-xs font-extrabold text-amber-700" data-testid={`edit-revenue-button-${item.id}`}><Pencil className="h-4 w-4" /> تعديل</button><button type="button" onClick={() => deleteRevenue(item)} className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 text-xs font-extrabold text-red-700" data-testid={`delete-revenue-button-${item.id}`}><Trash2 className="h-4 w-4" /> حذف</button></div></TableCell>}</TableRow>)}</TableBody>
            </Table>
          </div>
        </section>
      </section>

      {searchOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 print:hidden" data-testid="revenue-search-modal-overlay"><section className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-xl bg-white p-6 shadow-2xl" role="dialog" aria-modal="true" data-testid="revenue-search-modal"><div className="mb-5 flex items-center justify-between gap-3" data-testid="revenue-search-modal-heading"><div><p className="text-sm font-extrabold text-emerald-700" data-testid="revenue-search-modal-eyebrow">نتيجة البحث</p><h3 className="text-2xl font-extrabold text-slate-950" data-testid="revenue-search-modal-title">بيانات الإيراد</h3></div><button type="button" onClick={() => setSearchOpen(false)} className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white" data-testid="close-revenue-search-modal-button"><X className="h-4 w-4" /></button></div>{searchResults.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center" data-testid="revenue-search-empty-state"><p className="text-xl font-extrabold text-slate-950" data-testid="revenue-search-empty-title">لا توجد نتيجة مطابقة</p></div> : <div className="space-y-4" data-testid="revenue-search-results-list">{searchResults.map((item) => <article key={item.id} className="rounded-xl border border-slate-200 p-4" data-testid={`revenue-search-result-${item.id}`}><DetailGrid item={item} prefix={`revenue-search-result-${item.id}`} /></article>)}</div>}</section></div>}
      <footer className="px-4 pb-5 print:hidden" data-testid="revenues-footer"><CreditLine testId="revenues-creator-credit" /></footer>
    </main>
  );
}