import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Beaker, Edit3, GitCompareArrows, Home, LogOut, PlayCircle, Plus, Save, X } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

const eventOptions = [
  ["Income", "إيراد"], ["Expense", "مصروف"], ["BankFee", "مصروف بنكي"], ["Deposit", "وديعة"],
  ["Interest", "فائدة"], ["AssetPurchase", "شراء أصل"], ["Loan", "سلفة"], ["Custody", "عهدة"],
];
const eventLabels = Object.fromEntries(eventOptions);
const subTypeOptions = [
  ["General", "عام"], ["administrative", "إدارية"], ["banking", "بنكية"], ["operating", "تشغيل"],
  ["hajj_umrah", "جمعية الحج والعمرة"], ["meat_installment", "قسط لحوم"], ["union_committee", "لجنة نقابية"],
  ["death_benefits", "إعانات وفاة"], ["Principal", "أصل الوديعة"], ["Accrued", "فائدة مستحقة"],
  ["Received", "فائدة محصلة"], ["Employee Loan", "سلفة موظف"], ["Employee Custody", "عهدة موظف"],
];
const subTypeLabels = Object.fromEntries(subTypeOptions);
const paymentOptions = [
  ["cheque", "شيك"], ["cash_receipt", "نقدي برقم إيصال استلام نقدية"],
  ["bank_transfer", "تحويل بنكي"], ["electronic_payment_order", "أمر دفع إلكتروني"],
];
const paymentLabels = Object.fromEntries(paymentOptions);
const defaultRule = { event_type: "Expense", sub_type: "General", payment_method: "bank_transfer", debit_account: "المصروفات", credit_account: "البنك", is_active: true, notes: "" };
const defaultSimulation = { event_type: "Expense", sub_type: "General", payment_method: "bank_transfer", amount: "100", bank_id: "industrial-development" };
const dynamicAccountOptions = [
  { id: "dynamic-bank", code: "AUTO", name: "البنك", nature: "auto", is_dynamic: true },
  { id: "dynamic-revenue", code: "AUTO", name: "الإيرادات", nature: "credit", is_dynamic: true },
  { id: "dynamic-expense", code: "AUTO", name: "المصروفات", nature: "debit", is_dynamic: true },
  { id: "dynamic-bank-expense", code: "AUTO", name: "المصروفات البنكية", nature: "debit", is_dynamic: true },
  { id: "dynamic-deposits", code: "AUTO", name: "ودائع لأجل", nature: "debit", is_dynamic: true },
  { id: "dynamic-accrued-interest", code: "AUTO", name: "عوائد ودائع مستحقة", nature: "debit", is_dynamic: true },
  { id: "dynamic-interest-revenue", code: "AUTO", name: "إيرادات فوائد ودائع", nature: "credit", is_dynamic: true },
  { id: "dynamic-loans", code: "AUTO", name: "سلف الموظفين", nature: "debit", is_dynamic: true },
  { id: "dynamic-custody", code: "AUTO", name: "عهد الموظفين", nature: "debit", is_dynamic: true },
];

