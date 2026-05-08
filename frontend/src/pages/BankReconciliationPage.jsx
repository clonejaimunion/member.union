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
import { bankPalette, fallbackBanks } from "@/lib/banks";
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

  const totals = useMemo(() => {
    const outstanding = outstandingChecks.reduce((sum, item) => sum + Number(sanitizeDecimalInput(item.amount) || 0), 0);
    const collection = collectionChecks.reduce((sum, item) => sum + Number(sanitizeDecimalInput(item.amount) || 0), 0);
    const calculated = Number(bookBalance || 0) + outstanding - collection;
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
      setBookBalance(String(response.data.book_balance ?? 0));
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

  const escapePrintHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  const absoluteAssetUrl = (value) => {
    if (!value) return "";
    try {
      return new URL(value, window.location.origin).href;
    } catch {
      return value;
    }
  };

  const periodMeta = (label) => {
    const text = String(label || "").trim();
    const months = ["يناير", "فبراير", "مارس", "أبريل", "ابريل", "مايو", "يونيو", "يوليو", "أغسطس", "اغسطس", "سبتمبر", "أكتوبر", "اكتوبر", "نوفمبر", "ديسمبر"];
    const foundMonth = months.find((month) => text.includes(month));
    const yearMatch = text.match(/(19|20)\d{2}/);
    return { month: foundMonth || text || "—", year: yearMatch?.[0] || "—" };
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
    setTimeout(() => {
      const printWindow = window.open("", "_blank", "width=900,height=1200");
      if (!printWindow) {
        window.print();
        return;
      }
      const meta = periodMeta(item.period_label);
      const logoSource = absoluteAssetUrl(bank.logo_url || bankPalette[bank.id]?.logo);
      const logo = logoSource ? `<div class="memo-logo-box"><img class="memo-logo" src="${escapePrintHtml(logoSource)}" alt="${escapePrintHtml(bank.name)}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';" /><div class="memo-logo-fallback">${escapePrintHtml(bank.name)}</div></div>` : `<div class="memo-logo-box"><div class="memo-logo-fallback" style="display:flex">${escapePrintHtml(bank.name)}</div></div>`;
      const rowsHtml = (rows) => (rows || []).length ? rows.map((row) => `<tr><td>${escapePrintHtml(formatCheckDate(row.check_date))}</td><td>${escapePrintHtml(row.check_number)}</td><td>${escapePrintHtml(formatEgpText(row.amount))}</td></tr>`).join("") : `<tr><td colspan="3" class="empty-cell">—</td></tr>`;
      const checksSection = (title, rows, total) => `<section class="checks-section"><h3>${escapePrintHtml(title)}</h3><table><thead><tr><th>التاريخ يوم/شهر</th><th>رقم الشيك</th><th>المبلغ</th></tr></thead><tbody>${rowsHtml(rows)}<tr class="total-row"><td colspan="2">الإجمالي</td><td>${escapePrintHtml(formatEgpText(total))}</td></tr></tbody></table></section>`;
      printWindow.document.write(`<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8" /><title>مذكرة التسوية</title><style>@page{size:A4 portrait;margin:5mm}html,body{margin:0;padding:0;background:#fff;direction:rtl;font-family:Tahoma,Arial,sans-serif;color:#111827}body{width:200mm;height:287mm;overflow:hidden}.memo-page{position:relative;box-sizing:border-box;width:190mm;height:277mm;max-height:277mm;overflow:hidden;padding:10mm 12mm 8mm;margin:0 auto;background:#fff}.memo-header{position:relative;min-height:38mm;text-align:center}.memo-logo-box{position:absolute;left:0;top:0;width:42mm;height:24mm;display:flex;align-items:center;justify-content:center;border:1px solid #e5e7eb;background:#fff}.memo-logo{width:40mm;height:22mm;object-fit:contain;display:block}.memo-logo-fallback{display:none;width:100%;height:100%;align-items:center;justify-content:center;text-align:center;font-weight:900;font-size:13px;line-height:1.35;color:#111827;padding:2mm}.memo-logo-text{position:absolute;left:0;top:0;width:38mm;border:1px solid #ddd;padding:3mm;font-weight:700;text-align:center}.org-title{font-size:15px;line-height:1.5;font-weight:900;margin:0;padding:0 42mm 0 20mm}.bank-line{font-size:10px;font-weight:700;color:#4b5563;margin:2mm 0 0}.period-line{font-size:13px;font-weight:900;margin:2mm 0 0}.balance{margin:15mm 0 7mm;text-align:right;padding-right:8mm}.balance .label{font-size:13px;font-weight:900}.balance .value{font-size:16px;font-weight:900;margin-top:2mm}.checks-section{padding:0 8mm;margin-top:7mm;break-inside:avoid;page-break-inside:avoid}.checks-section h3{font-size:12px;font-weight:900;margin:0 0 2mm;text-align:right}table{width:100%;border-collapse:collapse;table-layout:fixed;break-inside:avoid;page-break-inside:avoid}th,td{border:1px solid #d7d7d7;padding:1.3mm 2mm;font-size:9px;line-height:1.15;text-align:right;vertical-align:middle}th{font-weight:900;background:#fff}.total-row td{border-top:1.6px solid #111827;font-weight:900}.empty-cell{text-align:center;color:#9ca3af}.footer{position:absolute;left:20mm;bottom:15mm;text-align:left;direction:rtl}.footer .status{font-size:13px;font-weight:900}.footer .amount{font-size:10px;font-weight:700;color:#374151;margin-top:1mm}@media print{html,body{width:200mm;height:287mm;overflow:hidden}.memo-page{page-break-after:avoid;break-after:avoid}.memo-logo-box{print-color-adjust:exact;-webkit-print-color-adjust:exact}}</style></head><body><main class="memo-page"><header class="memo-header">${logo}<h1 class="org-title">${escapePrintHtml(item.administration || administration || currentAdministrationName)}</h1><p class="bank-line">${escapePrintHtml(bank.name)}</p><p class="period-line">${escapePrintHtml(`${meta.month} ${meta.year}`)}</p></header><section class="balance"><p class="label">الرصيد</p><p class="value">${escapePrintHtml(formatEgpText(item.book_balance))}</p></section>${checksSection("يضاف: شيكات لم تقدم للصرف", item.outstanding_checks, item.total_outstanding_checks)}${checksSection("يخصم: شيكات تحت التحصيل", item.collection_checks, item.total_collection_checks)}<footer class="footer"><p class="status">${escapePrintHtml(item.is_matched ? "الرصيد مطابق" : "الرصيد غير مطابق")}</p><p class="amount">${escapePrintHtml(formatEgpText(item.calculated_balance))}</p></footer></main></body></html>`);
      printWindow.document.close();
      printWindow.focus();
      const images = Array.from(printWindow.document.images || []);
      const waitForImages = Promise.all(images.map((image) => image.complete ? Promise.resolve() : new Promise((resolve) => {
        image.onload = resolve;
        image.onerror = resolve;
      })));
      waitForImages.finally(() => setTimeout(() => {
        printWindow.print();
        printWindow.close();
      }, 250));
    }, 120);
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
    <section className="reconciliation-memo-checks-section space-y-2" data-testid={`${testId}-print-section`}>
      <h3 className="reconciliation-memo-section-title text-lg font-extrabold text-slate-950" data-testid={`${testId}-print-title`}>{title}</h3>
      <div className="reconciliation-memo-table-wrapper overflow-hidden bg-white" data-testid={`${testId}-table-wrapper`}>
        <Table className="reconciliation-memo-check-table" data-testid={`${testId}-table`}>
          <TableHeader>
            <TableRow className="hover:bg-transparent" data-testid={`${testId}-header-row`}>
              <TableHead className="text-right font-extrabold text-slate-950">التاريخ يوم/شهر</TableHead>
              <TableHead className="text-right font-extrabold text-slate-950">رقم الشيك</TableHead>
              <TableHead className="text-right font-extrabold text-slate-950">المبلغ</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(rows || []).length === 0 && <TableRow data-testid={`${testId}-empty-row`}><TableCell colSpan={3} className="text-center text-slate-400">—</TableCell></TableRow>}
            {(rows || []).map((row, index) => (
              <TableRow key={`${testId}-${index}`} data-testid={`${testId}-row-${index}`}>
                <TableCell data-testid={`${testId}-row-${index}-date`}>{formatCheckDate(row.check_date)}</TableCell>
                <TableCell className="font-extrabold" data-testid={`${testId}-row-${index}-number`}>{row.check_number}</TableCell>
                <TableCell data-testid={`${testId}-row-${index}-amount`}>{formatEgpText(row.amount)}</TableCell>
              </TableRow>
            ))}
            <TableRow className="reconciliation-memo-total-row bg-white hover:bg-white" data-testid={`${testId}-total-row`}>
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
              printSelectors={["[data-testid='reconciliation-print-report']"]}
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
              <Label data-testid="book-balance-label">رصيد التسوية البنكية التلقائي قبل تسويات الشيكات</Label>
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
              <div className="rounded-lg bg-emerald-50 p-4" data-testid="breakdown-opening-balance-card"><p className="text-xs font-bold text-emerald-700">الرصيد الافتتاحي</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.opening_balance || 0)}</p></div>
              <div className="rounded-lg bg-emerald-50 p-4" data-testid="breakdown-monthly-revenues-card"><p className="text-xs font-bold text-emerald-700">الإيرادات خلال الفترة</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.monthly_revenues || 0)}</p></div>
              <div className="rounded-lg bg-emerald-50 p-4" data-testid="breakdown-deposit-settlements-card"><p className="text-xs font-bold text-emerald-700">فوائد الودائع الشهرية داخل الفترة</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.monthly_deposit_interest ?? balanceBreakdown?.deposit_settlements ?? 0)}</p></div>
              <div className="rounded-lg bg-emerald-100 p-4" data-testid="breakdown-total-receipts-card"><p className="text-xs font-bold text-emerald-800">إجمالي الزيادة قبل المصروفات</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.gross_total || 0)}</p></div>
              <div className="rounded-lg bg-red-50 p-4" data-testid="breakdown-bank-expenses-card"><p className="text-xs font-bold text-red-700">المصروفات البنكية خلال الفترة</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.bank_expenses || 0)}</p></div>
              <div className="rounded-lg bg-red-50 p-4" data-testid="breakdown-monthly-expenses-card"><p className="text-xs font-bold text-red-700">إجمالي مصروفات البنك خلال الفترة</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.monthly_expenses || 0)}</p></div>
              <div className="rounded-lg bg-slate-100 p-4" data-testid="breakdown-book-balance-card"><p className="text-xs font-bold text-slate-700">الرصيد قبل تسويات الشيكات</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.book_balance || 0)}</p></div>
              <div className="rounded-lg bg-emerald-50 p-4" data-testid="breakdown-checks-not-presented-card"><p className="text-xs font-bold text-emerald-700">يضاف: شيكات لم تقدم للصرف</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.checks_not_presented || 0)}</p></div>
              <div className="rounded-lg bg-red-50 p-4" data-testid="breakdown-checks-under-collection-card"><p className="text-xs font-bold text-red-700">يخصم: شيكات تحت التحصيل</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.checks_under_collection || 0)}</p></div>
              <div className="rounded-lg bg-red-100 p-4" data-testid="breakdown-total-payments-card"><p className="text-xs font-bold text-red-800">إجمالي المصروفات قبل تسويات الشيكات</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.total_payments || 0)}</p></div>
              <div className="rounded-lg bg-slate-950 p-4 text-white" data-testid="breakdown-reconciliation-balance-card"><p className="text-xs font-bold text-slate-200">رصيد التسوية البنكية في نهاية الشهر</p><p className="mt-1 font-extrabold">{formatEgpText(balanceBreakdown?.reconciliation_balance || 0)}</p></div>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-4 md:grid-cols-4" data-testid="reconciliation-live-summary">
            <div className="rounded-xl bg-slate-950 p-5 text-white" data-testid="summary-book-balance-card"><p className="text-xs font-bold text-slate-300">الرصيد التلقائي قبل الشيكات</p><p className="mt-2 text-xl font-extrabold">{formatEgpText(bookBalance)}</p></div>
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
          <section className="reconciliation-memo-page space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm print:flex print:min-h-[95vh] print:flex-col print:border-0 print:shadow-none sm:p-8" data-testid="reconciliation-print-report">
            <div className="flex flex-col gap-3 print:hidden lg:flex-row lg:items-center lg:justify-between" data-testid="reconciliation-preview-actions">
              <Badge className="w-fit bg-sky-50 px-3 py-1 text-sky-800 hover:bg-sky-50" data-testid="reconciliation-preview-badge">معاينة قبل الطباعة والاعتماد</Badge>
              <Button type="button" onClick={() => printReconciliation(activeReconciliation)} className="h-10 rounded-lg bg-slate-950 text-white" data-testid="reconciliation-preview-print-button"><Printer className="h-4 w-4" /> طباعة هذه المعاينة</Button>
            </div>
            <div className="reconciliation-memo-sheet bg-white" data-testid="reconciliation-print-sheet-frame">
              <div className="reconciliation-memo-header relative text-center" data-testid="reconciliation-print-header">
                <div className="reconciliation-memo-logo absolute left-0 top-0" data-testid="reconciliation-print-bank-logo">
                  <BankLogo bankId={bank.id} bankName={bank.name} logoUrl={bank.logo_url} className="h-16 w-28" testId="reconciliation-print-bank-logo-mark" />
                </div>
                <h2 className="reconciliation-memo-org-title font-black text-slate-950" data-testid="reconciliation-print-organization">{activeReconciliation.administration || administration || currentAdministrationName}</h2>
                <p className="reconciliation-memo-bank-line font-bold text-slate-600" data-testid="reconciliation-print-meta-bank">{bank.name}</p>
                <p className="reconciliation-memo-period font-extrabold text-slate-800" data-testid="reconciliation-print-period">{periodMeta(activeReconciliation.period_label).month} {periodMeta(activeReconciliation.period_label).year}</p>
                <span className="sr-only" data-testid="reconciliation-print-meta-month">{periodMeta(activeReconciliation.period_label).month}</span>
                <span className="sr-only" data-testid="reconciliation-print-meta-year">{periodMeta(activeReconciliation.period_label).year}</span>
                <span className="sr-only" data-testid="reconciliation-print-meta-created">{formatDateTime(activeReconciliation.created_at)}</span>
              </div>
              <div className="reconciliation-memo-balance text-right" data-testid="reconciliation-print-formula-book-balance">
                <p className="reconciliation-memo-balance-label font-black text-slate-950">الرصيد</p>
                <p className="reconciliation-memo-balance-value font-black text-slate-950">{formatEgpText(activeReconciliation.book_balance)}</p>
              </div>
            </div>
            <ChecksTable title="يضاف: شيكات لم تقدم للصرف" rows={activeReconciliation.outstanding_checks || []} testId="outstanding-print" total={activeReconciliation.total_outstanding_checks} />
            <ChecksTable title="يخصم: شيكات تحت التحصيل" rows={activeReconciliation.collection_checks || []} testId="collection-print" total={activeReconciliation.total_collection_checks} />
            <div className="hidden" data-testid="reconciliation-print-formula-wrapper"><span data-testid="reconciliation-print-formula-table" /><span data-testid="reconciliation-print-formula-outstanding">{formatEgpText(activeReconciliation.total_outstanding_checks)}</span><span data-testid="reconciliation-print-formula-collection">{formatEgpText(activeReconciliation.total_collection_checks)}</span><span data-testid="reconciliation-print-formula-calculated">{formatEgpText(activeReconciliation.calculated_balance)}</span><span data-testid="reconciliation-print-formula-bank-statement">{formatEgpText(activeReconciliation.bank_statement_balance)}</span><span data-testid="reconciliation-print-formula-difference">{formatEgpText(activeReconciliation.difference)}</span></div>
            <div className="reconciliation-memo-footer flex justify-start pt-8" data-testid="print-status-wrapper">
              <div className="text-left" data-testid="print-status"><p className="reconciliation-memo-status font-extrabold text-slate-950" data-testid="print-status-text">{activeReconciliation.is_matched ? "الرصيد مطابق" : "الرصيد غير مطابق"}</p><p className="reconciliation-memo-final-balance mt-1 font-bold text-slate-700" data-testid="print-matched-balance-value">{formatEgpText(activeReconciliation.calculated_balance)}</p></div>
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
