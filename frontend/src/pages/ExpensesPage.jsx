import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, Home, LogOut, MinusCircle, Pencil, Plus, RotateCcw, Save, Search, SendToBack, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreditLine } from "@/components/CreditLine";
import { ExportReportButtons } from "@/components/ExportReportButtons";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { fallbackBanks } from "@/lib/banks";
import { formatCurrency, formatEgpLabel, sanitizeDecimalInput, sanitizeDigitsInput } from "@/lib/format";

const today = () => new Date().toISOString().slice(0, 10);
const emptyDeduction = () => ({ amount: "", statement: "" });
const methodLabels = { cash: "نقداً", check: "شيك", bank_transfer: "تحويل بنكي" };
const organizationLabels = { general_union: "النقابة العامة", social_solidarity_project: "مشروع التكافل الاجتماعي" };
const categoryLabels = { general_expenses: "مصروفات عمومية", death_benefits: "إعانات وفاة" };
const monthLabels = { "01": "يناير", "02": "فبراير", "03": "مارس", "04": "أبريل", "05": "مايو", "06": "يونيو", "07": "يوليو", "08": "أغسطس", "09": "سبتمبر", "10": "أكتوبر", "11": "نوفمبر", "12": "ديسمبر" };
const employeeOptions = ["يوسف عبدالغني", "دعاء علي"];

const amountParts = (value) => {
  const [pounds, piastres] = Math.abs(Number(value || 0)).toFixed(2).split(".");
  return { pounds, piastres };
};

const defaultForm = () => ({
  expense_number: "",
  organization_scope: "social_solidarity_project",
  expense_category: "general_expenses",
  payment_method: "cash",
  payee_name: "",
  check_number: "",
  transfer_number: "",
  transfer_to: "",
  membership_number: "",
  committee: "",
  governorate: "",
  bank_id: "industrial-development",
  gross_amount: "",
  gross_statement: "",
  deductions: [emptyDeduction()],
  issued_at: today(),
  responsible_employee: "يوسف عبدالغني",
});