export default function RulesEnginePage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [rules, setRules] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [editingRuleId, setEditingRuleId] = useState(null);
  const [ruleForm, setRuleForm] = useState(defaultRule);
  const [simulation, setSimulation] = useState(defaultSimulation);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);

  const accountOptions = useMemo(() => {
    const realAccounts = accounts.filter((account) => account.is_active && account.is_postable);
    const names = new Set(realAccounts.map((account) => account.name));
    return [...dynamicAccountOptions.filter((account) => !names.has(account.name)), ...realAccounts];
  }, [accounts]);
  const accountLabel = (account) => `${account.code} - ${account.name} (${account.is_dynamic ? "ديناميكي" : account.nature === "credit" ? "دائن" : "مدين"})`;

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [rulesResponse, accountsResponse] = await Promise.all([api.get("/rules-engine/rules"), api.get("/chart-accounts")]);
      setRules(rulesResponse.data);
      setAccounts(accountsResponse.data);
    } catch (error) {
      toast.error("تعذر تحميل قواعد محرك القيود");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const startEditRule = (rule) => {
    setEditingRuleId(rule.id);
    setRuleForm({ event_type: rule.event_type, sub_type: rule.sub_type || "General", payment_method: rule.payment_method || "bank_transfer", debit_account: rule.debit_account, credit_account: rule.credit_account, is_active: rule.is_active, notes: rule.notes || "" });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const resetEditor = () => {
    setEditingRuleId(null);
    setRuleForm(defaultRule);
  };

  const saveRule = async (event) => {
    event.preventDefault();
    try {
      if (editingRuleId) {
        await api.put(`/rules-engine/rules/${editingRuleId}`, ruleForm);
        toast.success("تم تعديل القاعدة — الأولوية حُسبت تلقائياً");
      } else {
        await api.post("/rules-engine/rules", ruleForm);
        toast.success("تم حفظ قاعدة جديدة — الأولوية حُسبت تلقائياً");
      }
      resetEditor();
      await loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ القاعدة");
    }
  };

  const runSimulation = async () => {
    try {
      const response = await api.post("/rules-engine/simulate", { ...simulation, amount: Number(simulation.amount || 0) });
      setPreview(response.data);
      if (response.data.is_valid) toast.success("Simulation Mode ناجح — لا يوجد ترحيل فعلي");
      else toast.error("Simulation Mode أظهر أخطاء تمنع الترحيل");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تشغيل المحاكاة");
    }
  };

  const renderRuleSelect = (field, options, testId) => (
    <select value={ruleForm[field]} onChange={(event) => setRuleForm((current) => ({ ...current, [field]: event.target.value }))} className="mt-2 h-11 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 font-bold" data-testid={testId}>{options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
  );
  const renderSimulationSelect = (field, options, testId) => (
    <select value={simulation[field]} onChange={(event) => setSimulation((current) => ({ ...current, [field]: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-slate-50 px-3 font-bold" data-testid={testId}>{options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
  );
  const renderAccountSelect = (field, testId) => {
    const options = accountOptions;
    return <select value={ruleForm[field]} onChange={(event) => setRuleForm((current) => ({ ...current, [field]: event.target.value }))} className="mt-2 h-11 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 font-bold" data-testid={testId}>{options.map((account) => <option key={account.id} value={account.name}>{accountLabel(account)}</option>)}</select>;
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="rules-engine-page">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur-xl print:hidden" data-testid="rules-engine-header"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8"><div className="flex items-center gap-3" data-testid="rules-engine-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="rules-engine-brand-icon"><GitCompareArrows className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700" data-testid="rules-engine-eyebrow">Rule Engine UI</p><h1 className="text-2xl font-extrabold" data-testid="rules-engine-title">محرك قواعد القيود التلقائي</h1></div></div><div className="flex flex-wrap items-center gap-3" data-testid="rules-engine-header-actions"><Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm" data-testid="rules-engine-user-badge">{user?.username}</Badge><Button asChild variant="outline" className="h-11 bg-white" data-testid="rules-engine-home-button"><Link to="/"><Home className="h-4 w-4" /> الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="rules-engine-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 bg-white" data-testid="rules-engine-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div></div></header>
      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 lg:grid-cols-[1fr_440px] sm:px-6 lg:px-8" data-testid="rules-engine-content">
        <section className="space-y-5" data-testid="rules-engine-main-column">
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="rules-engine-rules-section"><div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between" data-testid="rules-engine-rules-heading"><h2 className="text-2xl font-extrabold" data-testid="rules-engine-rules-title">القواعد الحالية</h2><Badge className="w-fit bg-emerald-50 text-emerald-800" data-testid="rules-engine-rules-count">{rules.length} قاعدة</Badge></div><div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="rules-engine-rules-table-wrapper"><Table data-testid="rules-engine-rules-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">الحدث</TableHead><TableHead className="text-right text-white">النوع الفرعي</TableHead><TableHead className="text-right text-white">طريقة الدفع</TableHead><TableHead className="text-right text-white">مدين</TableHead><TableHead className="text-right text-white">دائن</TableHead><TableHead className="text-right text-white">تحديد ذكي</TableHead><TableHead className="text-right text-white">إجراء</TableHead></TableRow></TableHeader><TableBody>{loading && <TableRow data-testid="rules-engine-loading-row"><TableCell colSpan={7} className="py-6 text-center font-bold">جاري التحميل...</TableCell></TableRow>}{rules.map((rule) => <TableRow key={rule.id} data-testid={`rules-engine-rule-row-${rule.id}`}><TableCell className="font-extrabold" data-testid={`rules-engine-rule-${rule.id}-event`}>{eventLabels[rule.event_type] || rule.event_type}</TableCell><TableCell data-testid={`rules-engine-rule-${rule.id}-sub-type`}>{subTypeLabels[rule.sub_type] || rule.sub_type || "—"}</TableCell><TableCell data-testid={`rules-engine-rule-${rule.id}-payment`}>{paymentLabels[rule.payment_method] || rule.payment_method || "—"}</TableCell><TableCell data-testid={`rules-engine-rule-${rule.id}-debit`}>{rule.debit_account}</TableCell><TableCell data-testid={`rules-engine-rule-${rule.id}-credit`}>{rule.credit_account}</TableCell><TableCell data-testid={`rules-engine-rule-${rule.id}-smart-score`}>Scoring تلقائي</TableCell><TableCell><Button type="button" onClick={() => startEditRule(rule)} variant="outline" className="h-9 bg-white" data-testid={`rules-engine-edit-rule-${rule.id}-button`}><Edit3 className="h-4 w-4" /> تعديل</Button></TableCell></TableRow>)}</TableBody></Table></div></section>
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="rules-engine-preview-section"><div className="mb-4 flex items-center gap-3" data-testid="rules-engine-preview-heading"><Beaker className="h-6 w-6 text-emerald-700" /><h2 className="text-2xl font-extrabold" data-testid="rules-engine-preview-title">Simulation Mode — بدون ترحيل</h2></div><div className="grid grid-cols-1 gap-3 md:grid-cols-5" data-testid="rules-engine-simulation-grid">{renderSimulationSelect("event_type", eventOptions, "rules-engine-simulation-event-select")}{renderSimulationSelect("sub_type", subTypeOptions, "rules-engine-simulation-subtype-select")}{renderSimulationSelect("payment_method", paymentOptions, "rules-engine-simulation-method-select")}<Input value={simulation.amount} onChange={(event) => setSimulation((current) => ({ ...current, amount: event.target.value }))} className="h-11 bg-slate-50 text-right" placeholder="المبلغ" data-testid="rules-engine-simulation-amount-input" /><Button type="button" onClick={runSimulation} className="h-11 bg-slate-950 text-white" data-testid="rules-engine-run-simulation-button"><PlayCircle className="h-4 w-4" /> تشغيل</Button></div>{preview && <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4" data-testid="rules-engine-simulation-result"><p className={`font-extrabold ${preview.is_valid ? "text-emerald-700" : "text-red-700"}`} data-testid="rules-engine-simulation-status">{preview.is_valid ? "القيد صالح للترحيل — لكن هذه محاكاة فقط" : "Fail-Safe: يوجد خطأ يمنع الترحيل"}</p>{preview.errors?.map((error, index) => <p key={index} className="mt-2 text-sm font-bold text-red-700" data-testid={`rules-engine-simulation-error-${index}`}>{error}</p>)}<div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="rules-engine-preview-lines">{preview.preview_lines?.map((line, index) => <div key={index} className="rounded-lg bg-white p-3 text-sm font-bold" data-testid={`rules-engine-preview-line-${index}`}><p data-testid={`rules-engine-preview-line-${index}-account`}>{line.account_code} - {line.account_name}</p><p data-testid={`rules-engine-preview-line-${index}-amount`}>مدين: {formatCurrency(line.debit)} / دائن: {formatCurrency(line.credit)}</p></div>)}</div>{preview.conflicts?.length > 0 && <p className="mt-3 rounded-lg bg-amber-50 p-3 font-extrabold text-amber-800" data-testid="rules-engine-conflict-warning">Conflict detection: توجد قواعد متعارضة بنفس التحديد الذكي.</p>}</div>}</section>
        </section>
        <aside className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="rules-engine-editor-section"><div className="mb-4 flex items-center justify-between gap-3" data-testid="rules-engine-editor-heading"><h2 className="text-2xl font-extrabold" data-testid="rules-engine-editor-title">{editingRuleId ? "تعديل قاعدة" : "إضافة قاعدة مخصصة"}</h2>{editingRuleId && <Button type="button" onClick={resetEditor} variant="outline" className="h-9 bg-white" data-testid="rules-engine-cancel-edit-button"><X className="h-4 w-4" /> إلغاء</Button>}</div><form onSubmit={saveRule} className="space-y-3" data-testid="rules-engine-editor-form"><div data-testid="rules-engine-editor-event-wrapper"><Label>نوع الحدث</Label>{renderRuleSelect("event_type", eventOptions, "rules-engine-editor-event-select")}</div><div data-testid="rules-engine-editor-subtype-wrapper"><Label>النوع الفرعي</Label>{renderRuleSelect("sub_type", subTypeOptions, "rules-engine-editor-subtype-select")}</div><div data-testid="rules-engine-editor-payment-wrapper"><Label>طريقة الدفع</Label>{renderRuleSelect("payment_method", paymentOptions, "rules-engine-editor-payment-select")}</div><div data-testid="rules-engine-editor-debit-wrapper"><div className="flex items-center justify-between"><Label>الحساب المدين</Label><Button asChild variant="link" className="h-6 px-0 text-emerald-700" data-testid="rules-engine-add-debit-account-link"><Link to="/admin"><Plus className="h-3 w-3" /> إضافة حساب</Link></Button></div>{renderAccountSelect("debit_account", "rules-engine-editor-debit-account-select")}</div><div data-testid="rules-engine-editor-credit-wrapper"><div className="flex items-center justify-between"><Label>الحساب الدائن</Label><Button asChild variant="link" className="h-6 px-0 text-emerald-700" data-testid="rules-engine-add-credit-account-link"><Link to="/admin"><Plus className="h-3 w-3" /> إضافة حساب</Link></Button></div>{renderAccountSelect("credit_account", "rules-engine-editor-credit-account-select")}</div><div className="rounded-lg bg-emerald-50 p-3 text-sm font-bold text-emerald-800" data-testid="rules-engine-priority-auto-note">الأولوية مخفية وتحسب تلقائياً بنظام Scoring + Specificity.</div><div data-testid="rules-engine-editor-notes-wrapper"><Label>ملاحظات</Label><Input value={ruleForm.notes} onChange={(event) => setRuleForm((current) => ({ ...current, notes: event.target.value }))} className="mt-2 h-11 bg-slate-50 text-right" data-testid="rules-engine-editor-notes-input" /></div><Button type="submit" className="h-11 w-full bg-slate-950 text-white" data-testid="rules-engine-save-rule-button"><Save className="h-4 w-4" /> {editingRuleId ? "حفظ التعديل" : "حفظ القاعدة"}</Button></form></aside>
      </section>
      <footer className="px-4 pb-5 print:hidden" data-testid="rules-engine-footer"><CreditLine testId="rules-engine-creator-credit" /></footer>
    </main>
  );
}