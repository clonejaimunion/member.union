import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Home, LogOut, PackageSearch, Plus, Save } from "lucide-react";
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
      await api.post("/inventory/movements", {
        ...form,
        item_id: form.item_id || null,
        item_code: form.item_code || null,
        item_name: form.item_name || null,
        quantity: Number(form.quantity || 0),
        unit_cost: form.unit_cost === "" ? null : Number(form.unit_cost || 0),
      });
      toast.success("تم حفظ حركة المخزون وإنشاء القيد تلقائياً");
      setForm({ movement_date: today, item_id: "", item_code: "", item_name: "", unit: "وحدة", movement_type: "in", quantity: "", unit_cost: "", description: "", reference: "" });
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
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="inventory-form-section"><h2 className="mb-4 text-2xl font-extrabold" data-testid="inventory-form-title">إدخال حركة مخزون</h2><form onSubmit={saveMovement} className="space-y-4" data-testid="inventory-movement-form"><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><div><Label data-testid="inventory-date-label">التاريخ</Label><Input type="date" value={form.movement_date} onChange={(e) => updateForm("movement_date", e.target.value)} required data-testid="inventory-date-input" /></div><div><Label data-testid="inventory-type-label">نوع الحركة</Label><select value={form.movement_type} onChange={(e) => updateForm("movement_type", e.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 font-bold" data-testid="inventory-type-select"><option value="in" data-testid="inventory-type-in-option">وارد</option><option value="out" data-testid="inventory-type-out-option">منصرف</option></select></div></div><div><Label data-testid="inventory-existing-item-label">الصنف المسجل</Label><select value={form.item_id} onChange={(e) => updateForm("item_id", e.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 font-bold" data-testid="inventory-item-select"><option value="" data-testid="inventory-item-new-option">صنف جديد / بدون اختيار</option>{items.map((item) => <option key={item.id} value={item.id} data-testid={`inventory-item-option-${item.id}`}>{item.item_code} — {item.item_name}</option>)}</select></div><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><Input placeholder="كود صنف جديد" value={form.item_code} onChange={(e) => updateForm("item_code", e.target.value)} data-testid="inventory-item-code-input" /><Input placeholder="اسم صنف جديد" value={form.item_name} onChange={(e) => updateForm("item_name", e.target.value)} data-testid="inventory-item-name-input" /></div><div className="grid grid-cols-1 gap-3 md:grid-cols-3"><Input placeholder="الوحدة" value={form.unit} onChange={(e) => updateForm("unit", e.target.value)} data-testid="inventory-unit-input" /><Input placeholder="الكمية" inputMode="decimal" value={form.quantity} onChange={(e) => updateForm("quantity", e.target.value)} required data-testid="inventory-quantity-input" /><Input placeholder="تكلفة الوحدة" inputMode="decimal" value={form.unit_cost} onChange={(e) => updateForm("unit_cost", e.target.value)} data-testid="inventory-unit-cost-input" /></div><Input placeholder="البيان" value={form.description} onChange={(e) => updateForm("description", e.target.value)} required data-testid="inventory-description-input" /><Input placeholder="رقم مستند اختياري" value={form.reference} onChange={(e) => updateForm("reference", e.target.value)} data-testid="inventory-reference-input" /><Button type="submit" disabled={saving} className="h-11 w-full bg-slate-950 text-white" data-testid="inventory-save-button"><Save className="h-4 w-4" /> حفظ الحركة وإنشاء القيد</Button></form></section>
        <section className="space-y-5" data-testid="inventory-ledger-section"><div className="grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="inventory-kpis"><div className="rounded-xl bg-white p-5 shadow-sm" data-testid="inventory-total-quantity-card"><p className="text-xs font-bold text-slate-500">إجمالي الكميات</p><p className="text-2xl font-extrabold">{totals.quantity.toFixed(2)}</p></div><div className="rounded-xl bg-emerald-50 p-5 text-emerald-900 shadow-sm" data-testid="inventory-total-value-card"><p className="text-xs font-bold">قيمة المخزون ضمن الأصول المتداولة</p><p className="text-2xl font-extrabold">{formatCurrency(totals.value)}</p></div></div><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="inventory-filters-section"><div className="grid grid-cols-1 gap-2 md:grid-cols-4"><Input type="date" value={filters.from_date} onChange={(e) => setFilters((c) => ({ ...c, from_date: e.target.value }))} data-testid="inventory-filter-from-date" /><Input type="date" value={filters.to_date} onChange={(e) => setFilters((c) => ({ ...c, to_date: e.target.value }))} data-testid="inventory-filter-to-date" /><select value={filters.item_id} onChange={(e) => setFilters((c) => ({ ...c, item_id: e.target.value }))} className="h-10 rounded-md border border-slate-300 bg-white px-3 font-bold" data-testid="inventory-filter-item-select"><option value="">كل الأصناف</option>{items.map((item) => <option key={item.id} value={item.id}>{item.item_name}</option>)}</select><Button onClick={loadData} variant="outline" className="h-10 bg-white" data-testid="inventory-filter-apply-button">تطبيق</Button></div></div><div className="overflow-x-auto rounded-xl border border-slate-200 bg-white" data-testid="inventory-movements-table-wrapper"><Table data-testid="inventory-movements-table"><TableHeader className="bg-slate-950"><TableRow><TableHead className="text-right text-white">التاريخ</TableHead><TableHead className="text-right text-white">الصنف</TableHead><TableHead className="text-right text-white">الحركة</TableHead><TableHead className="text-right text-white">الكمية</TableHead><TableHead className="text-right text-white">القيمة</TableHead><TableHead className="text-right text-white">الرصيد</TableHead><TableHead className="text-right text-white">القيد</TableHead></TableRow></TableHeader><TableBody>{loading && <TableRow><TableCell colSpan={7} className="py-8 text-center font-bold">جاري التحميل...</TableCell></TableRow>}{!loading && movements.length === 0 && <TableRow data-testid="inventory-empty-row"><TableCell colSpan={7} className="py-8 text-center font-bold text-slate-500">لا توجد حركات مخزون</TableCell></TableRow>}{movements.map((movement) => <TableRow key={movement.id} data-testid={`inventory-movement-row-${movement.id}`}><TableCell>{formatDate(movement.movement_date)}</TableCell><TableCell className="font-extrabold">{movement.item_name}</TableCell><TableCell>{movementLabels[movement.movement_type]}</TableCell><TableCell>{movement.quantity}</TableCell><TableCell>{formatCurrency(movement.total_value)}</TableCell><TableCell>{movement.quantity_balance_after} / {formatCurrency(movement.value_balance_after)}</TableCell><TableCell>{movement.journal_entry_id ? "تم الترحيل" : "غير مرحل"}</TableCell></TableRow>)}</TableBody></Table></div></section>
      </section><footer className="px-4 pb-5 print:hidden"><CreditLine testId="inventory-creator-credit" /></footer>
    </main>
  );
}