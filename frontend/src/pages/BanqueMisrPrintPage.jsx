import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Clock3, DatabaseZap, FileArchive, Home, Link2, LogOut, Printer, RefreshCcw, Save, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BankLogo } from "@/components/BankLogo";
import { CreditLine } from "@/components/CreditLine";
import { PrintOrientationToggle } from "@/components/PrintOrientationToggle";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import { usePrintOrientation, printWithOrientation } from "@/lib/printOrientation";

const sourceUrl = "https://www.banquemisr.ae/#tab-2";
const emptyExternalData = { rows: [], status: "NO_DATA" };
const emptyManualInputs = { bank_notes: "", checks_or_settlements_numbers: "", descriptive_adjustments: "", period_from: "", period_to: "", internal_approver_name: "", internal_signature: "", approval_code: "" };

const statusLabels = { saved_before_print: "محفوظ قبل الطباعة", printed: "تمت الطباعة", cancelled: "ملغي" };

const normalizeManualPayload = (manualInputs) => Object.fromEntries(Object.entries(manualInputs).map(([key, value]) => [key, value || null]));

const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));

const printable = (value, fallback = "-") => escapeHtml(value || fallback);

const printRequest = (request, markPrinted, orientation = "portrait") => {
  const printWindow = window.open("", "_blank", "width=1200,height=800");
  if (!printWindow) {
    printWithOrientation(orientation);
    return;
  }
  const manual = request.manual_inputs || {};
  const external = request.external_data || emptyExternalData;
  const rows = external.rows || [];
  const rowsHtml = rows.map((row, index) => `<tr><td>${index + 1}</td><td>${printable(row.section, "")}</td><td>${printable(row.title, "")}</td><td>${printable(row.currency)}</td><td>${printable(row.buy)}</td><td>${printable(row.sell)}</td><td>${printable(row.description, "")}</td></tr>`).join("");
  const emptyRowsHtml = `<tr><td colspan="7">لا توجد بيانات خارجية</td></tr>`;
  printWindow.document.write(`<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8" /><title>مطبوعة بنك مصر</title><style>@page{size:A4 ${orientation};margin:8mm}body{font-family:Tahoma,Arial,sans-serif;color:#111827;direction:rtl}h1,h2,h3,p{margin:0 0 8px}.meta{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:10px 0}.box{border:1px solid #94a3b8;padding:8px;border-radius:6px}table{width:100%;border-collapse:collapse;margin-top:10px}th,td{border:1px solid #111827;padding:6px;text-align:right;font-size:11px;vertical-align:top}th{background:#0f172a;color:white}.stamp{font-size:10px;color:#475569;margin-top:10px}</style></head><body><h1>مطبوعة بنك مصر - تقرير خارجي مدمج</h1><p>طلب رقم: ${printable(request.id, "")}</p><p>مصدر البيانات: ${printable(external.source_url || sourceUrl, "")}</p><p>وقت جلب البيانات: ${printable(external.fetched_at, "")}</p><section class="meta"><div class="box"><h3>بيانات ما قبل الطباعة</h3><p>الفترة: ${printable(manual.period_from)} إلى ${printable(manual.period_to)}</p><p>ملاحظات البنك: ${printable(manual.bank_notes)}</p><p>أرقام الشيكات/التسويات: ${printable(manual.checks_or_settlements_numbers)}</p><p>تعديلات وصفية: ${printable(manual.descriptive_adjustments)}</p></div><div class="box"><h3>الاعتماد الداخلي</h3><p>الاسم: ${printable(manual.internal_approver_name)}</p><p>التوقيع/الكود: ${printable(manual.internal_signature)}</p><p>كود الاعتماد: ${printable(manual.approval_code)}</p><p>حالة الطلب: ${printable(statusLabels[request.status] || request.status)}</p></div></section><table><thead><tr><th>م</th><th>القسم</th><th>البند</th><th>العملة</th><th>شراء</th><th>بيع</th><th>الوصف</th></tr></thead><tbody>${rowsHtml || emptyRowsHtml}</tbody></table><p class="stamp">تم إنشاء التقرير من طبقة دمج مستقلة: External Data + Manual Inputs. لا يوجد أثر على القيود أو التسويات.</p></body></html>`);
  printWindow.document.close();
  printWindow.focus();
  setTimeout(() => {
    printWindow.print();
    markPrinted?.();
  }, 250);
};

