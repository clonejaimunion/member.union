import { useCallback, useEffect, useMemo, useState } from "react";
import { Eye, Pencil, Printer, Save, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { BankShell } from "@/components/BankShell";
import { ExportReportButtons } from "@/components/ExportReportButtons";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fallbackBanks } from "@/lib/banks";
import { formatDateTime, sanitizeDayMonthInput, sanitizeDecimalInput, sanitizeDigitsInput } from "@/lib/format";
import { useAuth } from "@/contexts/AuthContext";
import { useAppSettings } from "@/contexts/AppSettingsContext";
import { BankLogo } from "@/components/BankLogo";

const currentDayMonth = () => {
  const now = new Date();
  return `${String(now.getDate()).padStart(2, "0")}/${String(now.getMonth() + 1).padStart(2, "0")}`;
};

const emptyCheck = () => ({ check_number: "", amount: "", check_date: currentDayMonth() });

export default function BankReconciliationPage() {
  const { bankId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { settings } = useAppSettings();
  const unionFullName = settings.organizations?.["general-union"]?.name || "النقابة العامة للعاملين بالزراعة والري";
  const socialName = settings.organizations?.["social-solidarity"]?.login_label || settings.organizations?.["social-solidarity"]?.name || "مشروع التكافل الاجتماعي";
  const currentAdministrationName = user?.organization_id === "social-solidarity" ? socialName : unionFullName;
  const [banks, setBanks] = useState(fallbackBanks);
  const [periodLabel, setPeriodLabel] = useState("");
  const [administration, setAdministration] = useState(currentAdministrationName);
  const [bookBalance, setBookBalance] = useState("");
  const [balanceBreakdown, setBalanceBreakdown] = useState(null);
  const [bankStatementBalance, setBankStatementBalance] = useState("");
  const [outstandingChecks, setOutstandingChecks] = useState([emptyCheck()]);
  const [collectionChecks, setCollectionChecks] = useState([emptyCheck()]);
  const [reconciliations, setReconciliations] = useState([]);
  const [activeReconciliation, setActiveReconciliation] = useState(null);
  const [editingReconciliationId, setEditingReconciliationId] = useState(null);
  const [selectedHistoryYear, setSelectedHistoryYear] = useState("");
  const [saving, setSaving] = useState(false);
  const [syncingChecks, setSyncingChecks] = useState(false);
  const [committedFormSnapshot, setCommittedFormSnapshot] = useState("");
  const [leavePromptOpen, setLeavePromptOpen] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState(null);

  const bank = banks.find((item) => item.id === bankId) || fallbackBanks.find((item) => item.id === bankId) || fallbackBanks[0];
  const canEditReconciliation = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.manage_reconciliations;
  const organizationPrintName = (value) => value === socialName ? `${unionFullName} - ${socialName}` : unionFullName;

  const totals = useMemo(() => {
    const outstanding = outstandingChecks.reduce((sum, item) => sum + Number(sanitizeDecimalInput(item.amount) || 0), 0);
    const collection = collectionChecks.reduce((sum, item) => sum + Number(sanitizeDecimalInput(item.amount) || 0), 0);
    const calculated = Number(bookBalance || 0);
    const difference = calculated - Number(bankStatementBalance || 0);
    return {
      outstanding,
      collection,
      calculated,
      difference,
      matched: Math.abs(difference) < 0.01,
    };
  }, [bookBalance, bankStatementBalance, outstandingChecks, collectionChecks]);

  const getReconciliationYear = (item) => {
    const labelMatch = String(item.period_label || "").match(/(20\d{2}|19\d{2})/);
    if (labelMatch) return labelMatch[1];
    return String(new Date(item.created_at).getFullYear());
  };

  const historyYears = useMemo(() => {
    const years = [...new Set(reconciliations.map(getReconciliationYear))].sort((a, b) => Number(b) - Number(a));
    return years;
  }, [reconciliations]);

  const buildFormSnapshot = useCallback((data) => JSON.stringify({
    periodLabel: data.periodLabel,
    administration: data.administration,
    bookBalance: data.bookBalance,
    bankStatementBalance: data.bankStatementBalance,
    outstandingChecks: data.outstandingChecks,
    collectionChecks: data.collectionChecks,
  }), []);

  const currentFormSnapshot = useMemo(() => buildFormSnapshot({
    periodLabel,
    administration,
    bookBalance,
    bankStatementBalance,
    outstandingChecks,
    collectionChecks,
  }), [administration, bankStatementBalance, bookBalance, buildFormSnapshot, collectionChecks, outstandingChecks, periodLabel]);

  const hasUnsavedChanges = canEditReconciliation && Boolean(committedFormSnapshot) && currentFormSnapshot !== committedFormSnapshot;

  const filteredReconciliations = useMemo(() => {
    if (!selectedHistoryYear) return [];
    return reconciliations.filter((item) => getReconciliationYear(item) === selectedHistoryYear);
  }, [reconciliations, selectedHistoryYear]);

  const loadReconciliations = useCallback(() => {
    api.get(`/banks/${bankId}/reconciliations`).then((response) => {
      setReconciliations(response.data);
    }).catch(() => {
      setReconciliations([]);
      setActiveReconciliation(null);
    });
  }, [bankId]);

  const loadBookBalance = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (periodLabel) params.set("period_label", periodLabel);
      const response = await api.get(`/banks/${bankId}/reconciliation-balance${params.toString() ? `?${params.toString()}` : ""}`);
      setBookBalance(String(response.data.reconciliation_balance ?? 0));
      setBalanceBreakdown(response.data);
    } catch (error) {
      toast.error("تعذر تحميل رصيد التسوية البنكية تلقائياً");
    }
  }, [bankId, periodLabel]);

  const formatSourceCheckDate = useCallback((value) => {
    if (!value) return currentDayMonth();
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return currentDayMonth();
    return `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}`;
  }, []);

  const rowsFromExpenseChecks = useCallback((items) => {
    const rows = items
      .filter((item) => item.payment_method === "check" && (item.bank_payment_status || "not_presented") === "not_presented")
      .filter((item) => item.check_number || Number(item.net_amount || item.gross_amount || 0) > 0)
      .map((item) => ({
        check_number: item.check_number || "",
        amount: String(item.net_amount ?? item.gross_amount ?? ""),
        check_date: formatSourceCheckDate(item.issued_at),
      }));
    return rows;
  }, [formatSourceCheckDate]);

  const rowsFromRevenueChecks = useCallback((items) => {
    const rows = items
      .filter((item) => item.collection_method === "check" && (item.bank_collection_status || "under_collection") === "under_collection")
      .filter((item) => item.check_number || Number(item.amount || 0) > 0)
      .map((item) => ({
        check_number: item.check_number || "",
        amount: String(item.amount ?? ""),
        check_date: formatSourceCheckDate(item.dated || item.issued_at),
      }));
    return rows;
  }, [formatSourceCheckDate]);

  const syncChecksFromRecords = useCallback(async (type = "both", silent = false) => {
    setSyncingChecks(true);
    try {
      const requests = [];
      if (type === "both" || type === "outstanding") requests.push(api.get(`/expenses?bank_id=${bankId}&payment_method=check`));
      if (type === "both" || type === "collection") requests.push(api.get(`/revenues?bank_id=${bankId}&collection_method=check`));
      const responses = await Promise.all(requests);
      let responseIndex = 0;
      if (type === "both" || type === "outstanding") {
        setOutstandingChecks(rowsFromExpenseChecks(responses[responseIndex].data));
        responseIndex += 1;
      }
      if (type === "both" || type === "collection") {
        setCollectionChecks(rowsFromRevenueChecks(responses[responseIndex].data));
      }
      if (!silent) toast.success("تم تحديث بيانات الشيكات تلقائياً");
    } catch (error) {
      if (!silent) toast.error("تعذر تحديث الشيكات من الإيرادات والمصروفات");
    } finally {
      setSyncingChecks(false);
    }
  }, [bankId, rowsFromExpenseChecks, rowsFromRevenueChecks]);

  useEffect(() => {
    api.get("/banks").then((response) => setBanks(response.data)).catch(() => setBanks([]));
    loadReconciliations();
    loadBookBalance();
  }, [bankId, loadReconciliations, loadBookBalance]);

  useEffect(() => {
    if (!editingReconciliationId) setAdministration(currentAdministrationName);
  }, [currentAdministrationName, editingReconciliationId]);

  useEffect(() => {
    if (canEditReconciliation && !editingReconciliationId) syncChecksFromRecords("both", true);
  }, [canEditReconciliation, editingReconciliationId, syncChecksFromRecords]);

  useEffect(() => {
    if (!committedFormSnapshot) setCommittedFormSnapshot(currentFormSnapshot);
  }, [committedFormSnapshot, currentFormSnapshot]);

  const requestNavigation = useCallback((action) => {
    if (!hasUnsavedChanges) {
      action();
      return true;
    }
    setPendingNavigation(() => action);
    setLeavePromptOpen(true);
    return false;
  }, [hasUnsavedChanges]);

  useEffect(() => {
    window.__bankAppConfirmNavigation = requestNavigation;
    return () => {
      if (window.__bankAppConfirmNavigation === requestNavigation) delete window.__bankAppConfirmNavigation;
    };
  }, [requestNavigation]);

  useEffect(() => {
    if (!hasUnsavedChanges) return undefined;
    const handleBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

  useEffect(() => {
    const handleDocumentClick = (event) => {
      if (!hasUnsavedChanges || event.defaultPrevented) return;
      const anchor = event.target.closest?.("a[href]");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#") || anchor.target === "_blank") return;
      event.preventDefault();
      event.stopPropagation();
      const url = new URL(anchor.href);
      const nextPath = `${url.pathname}${url.search}${url.hash}`;
      requestNavigation(() => navigate(nextPath));
    };
    document.addEventListener("click", handleDocumentClick, true);
    return () => document.removeEventListener("click", handleDocumentClick, true);
  }, [hasUnsavedChanges, location.pathname, navigate, requestNavigation]);

  const normalizeDayMonthToDateTime = (value) => {
    if (!value) return `${new Date().getFullYear()}-01-01T00:00:00`;
    const sanitized = sanitizeDayMonthInput(value);
    if (/^\d{1,2}\/\d{1,2}$/.test(sanitized)) {
      const [dayValue, monthValue] = sanitized.split("/");
      const day = String(Math.min(Math.max(Number(dayValue), 1), 31)).padStart(2, "0");
      const month = String(Math.min(Math.max(Number(monthValue), 1), 12)).padStart(2, "0");
      return `${new Date().getFullYear()}-${month}-${day}T00:00:00`;
    }
    return sanitized || `${new Date().getFullYear()}-01-01T00:00:00`;
  };

  const cleanChecks = (checks) => checks
    .filter((item) => item.check_number || Number(sanitizeDecimalInput(item.amount) || 0) > 0)
    .map((item) => ({
      check_number: sanitizeDigitsInput(item.check_number),
      amount: Number(sanitizeDecimalInput(item.amount) || 0),
      check_date: normalizeDayMonthToDateTime(item.check_date),
    }));

  const fillFormFromReconciliation = (item) => {
    const nextOutstandingChecks = (item.outstanding_checks?.length ? item.outstanding_checks : [emptyCheck()]).map((check) => ({
      check_number: check.check_number || "",
      amount: String(check.amount ?? ""),
      check_date: formatCheckDate(check.check_date),
    }));
    const nextCollectionChecks = (item.collection_checks?.length ? item.collection_checks : [emptyCheck()]).map((check) => ({
      check_number: check.check_number || "",
      amount: String(check.amount ?? ""),
      check_date: formatCheckDate(check.check_date),
    }));
    setEditingReconciliationId(item.id);
    setActiveReconciliation(item);
    setPeriodLabel(item.period_label || "");
    setAdministration(currentAdministrationName);
    setBookBalance(String(item.book_balance ?? ""));
    setBalanceBreakdown(item.balance_breakdown || null);
    setBankStatementBalance(String(item.bank_statement_balance ?? ""));
    setOutstandingChecks(nextOutstandingChecks);
    setCollectionChecks(nextCollectionChecks);
    setCommittedFormSnapshot(buildFormSnapshot({
      periodLabel: item.period_label || "",
      administration: currentAdministrationName,
      bookBalance: String(item.book_balance ?? ""),
      bankStatementBalance: String(item.bank_statement_balance ?? ""),
      outstandingChecks: nextOutstandingChecks,
      collectionChecks: nextCollectionChecks,
    }));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const resetForm = () => {
    const nextOutstandingChecks = [emptyCheck()];
    const nextCollectionChecks = [emptyCheck()];
    setEditingReconciliationId(null);
    setPeriodLabel("");
    setAdministration(currentAdministrationName);
    setBalanceBreakdown(null);
    loadBookBalance();
    setBankStatementBalance("");
    setOutstandingChecks(nextOutstandingChecks);
    setCollectionChecks(nextCollectionChecks);
    setCommittedFormSnapshot(buildFormSnapshot({
      periodLabel: "",
      administration: currentAdministrationName,
      bookBalance: "",
      bankStatementBalance: "",
      outstandingChecks: nextOutstandingChecks,
      collectionChecks: nextCollectionChecks,
    }));
    setTimeout(() => syncChecksFromRecords("both", true), 0);
  };

  const saveReconciliation = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = {
        period_label: periodLabel,
        administration,
        book_balance: Number(bookBalance || 0),
        bank_statement_balance: Number(bankStatementBalance || 0),
        outstanding_checks: cleanChecks(outstandingChecks),
        collection_checks: cleanChecks(collectionChecks),
      };
      const response = editingReconciliationId
        ? await api.put(`/banks/${bankId}/reconciliations/${editingReconciliationId}`, payload)
        : await api.post(`/banks/${bankId}/reconciliations`, payload);
      setActiveReconciliation(response.data);
      setCommittedFormSnapshot(currentFormSnapshot);
      toast.success(editingReconciliationId ? "تم تعديل مذكرة التسوية" : "تم حفظ مذكرة التسوية البنكية");
      setEditingReconciliationId(null);
      loadReconciliations();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ التسوية البنكية");
    } finally {
      setSaving(false);
    }
  };

  const formatEgpText = (value) => `${new Intl.NumberFormat("ar-EG", { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(Number(value || 0))} جنيه مصري`;

  const formatCheckDate = (value) => {
    if (!value) return "—";
    if (/^\d{1,2}\/\d{1,2}$/.test(value)) return sanitizeDayMonthInput(value);
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return sanitizeDayMonthInput(value);
    return `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}`;
  };

  const deleteReconciliation = async (item) => {
    const confirmed = window.confirm(`هل أنت متأكد من حذف مذكرة التسوية ${item.period_label || "المحددة"}؟`);
    if (!confirmed) return;
    try {
      await api.delete(`/banks/${bankId}/reconciliations/${item.id}`);
      toast.success("تم حذف مذكرة التسوية");
      loadReconciliations();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حذف مذكرة التسوية");
    }
  };

  const previewReconciliation = (item) => {
    setActiveReconciliation(item);
    setTimeout(() => document.querySelector('[data-testid="reconciliation-print-report"]')?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  };

  const printReconciliation = (item) => {
    setActiveReconciliation(item);
    setTimeout(() => window.print(), 120);
  };

  const confirmLeaveWithoutSaving = () => {
    setLeavePromptOpen(false);
    setCommittedFormSnapshot(currentFormSnapshot);
    const action = pendingNavigation;
    setPendingNavigation(null);
    if (action) action();
  };

  const cancelLeavePrompt = () => {
    setLeavePromptOpen(false);
    setPendingNavigation(null);
  };

  const renderCheckEditor = ({ title, type, checks }) => (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid={`${type}-checks-section`}>
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between" data-testid={`${type}-checks-heading`}>
        <h3 className="text-xl font-extrabold text-slate-950" data-testid={`${type}-checks-title`}>{title}</h3>
        <div className="flex flex-wrap gap-2 print:hidden" data-testid={`${type}-checks-actions`}>
          <Button type="button" onClick={() => syncChecksFromRecords(type)} disabled={syncingChecks} variant="outline" className="h-10 rounded-lg bg-emerald-50 text-emerald-800 hover:bg-emerald-100" data-testid={`sync-${type}-checks-button`}>
            <Save className="h-4 w-4" /> {type === "outstanding" ? "تحديث من المصروفات" : "تحديث من الإيرادات"}
          </Button>
        </div>
      </div>
      <div className="space-y-3" data-testid={`${type}-checks-list`}>
        {checks.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-5 text-center text-sm font-bold text-slate-500" data-testid={`${type}-checks-empty-state`}>
            {type === "outstanding" ? "لا توجد شيكات لم تقدم للصرف في المصروفات" : "لا توجد شيكات تحت التحصيل في الإيرادات"}
          </div>
        )}
        {checks.map((item, index) => (
          <div key={`${type}-${index}`} className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 md:grid-cols-[1fr_1fr_1fr_auto]" data-testid={`${type}-check-row-${index}`}>
            <div className="space-y-2" data-testid={`${type}-check-${index}-number-wrapper`}>
              <Label data-testid={`${type}-check-${index}-number-label`}>رقم الشيك</Label>
              <Input readOnly aria-readonly="true" inputMode="numeric" dir="ltr" value={item.check_number} className="h-11 rounded-lg bg-slate-100 text-right font-extrabold text-slate-700" data-testid={`${type}-check-${index}-number-input`} />
            </div>
            <div className="space-y-2" data-testid={`${type}-check-${index}-amount-wrapper`}>
              <Label data-testid={`${type}-check-${index}-amount-label`}>مبلغ الشيك</Label>
              <Input readOnly aria-readonly="true" inputMode="decimal" dir="ltr" value={item.amount} className="h-11 rounded-lg bg-slate-100 text-right font-extrabold text-slate-700" data-testid={`${type}-check-${index}-amount-input`} />
            </div>
            <div className="space-y-2" data-testid={`${type}-check-${index}-date-wrapper`}>
              <Label data-testid={`${type}-check-${index}-date-label`}>تاريخ الشيك</Label>
              <Input readOnly aria-readonly="true" inputMode="numeric" dir="ltr" value={item.check_date} placeholder="يوم/شهر" maxLength={5} className="h-11 rounded-lg bg-slate-100 text-center font-extrabold tracking-wider text-slate-700" data-testid={`${type}-check-${index}-date-input`} />
            </div>
            <div className="mt-7 hidden h-11 md:block" data-testid={`${type}-check-${index}-protected-spacer`} />
          </div>
        ))}
      </div>
    </section>
  );

  const ChecksTable = ({ title, rows, testId, total }) => (
    <section className="space-y-3" data-testid={`${testId}-print-section`}>
      <h3 className="text-xl font-extrabold text-slate-950" data-testid={`${testId}-print-title`}>{title}</h3>
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white" data-testid={`${testId}-table-wrapper`}>
        <Table data-testid={`${testId}-table`}>
          <TableHeader className="bg-slate-950">
            <TableRow className="hover:bg-slate-950" data-testid={`${testId}-header-row`}>
              <TableHead className="text-right font-extrabold text-white">التاريخ يوم/شهر</TableHead>
              <TableHead className="text-right font-extrabold text-white">رقم الشيك</TableHead>
              <TableHead className="text-right font-extrabold text-white">المبلغ</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(rows || []).map((row, index) => (
              <TableRow key={`${testId}-${index}`} data-testid={`${testId}-row-${index}`}>
                <TableCell data-testid={`${testId}-row-${index}-date`}>{formatCheckDate(row.check_date)}</TableCell>
                <TableCell className="font-extrabold" data-testid={`${testId}-row-${index}-number`}>{row.check_number}</TableCell>
                <TableCell data-testid={`${testId}-row-${index}-amount`}>{formatEgpText(row.amount)}</TableCell>
              </TableRow>
            ))}
            <TableRow className="bg-slate-50 hover:bg-slate-50" data-testid={`${testId}-total-row`}>
              <TableCell colSpan={2} className="font-extrabold text-slate-950" data-testid={`${testId}-total-label`}>الإجمالي</TableCell>
              <TableCell className="font-extrabold text-slate-950" data-testid={`${testId}-total-amount`}>{formatEgpText(total)}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </section>
  );

  return (
    <BankShell>
      <div className="space-y-6" data-testid="bank-reconciliation-page">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8 print:hidden" data-testid="reconciliation-heading-section">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm font-extrabold text-emerald-700" data-testid="reconciliation-eyebrow">مذكرة تسوية</p>
              <h2 className="text-3xl font-extrabold text-slate-950 sm:text-4xl" data-testid="reconciliation-title">مذكرة تسوية حساب - {bank.name}</h2>
            </div>
            <ExportReportButtons
              title={`مذكرة تسوية حساب - ${bank.name} - ${activeReconciliation?.period_label || ""}`}
              fileName={`مذكرة-تسوية-${bank.name}-${activeReconciliation?.period_label || ""}`}
              selectors={["[data-testid='reconciliation-print-report']"]}
              disabled={!activeReconciliation}
              pdfTestId="print-reconciliation-pdf-button"
              excelTestId="export-reconciliation-excel-button"
              wordTestId="export-reconciliation-word-button"
            />
          </div>
        </section>

        {canEditReconciliation && <form onSubmit={saveReconciliation} className="space-y-6 print:hidden" data-testid="reconciliation-form">
          <section className="grid grid-cols-1 gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-3" data-testid="reconciliation-balances-section">
            <div className="space-y-2" data-testid="reconciliation-administration-wrapper">
              <Label data-testid="reconciliation-administration-label">الإدارة</Label>
              <select value={administration} onChange={(event) => setAdministration(event.target.value)} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold text-slate-800 outline-none focus:border-slate-900" data-testid="reconciliation-administration-select">
                <option value={currentAdministrationName} data-testid={`reconciliation-administration-option-${user?.organization_id || "general-union"}`}>{currentAdministrationName}</option>
              </select>
            </div>
            <div className="space-y-2" data-testid="reconciliation-period-wrapper">
              <Label data-testid="reconciliation-period-label">الفترة / الشهر</Label>
              <Input value={periodLabel} onChange={(event) => setPeriodLabel(event.target.value)} placeholder="مثال: يناير 2025" className="h-12 rounded-lg bg-slate-50 text-right" data-testid="reconciliation-period-input" />
            </div>
            <div className="space-y-2" data-testid="book-balance-wrapper">
              <Label data-testid="book-balance-label">رصيد التسوية البنكية التلقائي</Label>
              <Input readOnly aria-readonly="true" type="number" step="0.01" value={bookBalance} className="h-12 rounded-lg bg-slate-100 text-right font-extrabold text-slate-700" data-testid="book-balance-input" />
            </div>
            <div className="space-y-2" data-testid="bank-statement-balance-wrapper">
              <Label data-testid="bank-statement-balance-label">الرصيد - كشف الحساب البنكي</Label>
              <Input type="number" step="0.01" value={bankStatementBalance} onChange={(event) => setBankStatementBalance(event.target.value)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="bank-statement-balance-input" />
            </div>
          </section>

          {renderCheckEditor({ title: "شيكات لم تقدم للصرف", type: "outstanding", checks: outstandingChecks })}
          {renderCheckEditor({ title: "شيكات تحت التحصيل", type: "collection", checks: collectionChecks })}

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="reconciliation-balance-breakdown-section">
            <div className="mb-4 flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between" data-testid="reconciliation-balance-breakdown-heading">
              <div data-testid="reconciliation-balance-breakdown-title-block"><h3 className="text-xl font-extrabold text-slate-950" data-testid="reconciliation-balance-breakdown-title">تفصيل رصيد التسوية البنكية التلقائي</h3><p className="text-sm font-bold text-slate-500" data-testid="reconciliation-balance-breakdown-period">الفترة: {balanceBreakdown?.period_from || "—"} إلى {balanceBreakdown?.period_to || "—"}</p></div>
              <Button type="button" onClick={loadBookBalance} variant="outline" className="h-10 bg-white" data-testid="refresh-reconciliation-balance-button"><Save className="h-4 w-4" /> تحديث الرصيد</Button>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4" data-testid="reconciliation-balance-breakdown-grid">
              <div className="rounded-lg bg-emerald-50 p-4" data-testid="breakdown-opening-balance-card"><p className="text-xs font-bold text-emerald-700">رصيد أول الشهر</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.opening_balance || 0)}</p></div>
              <div className="rounded-lg bg-emerald-50 p-4" data-testid="breakdown-monthly-revenues-card"><p className="text-xs font-bold text-emerald-700">المقبوضات المسجلة بالبنك</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.monthly_revenues || 0)}</p></div>
              <div className="rounded-lg bg-emerald-50 p-4" data-testid="breakdown-deposit-settlements-card"><p className="text-xs font-bold text-emerald-700">فوائد ودائع شهرية</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.monthly_deposit_interest ?? balanceBreakdown?.deposit_settlements ?? 0)}</p></div>
              <div className="rounded-lg bg-emerald-100 p-4" data-testid="breakdown-total-receipts-card"><p className="text-xs font-bold text-emerald-800">إجمالي المقبوضات والحركات المدينة</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.total_receipts || 0)}</p></div>
              <div className="rounded-lg bg-red-50 p-4" data-testid="breakdown-monthly-expenses-card"><p className="text-xs font-bold text-red-700">المدفوعات المسجلة بالبنك</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.monthly_expenses || 0)}</p></div>
              <div className="rounded-lg bg-red-50 p-4" data-testid="breakdown-bank-expenses-card"><p className="text-xs font-bold text-red-700">المصروفات البنكية</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.bank_expenses || 0)}</p></div>
              <div className="rounded-lg bg-red-100 p-4" data-testid="breakdown-total-payments-card"><p className="text-xs font-bold text-red-800">إجمالي المدفوعات والحركات الدائنة</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.total_payments || 0)}</p></div>
              <div className="rounded-lg bg-slate-100 p-4" data-testid="breakdown-book-balance-card"><p className="text-xs font-bold text-slate-700">الرصيد بعد معادلة الشهر</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.book_balance || 0)}</p></div>
              <div className="rounded-lg bg-slate-950 p-4 text-white" data-testid="breakdown-reconciliation-balance-card"><p className="text-xs font-bold text-slate-200">رصيد التسوية البنكية في نهاية الشهر</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.reconciliation_balance || 0)}</p></div>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-4 md:grid-cols-4" data-testid="reconciliation-live-summary">
            <div className="rounded-xl bg-slate-950 p-5 text-white" data-testid="summary-book-balance-card"><p className="text-xs font-bold text-slate-300">رصيد التسوية البنكية</p><p className="mt-2 text-xl font-extrabold">{formatEgpText(bookBalance)}</p></div>
            <div className="rounded-xl bg-emerald-50 p-5 text-emerald-900" data-testid="summary-outstanding-card"><p className="text-xs font-bold text-emerald-700">إجمالي شيكات لم تقدم</p><p className="mt-2 text-xl font-extrabold">{formatEgpText(totals.outstanding)}</p></div>
            <div className="rounded-xl bg-amber-50 p-5 text-amber-950" data-testid="summary-collection-card"><p className="text-xs font-bold text-amber-700">إجمالي تحت التحصيل</p><p className="mt-2 text-xl font-extrabold">{formatEgpText(totals.collection)}</p></div>
            <div className={`rounded-xl p-5 ${totals.matched ? "bg-emerald-700 text-white" : "bg-red-700 text-white"}`} data-testid="summary-matched-card"><p className="text-xs font-bold opacity-80">الحالة</p><p className="mt-2 text-xl font-extrabold">{totals.matched ? "الرصيد مطابق" : "الرصيد غير مطابق"}</p></div>
          </section>

          <div className="flex flex-col gap-3 sm:flex-row" data-testid="reconciliation-form-actions">
            <Button type="submit" disabled={saving} className="h-12 rounded-lg bg-slate-950 px-7 text-white hover:bg-slate-800" data-testid="save-reconciliation-button">
              <Save className="h-4 w-4" /> {saving ? "جاري الحفظ..." : editingReconciliationId ? "حفظ تعديل مذكرة التسوية" : "حفظ مذكرة التسوية"}
            </Button>
            {editingReconciliationId && (
              <Button type="button" onClick={resetForm} variant="outline" className="h-12 rounded-lg bg-white px-7" data-testid="cancel-edit-reconciliation-button">
                <X className="h-4 w-4" /> إلغاء التعديل
              </Button>
            )}
          </div>
        </form>}

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:hidden" data-testid="reconciliations-history-section">
          <h3 className="mb-4 text-xl font-extrabold text-slate-950" data-testid="reconciliations-history-title">مذكرات محفوظة</h3>
          <div className="mb-5 max-w-xs" data-testid="reconciliations-year-filter-wrapper">
            <Label data-testid="reconciliations-year-filter-label">اختيار السنة</Label>
            <select value={selectedHistoryYear} onChange={(event) => setSelectedHistoryYear(event.target.value)} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm font-extrabold text-slate-800 outline-none focus:border-slate-900" data-testid="reconciliations-year-filter-select">
              <option value="" data-testid="reconciliations-year-filter-placeholder-option">اختر السنة لعرض المذكرات</option>
              {historyYears.map((year) => (
                <option key={year} value={year} data-testid={`reconciliations-year-filter-option-${year}`}>{year}</option>
              ))}
            </select>
          </div>
          {!selectedHistoryYear ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center" data-testid="reconciliations-history-year-required-state">
              <p className="text-lg font-extrabold text-slate-950" data-testid="reconciliations-history-year-required-title">اختر السنة أولاً</p>
              <p className="mt-2 text-sm font-semibold text-slate-500" data-testid="reconciliations-history-year-required-description">لن تظهر المذكرات المحفوظة إلا بعد تحديد سنة من القائمة.</p>
            </div>
          ) : filteredReconciliations.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center" data-testid="reconciliations-history-empty-year-state">
              <p className="text-lg font-extrabold text-slate-950" data-testid="reconciliations-history-empty-year-title">لا توجد مذكرات لهذه السنة</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3" data-testid="reconciliations-history-grid">
              {filteredReconciliations.map((item) => (
              <div key={item.id} className={`rounded-xl border p-4 transition-transform hover:-translate-y-0.5 ${activeReconciliation?.id === item.id ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-slate-50 text-slate-800 hover:bg-white"}`} data-testid={`reconciliation-history-card-${item.id}`}>
                <button type="button" onClick={() => setActiveReconciliation(item)} className="w-full text-right" data-testid={`reconciliation-history-button-${item.id}`}>
                  <p className="text-xs font-bold opacity-70" data-testid={`reconciliation-history-button-${item.id}-period`}>{item.period_label || "بدون فترة"}</p>
                  <p className="mt-1 text-lg font-extrabold" data-testid={`reconciliation-history-button-${item.id}-status`}>{item.status_text}</p>
                  <p className="mt-1 text-sm font-bold opacity-80" data-testid={`reconciliation-history-button-${item.id}-balance`}>{formatEgpText(item.calculated_balance)}</p>
                </button>
                {user?.role === "admin" && (
                  <button type="button" onClick={() => deleteReconciliation(item)} className="mt-3 inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 text-sm font-extrabold text-red-700 hover:bg-red-100" data-testid={`delete-reconciliation-button-${item.id}`}>
                    <Trash2 className="h-4 w-4" /> حذف مذكرة التسوية
                  </button>
                )}
                <div className="mt-3 grid grid-cols-1 gap-2" data-testid={`reconciliation-history-actions-${item.id}`}>
                  <button type="button" onClick={() => previewReconciliation(item)} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm font-extrabold text-slate-800 hover:bg-slate-100" data-testid={`preview-reconciliation-button-${item.id}`}>
                    <Eye className="h-4 w-4" /> معاينة
                  </button>
                  <button type="button" onClick={() => printReconciliation(item)} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 text-sm font-extrabold text-emerald-700 hover:bg-emerald-100" data-testid={`print-saved-reconciliation-button-${item.id}`}>
                    <Printer className="h-4 w-4" /> طباعة
                  </button>
                  {canEditReconciliation && (
                    <button type="button" onClick={() => fillFormFromReconciliation(item)} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 text-sm font-extrabold text-amber-700 hover:bg-amber-100" data-testid={`edit-reconciliation-button-${item.id}`}>
                      <Pencil className="h-4 w-4" /> تعديل
                    </button>
                  )}
                </div>
              </div>
              ))}
            </div>
          )}
        </section>

        {activeReconciliation && (
          <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:flex print:min-h-[95vh] print:flex-col print:border-0 print:shadow-none sm:p-8" data-testid="reconciliation-print-report">
            <div className="relative text-center" data-testid="reconciliation-print-header">
              <div className="absolute left-0 top-0" data-testid="reconciliation-print-bank-logo">
                <BankLogo bankId={bank.id} bankName={bank.name} logoUrl={bank.logo_url} className="h-16 w-28" testId="reconciliation-print-bank-logo-mark" />
              </div>
              <p className="text-base font-extrabold text-slate-700" data-testid="reconciliation-print-organization">{organizationPrintName(activeReconciliation.administration)}</p>
              <p className="mt-2 text-lg font-bold text-slate-600" data-testid="reconciliation-print-period">{activeReconciliation.period_label || "—"}</p>
            </div>
            <div className="grid grid-cols-1 gap-4" data-testid="reconciliation-print-kpis">
              <div className="rounded-xl bg-slate-50 p-4" data-testid="print-book-balance"><p className="text-xs font-bold text-slate-500">رصيد التسوية البنكية</p><p className="text-xl font-extrabold">{formatEgpText(activeReconciliation.book_balance)}</p></div>
            </div>
            {activeReconciliation.balance_breakdown && <div className="grid grid-cols-2 gap-2 text-sm" data-testid="print-balance-breakdown"><div className="rounded-lg border p-2" data-testid="print-breakdown-opening">رصيد أول الشهر: {formatEgpText(activeReconciliation.balance_breakdown.opening_balance)}</div><div className="rounded-lg border p-2" data-testid="print-breakdown-revenues">المقبوضات المسجلة بالبنك: {formatEgpText(activeReconciliation.balance_breakdown.monthly_revenues)}</div><div className="rounded-lg border p-2" data-testid="print-breakdown-deposits">فوائد ودائع شهرية: {formatEgpText(activeReconciliation.balance_breakdown.monthly_deposit_interest ?? activeReconciliation.balance_breakdown.deposit_settlements ?? 0)}</div><div className="rounded-lg border p-2 font-extrabold" data-testid="print-breakdown-total-receipts">إجمالي المقبوضات والحركات المدينة: {formatEgpText(activeReconciliation.balance_breakdown.total_receipts)}</div><div className="rounded-lg border p-2" data-testid="print-breakdown-expenses">المدفوعات المسجلة بالبنك: {formatEgpText(activeReconciliation.balance_breakdown.monthly_expenses)}</div><div className="rounded-lg border p-2" data-testid="print-breakdown-bank-expenses">المصروفات البنكية: {formatEgpText(activeReconciliation.balance_breakdown.bank_expenses)}</div><div className="rounded-lg border p-2 font-extrabold" data-testid="print-breakdown-total-payments">إجمالي المدفوعات والحركات الدائنة: {formatEgpText(activeReconciliation.balance_breakdown.total_payments)}</div><div className="rounded-lg border p-2 font-extrabold" data-testid="print-breakdown-final">رصيد التسوية: {formatEgpText(activeReconciliation.balance_breakdown.reconciliation_balance)}</div></div>}
            {activeReconciliation.outstanding_checks?.length > 0 && <ChecksTable title="يخصم: شيكات لم تقدم للصرف" rows={activeReconciliation.outstanding_checks} testId="outstanding-print" total={activeReconciliation.total_outstanding_checks} />}
            {activeReconciliation.collection_checks?.length > 0 && <ChecksTable title="يضاف: شيكات تحت التحصيل" rows={activeReconciliation.collection_checks} testId="collection-print" total={activeReconciliation.total_collection_checks} />}
            <div className="flex justify-end pt-6 print:mt-auto print:justify-start" data-testid="print-status-wrapper">
              <div className={`rounded-xl p-4 text-center print:bg-transparent print:p-0 ${activeReconciliation.is_matched ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"}`} data-testid="print-status"><p className="text-xl font-extrabold" data-testid="print-status-text">{activeReconciliation.status_text}</p>{activeReconciliation.is_matched && <p className="mt-2 text-2xl font-black text-slate-950 print:mt-1" data-testid="print-matched-balance-value">{formatEgpText(activeReconciliation.calculated_balance)}</p>}</div>
            </div>
          </section>
        )}

        {leavePromptOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 p-4 print:hidden" data-testid="unsaved-reconciliation-modal-overlay">
            <section className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 text-right shadow-2xl" role="dialog" aria-modal="true" data-testid="unsaved-reconciliation-modal">
              <h3 className="text-2xl font-extrabold text-slate-950" data-testid="unsaved-reconciliation-modal-title">لم يتم حفظ التغييرات</h3>
              <p className="mt-3 text-sm font-semibold leading-7 text-slate-600" data-testid="unsaved-reconciliation-modal-description">يوجد تعديل داخل مذكرة التسوية لم يتم حفظه بعد.</p>
              <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="unsaved-reconciliation-modal-actions">
                <Button type="button" onClick={confirmLeaveWithoutSaving} className="h-12 rounded-lg bg-red-700 text-white hover:bg-red-800" data-testid="confirm-leave-without-saving-button">موافق على عدم الحفظ</Button>
                <Button type="button" onClick={cancelLeavePrompt} variant="outline" className="h-12 rounded-lg bg-white" data-testid="cancel-leave-and-save-button">تراجع للحفظ</Button>
              </div>
            </section>
          </div>
        )}
      </div>
    </BankShell>
  );
}
