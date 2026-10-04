import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Calculator, FileText, Pencil, Save, Trash2, WalletCards } from "lucide-react";
import { toast } from "sonner";
import { BankShell } from "@/components/BankShell";
import { DepositSummary } from "@/components/DepositSummary";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { formatCurrency, formatRate, toDateInput } from "@/lib/format";
import { useAuth } from "@/contexts/AuthContext";

const defaultForm = () => {
  const now = new Date();
  const maturity = new Date(now);
  maturity.setFullYear(now.getFullYear() + 1);
  return {
    account_number: "",
    deposit_number: "",
    amount: "",
    creation_datetime: toDateInput(now),
    maturity_datetime: toDateInput(maturity),
    monthly_interest_rate: "",
    is_opening_balance_deposit: false,
    renewed_from_deposit_id: "",
    renewal_notes: "",
    deposit_nature: "monthly",
    auto_renew: false,
    contract_duration_years: 1,
  };
};

export default function DepositRegistration() {
  const { bankId } = useParams();
  const { user } = useAuth();
  const [form, setForm] = useState(defaultForm);
  const [deposits, setDeposits] = useState([]);
  const [selectedDeposit, setSelectedDeposit] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [editingDepositId, setEditingDepositId] = useState(null);

  const expectedAnnualInterest = useMemo(() => {
    const amount = Number(form.amount || 0);
    const rate = Number(form.monthly_interest_rate || 0);
    return amount * rate / 100;
  }, [form.amount, form.monthly_interest_rate]);

  const loadDeposits = useCallback(() => {
    api.get(`/banks/${bankId}/deposits`).then((response) => {
      setDeposits(response.data);
      const active = response.data.filter((deposit) => deposit.status !== "renewed");
      setSelectedDeposit(active[0] || response.data[0] || null);
    }).catch(() => {
      setDeposits([]);
      setSelectedDeposit(null);
    });
  }, [bankId]);

  const activeDeposits = useMemo(() => deposits.filter((deposit) => deposit.status !== "renewed"), [deposits]);

  useEffect(() => {
    loadDeposits();
  }, [loadDeposits]);

  const updateField = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  const startEditDeposit = (deposit) => {
    setEditingDepositId(deposit.id);
    setForm({
      account_number: deposit.account_number || "",
      deposit_number: deposit.deposit_number || "",
      amount: String(deposit.amount ?? ""),
      creation_datetime: String(deposit.creation_datetime).slice(0, 10),
      maturity_datetime: String(deposit.maturity_datetime).slice(0, 10),
      monthly_interest_rate: String(deposit.monthly_interest_rate ?? ""),
      is_opening_balance_deposit: !!deposit.is_opening_balance_deposit,
      renewed_from_deposit_id: deposit.renewed_from_deposit_id || "",
      renewal_notes: deposit.renewal_notes || "",
      deposit_nature: deposit.deposit_nature || "monthly",
      auto_renew: !!deposit.auto_renew,
      contract_duration_years: deposit.contract_duration_years || 1,
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const cancelEditDeposit = () => { setEditingDepositId(null); setForm(defaultForm()); };

  const submitDeposit = async (event) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      const payload = {
        ...form,
        amount: Number(form.amount),
        monthly_interest_rate: Number(form.monthly_interest_rate),
        creation_datetime: `${form.creation_datetime}T00:00`,
        maturity_datetime: `${form.maturity_datetime}T00:00`,
        renewed_from_deposit_id: form.renewed_from_deposit_id || null,
        renewal_notes: form.renewal_notes || null,
        deposit_nature: form.deposit_nature || "monthly",
        auto_renew: !!form.auto_renew,
        contract_duration_years: Number(form.contract_duration_years) || 1,
      };
      let response;
      if (editingDepositId) {
        response = await api.put(`/banks/${bankId}/deposits/${editingDepositId}`, payload);
        toast.success("تم تعديل بيانات الوديعة وتحديث قيدها");
      } else {
        response = await api.post(`/banks/${bankId}/deposits`, payload);
        toast.success("تم تسجيل الوديعة بنجاح");
      }
      setSelectedDeposit(response.data);
      setEditingDepositId(null);
      setForm(defaultForm());
      loadDeposits();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تسجيل الوديعة، راجع البيانات المدخلة");
    } finally {
      setIsSaving(false);
    }
  };

  const deleteDeposit = async (deposit) => {    const confirmed = window.confirm(`هل أنت متأكد من حذف الوديعة رقم ${deposit.deposit_number} بالكامل؟ لا يمكن التراجع عن هذه العملية.`);
    if (!confirmed) return;

    try {
      await api.delete(`/banks/${bankId}/deposits/${deposit.id}`);
      toast.success("تم حذف الوديعة بالكامل");
      if (selectedDeposit?.id === deposit.id) setSelectedDeposit(null);
      loadDeposits();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حذف الوديعة");
    }
  };

  return (
    <BankShell>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.05fr_0.95fr]" data-testid="deposit-registration-page">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8" data-testid="deposit-form-section">
          <div className="mb-7 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-extrabold text-emerald-700" data-testid="deposit-form-eyebrow">تسجيل بيانات الوديعة</p>
              <h2 className="mt-2 text-3xl font-extrabold text-slate-950" data-testid="deposit-form-title">ملف وديعة جديد</h2>
            </div>
            <div className="rounded-xl bg-slate-50 p-4" data-testid="expected-interest-box">
              <p className="text-xs font-bold text-slate-500" data-testid="expected-interest-label">العائد السنوي المتوقع</p>
              <p className="text-2xl font-extrabold text-slate-950" data-testid="expected-interest-value">{formatCurrency(expectedAnnualInterest)}</p>
            </div>
          </div>
          <form onSubmit={submitDeposit} className="grid grid-cols-1 gap-5 md:grid-cols-2" data-testid="deposit-registration-form">
            <div className="space-y-2" data-testid="field-account-number-wrapper">
              <Label htmlFor="account_number" data-testid="label-account-number">رقم الحساب</Label>
              <Input id="account_number" required value={form.account_number} onChange={(event) => updateField("account_number", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="input-account-number" />
            </div>
            <div className="space-y-2" data-testid="field-deposit-number-wrapper">
              <Label htmlFor="deposit_number" data-testid="label-deposit-number">رقم الوديعة</Label>
              <Input id="deposit_number" required value={form.deposit_number} onChange={(event) => updateField("deposit_number", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="input-deposit-number" />
            </div>
            <div className="space-y-2" data-testid="field-amount-wrapper">
              <Label htmlFor="amount" data-testid="label-deposit-amount">مبلغ الوديعة بالجنيه المصري</Label>
              <Input id="amount" required min="1" step="0.01" type="number" value={form.amount} onChange={(event) => updateField("amount", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="input-deposit-amount" />
            </div>
            <div className="space-y-2" data-testid="field-interest-rate-wrapper">
              <Label htmlFor="monthly_interest_rate" data-testid="label-interest-rate">النسبة المئوية للفائدة السنوية</Label>
              <Input id="monthly_interest_rate" required min="0" step="0.001" type="number" value={form.monthly_interest_rate} onChange={(event) => updateField("monthly_interest_rate", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="input-interest-rate" />
            </div>
            <div className="space-y-2" data-testid="field-creation-date-wrapper">
              <Label htmlFor="creation_datetime" data-testid="label-creation-date">تاريخ إنشاء الوديعة</Label>
              <Input id="creation_datetime" required type="date" value={form.creation_datetime} onChange={(event) => updateField("creation_datetime", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="input-creation-datetime" />
            </div>
            <div className="space-y-2" data-testid="field-maturity-date-wrapper">
              <Label htmlFor="maturity_datetime" data-testid="label-maturity-date">تاريخ استحقاق الوديعة</Label>
              <Input id="maturity_datetime" required type="date" value={form.maturity_datetime} onChange={(event) => updateField("maturity_datetime", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="input-maturity-datetime" />
            </div>
            <button type="button" onClick={() => updateField("is_opening_balance_deposit", !form.is_opening_balance_deposit)} className={`rounded-xl border p-4 text-right transition-colors md:col-span-2 ${form.is_opening_balance_deposit ? "border-emerald-300 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-slate-50 text-slate-700"}`} data-testid="opening-balance-deposit-toggle">
              <span className="block text-sm font-extrabold" data-testid="opening-balance-deposit-toggle-title">{form.is_opening_balance_deposit ? "✓ وديعة قائمة عند بداية الفترة" : "○ وديعة جديدة خلال الفترة"}</span>
              <span className="mt-1 block text-xs font-bold" data-testid="opening-balance-deposit-toggle-description">اخترها إذا كان تاريخ ربط الوديعة أقدم من تاريخ الرصيد الافتتاحي؛ سيتم إثباتها كرصيد افتتاحي للودائع بدون حركة بنك تاريخية قبل بداية الفترة.</span>
            </button>
            <div className="space-y-2 md:col-span-2" data-testid="field-renewed-from-wrapper">
              <Label htmlFor="renewed_from_deposit_id" data-testid="label-renewed-from-deposit">تم تجديد هذه الوديعة من وديعة سابقة</Label>
              <select id="renewed_from_deposit_id" value={form.renewed_from_deposit_id} onChange={(event) => updateField("renewed_from_deposit_id", event.target.value)} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="select-renewed-from-deposit">
                <option value="" label="وديعة جديدة مستقلة بدون تجديد" data-testid="renewed-from-empty-option" />
                {deposits.map((deposit) => {
                  const optionLabel = `${deposit.deposit_number} — ${formatCurrency(deposit.amount)}`;
                  return <option key={deposit.id} value={deposit.id} label={optionLabel} data-testid={`renewed-from-option-${deposit.id}`} />;
                })}
              </select>
            </div>
            <div className="space-y-2" data-testid="field-contract-duration-wrapper">
              <Label htmlFor="contract_duration_years" data-testid="label-contract-duration">مدة التعاقد (بالسنوات)</Label>
              <select id="contract_duration_years" value={form.contract_duration_years} onChange={(event) => updateField("contract_duration_years", Number(event.target.value))} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="select-contract-duration">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((years) => (
                  <option key={years} value={years} data-testid={`contract-duration-option-${years}`}>{years === 1 ? "سنة واحدة" : years === 2 ? "سنتان" : `${years} سنوات`}</option>
                ))}
              </select>
              <p className="text-xs font-bold text-slate-500" data-testid="contract-duration-hint">تُستخدم لتحديد مدة التجديد التلقائي عند الاستحقاق.</p>
            </div>
            <div className="space-y-2" data-testid="field-deposit-nature-wrapper">
              <Label htmlFor="deposit_nature" data-testid="label-deposit-nature">طبيعة الوديعة</Label>
              <select id="deposit_nature" value={form.deposit_nature} onChange={(event) => updateField("deposit_nature", event.target.value)} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="select-deposit-nature">
                <option value="monthly" data-testid="deposit-nature-monthly-option">شهرية</option>
                <option value="advance" data-testid="deposit-nature-advance-option">فائدة مقدمة</option>
                <option value="quarterly" data-testid="deposit-nature-quarterly-option">ربع سنوية (3 شهور)</option>
              </select>
            </div>
            <button type="button" onClick={() => updateField("auto_renew", !form.auto_renew)} className={`rounded-xl border p-4 text-right transition-colors md:col-span-2 ${form.auto_renew ? "border-emerald-300 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-slate-50 text-slate-700"}`} data-testid="deposit-auto-renew-toggle">
              <span className="block text-sm font-extrabold" data-testid="deposit-auto-renew-toggle-title">{form.auto_renew ? "✓ تجديد تلقائي عند الاستحقاق" : "○ بدون تجديد تلقائي"}</span>
              <span className="mt-1 block text-xs font-bold" data-testid="deposit-auto-renew-toggle-description">عند تفعيله تتجدد الوديعة تلقائياً عند تاريخ الاستحقاق بنفس المبلغ ولمدة التعاقد المحددة أعلاه (بدون إضافة العائد للأصل).</span>
            </button>
            <div className="space-y-2 md:col-span-2" data-testid="field-renewal-notes-wrapper">
              <Label htmlFor="renewal_notes" data-testid="label-renewal-notes">ملاحظات التجديد / الملاحظات التوضيحية</Label>
              <textarea id="renewal_notes" value={form.renewal_notes} onChange={(event) => updateField("renewal_notes", event.target.value)} rows={3} className="w-full rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 text-right text-sm font-bold outline-none" placeholder="تظهر داخل تقارير الودائع فقط بدون أي أثر محاسبي" data-testid="textarea-renewal-notes" />
            </div>
            <div className="flex flex-col gap-3 md:col-span-2 sm:flex-row" data-testid="deposit-form-actions">
              <Button type="submit" disabled={isSaving} className="h-12 rounded-lg bg-slate-950 px-7 text-white hover:bg-slate-800" data-testid="submit-deposit-button">
                <Save className="h-4 w-4" /> {isSaving ? "جاري الحفظ..." : editingDepositId ? "حفظ تعديل الوديعة" : "حفظ بيانات الوديعة"}
              </Button>
              {editingDepositId && (
                <Button type="button" variant="outline" onClick={cancelEditDeposit} className="h-12 rounded-lg border-slate-300 bg-white px-7" data-testid="cancel-edit-deposit-button">إلغاء التعديل</Button>
              )}
              {selectedDeposit && (
                <Button asChild type="button" variant="outline" className="h-12 rounded-lg border-slate-300 bg-white px-7" data-testid="open-current-report-button">
                  <Link to={`/bank/${bankId}/current-year?deposit_id=${selectedDeposit.id}`}><FileText className="h-4 w-4" /> عرض تقرير السنة الحالية</Link>
                </Button>
              )}
            </div>
          </form>
        </section>
        <aside className="space-y-5" data-testid="deposit-side-panel">
          <section className="rounded-xl border border-slate-200 bg-slate-950 p-6 text-white shadow-sm" data-testid="deposit-count-section">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-white/10" data-testid="deposit-count-icon"><WalletCards className="h-6 w-6" /></div>
              <div>
                <p className="text-sm font-bold text-slate-300" data-testid="deposit-count-label">عدد الودائع النشطة لهذا البنك</p>
                <p className="text-4xl font-extrabold" data-testid="deposit-count-value">{activeDeposits.length}</p>
              </div>
            </div>
          </section>
          {selectedDeposit ? (
            <div className="space-y-4" data-testid="latest-deposit-preview">
              <div className="flex items-center justify-between gap-3" data-testid="latest-deposit-header">
                <h3 className="text-xl font-extrabold text-slate-950" data-testid="latest-deposit-title">آخر وديعة مسجلة</h3>
                <Calculator className="h-5 w-5 text-emerald-700" data-testid="latest-deposit-icon" />
              </div>
              <DepositSummary deposit={selectedDeposit} />
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center" data-testid="empty-deposit-state">
              <p className="text-lg font-extrabold text-slate-950" data-testid="empty-deposit-title">لا توجد ودائع مسجلة بعد</p>
              <p className="mt-2 text-sm font-semibold text-slate-500" data-testid="empty-deposit-description">ابدأ بإدخال بيانات الوديعة من النموذج.</p>
            </div>
          )}
          {(user?.role === "admin" || user?.role === "super_admin" || user?.permissions?.enter_deposits || user?.permissions?.edit_deposits) && activeDeposits.length > 0 && (
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="admin-delete-deposits-section">
              <div className="mb-4" data-testid="admin-delete-deposits-heading">
                <p className="text-sm font-extrabold text-emerald-700" data-testid="admin-delete-deposits-eyebrow">إدارة الودائع النشطة</p>
                <h3 className="text-xl font-extrabold text-slate-950" data-testid="admin-delete-deposits-title">تعديل أو حذف وديعة</h3>
                <p className="mt-1 text-sm font-semibold text-slate-500" data-testid="admin-delete-deposits-description">اضغط "تعديل" لفتح بيانات الوديعة في النموذج أعلاه، أو "حذف" لإزالتها بالكامل. الودائع المنتهية/المجددة لا تظهر هنا. الحذف لا يمكن التراجع عنه.</p>
              </div>
              <div className="space-y-3" data-testid="admin-delete-deposits-list">
                {activeDeposits.map((deposit) => (
                  <div key={deposit.id} className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:flex-row sm:items-center sm:justify-between" data-testid={`admin-delete-deposit-row-${deposit.id}`}>
                    <div className="min-w-0" data-testid={`admin-delete-deposit-row-${deposit.id}-details`}>
                      <p className="break-words text-base font-extrabold text-slate-950" data-testid={`admin-delete-deposit-row-${deposit.id}-number`}>{deposit.deposit_number}</p>
                      <p className="text-sm font-bold text-slate-500" data-testid={`admin-delete-deposit-row-${deposit.id}-account`}>حساب: {deposit.account_number}</p>
                      <p className="text-sm font-bold text-slate-500" data-testid={`admin-delete-deposit-row-${deposit.id}-rate`}>نسبة الفائدة: {formatRate(deposit.monthly_interest_rate)}%</p>
                      <p className="text-xs font-extrabold text-emerald-700" data-testid={`admin-delete-deposit-row-${deposit.id}-status`}>الحالة: {deposit.status === "matured" ? "مستحقة" : deposit.status === "closed" ? "مغلقة" : "نشطة"}{deposit.renewed_from_deposit_id ? " • 🔁 مجددة من وديعة سابقة" : ""}</p>
                    </div>
                    <div className="flex gap-2" data-testid={`admin-deposit-row-${deposit.id}-actions`}>
                      <button
                        type="button"
                        onClick={() => startEditDeposit(deposit)}
                        className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 text-sm font-extrabold text-emerald-700 transition-colors hover:bg-emerald-100"
                        data-testid={`edit-deposit-button-${deposit.id}`}
                      >
                        <Pencil className="h-4 w-4" /> تعديل
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteDeposit(deposit)}
                        className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 text-sm font-extrabold text-red-700 transition-colors hover:bg-red-100"
                        data-testid={`delete-deposit-button-${deposit.id}`}
                      >
                        <Trash2 className="h-4 w-4" /> حذف
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </aside>
      </div>
    </BankShell>
  );
}