export default function BanqueMisrPrintPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [externalData, setExternalData] = useState(emptyExternalData);
  const [archive, setArchive] = useState([]);
  const [manualInputs, setManualInputs] = useState(emptyManualInputs);
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [loadingExternal, setLoadingExternal] = useState(true);
  const [saving, setSaving] = useState(false);
  const [orientation, setOrientation] = usePrintOrientation("portrait");

  const rows = useMemo(() => externalData.rows || [], [externalData.rows]);
  const loadExternalData = useCallback(async () => {
    setLoadingExternal(true);
    try {
      const response = await api.get("/bank-prints/banque-misr/external-data");
      setExternalData(response.data);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر جلب بيانات بنك مصر الخارجية");
      setExternalData(emptyExternalData);
    } finally {
      setLoadingExternal(false);
    }
  }, []);

  const loadArchive = useCallback(async () => {
    try {
      const response = await api.get("/bank-prints/requests?bank_id=banque-misr");
      setArchive(response.data);
    } catch {
      setArchive([]);
    }
  }, []);

  useEffect(() => { loadExternalData(); loadArchive(); }, [loadArchive, loadExternalData]);

  const updateManualInput = (field, value) => setManualInputs((current) => ({ ...current, [field]: value }));

  const markPrinted = async (requestId) => {
    try {
      const response = await api.patch(`/bank-prints/requests/${requestId}/status`, { status: "printed" });
      setSelectedRequest(response.data);
      loadArchive();
    } catch {
      toast.error("تم فتح الطباعة، لكن تعذر تحديث حالة الطلب في الأرشيف");
    }
  };

  const saveBeforePrint = async (event) => {
    event.preventDefault();
    if (manualInputs.period_from && manualInputs.period_to && manualInputs.period_from > manualInputs.period_to) {
      toast.error("تاريخ بداية الفترة يجب أن يكون قبل تاريخ النهاية");
      return;
    }
    setSaving(true);
    try {
      const response = await api.post("/bank-prints/banque-misr/requests", { manual_inputs: normalizeManualPayload(manualInputs) });
      setSelectedRequest(response.data);
      setArchive((current) => [response.data, ...current]);
      toast.success("تم حفظ طلب الطباعة قبل التنفيذ");
      printRequest(response.data, () => markPrinted(response.data.id));
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ طلب الطباعة");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f4f8fb] text-slate-950" data-testid="banque-misr-print-page">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur-xl print:hidden" data-testid="banque-misr-print-header">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8" data-testid="banque-misr-print-header-inner">
          <div className="flex items-center gap-3" data-testid="banque-misr-print-brand"><BankLogo bankId="banque-misr" bankName="بنك مصر" className="h-12 w-20 rounded-xl ring-2 ring-sky-100" testId="banque-misr-print-logo" /><div data-testid="banque-misr-print-brand-text"><p className="text-xs font-extrabold text-sky-700" data-testid="banque-misr-print-eyebrow">External Data Fetch → Pre-Print Form → Archive</p><h1 className="text-2xl font-black" data-testid="banque-misr-print-title">مطبوعات بنك مصر</h1></div></div>
          <div className="flex flex-wrap gap-3" data-testid="banque-misr-print-actions"><Badge className="bg-white text-slate-700" data-testid="banque-misr-print-user-badge">{user?.username}</Badge><Button asChild variant="outline" className="h-11 bg-white" data-testid="banque-misr-print-home-button"><Link to="/"><Home className="h-4 w-4" /> الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="banque-misr-print-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 bg-white" data-testid="banque-misr-print-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>

      <section className="mx-auto grid max-w-[1500px] grid-cols-1 gap-6 px-4 py-8 sm:px-6 lg:px-8 xl:grid-cols-[minmax(0,1fr)_390px]" data-testid="banque-misr-print-content">
        <div className="space-y-6" data-testid="banque-misr-print-main-column">
          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="banque-misr-external-section">
            <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between" data-testid="banque-misr-external-heading"><div data-testid="banque-misr-external-title-block"><p className="text-sm font-extrabold text-sky-700" data-testid="banque-misr-external-eyebrow">📥 جلب البيانات Auto</p><h2 className="text-3xl font-black" data-testid="banque-misr-external-title">بيانات بنك مصر جاهزة تلقائياً</h2><p className="mt-2 text-sm font-bold text-slate-500" data-testid="banque-misr-external-source"><Link2 className="ml-1 inline h-4 w-4" /> المصدر: {sourceUrl}</p></div><Button type="button" onClick={loadExternalData} disabled={loadingExternal} variant="outline" className="h-11 bg-white" data-testid="banque-misr-refresh-external-button"><RefreshCcw className="h-4 w-4" /> تحديث لحظي</Button></div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="banque-misr-external-stats"><article className="rounded-xl bg-sky-50 p-4 text-sky-950" data-testid="banque-misr-external-status-card"><p className="text-xs font-bold text-sky-700">حالة الجلب</p><p className="mt-2 text-xl font-black" data-testid="banque-misr-external-status">{loadingExternal ? "جاري الجلب" : externalData.status === "OK" ? "جاهز" : "لا توجد بيانات"}</p></article><article className="rounded-xl bg-emerald-50 p-4 text-emerald-950" data-testid="banque-misr-external-count-card"><p className="text-xs font-bold text-emerald-700">عدد البنود</p><p className="mt-2 text-xl font-black" data-testid="banque-misr-external-count">{rows.length}</p></article><article className="rounded-xl bg-slate-950 p-4 text-white" data-testid="banque-misr-external-time-card"><p className="text-xs font-bold text-slate-300">وقت الجلب</p><p className="mt-2 text-sm font-black" data-testid="banque-misr-external-fetched-at">{formatDateTime(externalData.fetched_at)}</p></article></div>
            <div className="mt-5 overflow-x-auto rounded-xl border border-slate-200" data-testid="banque-misr-external-table-wrapper"><Table data-testid="banque-misr-external-table"><TableHeader className="bg-slate-950"><TableRow><TableHead className="text-right text-white">القسم</TableHead><TableHead className="text-right text-white">البند</TableHead><TableHead className="text-right text-white">العملة</TableHead><TableHead className="text-right text-white">شراء</TableHead><TableHead className="text-right text-white">بيع</TableHead><TableHead className="text-right text-white">الوصف</TableHead></TableRow></TableHeader><TableBody>{loadingExternal && <TableRow data-testid="banque-misr-external-loading-row"><TableCell colSpan={6} className="py-8 text-center font-bold">جاري جلب البيانات من بنك مصر...</TableCell></TableRow>}{!loadingExternal && rows.length === 0 && <TableRow data-testid="banque-misr-external-empty-row"><TableCell colSpan={6} className="py-8 text-center font-bold text-slate-500">لا توجد بيانات مستخرجة من المصدر الخارجي حالياً</TableCell></TableRow>}{rows.map((row) => <TableRow key={row.id} data-testid={`banque-misr-external-row-${row.id}`}><TableCell className="font-bold" data-testid={`banque-misr-external-row-${row.id}-section`}>{row.section}</TableCell><TableCell className="font-black" data-testid={`banque-misr-external-row-${row.id}-title`}>{row.title}</TableCell><TableCell data-testid={`banque-misr-external-row-${row.id}-currency`}>{row.currency || "—"}</TableCell><TableCell data-testid={`banque-misr-external-row-${row.id}-buy`}>{row.buy || "—"}</TableCell><TableCell data-testid={`banque-misr-external-row-${row.id}-sell`}>{row.sell || "—"}</TableCell><TableCell data-testid={`banque-misr-external-row-${row.id}-description`}>{row.description || "—"}</TableCell></TableRow>)}</TableBody></Table></div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="banque-misr-form-section">
            <div className="mb-5" data-testid="banque-misr-form-heading"><p className="text-sm font-extrabold text-sky-700" data-testid="banque-misr-form-eyebrow">✍️ شاشة إدخال قبل الطباعة</p><h2 className="text-3xl font-black" data-testid="banque-misr-form-title">طبقة البيانات اليدوية</h2><p className="mt-2 text-sm font-bold text-slate-500" data-testid="banque-misr-form-subtitle">هذه البيانات تُدمج في التقرير فقط ولا تعدل المصدر الخارجي أو النظام المحاسبي.</p></div>
            <form onSubmit={saveBeforePrint} className="space-y-4" data-testid="banque-misr-preprint-form">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2" data-testid="banque-misr-period-grid"><div data-testid="banque-misr-period-from-wrapper"><Label data-testid="banque-misr-period-from-label">من فترة</Label><Input type="date" value={manualInputs.period_from} onChange={(event) => updateManualInput("period_from", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="banque-misr-period-from-input" /></div><div data-testid="banque-misr-period-to-wrapper"><Label data-testid="banque-misr-period-to-label">إلى فترة</Label><Input type="date" value={manualInputs.period_to} onChange={(event) => updateManualInput("period_to", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="banque-misr-period-to-input" /></div></div>
              <div data-testid="banque-misr-notes-wrapper"><Label data-testid="banque-misr-notes-label">ملاحظات البنك</Label><textarea value={manualInputs.bank_notes} onChange={(event) => updateManualInput("bank_notes", event.target.value)} className="mt-2 min-h-24 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-right text-sm font-bold" data-testid="banque-misr-bank-notes-textarea" /></div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2" data-testid="banque-misr-manual-grid"><div data-testid="banque-misr-checks-wrapper"><Label data-testid="banque-misr-checks-label">رقم الشيكات أو التسويات</Label><Input value={manualInputs.checks_or_settlements_numbers} onChange={(event) => updateManualInput("checks_or_settlements_numbers", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="banque-misr-checks-input" /></div><div data-testid="banque-misr-adjustments-wrapper"><Label data-testid="banque-misr-adjustments-label">تعديلات وصفية</Label><Input value={manualInputs.descriptive_adjustments} onChange={(event) => updateManualInput("descriptive_adjustments", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="banque-misr-adjustments-input" /></div></div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="banque-misr-approval-grid"><div data-testid="banque-misr-approver-wrapper"><Label data-testid="banque-misr-approver-label">اسم الاعتماد الداخلي</Label><Input value={manualInputs.internal_approver_name} onChange={(event) => updateManualInput("internal_approver_name", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="banque-misr-approver-input" /></div><div data-testid="banque-misr-signature-wrapper"><Label data-testid="banque-misr-signature-label">توقيع / كود</Label><Input value={manualInputs.internal_signature} onChange={(event) => updateManualInput("internal_signature", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="banque-misr-signature-input" /></div><div data-testid="banque-misr-approval-code-wrapper"><Label data-testid="banque-misr-approval-code-label">كود الاعتماد</Label><Input value={manualInputs.approval_code} onChange={(event) => updateManualInput("approval_code", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="banque-misr-approval-code-input" /></div></div>
              <Button type="submit" disabled={saving || loadingExternal} className="h-12 w-full rounded-lg bg-sky-800 text-white" data-testid="banque-misr-save-print-request-button"><Save className="h-4 w-4" /> حفظ الطلب ثم طباعة PDF</Button>
              <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2" data-testid="banque-misr-orientation-row"><span className="text-xs font-extrabold text-slate-600">اتجاه الورق عند الطباعة</span><PrintOrientationToggle orientation={orientation} onChange={setOrientation} testIdPrefix="banque-misr-orientation" /></div>
            </form>
          </section>
        </div>

        <aside className="space-y-5" data-testid="banque-misr-print-sidebar">
          <section className="rounded-2xl border border-sky-200 bg-sky-50 p-5 shadow-sm" data-testid="banque-misr-merge-card"><h3 className="text-xl font-black text-sky-950" data-testid="banque-misr-merge-title">🔗 Merge Engine</h3><div className="mt-4 space-y-3 text-sm font-bold text-sky-900" data-testid="banque-misr-merge-steps"><p data-testid="banque-misr-merge-step-1"><DatabaseZap className="ml-1 inline h-4 w-4" /> البيانات الخارجية لا تتعدل.</p><p data-testid="banque-misr-merge-step-2"><ShieldCheck className="ml-1 inline h-4 w-4" /> البيانات اليدوية طبقة منفصلة.</p><p data-testid="banque-misr-merge-step-3"><Printer className="ml-1 inline h-4 w-4" /> الناتج تقرير موحد قابل للطباعة.</p></div></section>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" data-testid="banque-misr-archive-section"><div className="mb-4 flex items-center justify-between gap-3" data-testid="banque-misr-archive-heading"><div data-testid="banque-misr-archive-title-block"><p className="text-xs font-extrabold text-sky-700" data-testid="banque-misr-archive-eyebrow">Print Requests Archive</p><h3 className="text-xl font-black" data-testid="banque-misr-archive-title">أرشيف الطلبات</h3></div><Button type="button" onClick={loadArchive} variant="outline" className="h-10 bg-white" data-testid="banque-misr-refresh-archive-button"><RefreshCcw className="h-4 w-4" /></Button></div><div className="max-h-[520px] space-y-3 overflow-auto" data-testid="banque-misr-archive-list">{archive.length === 0 && <p className="rounded-lg bg-slate-50 p-4 text-sm font-bold text-slate-500" data-testid="banque-misr-archive-empty">لا توجد طلبات محفوظة بعد</p>}{archive.map((request) => <article key={request.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4" data-testid={`banque-misr-archive-item-${request.id}`}><div className="flex items-start justify-between gap-2" data-testid={`banque-misr-archive-item-${request.id}-heading`}><div><p className="text-xs font-bold text-slate-500" data-testid={`banque-misr-archive-item-${request.id}-date`}><Clock3 className="ml-1 inline h-3 w-3" /> {formatDateTime(request.created_at)}</p><p className="mt-1 text-sm font-black" data-testid={`banque-misr-archive-item-${request.id}-status`}>{statusLabels[request.status] || request.status}</p></div><FileArchive className="h-5 w-5 text-sky-700" /></div><p className="mt-2 truncate text-xs font-bold text-slate-500" data-testid={`banque-misr-archive-item-${request.id}-id`}>{request.id}</p><div className="mt-3 flex gap-2" data-testid={`banque-misr-archive-item-${request.id}-actions`}><Button type="button" variant="outline" onClick={() => setSelectedRequest(request)} className="h-9 flex-1 bg-white" data-testid={`banque-misr-view-request-${request.id}-button`}>مراجعة</Button><Button type="button" onClick={() => printRequest(request, () => markPrinted(request.id), orientation)} className="h-9 flex-1 bg-slate-950 text-white" data-testid={`banque-misr-reprint-request-${request.id}-button`}>إعادة طباعة</Button></div></article>)}</div></section>
          {selectedRequest && <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm" data-testid="banque-misr-selected-request-card"><h3 className="text-xl font-black text-emerald-950" data-testid="banque-misr-selected-request-title">آخر طلب محفوظ</h3><p className="mt-2 text-sm font-bold text-emerald-900" data-testid="banque-misr-selected-request-id">{selectedRequest.id}</p><p className="mt-1 text-sm font-bold text-emerald-900" data-testid="banque-misr-selected-request-status">{statusLabels[selectedRequest.status] || selectedRequest.status}</p><Button type="button" onClick={() => printRequest(selectedRequest, () => markPrinted(selectedRequest.id), orientation)} className="mt-4 h-10 w-full bg-emerald-800 text-white" data-testid="banque-misr-selected-request-print-button"><Printer className="h-4 w-4" /> طباعة الطلب</Button></section>}
        </aside>
      </section>
      <footer className="px-4 pb-5 print:hidden" data-testid="banque-misr-print-footer"><CreditLine testId="banque-misr-print-creator-credit" /></footer>
    </main>
  );
}