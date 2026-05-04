import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Beaker, GitCompareArrows, Home, LogOut, PlayCircle, Save } from "lucide-react";
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

const defaultRule = { event_type: "Expense", sub_type: "General", payment_method: "bank", debit_account: "المصروفات", credit_account: "البنك", priority: 5, is_active: true, notes: "" };
const defaultSimulation = { event_type: "Expense", sub_type: "General", payment_method: "bank", amount: "100", bank_id: "industrial-development" };
const eventLabels = { Income: "إيراد", Expense: "مصروف", BankFee: "مصروف بنكي", Deposit: "وديعة", Interest: "فائدة", AssetPurchase: "شراء أصل", Loan: "سلفة", Custody: "عهدة" };

export default function RulesEnginePage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [rules, setRules] = useState([]);
  const [ruleForm, setRuleForm] = useState(defaultRule);
  const [simulation, setSimulation] = useState(defaultSimulation);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadRules = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get("/rules-engine/rules");
      setRules(response.data);
    } catch (error) {
      toast.error("تعذر تحميل قواعد محرك القيود");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRules(); }, [loadRules]);

  const saveRule = async (event) => {
    event.preventDefault();
    try {
      await api.post("/rules-engine/rules", { ...ruleForm, priority: Number(ruleForm.priority || 5) });
      toast.success("تم حفظ قاعدة جديدة");
      setRuleForm(defaultRule);
      await loadRules();
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

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="rules-engine-page">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur-xl print:hidden" data-testid="rules-engine-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="rules-engine-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="rules-engine-brand-icon"><GitCompareArrows className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700" data-testid="rules-engine-eyebrow">Rule Engine UI</p><h1 className="text-2xl font-extrabold" data-testid="rules-engine-title">محرك قواعد القيود التلقائي</h1></div></div>
          <div className="flex flex-wrap items-center gap-3" data-testid="rules-engine-header-actions"><Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm" data-testid="rules-engine-user-badge">{user?.username}</Badge><Button asChild variant="outline" className="h-11 bg-white" data-testid="rules-engine-home-button"><Link to="/"><Home className="h-4 w-4" /> الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="rules-engine-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 bg-white" data-testid="rules-engine-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>
      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 lg:grid-cols-[1fr_420px] sm:px-6 lg:px-8" data-testid="rules-engine-content">
        <section className="space-y-5" data-testid="rules-engine-main-column">
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="rules-engine-rules-section">
            <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between" data-testid="rules-engine-rules-heading"><h2 className="text-2xl font-extrabold" data-testid="rules-engine-rules-title">القواعد الحالية</h2><Badge className="w-fit bg-emerald-50 text-emerald-800" data-testid="rules-engine-rules-count">{rules.length} قاعدة</Badge></div>
            <div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="rules-engine-rules-table-wrapper"><Table data-testid="rules-engine-rules-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">الحدث</TableHead><TableHead className="text-right text-white">النوع</TableHead><TableHead className="text-right text-white">مدين</TableHead><TableHead className="text-right text-white">دائن</TableHead><TableHead className="text-right text-white">الأولوية</TableHead><TableHead className="text-right text-white">المصدر</TableHead></TableRow></TableHeader><TableBody>{loading && <TableRow data-testid="rules-engine-loading-row"><TableCell colSpan={6} className="py-6 text-center font-bold">جاري التحميل...</TableCell></TableRow>}{rules.map((rule) => <TableRow key={rule.id} data-testid={`rules-engine-rule-row-${rule.id}`}><TableCell className="font-extrabold" data-testid={`rules-engine-rule-${rule.id}-event`}>{eventLabels[rule.event_type] || rule.event_type}</TableCell><TableCell data-testid={`rules-engine-rule-${rule.id}-sub-type`}>{rule.sub_type || "—"}</TableCell><TableCell data-testid={`rules-engine-rule-${rule.id}-debit`}>{rule.debit_account}</TableCell><TableCell data-testid={`rules-engine-rule-${rule.id}-credit`}>{rule.credit_account}</TableCell><TableCell data-testid={`rules-engine-rule-${rule.id}-priority`}>{rule.priority}</TableCell><TableCell data-testid={`rules-engine-rule-${rule.id}-source`}>{rule.is_system ? "نظام" : "مخصص"}</TableCell></TableRow>)}</TableBody></Table></div>
          </section>
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="rules-engine-preview-section"><div className="mb-4 flex items-center gap-3" data-testid="rules-engine-preview-heading"><Beaker className="h-6 w-6 text-emerald-700" /><h2 className="text-2xl font-extrabold" data-testid="rules-engine-preview-title">Simulation Mode — بدون ترحيل</h2></div><div className="grid grid-cols-1 gap-3 md:grid-cols-5" data-testid="rules-engine-simulation-grid"><select value={simulation.event_type} onChange={(event) => setSimulation((current) => ({ ...current, event_type: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="rules-engine-simulation-event-select">{Object.entries(eventLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><Input value={simulation.sub_type} onChange={(event) => setSimulation((current) => ({ ...current, sub_type: event.target.value }))} className="h-11 bg-slate-50 text-right" placeholder="SubType" data-testid="rules-engine-simulation-subtype-input" /><Input value={simulation.payment_method} onChange={(event) => setSimulation((current) => ({ ...current, payment_method: event.target.value }))} className="h-11 bg-slate-50 text-right" placeholder="طريقة الدفع" data-testid="rules-engine-simulation-method-input" /><Input value={simulation.amount} onChange={(event) => setSimulation((current) => ({ ...current, amount: event.target.value }))} className="h-11 bg-slate-50 text-right" placeholder="المبلغ" data-testid="rules-engine-simulation-amount-input" /><Button type="button" onClick={runSimulation} className="h-11 bg-slate-950 text-white" data-testid="rules-engine-run-simulation-button"><PlayCircle className="h-4 w-4" /> تشغيل</Button></div>{preview && <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4" data-testid="rules-engine-simulation-result"><p className={`font-extrabold ${preview.is_valid ? "text-emerald-700" : "text-red-700"}`} data-testid="rules-engine-simulation-status">{preview.is_valid ? "القيد صالح للترحيل — لكن هذه محاكاة فقط" : "Fail-Safe: يوجد خطأ يمنع الترحيل"}</p>{preview.errors?.map((error, index) => <p key={index} className="mt-2 text-sm font-bold text-red-700" data-testid={`rules-engine-simulation-error-${index}`}>{error}</p>)}<div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="rules-engine-preview-lines">{preview.preview_lines?.map((line, index) => <div key={index} className="rounded-lg bg-white p-3 text-sm font-bold" data-testid={`rules-engine-preview-line-${index}`}><p data-testid={`rules-engine-preview-line-${index}-account`}>{line.account_code} - {line.account_name}</p><p data-testid={`rules-engine-preview-line-${index}-amount`}>مدين: {formatCurrency(line.debit)} / دائن: {formatCurrency(line.credit)}</p></div>)}</div>{preview.conflicts?.length > 0 && <p className="mt-3 rounded-lg bg-amber-50 p-3 font-extrabold text-amber-800" data-testid="rules-engine-conflict-warning">Conflict detection: توجد قواعد متعارضة بنفس الأولوية.</p>}</div>}</section>
        </section>
        <aside className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="rules-engine-editor-section"><h2 className="mb-4 text-2xl font-extrabold" data-testid="rules-engine-editor-title">إضافة قاعدة مخصصة</h2><form onSubmit={saveRule} className="space-y-3" data-testid="rules-engine-editor-form"><div data-testid="rules-engine-editor-event-wrapper"><Label>نوع الحدث</Label><select value={ruleForm.event_type} onChange={(event) => setRuleForm((current) => ({ ...current, event_type: event.target.value }))} className="mt-2 h-11 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="rules-engine-editor-event-select">{Object.entries(eventLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>{[["sub_type", "النوع الفرعي"], ["payment_method", "طريقة الدفع"], ["debit_account", "الحساب المدين"], ["credit_account", "الحساب الدائن"], ["priority", "الأولوية"], ["notes", "ملاحظات"]].map(([field, label]) => <div key={field} data-testid={`rules-engine-editor-${field}-wrapper`}><Label>{label}</Label><Input value={ruleForm[field]} onChange={(event) => setRuleForm((current) => ({ ...current, [field]: event.target.value }))} className="mt-2 h-11 bg-slate-50 text-right" data-testid={`rules-engine-editor-${field}-input`} /></div>)}<Button type="submit" className="h-11 w-full bg-slate-950 text-white" data-testid="rules-engine-save-rule-button"><Save className="h-4 w-4" /> حفظ القاعدة</Button></form></aside>
      </section>
      <footer className="px-4 pb-5 print:hidden" data-testid="rules-engine-footer"><CreditLine testId="rules-engine-creator-credit" /></footer>
    </main>
  );
}