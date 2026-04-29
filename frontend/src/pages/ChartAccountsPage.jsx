import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, GitFork, Home, LogOut, Plus, RefreshCw, Save } from "lucide-react";
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

const accountTypes = { asset: "أصول", liability: "التزامات", equity: "حقوق الملكية", revenue: "إيرادات", expense: "مصروفات" };
const natureLabels = { debit: "مدين", credit: "دائن" };

export default function ChartAccountsPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", account_type: "asset", nature: "debit", parent_id: "", is_postable: true, opening_balance: "" });
  const [typeFilter, setTypeFilter] = useState("all");
  const canManage = user?.role === "admin";

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const response = await api.get("/chart-accounts");
      setAccounts(response.data);
    } catch (error) {
      toast.error("تعذر تحميل شجرة الحسابات");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAccounts(); }, []);

  const filteredAccounts = useMemo(() => accounts.filter((account) => typeFilter === "all" || account.account_type === typeFilter), [accounts, typeFilter]);
  const parentOptions = useMemo(() => accounts.filter((account) => !account.is_postable), [accounts]);

  const syncAccounts = async () => {
    setSaving(true);
    try {
      const response = await api.post("/chart-accounts/sync");
      setAccounts(response.data);
      toast.success("تم تحديث شجرة الحسابات تلقائياً");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تحديث الشجرة");
    } finally {
      setSaving(false);
    }
  };

  const createAccount = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await api.post("/chart-accounts", { ...form, parent_id: form.parent_id || null, opening_balance: Number(form.opening_balance || 0) });
      toast.success("تم إضافة الحساب");
      setForm({ code: "", name: "", account_type: "asset", nature: "debit", parent_id: "", is_postable: true, opening_balance: "" });
      loadAccounts();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إضافة الحساب");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="chart-accounts-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="chart-accounts-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="chart-accounts-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white"><GitFork className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700">النظام المحاسبي</p><h1 className="text-2xl font-extrabold" data-testid="chart-accounts-title">شجرة الحسابات</h1></div></div>
          <div className="flex flex-wrap items-center gap-3" data-testid="chart-accounts-actions"><Badge className="bg-white text-slate-700" data-testid="chart-accounts-user-badge">{user?.organization_name}</Badge><Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="chart-accounts-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="chart-accounts-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="chart-accounts-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 sm:px-6 xl:grid-cols-[0.75fr_1.25fr] lg:px-8" data-testid="chart-accounts-content">
        {canManage && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="chart-account-create-section">
          <div className="mb-5 flex items-center justify-between gap-3"><h2 className="text-2xl font-extrabold" data-testid="chart-account-create-title">إضافة حساب</h2><Button type="button" onClick={syncAccounts} disabled={saving} variant="outline" className="h-10 bg-white" data-testid="sync-chart-accounts-button"><RefreshCw className="h-4 w-4" /> تحديث تلقائي</Button></div>
          <p className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm font-bold text-emerald-800" data-testid="chart-account-auto-note">النظام ينشئ الحسابات الأساسية والبنوك تلقائياً لكل جهة، ويمكن إضافة حسابات فرعية عند الحاجة.</p>
          <form onSubmit={createAccount} className="space-y-4" data-testid="chart-account-create-form">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2"><div><Label>كود الحساب</Label><Input value={form.code} onChange={(e) => setForm((c) => ({ ...c, code: e.target.value }))} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="chart-account-code-input" /></div><div><Label>اسم الحساب</Label><Input value={form.name} onChange={(e) => setForm((c) => ({ ...c, name: e.target.value }))} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="chart-account-name-input" /></div></div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2"><div><Label>نوع الحساب</Label><select value={form.account_type} onChange={(e) => setForm((c) => ({ ...c, account_type: e.target.value, nature: ["asset", "expense"].includes(e.target.value) ? "debit" : "credit" }))} className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="chart-account-type-select">{Object.entries(accountTypes).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div><div><Label>طبيعة الحساب</Label><select value={form.nature} onChange={(e) => setForm((c) => ({ ...c, nature: e.target.value }))} className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="chart-account-nature-select"><option value="debit">مدين</option><option value="credit">دائن</option></select></div></div>
            <div><Label>الحساب الرئيسي</Label><select value={form.parent_id} onChange={(e) => setForm((c) => ({ ...c, parent_id: e.target.value }))} className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="chart-account-parent-select"><option value="">بدون حساب رئيسي</option>{parentOptions.map((account) => <option key={account.id} value={account.id}>{account.code} - {account.name}</option>)}</select></div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2"><div><Label>الرصيد الافتتاحي</Label><Input inputMode="decimal" value={form.opening_balance} onChange={(e) => setForm((c) => ({ ...c, opening_balance: sanitizeDecimalInput(e.target.value) }))} className="mt-2 h-11 bg-slate-50 text-right" data-testid="chart-account-opening-balance-input" /></div><label className="mt-7 flex h-11 items-center gap-2 rounded-md bg-slate-50 px-3 font-bold"><input type="checkbox" checked={form.is_postable} onChange={(e) => setForm((c) => ({ ...c, is_postable: e.target.checked }))} data-testid="chart-account-postable-checkbox" /> يسمح بالترحيل عليه</label></div>
            <Button type="submit" disabled={saving} className="h-11 w-full bg-slate-950 text-white" data-testid="chart-account-save-button"><Save className="h-4 w-4" /> حفظ الحساب</Button>
          </form>
        </section>}

        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="chart-accounts-list-section">
          <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between"><div><h2 className="text-2xl font-extrabold" data-testid="chart-accounts-list-title">دليل الحسابات</h2><p className="text-sm font-bold text-slate-500">الحسابات النظامية تتحدث تلقائياً عند إضافة بنك جديد.</p></div><select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="h-11 rounded-md border border-slate-300 bg-white px-3 font-bold" data-testid="chart-account-type-filter"><option value="all">كل الأنواع</option>{Object.entries(accountTypes).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>
          <div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="chart-accounts-table-wrapper"><Table data-testid="chart-accounts-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">الكود</TableHead><TableHead className="text-right text-white">اسم الحساب</TableHead><TableHead className="text-right text-white">النوع</TableHead><TableHead className="text-right text-white">الطبيعة</TableHead><TableHead className="text-right text-white">رئيسي/فرعي</TableHead><TableHead className="text-right text-white">الرصيد الافتتاحي</TableHead></TableRow></TableHeader><TableBody>{loading && <TableRow><TableCell colSpan={6} className="py-8 text-center font-bold">جاري التحميل...</TableCell></TableRow>}{!loading && filteredAccounts.map((account) => <TableRow key={account.id} className={!account.is_postable ? "bg-slate-50" : "bg-white"} data-testid={`chart-account-row-${account.id}`}><TableCell className="font-extrabold" data-testid={`chart-account-${account.id}-code`}>{account.code}</TableCell><TableCell data-testid={`chart-account-${account.id}-name`}><span className="font-extrabold">{account.name}</span>{account.system_key && <Badge className="mr-2 bg-emerald-50 text-emerald-700 hover:bg-emerald-50">تلقائي</Badge>}<p className="text-xs font-bold text-slate-500">{account.parent_name || "حساب رئيسي"}</p></TableCell><TableCell>{accountTypes[account.account_type]}</TableCell><TableCell>{natureLabels[account.nature]}</TableCell><TableCell>{account.is_postable ? "فرعي قابل للترحيل" : "رئيسي"}</TableCell><TableCell>{formatCurrency(account.opening_balance || 0)}</TableCell></TableRow>)}</TableBody></Table></div>
        </section>
      </section>
      <footer className="px-4 pb-5 print:hidden"><CreditLine testId="chart-accounts-creator-credit" /></footer>
    </main>
  );
}