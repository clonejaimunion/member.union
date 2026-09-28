import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Home, LogOut, PackageSearch, Pencil, Plus, Save, Trash2, X } from "lucide-react";
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
const movementLabels = { in: "وارد", out: "منصرف" };

export default function InventoryPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [items, setItems] = useState([]);
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [filters, setFilters] = useState({ from_date: "", to_date: "", item_id: "" });
  const [form, setForm] = useState({ movement_date: today, item_id: "", item_code: "", item_name: "", unit: "وحدة", movement_type: "in", quantity: "", unit_cost: "", description: "", reference: "" });
  const [editingId, setEditingId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const emptyForm = () => ({ movement_date: today, item_id: "", item_code: "", item_name: "", unit: "وحدة", movement_type: "in", quantity: "", unit_cost: "", description: "", reference: "" });
  const resetForm = () => { setEditingId(null); setForm(emptyForm()); };
  const startEdit = (movement) => {
    setEditingId(movement.id);
    setForm({
      movement_date: String(movement.movement_date).slice(0, 10),
      item_id: movement.item_id,
      item_code: movement.item_code || "",
      item_name: movement.item_name || "",
      unit: movement.unit || "وحدة",
      movement_type: movement.movement_type,
      quantity: String(movement.quantity ?? ""),
      unit_cost: movement.movement_type === "in" ? String(movement.unit_cost ?? "") : "",
      description: movement.description || "",
      reference: movement.reference || "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/inventory/movements/${deleteTarget.id}`);
      toast.success("تم حذف الحركة وقيدها وإعادة احتساب رصيد الصنف");
      if (editingId === deleteTarget.id) resetForm();
      setDeleteTarget(null);
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حذف حركة المخزون");
    } finally {
      setDeleting(false);
    }
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.from_date) params.set("from_date", filters.from_date);
      if (filters.to_date) params.set("to_date", filters.to_date);
      if (filters.item_id) params.set("item_id", filters.item_id);
      const [itemsResponse, movementsResponse] = await Promise.all([api.get("/inventory/items"), api.get(`/inventory/movements?${params.toString()}`)]);
      setItems(itemsResponse.data);
      setMovements(movementsResponse.data);
    } catch (error) {
      toast.error("تعذر تحميل دفتر المخزون");
    } finally {
      setLoading(false);
    }
  }, [filters.from_date, filters.to_date, filters.item_id]);

  useEffect(() => { loadData(); }, [loadData]);

  const totals = useMemo(() => items.reduce((acc, item) => ({ quantity: acc.quantity + Number(item.quantity_balance || 0), value: acc.value + Number(item.value_balance || 0) }), { quantity: 0, value: 0 }), [items]);
  const updateForm = (field, value) => setForm((current) => ({ ...current, [field]: ["quantity", "unit_cost"].includes(field) ? sanitizeDecimalInput(value) : value }));

  const saveMovement = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...form,
        item_id: form.item_id || null,
        item_code: form.item_code || null,
        item_name: form.item_name || null,
        quantity: Number(form.quantity || 0),
        unit_cost: form.unit_cost === "" ? null : Number(form.unit_cost || 0),
      };
      if (editingId) {
        if (!form.item_id) {
          toast.error("لا يمكن تغيير الصنف أثناء التعديل");
          setSaving(false);
          return;
        }
        await api.put(`/inventory/movements/${editingId}`, payload);
        toast.success("تم تعديل الحركة وتحديث قيدها وإعادة احتساب الرصيد");
      } else {
        await api.post("/inventory/movements", payload);
        toast.success("تم حفظ حركة المخزون وإنشاء القيد تلقائياً");
      }
      resetForm();
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ حركة المخزون");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="inventory-page">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur print:hidden" data-testid="inventory-header"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8"><div className="flex items-center gap-3" data-testid="inventory-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white"><PackageSearch className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700">تدفق محاسبي تلقائي</p><h1 className="text-2xl font-extrabold" data-testid="inventory-title">دفتر المخزون</h1></div></div><div className="flex flex-wrap items-center gap-3" data-testid="inventory-actions"><Badge className="bg-white text-slate-700" data-testid="inventory-user-badge">{user?.full_name || user?.username}</Badge><Button asChild variant="outline" className="h-11 bg-white" data-testid="inventory-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="inventory-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 bg-white" data-testid="inventory-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div></div></header>
      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 sm:px-6 xl:grid-cols-[0.85fr_1.15fr] lg:px-8" data-testid="inventory-content">
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="inventory-form-section"><h2 className="mb-4 text-2xl font-extrabold" data-testid="inventory-form-title">{editingId ? "تعديل حركة مخزون" : "إدخال حركة مخزون"}</h2>{editingId && <div className="mb-4 flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-extrabold text-amber-800" data-testid="inventory-editing-banner"><span>أنت تعدّل حركة مسجّلة — سيتم تحديث القيد وإعادة احتساب رصيد الصنف تلقائياً</span><button type="button" onClick={resetForm} className="inline-flex items-center gap-1 text-amber-900" data-testid="inventory-cancel-edit-inline"><X className="h-4 w-4" /> إلغاء</button></div>}<form onSubmit={saveMovement} className="space-y-4" data-testid="inventory-movement-form"><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><div><Label data-testid="inventory-date-label">التاريخ</Label><Input type="date" value={form.movement_date} onChange={(e) => updateForm("movement_date", e.target.value)} required data-testid="inventory-date-input" /></div><div><Label data-testid="inventory-type-label">نوع الحركة</Label><select value={form.movement_type} onChange={(e) => updateForm("movement_type", e.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 font-bold" data-testid="inventory-type-select"><option value="in" data-testid="inventory-type-in-option">وارد</option><option value="out" data-testid="inventory-type-out-option">منصرف</option></select></div></div><div><Label data-testid="inventory-existing-item-label">الصنف المسجل</Label><select value={form.item_id} onChange={(e) => updateForm("item_id", e.target.value)} disabled={!!editingId} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 font-bold disabled:opacity-60" data-testid="inventory-item-select"><option value="" data-testid="inventory-item-new-option">صنف جديد / بدون اختيار</option>{items.map((item) => <option key={item.id} value={item.id} data-testid={`inventory-item-option-${item.id}`}>{item.item_code} — {item.item_name}</option>)}</select></div><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><Input placeholder="كود صنف جديد" value={form.item_code} onChange={(e) => updateForm("item_code", e.target.value)} disabled={!!editingId} data-testid="inventory-item-code-input" /><Input placeholder="اسم صنف جديد" value={form.item_name} onChange={(e) => updateForm("item_name", e.target.value)} disabled={!!editingId} data-testid="inventory-item-name-input" /></div><div className="grid grid-cols-1 gap-3 md:grid-cols-3"><Input placeholder="الوحدة" value={form.unit} onChange={(e) => updateForm("unit", e.target.value)} data-testid="inventory-unit-input" /><Input placeholder="الكمية" inputMode="decimal" value={form.quantity} onChange={(e) => updateForm("quantity", e.target.value)} required data-testid="inventory-quantity-input" /><Input placeholder="تكلفة الوحدة" inputMode="decimal" value={form.unit_cost} onChange={(e) => updateForm("unit_cost", e.target.value)} data-testid="inventory-unit-cost-input" /></div><Input placeholder="البيان" value={form.description} onChange={(e) => updateForm("description", e.target.value)} required data-testid="inventory-description-input" /><Input placeholder="رقم مستند اختياري" value={form.reference} onChange={(e) => updateForm("reference", e.target.value)} data-testid="inventory-reference-input" /><div className="flex gap-2"><Button type="submit" disabled={saving} className="h-11 w-full bg-slate-950 text-white" data-testid="inventory-save-button"><Save className="h-4 w-4" /> {editingId ? "حفظ التعديل وتحديث القيد" : "حفظ الحركة وإنشاء القيد"}</Button>{editingId && <Button type="button" variant="outline" onClick={resetForm} className="h-11 bg-white" data-testid="inventory-cancel-edit-button"><X className="h-4 w-4" /> إلغاء</Button>}</div></form></section>
        <section className="space-y-5" data-testid="inventory-ledger-section"><div className="grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="inventory-kpis"><div className="rounded-xl bg-white p-5 shadow-sm" data-testid="inventory-total-quantity-card"><p className="text-xs font-bold text-slate-500">إجمالي الكميات</p><p className="text-2xl font-extrabold">{totals.quantity.toFixed(2)}</p></div><div className="rounded-xl bg-emerald-50 p-5 text-emerald-900 shadow-sm" data-testid="inventory-total-value-card"><p className="text-xs font-bold">قيمة المخزون ضمن الأصول المتداولة</p><p className="text-2xl font-extrabold">{formatCurrency(totals.value)}</p></div></div><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="inventory-filters-section"><div className="grid grid-cols-1 gap-2 md:grid-cols-4"><Input type="date" value={filters.from_date} onChange={(e) => setFilters((c) => ({ ...c, from_date: e.target.value }))} data-testid="inventory-filter-from-date" /><Input type="date" value={filters.to_date} onChange={(e) => setFilters((c) => ({ ...c, to_date: e.target.value }))} data-testid="inventory-filter-to-date" /><select value={filters.item_id} onChange={(e) => setFilters((c) => ({ ...c, item_id: e.target.value }))} className="h-10 rounded-md border border-slate-300 bg-white px-3 font-bold" data-testid="inventory-filter-item-select"><option value="">كل الأصناف</option>{items.map((item) => <option key={item.id} value={item.id}>{item.item_name}</option>)}</select><Button onClick={loadData} variant="outline" className="h-10 bg-white" data-testid="inventory-filter-apply-button">تطبيق</Button></div></div><div className="overflow-x-auto rounded-xl border border-slate-200 bg-white" data-testid="inventory-movements-table-wrapper"><Table data-testid="inventory-movements-table"><TableHeader className="bg-slate-950"><TableRow><TableHead className="text-right text-white">التاريخ</TableHead><TableHead className="text-right text-white">الصنف</TableHead><TableHead className="text-right text-white">الحركة</TableHead><TableHead className="text-right text-white">الكمية</TableHead><TableHead className="text-right text-white">القيمة</TableHead><TableHead className="text-right text-white">الرصيد</TableHead><TableHead className="text-right text-white">القيد</TableHead><TableHead className="text-right text-white print:hidden">إجراءات</TableHead></TableRow></TableHeader><TableBody>{loading && <TableRow><TableCell colSpan={8} className="py-8 text-center font-bold">جاري التحميل...</TableCell></TableRow>}{!loading && movements.length === 0 && <TableRow data-testid="inventory-empty-row"><TableCell colSpan={8} className="py-8 text-center font-bold text-slate-500">لا توجد حركات مخزون</TableCell></TableRow>}{movements.map((movement) => <TableRow key={movement.id} data-testid={`inventory-movement-row-${movement.id}`}><TableCell>{formatDate(movement.movement_date)}</TableCell><TableCell className="font-extrabold">{movement.item_name}</TableCell><TableCell>{movementLabels[movement.movement_type]}</TableCell><TableCell>{movement.quantity}</TableCell><TableCell>{formatCurrency(movement.total_value)}</TableCell><TableCell>{movement.quantity_balance_after} / {formatCurrency(movement.value_balance_after)}</TableCell><TableCell>{movement.journal_entry_id ? "تم الترحيل" : "غير مرحل"}</TableCell><TableCell className="print:hidden"><div className="flex gap-2"><button type="button" onClick={() => startEdit(movement)} className="inline-flex h-9 items-center justify-center gap-1 rounded-lg border border-amber-200 bg-amber-50 px-3 text-xs font-extrabold text-amber-700" data-testid={`inventory-edit-button-${movement.id}`}><Pencil className="h-4 w-4" /> تعديل</button><button type="button" onClick={() => setDeleteTarget(movement)} className="inline-flex h-9 items-center justify-center gap-1 rounded-lg border border-red-200 bg-red-50 px-3 text-xs font-extrabold text-red-700" data-testid={`inventory-delete-button-${movement.id}`}><Trash2 className="h-4 w-4" /> حذف</button></div></TableCell></TableRow>)}</TableBody></Table></div></section>
      </section><footer className="px-4 pb-5 print:hidden"><CreditLine testId="inventory-creator-credit" /></footer>
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" data-testid="inventory-delete-modal">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-xl font-extrabold text-slate-950" data-testid="inventory-delete-modal-title">تأكيد حذف حركة المخزون</h3>
            <p className="mt-3 text-sm font-bold text-slate-600" data-testid="inventory-delete-modal-body">هل أنت متأكد من حذف حركة «{movementLabels[deleteTarget.movement_type]}» للصنف «{deleteTarget.item_name}»؟ سيتم حذف القيد المرتبط بها وإعادة احتساب رصيد الصنف والحركات اللاحقة تلقائياً.</p>
            <div className="mt-6 flex gap-3">
              <Button type="button" onClick={confirmDelete} disabled={deleting} className="h-11 flex-1 bg-red-600 text-white hover:bg-red-700" data-testid="inventory-delete-confirm-button"><Trash2 className="h-4 w-4" /> نعم، احذف</Button>
              <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)} disabled={deleting} className="h-11 flex-1 bg-white" data-testid="inventory-delete-cancel-button"><X className="h-4 w-4" /> تراجع</Button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}