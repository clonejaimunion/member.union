import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Calculator, FileText, Save, WalletCards } from "lucide-react";
import { toast } from "sonner";
import { BankShell } from "@/components/BankShell";
import { DepositSummary } from "@/components/DepositSummary";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { formatCurrency, toDateTimeLocal } from "@/lib/format";

const defaultForm = () => {
  const now = new Date();
  const maturity = new Date(now);
  maturity.setFullYear(now.getFullYear() + 1);
  return {
    account_number: "",
    deposit_number: "",
    amount: "",
    creation_datetime: toDateTimeLocal(now),
    maturity_datetime: toDateTimeLocal(maturity),
    monthly_interest_rate: "",
  };
};

export default function DepositRegistration() {
  const { bankId } = useParams();
  const [form, setForm] = useState(defaultForm);
  const [deposits, setDeposits] = useState([]);
  const [selectedDeposit, setSelectedDeposit] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  const expectedMonthlyInterest = useMemo(() => {
    const amount = Number(form.amount || 0);
    const rate = Number(form.monthly_interest_rate || 0);
    return amount * rate / 100;
  }, [form.amount, form.monthly_interest_rate]);

  const loadDeposits = () => {
    api.get(`/banks/${bankId}/deposits`).then((response) => {
      setDeposits(response.data);
      setSelectedDeposit(response.data[0] || null);
    }).catch(() => {
      setDeposits([]);
      setSelectedDeposit(null);
    });
  };

  useEffect(() => {
    loadDeposits();
  }, [bankId]);

  const updateField = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  const submitDeposit = async (event) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      const payload = {
        ...form,
        amount: Number(form.amount),
        monthly_interest_rate: Number(form.monthly_interest_rate),
      };
      const response = await api.post(`/banks/${bankId}/deposits`, payload);
      toast.success("تم تسجيل الوديعة بنجاح");
      setSelectedDeposit(response.data);
      setForm(defaultForm());
      loadDeposits();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تسجيل الوديعة، راجع البيانات المدخلة");
    } finally {
      setIsSaving(false);
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
              <p className="text-xs font-bold text-slate-500" data-testid="expected-interest-label">الفائدة الشهرية المتوقعة</p>
              <p className="text-2xl font-extrabold text-slate-950" data-testid="expected-interest-value">{formatCurrency(expectedMonthlyInterest)}</p>
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
              <Label htmlFor="monthly_interest_rate" data-testid="label-interest-rate">النسبة المئوية للفائدة الشهرية</Label>
              <Input id="monthly_interest_rate" required min="0" step="0.001" type="number" value={form.monthly_interest_rate} onChange={(event) => updateField("monthly_interest_rate", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="input-interest-rate" />
            </div>
            <div className="space-y-2" data-testid="field-creation-date-wrapper">
              <Label htmlFor="creation_datetime" data-testid="label-creation-date">تاريخ إنشاء الوديعة - ساعة/يوم/شهر/سنة</Label>
              <Input id="creation_datetime" required type="datetime-local" value={form.creation_datetime} onChange={(event) => updateField("creation_datetime", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="input-creation-datetime" />
            </div>
            <div className="space-y-2" data-testid="field-maturity-date-wrapper">
              <Label htmlFor="maturity_datetime" data-testid="label-maturity-date">تاريخ استحقاق الوديعة - ساعة/يوم/شهر/سنة</Label>
              <Input id="maturity_datetime" required type="datetime-local" value={form.maturity_datetime} onChange={(event) => updateField("maturity_datetime", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="input-maturity-datetime" />
            </div>
            <div className="flex flex-col gap-3 md:col-span-2 sm:flex-row" data-testid="deposit-form-actions">
              <Button type="submit" disabled={isSaving} className="h-12 rounded-lg bg-slate-950 px-7 text-white hover:bg-slate-800" data-testid="submit-deposit-button">
                <Save className="h-4 w-4" /> {isSaving ? "جاري الحفظ..." : "حفظ بيانات الوديعة"}
              </Button>
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
                <p className="text-sm font-bold text-slate-300" data-testid="deposit-count-label">عدد الودائع المسجلة لهذا البنك</p>
                <p className="text-4xl font-extrabold" data-testid="deposit-count-value">{deposits.length}</p>
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
        </aside>
      </div>
    </BankShell>
  );
}
