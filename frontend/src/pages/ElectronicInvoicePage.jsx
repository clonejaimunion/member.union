import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, ExternalLink, FileCheck2, Home, LogOut, Plus, RotateCcw, Save, Send, Wand2 } from "lucide-react";
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
import { formatCurrency, sanitizeDecimalInput } from "@/lib/format";

const today = () => new Date().toISOString().slice(0, 10);
const startOfYear = () => `${new Date().getFullYear()}-01-01`;
const statusLabels = { draft: "مسودة", ready: "جاهزة", needs_review: "تحتاج مراجعة", submitted: "مرسلة", accepted: "مقبولة", rejected: "مرفوضة" };
const customerTypes = { person: "فرد", company: "شركة", government: "جهة حكومية", union: "نقابة/هيئة" };

const defaultSettings = {
  organization_name: "النقابة العامة للعاملين بالزراعة والري",
  tax_registration_number: "",
  address: "",
  governorate: "",
  activity_code: "",
  default_tax_rate: "0",
  auto_generate_from_collected_revenues: true,
};

const defaultCustomer = { name: "", tax_number: "", customer_type: "person", address: "", governorate: "", phone: "", email: "" };
const defaultService = { code: "", name: "", tax_rate: "0", is_default: false };

export default function ElectronicInvoicePage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [settings, setSettings] = useState(defaultSettings);
  const [customers, setCustomers] = useState([]);
  const [services, setServices] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [customerForm, setCustomerForm] = useState(defaultCustomer);
  const [serviceForm, setServiceForm] = useState(defaultService);
  const [filters, setFilters] = useState({ status: "all", from_date: startOfYear(), to_date: today() });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const canManage = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.manage_revenues;

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.status !== "all") params.set("status", filters.status);
      if (filters.from_date) params.set("from_date", filters.from_date);
      if (filters.to_date) params.set("to_date", filters.to_date);
      const [settingsResponse, customersResponse, servicesResponse, invoicesResponse] = await Promise.all([
        api.get("/electronic-invoice/settings"),
        api.get("/electronic-invoice/customers"),
        api.get("/electronic-invoice/service-codes"),
        api.get(`/electronic-invoices?${params.toString()}`),
      ]);
      setSettings({ ...defaultSettings, ...settingsResponse.data, default_tax_rate: String(settingsResponse.data.default_tax_rate ?? 0) });
      setCustomers(customersResponse.data);
      setServices(servicesResponse.data);
      setInvoices(invoicesResponse.data);
    } catch (error) {
      toast.error("تعذر تحميل الفاتورة الإلكترونية");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { loadData(); }, [loadData]);

  const totals = useMemo(() => invoices.reduce((acc, item) => ({ net: acc.net + Number(item.net_amount || 0), tax: acc.tax + Number(item.tax_amount || 0), total: acc.total + Number(item.total_amount || 0) }), { net: 0, tax: 0, total: 0 }), [invoices]);

  const saveSettings = async () => {
    setSaving(true);
    try {
      await api.put("/electronic-invoice/settings", { ...settings, default_tax_rate: Number(settings.default_tax_rate || 0) });
      toast.success("تم حفظ إعدادات الفاتورة الإلكترونية");
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ الإعدادات");
    } finally {
      setSaving(false);
    }
  };

  const addCustomer = async () => {
    if (!customerForm.name.trim()) return toast.error("أدخل اسم العميل/الجهة");
    try {
      await api.post("/electronic-invoice/customers", customerForm);
      setCustomerForm(defaultCustomer);
      toast.success("تم إضافة العميل/الجهة");
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إضافة العميل");
    }
  };

  const addService = async () => {
    if (!serviceForm.code.trim() || !serviceForm.name.trim()) return toast.error("أدخل كود واسم الخدمة");
    try {
      await api.post("/electronic-invoice/service-codes", { ...serviceForm, tax_rate: Number(serviceForm.tax_rate || 0) });
      setServiceForm(defaultService);
      toast.success("تم إضافة كود الخدمة");
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إضافة كود الخدمة");
    }
  };

  const generateFromRevenues = async () => {
    setSaving(true);
    try {
      const response = await api.post("/electronic-invoices/generate-from-revenues");
      toast.success(`تم إنشاء ${response.data.length} فاتورة من الإيرادات المحصلة`);
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر توليد الفواتير");
    } finally {
      setSaving(false);
    }
  };

  const exportJson = () => {
    const content = JSON.stringify({ issuer: settings, invoices }, null, 2);
    const blob = new Blob([content], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "electronic-invoices.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const submitToEta = async (invoiceId) => {
    if (user?.role !== "super_admin") return toast.error("إرسال الفاتورة لمصلحة الضرائب متاح للسوبر أدمن فقط");
    setSaving(true);
    try {
      const response = await api.post(`/electronic-invoices/${invoiceId}/submit-eta`);
      if (response.data.status === "submitted") toast.success(response.data.message);
      else toast.error(response.data.message);
      loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إرسال الفاتورة لمنظومة الضرائب");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="electronic-invoice-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="electronic-invoice-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="electronic-invoice-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="electronic-invoice-brand-icon"><FileCheck2 className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700" data-testid="electronic-invoice-eyebrow">الفاتورة الإلكترونية</p><h1 className="text-2xl font-extrabold" data-testid="electronic-invoice-title">الفاتورة الإلكترونية</h1></div></div>
          <div className="flex flex-wrap items-center gap-3" data-testid="electronic-invoice-header-actions"><Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="electronic-invoice-user-badge">{user?.username}</Badge><Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="electronic-invoice-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="electronic-invoice-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="electronic-invoice-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>
      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="electronic-invoice-content">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden sm:p-8" data-testid="einvoice-settings-section">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><h2 className="text-3xl font-extrabold" data-testid="einvoice-settings-title">إعدادات الجهة الضريبية</h2>{canManage && <Button onClick={saveSettings} disabled={saving} className="h-11 rounded-lg bg-slate-950 text-white" data-testid="save-einvoice-settings-button"><Save className="h-4 w-4" /> حفظ الإعدادات</Button>}</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="einvoice-settings-grid">
            <div><Label>اسم الجهة</Label><Input value={settings.organization_name || ""} onChange={(e) => setSettings((c) => ({ ...c, organization_name: e.target.value }))} className="mt-2 h-12 bg-slate-50 text-right" data-testid="einvoice-organization-name-input" /></div>
            <div><Label>الرقم الضريبي</Label><Input value={settings.tax_registration_number || ""} onChange={(e) => setSettings((c) => ({ ...c, tax_registration_number: e.target.value }))} className="mt-2 h-12 bg-slate-50 text-right" data-testid="einvoice-tax-number-input" /></div>
            <div><Label>كود النشاط</Label><Input value={settings.activity_code || ""} onChange={(e) => setSettings((c) => ({ ...c, activity_code: e.target.value }))} className="mt-2 h-12 bg-slate-50 text-right" data-testid="einvoice-activity-code-input" /></div>
            <div><Label>العنوان</Label><Input value={settings.address || ""} onChange={(e) => setSettings((c) => ({ ...c, address: e.target.value }))} className="mt-2 h-12 bg-slate-50 text-right" data-testid="einvoice-address-input" /></div>
            <div><Label>المحافظة</Label><Input value={settings.governorate || ""} onChange={(e) => setSettings((c) => ({ ...c, governorate: e.target.value }))} className="mt-2 h-12 bg-slate-50 text-right" data-testid="einvoice-governorate-input" /></div>
            <div><Label>نسبة الضريبة الافتراضية %</Label><Input value={settings.default_tax_rate || ""} onChange={(e) => setSettings((c) => ({ ...c, default_tax_rate: sanitizeDecimalInput(e.target.value) }))} className="mt-2 h-12 bg-slate-50 text-right" data-testid="einvoice-default-tax-rate-input" /></div>
          </div>
        </section>

        {canManage && <section className="grid grid-cols-1 gap-6 xl:grid-cols-2 print:hidden" data-testid="einvoice-master-data-section">
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="einvoice-customers-section"><h2 className="mb-4 text-2xl font-extrabold" data-testid="einvoice-customers-title">العملاء والجهات</h2><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><Input placeholder="اسم العميل/الجهة" value={customerForm.name} onChange={(e) => setCustomerForm((c) => ({ ...c, name: e.target.value }))} data-testid="einvoice-customer-name-input" /><Input placeholder="الرقم الضريبي" value={customerForm.tax_number} onChange={(e) => setCustomerForm((c) => ({ ...c, tax_number: e.target.value }))} data-testid="einvoice-customer-tax-input" /><select value={customerForm.customer_type} onChange={(e) => setCustomerForm((c) => ({ ...c, customer_type: e.target.value }))} className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm" data-testid="einvoice-customer-type-select">{Object.entries(customerTypes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><Button onClick={addCustomer} data-testid="add-einvoice-customer-button"><Plus className="h-4 w-4" /> إضافة</Button></div><p className="mt-3 text-sm font-bold text-slate-500" data-testid="einvoice-customers-count">عدد العملاء: {customers.length}</p></section>
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="einvoice-services-section"><h2 className="mb-4 text-2xl font-extrabold" data-testid="einvoice-services-title">أكواد الخدمات</h2><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><Input placeholder="كود الخدمة" value={serviceForm.code} onChange={(e) => setServiceForm((c) => ({ ...c, code: e.target.value }))} data-testid="einvoice-service-code-input" /><Input placeholder="اسم الخدمة" value={serviceForm.name} onChange={(e) => setServiceForm((c) => ({ ...c, name: e.target.value }))} data-testid="einvoice-service-name-input" /><Input placeholder="نسبة الضريبة" value={serviceForm.tax_rate} onChange={(e) => setServiceForm((c) => ({ ...c, tax_rate: sanitizeDecimalInput(e.target.value) }))} data-testid="einvoice-service-tax-input" /><Button onClick={addService} data-testid="add-einvoice-service-button"><Plus className="h-4 w-4" /> إضافة</Button></div><p className="mt-3 text-sm font-bold text-slate-500" data-testid="einvoice-services-count">عدد الأكواد: {services.length}</p></section>
        </section>}

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden sm:p-8" data-testid="einvoice-tools-section"><div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto]"><div className="grid grid-cols-1 gap-3 md:grid-cols-3"><select value={filters.status} onChange={(e) => setFilters((c) => ({ ...c, status: e.target.value }))} className="h-12 rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="einvoice-status-filter"><option value="all">كل الحالات</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><Input type="date" value={filters.from_date} onChange={(e) => setFilters((c) => ({ ...c, from_date: e.target.value }))} data-testid="einvoice-from-date-input" /><Input type="date" value={filters.to_date} onChange={(e) => setFilters((c) => ({ ...c, to_date: e.target.value }))} data-testid="einvoice-to-date-input" /></div><div className="flex flex-wrap gap-2"><Button onClick={loadData} variant="outline" data-testid="refresh-einvoices-button"><RotateCcw className="h-4 w-4" /> تحديث</Button>{canManage && <Button onClick={generateFromRevenues} disabled={saving} className="bg-slate-950 text-white" data-testid="generate-einvoices-button"><Wand2 className="h-4 w-4" /> توليد من الإيرادات</Button>}<Button onClick={exportJson} variant="outline" data-testid="export-einvoices-json-button">JSON</Button><ExportReportButtons title="الفاتورة الإلكترونية" fileName="الفاتورة-الإلكترونية" selectors={["[data-testid='einvoices-report-section']"]} disabled={loading} pdfLabel="طباعة PDF" pdfTestId="print-einvoices-button" excelTestId="export-einvoices-excel-button" wordTestId="export-einvoices-word-button" /></div></div></section>

        <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:border-0 print:shadow-none sm:p-8" data-testid="einvoices-report-section"><div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><div><p className="text-sm font-extrabold text-emerald-700">الفواتير المولدة من الإيرادات المحصلة</p><h2 className="text-3xl font-extrabold" data-testid="einvoices-report-title">الفاتورة الإلكترونية</h2></div><div className="grid grid-cols-1 gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-950 p-4 text-white"><p className="text-xs font-bold text-slate-300">الصافي</p><p className="text-xl font-extrabold" data-testid="einvoices-net-total">{formatCurrency(totals.net)}</p></div><div className="rounded-xl bg-amber-50 p-4 text-amber-900"><p className="text-xs font-bold text-amber-700">الضريبة</p><p className="text-xl font-extrabold" data-testid="einvoices-tax-total">{formatCurrency(totals.tax)}</p></div><div className="rounded-xl bg-emerald-50 p-4 text-emerald-900"><p className="text-xs font-bold text-emerald-700">الإجمالي</p><p className="text-xl font-extrabold" data-testid="einvoices-total">{formatCurrency(totals.total)}</p></div></div></div><div className="overflow-hidden rounded-xl border border-slate-200"><Table data-testid="einvoices-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">رقم الفاتورة</TableHead><TableHead className="text-right text-white">التاريخ</TableHead><TableHead className="text-right text-white">العميل/الجهة</TableHead><TableHead className="text-right text-white">كود الخدمة</TableHead><TableHead className="text-right text-white">البيان</TableHead><TableHead className="text-right text-white">الصافي</TableHead><TableHead className="text-right text-white">الضريبة</TableHead><TableHead className="text-right text-white">الإجمالي</TableHead><TableHead className="text-right text-white">الحالة</TableHead><TableHead className="text-right text-white print:hidden">الربط الضريبي</TableHead></TableRow></TableHeader><TableBody>{invoices.length === 0 && <TableRow data-testid="einvoices-empty-row"><TableCell colSpan={10} className="py-8 text-center font-extrabold text-slate-500">لا توجد فواتير إلكترونية في الفترة المختارة</TableCell></TableRow>}{invoices.map((item) => <TableRow key={item.id} data-testid={`einvoice-row-${item.id}`}><TableCell className="font-extrabold">{item.invoice_number}</TableCell><TableCell>{item.issue_date}</TableCell><TableCell>{item.customer_name}</TableCell><TableCell>{item.service_code}</TableCell><TableCell className="max-w-xs break-words">{item.description}</TableCell><TableCell>{formatCurrency(item.net_amount)}</TableCell><TableCell>{formatCurrency(item.tax_amount)}</TableCell><TableCell className="font-extrabold">{formatCurrency(item.total_amount)}</TableCell><TableCell><Badge className="bg-slate-50 text-slate-700 hover:bg-slate-50">{statusLabels[item.status] || item.status}</Badge>{item.validation_notes?.length > 0 && <p className="mt-1 text-xs font-bold text-amber-700">{item.validation_notes.join("، ")}</p>}</TableCell><TableCell className="space-y-2 print:hidden" data-testid={`einvoice-row-${item.id}-eta-actions`}>{item.eta_document_uuid ? <a href={item.eta_portal_url || '#'} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-extrabold text-emerald-800" data-testid={`einvoice-row-${item.id}-eta-link`}><ExternalLink className="h-3 w-3" /> عرض بالمصلحة</a> : user?.role === "super_admin" ? <Button type="button" onClick={() => submitToEta(item.id)} disabled={saving} variant="outline" className="h-9 rounded-lg bg-white text-xs" data-testid={`einvoice-row-${item.id}-submit-eta-button`}><Send className="h-3 w-3" /> إرسال API</Button> : <span className="text-xs font-bold text-slate-400" data-testid={`einvoice-row-${item.id}-eta-readonly`}>غير مرسلة</span>}{item.eta_submission_id && <p className="text-[11px] font-bold text-slate-500" data-testid={`einvoice-row-${item.id}-eta-submission-id`}>{item.eta_submission_id}</p>}</TableCell></TableRow>)}</TableBody></Table></div></section>
      </section>
      <footer className="px-4 pb-5 print:hidden" data-testid="electronic-invoice-footer"><CreditLine testId="electronic-invoice-creator-credit" /></footer>
    </main>
  );
}