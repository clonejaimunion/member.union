import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Calculator, Home, LogOut, PackageCheck, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ExportReportButtons } from "@/components/ExportReportButtons";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { formatCurrency, sanitizeDecimalInput } from "@/lib/format";

const today = new Date();
const todayIso = today.toISOString().slice(0, 10);
const currentYear = today.getFullYear();
const currentMonth = today.getMonth() + 1;
const monthOptions = Array.from({ length: 12 }, (_, index) => index + 1);
const yearOptions = Array.from({ length: 11 }, (_, index) => currentYear - 5 + index);

const initialForm = { category_code: "", asset_name: "", purchase_date: todayIso, purchase_cost: "", bank_id: "", invoice_number: "", notes: "" };

export default function FixedAssetsPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [categories, setCategories] = useState([]);
  const [assetItems, setAssetItems] = useState([]);
  const [newAssetName, setNewAssetName] = useState("");
  const [banks, setBanks] = useState([]);
  const [assets, setAssets] = useState([]);
  const [depreciations, setDepreciations] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [runPeriod, setRunPeriod] = useState({ year: String(currentYear), month: String(currentMonth) });
  const [depreciationMode] = useState("yearly");
  const [assetReportFilter, setAssetReportFilter] = useState({ category_code: "all", asset_name: "all" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const canManage = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.manage_expenses;

  const loadAssetCatalog = useCallback(async (categoryCode) => {
    if (!categoryCode) return;
    try {
      const response = await api.get(`/fixed-assets/catalog-items?category_code=${encodeURIComponent(categoryCode)}`);
      setAssetItems(response.data);
      setForm((current) => ({ ...current, asset_name: current.asset_name === "__new__" || response.data.some((item) => item.name === current.asset_name) ? current.asset_name : response.data[0]?.name || "__new__" }));
    } catch (error) {
      toast.error("تعذر تحميل قائمة الأصول");
    }
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [categoriesResponse, banksResponse, assetsResponse, depreciationResponse] = await Promise.all([
        api.get("/fixed-assets/categories"),
        api.get("/banks"),
        api.get("/fixed-assets"),
        api.get(`/fixed-assets/depreciations?year=${runPeriod.year}`),
      ]);
      setCategories(categoriesResponse.data);
      setBanks(banksResponse.data);
      setAssets(assetsResponse.data);
      setDepreciations(depreciationResponse.data);
      setForm((current) => ({ ...current, category_code: current.category_code || categoriesResponse.data[0]?.code || "", asset_name: current.asset_name || categoriesResponse.data[0]?.items?.[0] || "", bank_id: current.bank_id || banksResponse.data[0]?.id || "" }));
    } catch (error) {
      toast.error("تعذر تحميل الأصول الثابتة");
    } finally {
      setLoading(false);
    }
  }, [runPeriod.year]);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { if (form.category_code) loadAssetCatalog(form.category_code); }, [form.category_code, loadAssetCatalog]);

  const activeCategory = useMemo(() => categories.find((item) => item.code === form.category_code), [categories, form.category_code]);
  const displayedAssets = useMemo(() => assets.filter((asset) => (assetReportFilter.category_code === "all" || asset.category_code === assetReportFilter.category_code) && (assetReportFilter.asset_name === "all" || asset.asset_name === assetReportFilter.asset_name)), [assets, assetReportFilter]);
  const assetNamesForFilter = useMemo(() => [...new Set(assets.filter((asset) => assetReportFilter.category_code === "all" || asset.category_code === assetReportFilter.category_code).map((asset) => asset.asset_name))].sort(), [assets, assetReportFilter.category_code]);
  const totals = useMemo(() => displayedAssets.reduce((acc, asset) => ({ cost: acc.cost + Number(asset.purchase_cost || 0), depreciation: acc.depreciation + Number(asset.accumulated_depreciation || 0), net: acc.net + Number(asset.net_book_value || 0) }), { cost: 0, depreciation: 0, net: 0 }), [displayedAssets]);

  const updateForm = (field, value) => {
    setForm((current) => ({ ...current, [field]: field === "purchase_cost" ? sanitizeDecimalInput(value) : value }));
  };

  const updateCategory = (categoryCode) => {
    setNewAssetName("");
    setForm((current) => ({ ...current, category_code: categoryCode, asset_name: "" }));
  };

  const createAsset = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      let assetName = form.asset_name;
      if (assetName === "__new__") {
        if (!newAssetName.trim()) {
          toast.error("اكتب اسم الأصل الجديد");
          setSaving(false);
          return;
        }
        const catalogResponse = await api.post("/fixed-assets/catalog-items", { category_code: form.category_code, name: newAssetName.trim() });
        assetName = catalogResponse.data.name;
      }
      await api.post("/fixed-assets", { ...form, asset_name: assetName, purchase_cost: Number(form.purchase_cost || 0), invoice_number: form.invoice_number || null, notes: form.notes || null, is_active: true });
      toast.success("تم تسجيل الأصل وإنشاء قيد الشراء تلقائياً");
      setNewAssetName("");
      setForm((current) => ({ ...initialForm, category_code: current.category_code, asset_name: assetName, bank_id: current.bank_id, purchase_date: todayIso }));
      await loadData();
      await loadAssetCatalog(form.category_code);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تسجيل الأصل الثابت");
    } finally {
      setSaving(false);
    }
  };

  const deleteSelectedAssetItem = async () => {
    const selected = assetItems.find((item) => item.name === form.asset_name);
    if (!selected) return toast.error("اختر أصل من القائمة لحذفه");
    if (!window.confirm(`هل تريد حذف ${selected.name} من قائمة الأصول؟`)) return;
    try {
      await api.delete(`/fixed-assets/catalog-items/${selected.id}`);
      toast.success("تم حذف الأصل من القائمة");
      setForm((current) => ({ ...current, asset_name: "" }));
      await loadAssetCatalog(form.category_code);
      await loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حذف الأصل من القائمة");
    }
  };

  const runDepreciation = async () => {
    setSaving(true);
    try {
      const response = await api.post("/fixed-assets/depreciation/run", { year: Number(runPeriod.year), month: 12 });
      setDepreciations(response.data);
      toast.success(`تم إثبات الإهلاك السنوي تلقائياً لعدد ${response.data.length} أصل`);
      await loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إثبات الإهلاك");
    } finally {
      setSaving(false);
    }
  };

  const deleteAsset = async (asset) => {
    if (!window.confirm(`هل تريد حذف الأصل ${asset.asset_name} مع قيوده؟`)) return;
    try {
      await api.delete(`/fixed-assets/${asset.id}`);
      toast.success("تم حذف الأصل وقيوده التلقائية");
      await loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حذف الأصل");
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="fixed-assets-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="fixed-assets-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8" data-testid="fixed-assets-header-inner">
          <div className="flex items-center gap-3" data-testid="fixed-assets-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="fixed-assets-brand-icon"><PackageCheck className="h-5 w-5" /></div><div data-testid="fixed-assets-title-block"><p className="text-xs font-extrabold text-emerald-700" data-testid="fixed-assets-eyebrow">النظام المحاسبي</p><h1 className="text-2xl font-extrabold" data-testid="fixed-assets-title">الأصول الثابتة</h1></div></div>
          <div className="flex flex-wrap items-center gap-3" data-testid="fixed-assets-actions"><Badge className="bg-white text-slate-700" data-testid="fixed-assets-organization-badge">{user?.organization_name}</Badge><Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="fixed-assets-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button type="button" onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="fixed-assets-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button type="button" onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="fixed-assets-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 sm:px-6 xl:grid-cols-[0.8fr_1.2fr] lg:px-8" data-testid="fixed-assets-content">
        {canManage && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="fixed-asset-create-section">
          <h2 className="mb-5 text-2xl font-extrabold" data-testid="fixed-asset-create-title">تسجيل أصل ثابت</h2>
          <form onSubmit={createAsset} className="space-y-4" data-testid="fixed-asset-create-form">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="fixed-asset-basic-grid"><div data-testid="fixed-asset-category-wrapper"><Label data-testid="fixed-asset-category-label">التصنيف</Label><select value={form.category_code} onChange={(event) => updateCategory(event.target.value)} required className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="fixed-asset-category-select">{categories.map((category) => <option key={category.code} value={category.code} label={`${category.code} - ${category.name} (${category.annual_depreciation_rate}%)`} />)}</select></div><div data-testid="fixed-asset-name-wrapper"><Label data-testid="fixed-asset-name-label">الأصل</Label><div className="mt-2 grid grid-cols-[1fr_auto] gap-2" data-testid="fixed-asset-name-control"><select value={form.asset_name} onChange={(event) => updateForm("asset_name", event.target.value)} required className="h-11 w-full rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="fixed-asset-name-select">{assetItems.map((item) => <option key={item.id} value={item.name} label={item.name} />)}<option value="__new__" label="إضافة أصل جديد" /></select><Button type="button" onClick={deleteSelectedAssetItem} variant="outline" className="h-11 bg-white text-red-700" data-testid="delete-fixed-asset-catalog-item-button"><Trash2 className="h-4 w-4" /></Button></div>{form.asset_name === "__new__" && <Input value={newAssetName} onChange={(event) => setNewAssetName(event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" placeholder="اكتب اسم الأصل الجديد" data-testid="fixed-asset-new-name-input" />}</div></div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="fixed-asset-money-grid"><div data-testid="fixed-asset-cost-wrapper"><Label data-testid="fixed-asset-cost-label">تكلفة الأصل</Label><Input inputMode="decimal" value={form.purchase_cost} onChange={(event) => updateForm("purchase_cost", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="fixed-asset-cost-input" /></div><div data-testid="fixed-asset-date-wrapper"><Label data-testid="fixed-asset-date-label">تاريخ الشراء</Label><Input type="text" value={form.purchase_date} onChange={(event) => updateForm("purchase_date", event.target.value)} required pattern="\d{4}-\d{2}-\d{2}" placeholder="YYYY-MM-DD" className="mt-2 h-11 bg-slate-50 text-right" data-testid="fixed-asset-purchase-date-input" /></div></div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="fixed-asset-bank-grid"><div data-testid="fixed-asset-bank-wrapper"><Label data-testid="fixed-asset-bank-label">البنك المسدد منه</Label><select value={form.bank_id} onChange={(event) => updateForm("bank_id", event.target.value)} required className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="fixed-asset-bank-select">{banks.map((bank) => <option key={bank.id} value={bank.id} label={bank.name} />)}</select></div><div data-testid="fixed-asset-invoice-wrapper"><Label data-testid="fixed-asset-invoice-label">رقم الفاتورة/المستند</Label><Input value={form.invoice_number} onChange={(event) => updateForm("invoice_number", event.target.value)} className="mt-2 h-11 bg-slate-50 text-right" data-testid="fixed-asset-invoice-input" /></div></div>
            <div data-testid="fixed-asset-notes-wrapper"><Label data-testid="fixed-asset-notes-label">ملاحظات</Label><Input value={form.notes} onChange={(event) => updateForm("notes", event.target.value)} className="mt-2 h-11 bg-slate-50 text-right" data-testid="fixed-asset-notes-input" /></div>
            <div className="rounded-lg bg-emerald-50 p-3 text-sm font-extrabold text-emerald-800" data-testid="fixed-asset-auto-calculation-note">معدل الإهلاك السنوي المختار: {activeCategory?.annual_depreciation_rate || 0}% — سيتم إنشاء قيد شراء الأصل تلقائياً، وحساب تاريخ تكهين الأصل عند انتهاء الإهلاك بالكامل.</div>
            <Button type="submit" disabled={saving} className="h-11 w-full bg-slate-950 text-white" data-testid="fixed-asset-save-button"><Save className="h-4 w-4" /> حفظ الأصل تلقائياً</Button>
          </form>
        </section>}

        <section className="space-y-6" data-testid="fixed-assets-report-column">
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="fixed-asset-depreciation-run-section"><div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between" data-testid="fixed-asset-depreciation-heading"><div data-testid="fixed-asset-depreciation-title-block"><h2 className="text-2xl font-extrabold" data-testid="fixed-asset-depreciation-title">الإهلاك السنوي التلقائي</h2><p className="text-sm font-bold text-slate-500" data-testid="fixed-asset-depreciation-subtitle">النظام يحسب الإهلاك سنوياً حسب السنة المختارة للميزانية ويرحل القيد تلقائياً.</p></div><ExportReportButtons title={`تقرير الأصول الثابتة سنة ${runPeriod.year}`} fileName={`الأصول-الثابتة-سنوي-${runPeriod.year}`} selectors={["[data-testid='fixed-assets-list-section']", "[data-testid='fixed-asset-depreciations-section']"]} disabled={loading} pdfLabel="طباعة PDF" pdfTestId="print-fixed-assets-report-button" excelTestId="export-fixed-assets-excel-button" wordTestId="export-fixed-assets-word-button" /></div><div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto]" data-testid="fixed-asset-depreciation-controls"><select value={runPeriod.year} onChange={(event) => setRunPeriod((current) => ({ ...current, year: event.target.value }))} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="fixed-asset-depreciation-year-select">{yearOptions.map((year) => <option key={year} value={year} label={String(year)} />)}</select><Button type="button" onClick={runDepreciation} disabled={saving} className="h-11 bg-slate-950 text-white disabled:opacity-50" data-testid="run-fixed-asset-depreciation-button"><Calculator className="h-4 w-4" /> تشغيل الإهلاك السنوي التلقائي</Button></div></section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="fixed-assets-list-section"><div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_auto] print:hidden" data-testid="fixed-assets-report-filters"><select value={assetReportFilter.category_code} onChange={(event) => setAssetReportFilter({ category_code: event.target.value, asset_name: "all" })} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="fixed-assets-category-report-filter"><option value="all" label="كل التصنيفات" />{categories.map((category) => <option key={category.code} value={category.code} label={`${category.code} - ${category.name}`} />)}</select><select value={assetReportFilter.asset_name} onChange={(event) => setAssetReportFilter((current) => ({ ...current, asset_name: event.target.value }))} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="fixed-assets-name-report-filter"><option value="all" label="كل الأصول" />{assetNamesForFilter.map((name) => <option key={name} value={name} label={name} />)}</select><Button type="button" onClick={() => window.print()} variant="outline" className="h-11 bg-white" data-testid="print-registered-fixed-assets-button">طباعة الأصول المسجلة</Button></div><div className="mb-5 grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="fixed-assets-kpi-grid"><div className="rounded-xl bg-slate-950 p-4 text-white" data-testid="fixed-assets-total-cost-card"><p className="text-xs font-bold text-slate-300" data-testid="fixed-assets-total-cost-label">إجمالي التكلفة</p><p className="text-xl font-extrabold" data-testid="fixed-assets-total-cost-value">{formatCurrency(totals.cost)}</p></div><div className="rounded-xl bg-amber-50 p-4" data-testid="fixed-assets-total-depreciation-card"><p className="text-xs font-bold text-amber-700" data-testid="fixed-assets-total-depreciation-label">مجمع الإهلاك</p><p className="text-xl font-extrabold" data-testid="fixed-assets-total-depreciation-value">{formatCurrency(totals.depreciation)}</p></div><div className="rounded-xl bg-emerald-50 p-4" data-testid="fixed-assets-total-net-card"><p className="text-xs font-bold text-emerald-700" data-testid="fixed-assets-total-net-label">صافي القيمة الدفترية</p><p className="text-xl font-extrabold" data-testid="fixed-assets-total-net-value">{formatCurrency(totals.net)}</p></div></div><div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="fixed-assets-table-wrapper"><Table data-testid="fixed-assets-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">الكود</TableHead><TableHead className="text-right text-white">الأصل</TableHead><TableHead className="text-right text-white">التصنيف</TableHead><TableHead className="text-right text-white">التكلفة</TableHead><TableHead className="text-right text-white">إهلاك شهري</TableHead><TableHead className="text-right text-white">مجمع الإهلاك</TableHead><TableHead className="text-right text-white">الصافي</TableHead><TableHead className="text-right text-white">تاريخ التكهين</TableHead><TableHead className="text-right text-white print:hidden">إجراء</TableHead></TableRow></TableHeader><TableBody>{loading && <TableRow data-testid="fixed-assets-loading-row"><TableCell colSpan={9} className="py-8 text-center font-bold">جاري التحميل...</TableCell></TableRow>}{!loading && displayedAssets.length === 0 && <TableRow data-testid="fixed-assets-empty-row"><TableCell colSpan={9} className="py-8 text-center font-bold text-slate-500">لا توجد أصول ثابتة مسجلة</TableCell></TableRow>}{displayedAssets.map((asset) => <TableRow key={asset.id} data-testid={`fixed-asset-row-${asset.id}`}><TableCell className="font-extrabold" data-testid={`fixed-asset-${asset.id}-code`}>{asset.asset_code}</TableCell><TableCell className="font-extrabold" data-testid={`fixed-asset-${asset.id}-name`}>{asset.asset_name}<p className="text-xs text-slate-500" data-testid={`fixed-asset-${asset.id}-purchase-date`}>{asset.purchase_date}</p></TableCell><TableCell data-testid={`fixed-asset-${asset.id}-category`}>{asset.category_code} - {asset.category_name}<p className="text-xs text-slate-500" data-testid={`fixed-asset-${asset.id}-rate`}>{asset.annual_depreciation_rate}%</p></TableCell><TableCell data-testid={`fixed-asset-${asset.id}-cost`}>{formatCurrency(asset.purchase_cost)}</TableCell><TableCell data-testid={`fixed-asset-${asset.id}-monthly-depreciation`}>{formatCurrency(asset.monthly_depreciation)}</TableCell><TableCell data-testid={`fixed-asset-${asset.id}-accumulated-depreciation`}>{formatCurrency(asset.accumulated_depreciation)}</TableCell><TableCell className="font-extrabold" data-testid={`fixed-asset-${asset.id}-net-book-value`}>{formatCurrency(asset.net_book_value)}</TableCell><TableCell className="font-extrabold text-emerald-700" data-testid={`fixed-asset-${asset.id}-disposal-date`}>{asset.disposal_date || "-"}</TableCell><TableCell className="print:hidden" data-testid={`fixed-asset-${asset.id}-actions`}>{user?.role === "admin" && <Button type="button" onClick={() => deleteAsset(asset)} variant="outline" className="h-9 bg-white text-red-700" data-testid={`fixed-asset-${asset.id}-delete-button`}><Trash2 className="h-4 w-4" /> حذف</Button>}</TableCell></TableRow>)}</TableBody></Table></div></section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="fixed-asset-depreciations-section"><div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><h2 className="text-2xl font-extrabold" data-testid="fixed-asset-depreciations-title">إهلاك سنة {runPeriod.year}</h2><Button type="button" onClick={() => window.print()} variant="outline" className="h-10 bg-white print:hidden" data-testid="print-fixed-asset-depreciation-period-button">طباعة تقرير الإهلاك</Button></div><div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="fixed-asset-depreciations-table-wrapper"><Table data-testid="fixed-asset-depreciations-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">الأصل</TableHead><TableHead className="text-right text-white">التصنيف</TableHead><TableHead className="text-right text-white">السنة</TableHead><TableHead className="text-right text-white">قيمة الإهلاك السنوي</TableHead><TableHead className="text-right text-white">مجمع بعد الإهلاك</TableHead><TableHead className="text-right text-white">الصافي بعد الإهلاك</TableHead></TableRow></TableHeader><TableBody>{depreciations.length === 0 && <TableRow data-testid="fixed-asset-depreciations-empty-row"><TableCell colSpan={6} className="py-8 text-center font-bold text-slate-500">لا توجد إهلاكات سنوية مثبتة لهذه السنة</TableCell></TableRow>}{depreciations.map((item) => <TableRow key={item.id} data-testid={`fixed-asset-depreciation-row-${item.id}`}><TableCell className="font-extrabold" data-testid={`fixed-asset-depreciation-${item.id}-asset`}>{item.asset_code} - {item.asset_name}</TableCell><TableCell data-testid={`fixed-asset-depreciation-${item.id}-category`}>{item.category_code} - {item.category_name}</TableCell><TableCell data-testid={`fixed-asset-depreciation-${item.id}-period`}>{item.year}</TableCell><TableCell data-testid={`fixed-asset-depreciation-${item.id}-amount`}>{formatCurrency(item.amount)}</TableCell><TableCell data-testid={`fixed-asset-depreciation-${item.id}-accumulated-after`}>{formatCurrency(item.accumulated_after)}</TableCell><TableCell className="font-extrabold" data-testid={`fixed-asset-depreciation-${item.id}-net-after`}>{formatCurrency(item.net_book_value_after)}</TableCell></TableRow>)}</TableBody></Table></div></section>
        </section>
      </section>
      <footer className="px-4 pb-5 print:hidden" data-testid="fixed-assets-footer"><CreditLine testId="fixed-assets-creator-credit" /></footer>
    </main>
  );
}