export default function ExpensesPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [banks, setBanks] = useState(fallbackBanks);
  const [expenses, setExpenses] = useState([]);
  const [form, setForm] = useState(defaultForm);
  const [filters, setFilters] = useState({ bank_id: "all", payment_method: "all", from_date: "", to_date: "" });
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [selectedExpense, setSelectedExpense] = useState(null);
  const [selectedGeneralVoucherYear, setSelectedGeneralVoucherYear] = useState("");
  const [selectedDeathBenefitYear, setSelectedDeathBenefitYear] = useState("");
  const [selectedGeneralVoucherMonth, setSelectedGeneralVoucherMonth] = useState("");
  const [selectedDeathBenefitMonth, setSelectedDeathBenefitMonth] = useState("");

  const canManage = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.manage_expenses;
  const deductionTotal = useMemo(() => form.deductions.reduce((sum, item) => sum + Number(sanitizeDecimalInput(item.amount) || 0), 0), [form.deductions]);
  const netAmount = useMemo(() => Number(sanitizeDecimalInput(form.gross_amount) || 0) - deductionTotal, [deductionTotal, form.gross_amount]);
  const reportTotals = useMemo(() => expenses.reduce((acc, item) => ({
    gross: acc.gross + Number(item.gross_amount || 0),
    deductions: acc.deductions + Number(item.total_deductions || 0),
    net: acc.net + Number(item.net_amount || 0),
  }), { gross: 0, deductions: 0, net: 0 }), [expenses]);
  const buildVoucherGroups = useCallback((items) => {
    const groups = items.reduce((acc, item) => {
      const year = String(item.issued_at || "").slice(0, 4) || "بدون سنة";
      if (!acc[year]) acc[year] = [];
      acc[year].push(item);
      return acc;
    }, {});
    return Object.entries(groups)
      .sort(([yearA], [yearB]) => Number(yearB) - Number(yearA))
      .map(([year, items]) => ({
        year,
        items: items.sort((a, b) => String(b.issued_at || "").localeCompare(String(a.issued_at || ""))),
      }));
  }, []);
  const generalVoucherGroups = useMemo(() => buildVoucherGroups(expenses.filter((item) => (item.expense_category || "general_expenses") === "general_expenses")), [buildVoucherGroups, expenses]);
  const deathBenefitGroups = useMemo(() => buildVoucherGroups(expenses.filter((item) => item.expense_category === "death_benefits")), [buildVoucherGroups, expenses]);
  const selectedGeneralVoucherGroup = useMemo(() => generalVoucherGroups.find((group) => group.year === selectedGeneralVoucherYear), [selectedGeneralVoucherYear, generalVoucherGroups]);
  const selectedDeathBenefitGroup = useMemo(() => deathBenefitGroups.find((group) => group.year === selectedDeathBenefitYear), [selectedDeathBenefitYear, deathBenefitGroups]);
  const getMonthOptions = (group) => [...new Set((group?.items || []).map((item) => String(item.issued_at || "").slice(5, 7)).filter(Boolean))].sort();
  const selectedGeneralMonthItems = useMemo(() => (selectedGeneralVoucherGroup?.items || []).filter((item) => String(item.issued_at || "").slice(5, 7) === selectedGeneralVoucherMonth), [selectedGeneralVoucherGroup, selectedGeneralVoucherMonth]);
  const selectedDeathBenefitMonthItems = useMemo(() => (selectedDeathBenefitGroup?.items || []).filter((item) => String(item.issued_at || "").slice(5, 7) === selectedDeathBenefitMonth), [selectedDeathBenefitGroup, selectedDeathBenefitMonth]);

  const loadBanks = useCallback(() => {
    api.get("/banks").then((response) => setBanks(response.data)).catch(() => setBanks(fallbackBanks));
  }, []);

  const loadExpenses = useCallback(() => {
    const params = new URLSearchParams();
    if (filters.bank_id !== "all") params.set("bank_id", filters.bank_id);
    if (filters.payment_method !== "all") params.set("payment_method", filters.payment_method);
    if (filters.from_date) params.set("from_date", filters.from_date);
    if (filters.to_date) params.set("to_date", filters.to_date);
    const query = params.toString() ? `?${params.toString()}` : "";
    api.get(`/expenses${query}`).then((response) => setExpenses(response.data)).catch(() => setExpenses([]));
  }, [filters]);

  useEffect(() => { loadBanks(); }, [loadBanks]);
  useEffect(() => { loadExpenses(); }, [loadExpenses]);

  useEffect(() => {
    if (selectedExpense) {
      document.body.setAttribute("data-expense-voucher-open", "true");
    } else {
      document.body.removeAttribute("data-expense-voucher-open");
    }
    return () => document.body.removeAttribute("data-expense-voucher-open");
  }, [selectedExpense]);

  const updateForm = (field, value) => {
    const nextValue = ["expense_number", "check_number", "transfer_number", "membership_number"].includes(field)
      ? sanitizeDigitsInput(value)
      : field === "gross_amount"
        ? sanitizeDecimalInput(value)
        : value;
    setForm((current) => ({ ...current, [field]: nextValue }));
  };

  const updateDeduction = (index, field, value) => {
    const nextValue = field === "amount" ? sanitizeDecimalInput(value) : value;
    setForm((current) => ({ ...current, deductions: current.deductions.map((item, itemIndex) => itemIndex === index ? { ...item, [field]: nextValue } : item) }));
  };

  const addDeduction = () => setForm((current) => ({ ...current, deductions: [...current.deductions, emptyDeduction()] }));
  const removeDeduction = (index) => setForm((current) => ({ ...current, deductions: current.deductions.length === 1 ? [emptyDeduction()] : current.deductions.filter((_, itemIndex) => itemIndex !== index) }));
  const resetForm = () => { setEditingId(null); setForm(defaultForm()); };

  const payloadFromForm = () => ({
    ...form,
    expense_number: sanitizeDigitsInput(form.expense_number),
    gross_amount: Number(sanitizeDecimalInput(form.gross_amount) || 0),
    membership_number: form.expense_category === "death_benefits" ? sanitizeDigitsInput(form.membership_number) : null,
    committee: form.expense_category === "death_benefits" ? form.committee.trim() : null,
    governorate: form.expense_category === "death_benefits" ? form.governorate.trim() : null,
    payee_name: ["cash", "check"].includes(form.payment_method) ? form.payee_name.trim() : null,
    check_number: form.payment_method === "check" ? sanitizeDigitsInput(form.check_number) : null,
    transfer_number: form.payment_method === "bank_transfer" ? sanitizeDigitsInput(form.transfer_number) : null,
    transfer_to: form.payment_method === "bank_transfer" ? form.transfer_to.trim() : null,
    deductions: form.deductions.filter((item) => item.statement.trim() || Number(sanitizeDecimalInput(item.amount) || 0) > 0).map((item) => ({ amount: Number(sanitizeDecimalInput(item.amount) || 0), statement: item.statement.trim() })),
  });

  const submitExpense = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = payloadFromForm();
      const response = editingId ? await api.put(`/expenses/${editingId}`, payload) : await api.post("/expenses", payload);
      toast.success(editingId ? "تم تعديل المصروف" : "تم حفظ المصروف");
      setEditingId(null);
      setForm({ ...defaultForm(), bank_id: response.data.bank_id });
      loadExpenses();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ المصروف");
    } finally {
      setSaving(false);
    }
  };

  const editExpense = (item) => {
    setEditingId(item.id);
    setForm({
      expense_number: item.expense_number || "",
      organization_scope: item.organization_scope || "social_solidarity_project",
      expense_category: item.expense_category || "general_expenses",
      payment_method: item.payment_method || "cash",
      payee_name: item.payee_name || "",
      check_number: item.check_number || "",
      transfer_number: item.transfer_number || "",
      transfer_to: item.transfer_to || "",
      membership_number: item.membership_number || "",
      committee: item.committee || "",
      governorate: item.governorate || "",
      bank_id: item.bank_id || "industrial-development",
      gross_amount: String(item.gross_amount ?? ""),
      gross_statement: item.gross_statement || "",
      deductions: item.deductions?.length ? item.deductions.map((deduction) => ({ amount: String(deduction.amount ?? ""), statement: deduction.statement || "" })) : [emptyDeduction()],
      issued_at: item.issued_at || today(),
      responsible_employee: item.responsible_employee || "يوسف عبدالغني",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const deleteExpense = async (item) => {
    if (!window.confirm(`هل تريد حذف المصروف رقم ${item.expense_number}؟`)) return;
    try {
      await api.delete(`/expenses/${item.id}`);
      toast.success("تم حذف المصروف");
      if (editingId === item.id) resetForm();
      loadExpenses();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حذف المصروف");
    }
  };

  const searchExpense = async (event) => {
    event.preventDefault();
    if (!searchQuery.trim()) { toast.error("اكتب رقم الإذن أو الشيك أو التحويل أو اسم الشخص"); return; }
    try {
      const response = await api.get(`/expenses/search?query=${encodeURIComponent(searchQuery.trim())}`);
      setSearchResults(response.data);
      setSearchOpen(true);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر البحث عن المصروف");
    }
  };

  const detailLabel = (item) => item.payment_method === "bank_transfer" ? "تم التحويل إلى" : "يصرف للسيد";
  const detailValue = (item) => item.payment_method === "bank_transfer" ? item.transfer_to : item.payee_name;
  const refValue = (item) => item.payment_method === "check" ? item.check_number : item.payment_method === "bank_transfer" ? item.transfer_number : "—";

  const DetailGrid = ({ item, prefix }) => (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid={`${prefix}-details-grid`}>
      {[["رقم الإذن", item.expense_number], ["الجهة", organizationLabels[item.organization_scope || "social_solidarity_project"]], ["نوع المصروف", categoryLabels[item.expense_category || "general_expenses"]], ["طريقة الصرف", methodLabels[item.payment_method]], [detailLabel(item), detailValue(item)], [item.payment_method === "bank_transfer" ? "رقم عملية التحويل" : "رقم الشيك", refValue(item)], ["البنك", item.bank_name], ...((item.expense_category === "death_benefits") ? [["رقم العضوية", item.membership_number], ["لجنة", item.committee], ["محافظة", item.governorate]] : []), ["المبلغ الكلي", formatCurrency(item.gross_amount)], ["بيان المبلغ", item.gross_statement], ["إجمالي الاستقطاعات", formatCurrency(item.total_deductions)], ["الصافي", formatCurrency(item.net_amount)], ["تحريراً في", item.issued_at], ["الموظف المختص", item.responsible_employee]].map(([label, value], index) => (
        <div key={`${prefix}-${label}`} className={index === 6 ? "rounded-lg bg-slate-50 p-3 md:col-span-2" : "rounded-lg bg-slate-50 p-3"} data-testid={`${prefix}-detail-${index}`}><p className="text-xs font-bold text-slate-500" data-testid={`${prefix}-detail-${index}-label`}>{label}</p><p className="mt-1 break-words text-base font-extrabold text-slate-950" data-testid={`${prefix}-detail-${index}-value`}>{value || "—"}</p></div>
      ))}
      {item.deductions?.length > 0 && <div className="rounded-lg bg-amber-50 p-3 md:col-span-2" data-testid={`${prefix}-deductions-list`}><p className="text-xs font-bold text-amber-700" data-testid={`${prefix}-deductions-title`}>بيانات الاستقطاعات</p>{item.deductions.map((deduction, index) => <p key={`${prefix}-deduction-${index}`} className="mt-2 text-sm font-bold text-slate-800" data-testid={`${prefix}-deduction-${index}`}>{formatCurrency(deduction.amount)} — {deduction.statement}</p>)}</div>}
    </div>
  );

  const ExpenseVoucher = ({ item }) => {
    const grossParts = amountParts(item.gross_amount);
    const netParts = amountParts(item.net_amount);
    const voucherTitle = item.payment_method === "check" ? "إذن صرف شيك" : item.payment_method === "bank_transfer" ? "إذن تحويل بنكي" : "إذن صرف نقدي";
    const isDeathBenefit = item.expense_category === "death_benefits";
    return (
      <article className="mx-auto w-full max-w-5xl bg-white p-6 text-slate-950 print:max-w-none print:p-0" data-testid="expense-voucher-document">
        <header className="text-center leading-7" data-testid="expense-voucher-header">
          <p className="text-sm font-extrabold" data-testid="expense-voucher-union-name">النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الأراضي</p>
          {item.organization_scope === "social_solidarity_project" && <p className="text-sm font-bold" data-testid="expense-voucher-fund-name">مشروع التكافل الاجتماعي</p>}
          <p className="text-xs font-bold text-slate-600" data-testid="expense-voucher-address">١٧٠ شارع بورسعيد - السيدة زينب - القاهرة</p>
        </header>
        <div className="mt-5 grid grid-cols-3 items-center" data-testid="expense-voucher-title-row">
          <p className="text-3xl font-extrabold text-slate-500" data-testid="expense-voucher-number">{item.expense_number}</p>
          <h2 className="text-center text-3xl font-extrabold" data-testid="expense-voucher-title">{voucherTitle}</h2>
          <div />
        </div>
        <section className="mt-6 grid grid-cols-1 gap-4 text-lg font-extrabold md:grid-cols-2" data-testid="expense-voucher-party-section">
          <p className="border-b border-dotted border-slate-400 pb-2" data-testid="expense-voucher-payee-line">{detailLabel(item)} : <span className="font-bold">{detailValue(item) || "................................"}</span></p>
          {isDeathBenefit && <p className="border-b border-dotted border-slate-400 pb-2" data-testid="expense-voucher-membership-line">رقم العضوية : <span className="font-bold">{item.membership_number}</span></p>}
          {isDeathBenefit && <p className="border-b border-dotted border-slate-400 pb-2" data-testid="expense-voucher-committee-line">لجنة : <span className="font-bold">{item.committee}</span></p>}
          {isDeathBenefit && <p className="border-b border-dotted border-slate-400 pb-2" data-testid="expense-voucher-governorate-line">محافظة : <span className="font-bold">{item.governorate}</span></p>}
          <p className="border-b border-dotted border-slate-400 pb-2 md:col-span-2" data-testid="expense-voucher-reference-line">
            {item.payment_method === "check" ? "شيك رقم" : item.payment_method === "bank_transfer" ? "عملية تحويل رقم" : "طريقة الصرف"} : <span className="font-bold">{refValue(item)}</span>
            <span className="mx-4">على بنك :</span><span className="font-bold">{item.bank_name}</span>
          </p>
        </section>
        <section dir="ltr" className="mt-6 overflow-hidden border-2 border-slate-900" data-testid="expense-voucher-table-wrapper">
          <div className="grid grid-cols-[1fr_150px_150px] border-b-2 border-slate-900 text-center text-lg font-extrabold" data-testid="expense-voucher-table-header">
            <div dir="rtl" className="border-r-2 border-slate-900 p-3" data-testid="expense-voucher-header-statement">البيان</div>
            <div dir="rtl" className="border-r-2 border-slate-900" data-testid="expense-voucher-header-partial"><div className="border-b border-slate-900 p-2">المبلغ الجزئي</div><div className="grid grid-cols-2"><span className="border-l border-slate-900 p-1" data-testid="expense-voucher-partial-piastres-header">قرش</span><span className="p-1" data-testid="expense-voucher-partial-pounds-header">جنيه</span></div></div>
            <div data-testid="expense-voucher-header-total"><div className="border-b border-slate-900 p-2">المبلغ الكلي</div><div className="grid grid-cols-2"><span className="border-l border-slate-900 p-1">جنيه</span><span className="p-1">قرش</span></div></div>
          </div>
          <div className="grid min-h-[82px] grid-cols-[1fr_150px_150px] border-b border-slate-300" data-testid="expense-voucher-entitlement-row">
            <div dir="rtl" className="border-r-2 border-slate-900 p-3 text-right text-lg font-bold" data-testid="expense-voucher-gross-statement">{item.gross_statement}</div>
            <div className="grid grid-cols-2 border-r-2 border-slate-900 text-center text-lg font-bold"><span className="border-l border-slate-300 p-3" data-testid="expense-voucher-gross-partial-pounds">—</span><span className="p-3" data-testid="expense-voucher-gross-partial-piastres">—</span></div>
            <div className="grid grid-cols-2 text-center text-lg font-extrabold"><span className="border-l border-slate-300 p-3" data-testid="expense-voucher-gross-pounds">{grossParts.pounds}</span><span className="p-3" data-testid="expense-voucher-gross-piastres">{grossParts.piastres}</span></div>
          </div>
          <div className="grid grid-cols-[1fr_150px_150px] border-b border-slate-900" data-testid="expense-voucher-deductions-heading-row">
            <div dir="rtl" className="border-r-2 border-slate-900 p-3 text-center text-xl font-extrabold underline" data-testid="expense-voucher-deductions-title">استقطاعات</div>
            <div className="border-r-2 border-slate-900 bg-slate-50" />
            <div className="bg-slate-50" />
          </div>
          {(item.deductions?.length ? item.deductions : [{ amount: 0, statement: "لا توجد استقطاعات" }]).map((deduction, index) => {
            const parts = amountParts(deduction.amount);
            return (
              <div key={`voucher-deduction-${index}`} className="grid min-h-[48px] grid-cols-[1fr_150px_150px] border-b border-dotted border-slate-300" data-testid={`expense-voucher-deduction-row-${index}`}>
                <div dir="rtl" className="border-r-2 border-slate-900 p-3 text-right font-bold" data-testid={`expense-voucher-deduction-${index}-statement`}>{deduction.statement}</div>
                <div className="grid grid-cols-2 border-r-2 border-slate-900 text-center font-bold"><span className="border-l border-slate-300 p-3" data-testid={`expense-voucher-deduction-${index}-piastres`}>{parts.piastres}</span><span className="p-3" data-testid={`expense-voucher-deduction-${index}-pounds`}>{parts.pounds}</span></div>
                <div className="grid grid-cols-2 text-center"><span className="border-l border-slate-300 p-3">—</span><span className="p-3">—</span></div>
              </div>
            );
          })}
          <div className="grid grid-cols-[1fr_150px_150px] bg-slate-50 text-xl font-extrabold" data-testid="expense-voucher-net-row">
            <div dir="rtl" className="border-r-2 border-slate-900 p-4 text-right" data-testid="expense-voucher-net-label">الصافي</div>
            <div className="border-r-2 border-slate-900 p-4 text-center" data-testid="expense-voucher-net-text">{formatCurrency(item.net_amount)}</div>
            <div className="grid grid-cols-2 text-center"><span className="border-l border-slate-300 p-4" data-testid="expense-voucher-net-pounds">{netParts.pounds}</span><span className="p-4" data-testid="expense-voucher-net-piastres">{netParts.piastres}</span></div>
          </div>
        </section>
        <footer className="mt-8 flex justify-end text-center text-lg font-extrabold" data-testid="expense-voucher-footer">
          <div className="w-full max-w-sm" data-testid="expense-voucher-employee-sign"><p>تحريراً في : {item.issued_at}</p><p className="mt-5">الموظف المختص</p><div className="mt-3 border-2 border-slate-900 p-3">{item.responsible_employee}</div></div>
        </footer>
      </article>
    );
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="expenses-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="expenses-header"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8"><div className="flex items-center gap-3" data-testid="expenses-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="expenses-brand-icon"><SendToBack className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-red-700" data-testid="expenses-eyebrow">المصروفات</p><h1 className="text-2xl font-extrabold" data-testid="expenses-title">تسجيل وتقرير المصروفات</h1></div></div><div className="flex flex-wrap items-center gap-3" data-testid="expenses-header-actions"><Badge className="border-slate-200 bg-white px-3 py-1 text-slate-700 shadow-sm hover:bg-white" data-testid="expenses-user-badge">{user?.username}</Badge><Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="expenses-home-button"><Link to="/"><Home className="h-4 w-4" /> القائمة الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="expenses-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="expenses-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div></div></header>
      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="expenses-content">
        {canManage && <form onSubmit={submitExpense} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden sm:p-8" data-testid="expense-form"><div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" data-testid="expense-form-heading"><div><p className="text-sm font-extrabold text-red-700" data-testid="expense-form-eyebrow">{editingId ? "تعديل بيانات المصروف" : "إضافة مصروف جديد"}</p><h2 className="text-3xl font-extrabold text-slate-950" data-testid="expense-form-title">بيانات المصروف</h2></div>{editingId && <Button type="button" onClick={resetForm} variant="outline" className="h-11 rounded-lg bg-white" data-testid="cancel-edit-expense-button"><RotateCcw className="h-4 w-4" /> إلغاء التعديل</Button>}</div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="expense-form-grid">
            <div className="space-y-2" data-testid="expense-organization-wrapper"><Label data-testid="expense-organization-label">الجهة</Label><select value={form.organization_scope} onChange={(event) => updateForm("organization_scope", event.target.value)} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="expense-organization-select"><option value="general_union" data-testid="expense-organization-general-union-option">النقابة العامة</option><option value="social_solidarity_project" data-testid="expense-organization-social-project-option">مشروع التكافل الاجتماعي</option></select></div>
            <div className="space-y-2" data-testid="expense-category-wrapper"><Label data-testid="expense-category-label">نوع المصروف</Label><select value={form.expense_category} onChange={(event) => updateForm("expense_category", event.target.value)} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="expense-category-select"><option value="general_expenses" data-testid="expense-category-general-option">مصروفات عمومية</option><option value="death_benefits" data-testid="expense-category-death-option">إعانات وفاة</option></select></div>
            <div className="space-y-2" data-testid="expense-number-wrapper"><Label data-testid="expense-number-label">رقم الإذن</Label><Input required inputMode="numeric" value={form.expense_number} onChange={(event) => updateForm("expense_number", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-number-input" /></div>
            <div className="space-y-2" data-testid="expense-method-wrapper"><Label data-testid="expense-method-label">طريقة الصرف</Label><select value={form.payment_method} onChange={(event) => updateForm("payment_method", event.target.value)} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="expense-method-select"><option value="cash" data-testid="expense-method-cash-option">نقداً</option><option value="check" data-testid="expense-method-check-option">شيك</option><option value="bank_transfer" data-testid="expense-method-transfer-option">تحويل بنكي</option></select></div>
            <div className="space-y-2" data-testid="expense-bank-wrapper"><Label data-testid="expense-bank-label">اسم البنك</Label><select value={form.bank_id} onChange={(event) => updateForm("bank_id", event.target.value)} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="expense-bank-select">{banks.map((bank) => <option key={bank.id} value={bank.id} data-testid={`expense-bank-option-${bank.id}`}>{bank.name}</option>)}</select></div>
            {form.payment_method !== "bank_transfer" && <div className="space-y-2" data-testid="expense-payee-wrapper"><Label data-testid="expense-payee-label">يصرف للسيد</Label><Input required value={form.payee_name} onChange={(event) => updateForm("payee_name", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-payee-input" /></div>}
            {form.payment_method === "check" && <div className="space-y-2" data-testid="expense-check-wrapper"><Label data-testid="expense-check-label">رقم الشيك</Label><Input required inputMode="numeric" value={form.check_number} onChange={(event) => updateForm("check_number", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-check-input" /></div>}
            {form.payment_method === "bank_transfer" && <><div className="space-y-2" data-testid="expense-transfer-wrapper"><Label data-testid="expense-transfer-label">رقم عملية التحويل</Label><Input required inputMode="numeric" value={form.transfer_number} onChange={(event) => updateForm("transfer_number", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-transfer-input" /></div><div className="space-y-2" data-testid="expense-transfer-to-wrapper"><Label data-testid="expense-transfer-to-label">تم التحويل إلى</Label><Input required value={form.transfer_to} onChange={(event) => updateForm("transfer_to", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-transfer-to-input" /></div></>}
            {form.expense_category === "death_benefits" && <><div className="space-y-2" data-testid="expense-membership-wrapper"><Label data-testid="expense-membership-label">رقم العضوية</Label><Input required inputMode="numeric" value={form.membership_number} onChange={(event) => updateForm("membership_number", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-membership-input" /></div><div className="space-y-2" data-testid="expense-committee-wrapper"><Label data-testid="expense-committee-label">لجنة</Label><Input required value={form.committee} onChange={(event) => updateForm("committee", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-committee-input" /></div><div className="space-y-2" data-testid="expense-governorate-wrapper"><Label data-testid="expense-governorate-label">محافظة</Label><Input required value={form.governorate} onChange={(event) => updateForm("governorate", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-governorate-input" /></div></>}
            <div className="space-y-2" data-testid="expense-gross-amount-wrapper"><Label data-testid="expense-gross-amount-label">المبلغ الكلي</Label><Input required inputMode="decimal" value={form.gross_amount} onChange={(event) => updateForm("gross_amount", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-gross-amount-input" /></div>
            <div className="space-y-2 md:col-span-2" data-testid="expense-gross-statement-wrapper"><Label data-testid="expense-gross-statement-label">بيان المبلغ</Label><Input required value={form.gross_statement} onChange={(event) => updateForm("gross_statement", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-gross-statement-input" /></div>
          </div>
          <section className="mt-6 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4" data-testid="expense-deductions-section"><div className="mb-3 flex items-center justify-between gap-3" data-testid="expense-deductions-heading"><h3 className="text-xl font-extrabold text-slate-950" data-testid="expense-deductions-title">استقطاعات</h3><Button type="button" onClick={addDeduction} variant="outline" className="h-10 rounded-lg bg-white" data-testid="add-expense-deduction-button"><Plus className="h-4 w-4" /> إضافة بيان</Button></div>{form.deductions.map((deduction, index) => <div key={`deduction-${index}`} className="mb-3 grid grid-cols-1 gap-3 md:grid-cols-[180px_1fr_auto]" data-testid={`expense-deduction-row-${index}`}><Input inputMode="decimal" value={deduction.amount} onChange={(event) => updateDeduction(index, "amount", event.target.value)} placeholder="المبلغ" className="h-12 rounded-lg bg-white text-right" data-testid={`expense-deduction-${index}-amount-input`} /><Input value={deduction.statement} onChange={(event) => updateDeduction(index, "statement", event.target.value)} placeholder="بيان المبلغ" className="h-12 rounded-lg bg-white text-right" data-testid={`expense-deduction-${index}-statement-input`} /><button type="button" onClick={() => removeDeduction(index)} className="inline-flex h-12 items-center justify-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 text-sm font-extrabold text-red-700" data-testid={`remove-expense-deduction-${index}-button`}><MinusCircle className="h-4 w-4" /> حذف</button></div>)}<div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="expense-calculation-summary"><div className="rounded-lg bg-white p-4" data-testid="expense-total-deductions-card"><p className="text-xs font-bold text-slate-500">إجمالي الاستقطاعات</p><p className="text-2xl font-extrabold text-red-700" data-testid="expense-total-deductions-value">{formatCurrency(deductionTotal)}</p></div><div className="rounded-lg bg-slate-950 p-4 text-white" data-testid="expense-net-card"><p className="text-xs font-bold text-slate-300">الصافي</p><p className="text-2xl font-extrabold" data-testid="expense-net-value">{formatCurrency(netAmount)}</p></div></div></section>
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2" data-testid="expense-final-fields"><div className="space-y-2" data-testid="expense-issued-wrapper"><Label data-testid="expense-issued-label">تحريراً في</Label><Input required type="date" value={form.issued_at} onChange={(event) => updateForm("issued_at", event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-issued-input" /></div><div className="space-y-2" data-testid="expense-employee-wrapper"><Label data-testid="expense-employee-label">الموظف المختص</Label><select value={form.responsible_employee} onChange={(event) => updateForm("responsible_employee", event.target.value)} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold outline-none" data-testid="expense-employee-select">{employeeOptions.map((name) => <option key={name} value={name} data-testid={`expense-employee-option-${name}`}>{name}</option>)}</select></div></div>
          <Button type="submit" disabled={saving} className="mt-6 h-12 rounded-lg bg-slate-950 px-7 text-white" data-testid="save-expense-button"><Save className="h-4 w-4" /> {saving ? "جاري الحفظ..." : editingId ? "حفظ تعديل المصروف" : "حفظ المصروف"}</Button></form>}

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden" data-testid="expenses-tools-section"><div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto]" data-testid="expenses-tools-grid"><form onSubmit={searchExpense} className="flex flex-col gap-3 sm:flex-row" data-testid="expense-search-form"><Input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="بحث برقم الإذن أو الشيك أو التحويل أو اسم الشخص" className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expense-search-input" /><Button type="submit" className="h-12 rounded-lg bg-red-700 px-6 text-white hover:bg-red-800" data-testid="expense-search-button"><Search className="h-4 w-4" /> بحث</Button></form><ExportReportButtons title="تقرير المصروفات" fileName="تقرير-المصروفات" selectors={["[data-testid='expenses-report-section']"]} pdfTestId="print-expenses-report-button" excelTestId="export-expenses-report-excel-button" wordTestId="export-expenses-report-word-button" /></div><div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-4" data-testid="expenses-filters-grid"><select value={filters.bank_id} onChange={(event) => setFilters((current) => ({ ...current, bank_id: event.target.value }))} className="h-12 rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="expenses-filter-bank-select"><option value="all" data-testid="expenses-filter-bank-all-option">كل البنوك</option>{banks.map((bank) => <option key={bank.id} value={bank.id} data-testid={`expenses-filter-bank-${bank.id}`}>{bank.name}</option>)}</select><select value={filters.payment_method} onChange={(event) => setFilters((current) => ({ ...current, payment_method: event.target.value }))} className="h-12 rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold" data-testid="expenses-filter-method-select"><option value="all" data-testid="expenses-filter-method-all-option">كل طرق الصرف</option><option value="cash" data-testid="expenses-filter-method-cash-option">نقداً</option><option value="check" data-testid="expenses-filter-method-check-option">شيك</option><option value="bank_transfer" data-testid="expenses-filter-method-transfer-option">تحويل بنكي</option></select><Input type="date" value={filters.from_date} onChange={(event) => setFilters((current) => ({ ...current, from_date: event.target.value }))} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expenses-filter-from-date-input" /><Input type="date" value={filters.to_date} onChange={(event) => setFilters((current) => ({ ...current, to_date: event.target.value }))} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="expenses-filter-to-date-input" /></div></section>

        <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:border-0 print:shadow-none sm:p-8" data-testid="expenses-report-section"><div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between" data-testid="expenses-report-heading"><div><p className="text-sm font-extrabold text-red-700" data-testid="expenses-report-eyebrow">تقرير المصروفات</p><h2 className="text-3xl font-extrabold text-slate-950" data-testid="expenses-report-title">بيان المصروفات المسجلة</h2></div><div className="grid grid-cols-1 gap-3 sm:grid-cols-3" data-testid="expenses-report-kpis"><div className="rounded-xl bg-slate-950 p-4 text-white" data-testid="expenses-gross-card"><p className="text-xs font-bold text-slate-300">إجمالي الاستحقاقات</p><p className="text-xl font-extrabold" data-testid="expenses-gross-value">{formatEgpLabel(reportTotals.gross)}</p></div><div className="rounded-xl bg-red-50 p-4 text-red-900" data-testid="expenses-deductions-card"><p className="text-xs font-bold text-red-700">إجمالي الاستقطاعات</p><p className="text-xl font-extrabold" data-testid="expenses-deductions-value">{formatEgpLabel(reportTotals.deductions)}</p></div><div className="rounded-xl bg-emerald-50 p-4 text-emerald-900" data-testid="expenses-net-total-card"><p className="text-xs font-bold text-emerald-700">إجمالي الصافي</p><p className="text-xl font-extrabold" data-testid="expenses-net-total-value">{formatEgpLabel(reportTotals.net)}</p></div></div></div><div className="overflow-hidden rounded-xl border border-slate-200" data-testid="expenses-table-wrapper"><Table data-testid="expenses-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950" data-testid="expenses-table-header-row">{["رقم الإذن", "الجهة", "نوع المصروف", "طريقة الصرف", "بيان الصرف", "المرجع", "البنك", "المبلغ الكلي", "إجمالي الاستقطاعات", "الصافي", "تحريراً في", "الموظف"].map((title) => <TableHead key={title} className="text-right font-extrabold text-white" data-testid={`expenses-header-${title}`}>{title}</TableHead>)}{canManage && <TableHead className="text-right font-extrabold text-white print:hidden" data-testid="expenses-header-actions">إجراءات</TableHead>}</TableRow></TableHeader><TableBody>{expenses.map((item) => <TableRow key={item.id} data-testid={`expense-row-${item.id}`}><TableCell className="font-extrabold" data-testid={`expense-row-${item.id}-number`}>{item.expense_number}</TableCell><TableCell data-testid={`expense-row-${item.id}-organization`}>{organizationLabels[item.organization_scope || "social_solidarity_project"]}</TableCell><TableCell data-testid={`expense-row-${item.id}-category`}>{categoryLabels[item.expense_category || "general_expenses"]}</TableCell><TableCell data-testid={`expense-row-${item.id}-method`}>{methodLabels[item.payment_method]}</TableCell><TableCell data-testid={`expense-row-${item.id}-detail`}>{detailValue(item)}</TableCell><TableCell data-testid={`expense-row-${item.id}-reference`}>{refValue(item)}</TableCell><TableCell data-testid={`expense-row-${item.id}-bank`}>{item.bank_name}</TableCell><TableCell data-testid={`expense-row-${item.id}-gross`}>{formatCurrency(item.gross_amount)}</TableCell><TableCell data-testid={`expense-row-${item.id}-deductions`}>{formatCurrency(item.total_deductions)}</TableCell><TableCell className="font-extrabold" data-testid={`expense-row-${item.id}-net`}>{formatCurrency(item.net_amount)}</TableCell><TableCell data-testid={`expense-row-${item.id}-issued`}>{item.issued_at}</TableCell><TableCell data-testid={`expense-row-${item.id}-employee`}>{item.responsible_employee}</TableCell>{canManage && <TableCell className="print:hidden" data-testid={`expense-row-${item.id}-actions`}><div className="flex flex-col gap-2" data-testid={`expense-row-${item.id}-manage-actions`}><button type="button" onClick={() => editExpense(item)} className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 text-xs font-extrabold text-amber-700" data-testid={`edit-expense-button-${item.id}`}><Pencil className="h-4 w-4" /> تعديل</button><button type="button" onClick={() => deleteExpense(item)} className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 text-xs font-extrabold text-red-700" data-testid={`delete-expense-button-${item.id}`}><Trash2 className="h-4 w-4" /> حذف</button></div></TableCell>}</TableRow>)}</TableBody></Table></div></section>
        {expenses.length > 0 && (
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden" data-testid="expense-voucher-actions-section">
            <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between" data-testid="expense-voucher-actions-heading">
              <div>
                <h3 className="text-2xl font-extrabold text-slate-950" data-testid="expense-voucher-actions-title">عرض إذن الصرف التفصيلي</h3>
                <p className="mt-1 text-sm font-bold text-slate-500" data-testid="expense-voucher-actions-description">اختر سنة التحرير لعرض الأذون المحفوظة، وتظهر إعانات الوفاة في مجموعة مستقلة.</p>
              </div>
              <Badge className="w-fit bg-red-50 text-red-700 hover:bg-red-50" data-testid="expense-voucher-actions-count">{expenses.length} مصروف</Badge>
            </div>
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2" data-testid="expense-voucher-category-panels">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4" data-testid="general-expense-voucher-panel">
                <h4 className="text-xl font-extrabold text-slate-950" data-testid="general-expense-voucher-title">مصروفات عمومية</h4>
                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="general-expense-voucher-date-filters"><div data-testid="general-expense-voucher-year-filter-wrapper"><Label data-testid="general-expense-voucher-year-filter-label">اختيار السنة</Label><select value={selectedGeneralVoucherYear} onChange={(event) => { setSelectedGeneralVoucherYear(event.target.value); setSelectedGeneralVoucherMonth(""); }} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-white px-4 text-sm font-extrabold text-slate-800 outline-none focus:border-slate-900" data-testid="general-expense-voucher-year-filter-select"><option value="" data-testid="general-expense-voucher-year-placeholder-option">اختر السنة</option>{generalVoucherGroups.map((group) => <option key={group.year} value={group.year} data-testid={`general-expense-voucher-year-option-${group.year}`}>{group.year}</option>)}</select></div><div data-testid="general-expense-voucher-month-filter-wrapper"><Label data-testid="general-expense-voucher-month-filter-label">اختيار الشهر</Label><select value={selectedGeneralVoucherMonth} onChange={(event) => setSelectedGeneralVoucherMonth(event.target.value)} disabled={!selectedGeneralVoucherYear} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-white px-4 text-sm font-extrabold text-slate-800 outline-none focus:border-slate-900 disabled:opacity-50" data-testid="general-expense-voucher-month-filter-select"><option value="" data-testid="general-expense-voucher-month-placeholder-option">اختر الشهر</option>{getMonthOptions(selectedGeneralVoucherGroup).map((month) => <option key={month} value={month} data-testid={`general-expense-voucher-month-option-${month}`}>{monthLabels[month] || month}</option>)}</select></div></div>
                <div className="mt-4" data-testid="general-expense-voucher-results">{!selectedGeneralVoucherYear ? <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center" data-testid="general-expense-voucher-year-required-state"><p className="font-extrabold text-slate-950">اختر السنة أولاً</p></div> : !selectedGeneralVoucherMonth ? <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center" data-testid="general-expense-voucher-month-required-state"><p className="font-extrabold text-slate-950">اختر الشهر أولاً</p></div> : selectedGeneralMonthItems.length ? <div className="grid grid-cols-1 gap-3" data-testid={`general-expense-voucher-month-grid-${selectedGeneralVoucherYear}-${selectedGeneralVoucherMonth}`}>{selectedGeneralMonthItems.map((item) => <button key={`voucher-${item.id}`} type="button" onClick={() => setSelectedExpense(item)} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-4 text-right transition-colors hover:border-slate-950" data-testid={`view-expense-voucher-button-${item.id}`}><span data-testid={`view-expense-voucher-button-${item.id}-text`}><span className="block text-sm font-extrabold text-slate-950">عرض إذن رقم {item.expense_number}</span><span className="mt-1 block text-xs font-bold text-slate-500">{methodLabels[item.payment_method]} — {formatCurrency(item.net_amount)}</span></span><Eye className="h-5 w-5 text-red-700" /></button>)}</div> : <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center" data-testid="general-expense-voucher-month-empty-state"><p className="font-extrabold text-slate-950">لا توجد أذون لهذا الشهر</p></div>}</div>
              </div>
              <div className="rounded-xl border border-red-100 bg-red-50 p-4" data-testid="death-benefit-voucher-panel">
                <h4 className="text-xl font-extrabold text-slate-950" data-testid="death-benefit-voucher-title">إعانات وفاة</h4>
                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="death-benefit-voucher-date-filters"><div data-testid="death-benefit-voucher-year-filter-wrapper"><Label data-testid="death-benefit-voucher-year-filter-label">اختيار السنة</Label><select value={selectedDeathBenefitYear} onChange={(event) => { setSelectedDeathBenefitYear(event.target.value); setSelectedDeathBenefitMonth(""); }} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-white px-4 text-sm font-extrabold text-slate-800 outline-none focus:border-slate-900" data-testid="death-benefit-voucher-year-filter-select"><option value="" data-testid="death-benefit-voucher-year-placeholder-option">اختر السنة</option>{deathBenefitGroups.map((group) => <option key={group.year} value={group.year} data-testid={`death-benefit-voucher-year-option-${group.year}`}>{group.year}</option>)}</select></div><div data-testid="death-benefit-voucher-month-filter-wrapper"><Label data-testid="death-benefit-voucher-month-filter-label">اختيار الشهر</Label><select value={selectedDeathBenefitMonth} onChange={(event) => setSelectedDeathBenefitMonth(event.target.value)} disabled={!selectedDeathBenefitYear} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-white px-4 text-sm font-extrabold text-slate-800 outline-none focus:border-slate-900 disabled:opacity-50" data-testid="death-benefit-voucher-month-filter-select"><option value="" data-testid="death-benefit-voucher-month-placeholder-option">اختر الشهر</option>{getMonthOptions(selectedDeathBenefitGroup).map((month) => <option key={month} value={month} data-testid={`death-benefit-voucher-month-option-${month}`}>{monthLabels[month] || month}</option>)}</select></div></div>
                <div className="mt-4" data-testid="death-benefit-voucher-results">{!selectedDeathBenefitYear ? <div className="rounded-xl border border-dashed border-red-200 bg-white p-6 text-center" data-testid="death-benefit-voucher-year-required-state"><p className="font-extrabold text-slate-950">اختر سنة إعانات الوفاة أولاً</p></div> : !selectedDeathBenefitMonth ? <div className="rounded-xl border border-dashed border-red-200 bg-white p-6 text-center" data-testid="death-benefit-voucher-month-required-state"><p className="font-extrabold text-slate-950">اختر شهر إعانات الوفاة أولاً</p></div> : selectedDeathBenefitMonthItems.length ? <div className="grid grid-cols-1 gap-3" data-testid={`death-benefit-voucher-month-grid-${selectedDeathBenefitYear}-${selectedDeathBenefitMonth}`}>{selectedDeathBenefitMonthItems.map((item) => <button key={`death-voucher-${item.id}`} type="button" onClick={() => setSelectedExpense(item)} className="flex items-center justify-between gap-3 rounded-lg border border-red-100 bg-white p-4 text-right transition-colors hover:border-red-700" data-testid={`view-death-benefit-voucher-button-${item.id}`}><span data-testid={`view-death-benefit-voucher-button-${item.id}-text`}><span className="block text-sm font-extrabold text-slate-950">عرض إعانة وفاة رقم {item.expense_number}</span><span className="mt-1 block text-xs font-bold text-slate-500">عضوية {item.membership_number} — {formatCurrency(item.net_amount)}</span></span><Eye className="h-5 w-5 text-red-700" /></button>)}</div> : <div className="rounded-xl border border-dashed border-red-200 bg-white p-6 text-center" data-testid="death-benefit-voucher-month-empty-state"><p className="font-extrabold text-slate-950">لا توجد إعانات وفاة لهذا الشهر</p></div>}</div>
              </div>
            </div>
          </section>
        )}
      </section>
      {selectedExpense && <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-950/60 p-4" data-testid="expense-invoice-modal-overlay"><section className="w-full max-w-6xl rounded-xl bg-white p-4 shadow-2xl" role="dialog" aria-modal="true" data-testid="expense-invoice-modal"><div className="mb-4 flex flex-wrap items-center justify-between gap-3 print:hidden" data-testid="expense-invoice-actions"><h3 className="text-2xl font-extrabold text-slate-950" data-testid="expense-invoice-modal-title">إذن صرف تفصيلي</h3><div className="flex flex-wrap gap-2" data-testid="expense-invoice-action-buttons"><ExportReportButtons title={`إذن صرف تفصيلي رقم ${selectedExpense.expense_number}`} fileName={`إذن-صرف-${selectedExpense.expense_number}`} selectors={["[data-testid='expense-voucher-document']"]} pdfTestId="print-expense-invoice-button" excelTestId="export-expense-invoice-excel-button" wordTestId="export-expense-invoice-word-button" /><Button type="button" onClick={() => setSelectedExpense(null)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="close-expense-invoice-button"><X className="h-4 w-4" /> إغلاق</Button></div></div><ExpenseVoucher item={selectedExpense} /></section></div>}
      {searchOpen && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 print:hidden" data-testid="expense-search-modal-overlay"><section className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-xl bg-white p-6 shadow-2xl" role="dialog" aria-modal="true" data-testid="expense-search-modal"><div className="mb-5 flex items-center justify-between gap-3" data-testid="expense-search-modal-heading"><div><p className="text-sm font-extrabold text-red-700" data-testid="expense-search-modal-eyebrow">نتيجة البحث</p><h3 className="text-2xl font-extrabold text-slate-950" data-testid="expense-search-modal-title">بيانات المصروف</h3></div><button type="button" onClick={() => setSearchOpen(false)} className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white" data-testid="close-expense-search-modal-button"><X className="h-4 w-4" /></button></div>{searchResults.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center" data-testid="expense-search-empty-state"><p className="text-xl font-extrabold text-slate-950" data-testid="expense-search-empty-title">لا توجد نتيجة مطابقة</p></div> : <div className="space-y-4" data-testid="expense-search-results-list">{searchResults.map((item) => <article key={item.id} className="rounded-xl border border-slate-200 p-4" data-testid={`expense-search-result-${item.id}`}><DetailGrid item={item} prefix={`expense-search-result-${item.id}`} /></article>)}</div>}</section></div>}
      <footer className="px-4 pb-5 print:hidden" data-testid="expenses-footer"><CreditLine testId="expenses-creator-credit" /></footer>
    </main>
  );
}