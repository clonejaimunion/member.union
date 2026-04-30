import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, BarChart3, FileUp, Home, LogOut, Printer, Search, UserRoundPlus, UsersRound, X } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

const today = new Date();
const currentYear = today.getFullYear();
const currentMonth = today.getMonth() + 1;
const yearOptions = Array.from({ length: 50 }, (_, index) => currentYear - 10 + index);
const monthOptions = Array.from({ length: 12 }, (_, index) => index + 1);
const initialForm = { governorate: "", union_committee: "", membership_number: "", name: "", national_id: "", birth_date: "", address: "", death_beneficiary: "" };

export default function MembershipPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [form, setForm] = useState(initialForm);
  const [importForm, setImportForm] = useState({ governorate: "", governorate_new: "", union_committee: "", union_committee_new: "", file: null });
  const [importResult, setImportResult] = useState(null);
  const [importPreview, setImportPreview] = useState(null);
  const [members, setMembers] = useState([]);
  const [searchName, setSearchName] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [selectedMember, setSelectedMember] = useState(null);
  const [filters, setFilters] = useState({ governorate: "", union_committee: "", year: String(currentYear), month: String(currentMonth) });
  const [retirementRows, setRetirementRows] = useState([]);
  const [currentSize, setCurrentSize] = useState(null);
  const [annualYear, setAnnualYear] = useState(String(currentYear));
  const [annualReport, setAnnualReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const canCreate = user?.role === "admin" || user?.permissions?.enter_deposits || user?.permissions?.manage_users;

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [membersResponse, sizeResponse] = await Promise.all([
        api.get("/memberships"),
        api.get("/memberships/current-size"),
      ]);
      setMembers(membersResponse.data);
      setCurrentSize(sizeResponse.data);
    } catch (error) {
      toast.error("تعذر تحميل بيانات العضوية");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const governorates = useMemo(() => [...new Set(members.map((item) => item.governorate).filter(Boolean))].sort(), [members]);
  const committees = useMemo(() => [...new Set(members.filter((item) => !filters.governorate || item.governorate === filters.governorate).map((item) => item.union_committee).filter(Boolean))].sort(), [members, filters.governorate]);
  const selectedImportGovernorate = importForm.governorate === "__new__" ? importForm.governorate_new.trim() : importForm.governorate;
  const selectedImportCommittee = importForm.union_committee === "__new__" ? importForm.union_committee_new.trim() : importForm.union_committee;
  const importCommittees = useMemo(() => [...new Set(members.filter((item) => selectedImportGovernorate && item.governorate === selectedImportGovernorate).map((item) => item.union_committee).filter(Boolean))].sort(), [members, selectedImportGovernorate]);

  const updateForm = (field, value) => setForm((current) => ({ ...current, [field]: field === "national_id" || field === "membership_number" ? value.replace(/[^0-9٠-٩]/g, "") : value }));
  const updateImportForm = (field, value) => setImportForm((current) => ({ ...current, [field]: value, ...(field === "governorate" ? { union_committee: "", union_committee_new: "" } : {}) }));

  const createMember = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await api.post("/memberships", form);
      toast.success("تم تسجيل العضوية الجديدة");
      setForm(initialForm);
      await loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تسجيل العضوية");
    } finally {
      setSaving(false);
    }
  };

  const importMembers = async (event) => {
    event.preventDefault();
    if (!importForm.file) return toast.error("اختر ملف PDF أو Word أو Excel");
    if (!selectedImportGovernorate) return toast.error("اختر المحافظة أو أضف محافظة جديدة");
    if (!selectedImportCommittee) return toast.error("اختر اللجنة أو أضف لجنة جديدة");
    setSaving(true);
    try {
      const payload = new FormData();
      payload.append("governorate", selectedImportGovernorate);
      payload.append("union_committee", selectedImportCommittee);
      payload.append("file", importForm.file);
      const response = await api.post("/memberships/import/preview", payload, { headers: { "Content-Type": "multipart/form-data" } });
      setImportPreview(response.data);
      toast.success(`تم تجهيز المراجعة: ${response.data.accepted_count} صف مقبول و ${response.data.skipped_count} صف مرفوض`);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر استيراد بيانات العضوية");
    } finally {
      setSaving(false);
    }
  };

  const commitImportPreview = async () => {
    if (!importPreview?.preview_id) return;
    setSaving(true);
    try {
      const response = await api.post("/memberships/import/commit", { preview_id: importPreview.preview_id });
      setImportResult(response.data);
      setImportPreview(null);
      setImportForm((current) => ({ ...current, file: null }));
      toast.success(`تم اعتماد ${response.data.imported_count} عضوية وتجاهل ${response.data.skipped_count} صف`);
      await loadData();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر اعتماد الاستيراد");
    } finally {
      setSaving(false);
    }
  };

  const searchMembers = async () => {
    if (!searchName.trim()) return toast.error("أدخل الاسم للبحث");
    try {
      const response = await api.get(`/memberships/search?name=${encodeURIComponent(searchName.trim())}`);
      setSearchResults(response.data);
      if (!response.data.length) toast.info("لا توجد بيانات مطابقة");
    } catch (error) {
      toast.error("تعذر تنفيذ البحث");
    }
  };

  const applyRetirementFilter = async () => {
    try {
      const params = new URLSearchParams({ year: filters.year, month: filters.month });
      if (filters.governorate) params.set("governorate", filters.governorate);
      if (filters.union_committee) params.set("union_committee", filters.union_committee);
      const response = await api.get(`/memberships/retirement?${params.toString()}`);
      setRetirementRows(response.data);
      if (!response.data.length) toast.info("لا يوجد أعضاء خروج معاش في الفترة المختارة");
    } catch (error) {
      toast.error("تعذر تطبيق عامل التصفية");
    }
  };

  const loadAnnualReport = async () => {
    try {
      const response = await api.get(`/memberships/annual-report?year=${annualYear}`);
      setAnnualReport(response.data);
      if (!response.data.rows.length) toast.info("لا توجد بيانات في التقرير السنوي");
    } catch (error) {
      toast.error("تعذر تحميل التقرير السنوي");
    }
  };

  const printSelected = () => window.print();
  const printRetirement = () => window.print();

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="membership-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="membership-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8" data-testid="membership-header-inner">
          <div className="flex items-center gap-3" data-testid="membership-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="membership-brand-icon"><UsersRound className="h-5 w-5" /></div><div data-testid="membership-title-block"><p className="text-xs font-extrabold text-emerald-700" data-testid="membership-eyebrow">مشروع التكافل الاجتماعي</p><h1 className="text-2xl font-extrabold" data-testid="membership-title">العضوية</h1></div></div>
          <div className="flex flex-wrap items-center gap-3" data-testid="membership-actions"><Badge className="bg-white text-slate-700" data-testid="membership-organization-badge">{user?.organization_name}</Badge><Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="membership-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button type="button" onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="membership-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button type="button" onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="membership-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 sm:px-6 xl:grid-cols-[0.85fr_1.15fr] lg:px-8" data-testid="membership-content">
        {canCreate && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="membership-create-section">
          <div className="mb-5 flex items-center gap-3" data-testid="membership-create-heading"><UserRoundPlus className="h-6 w-6 text-emerald-700" /><h2 className="text-2xl font-extrabold" data-testid="membership-create-title">تسجيل عضوية جديدة</h2></div>
          <form onSubmit={createMember} className="grid grid-cols-1 gap-4 md:grid-cols-2" data-testid="membership-create-form">
            <div data-testid="member-governorate-wrapper"><Label data-testid="member-governorate-label">محافظة</Label><Input value={form.governorate} onChange={(event) => updateForm("governorate", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="member-governorate-input" /></div>
            <div data-testid="member-committee-wrapper"><Label data-testid="member-committee-label">اللجنة النقابية</Label><Input value={form.union_committee} onChange={(event) => updateForm("union_committee", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="member-committee-input" /></div>
            <div data-testid="member-number-wrapper"><Label data-testid="member-number-label">رقم العضوية</Label><Input value={form.membership_number} onChange={(event) => updateForm("membership_number", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="member-number-input" /></div>
            <div data-testid="member-name-wrapper"><Label data-testid="member-name-label">الاسم</Label><Input value={form.name} onChange={(event) => updateForm("name", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="member-name-input" /></div>
            <div data-testid="member-national-id-wrapper"><Label data-testid="member-national-id-label">الرقم القومي</Label><Input value={form.national_id} maxLength={14} onChange={(event) => updateForm("national_id", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="member-national-id-input" /></div>
            <div data-testid="member-birth-date-wrapper"><Label data-testid="member-birth-date-label">تاريخ الميلاد</Label><Input type="date" value={form.birth_date} onChange={(event) => updateForm("birth_date", event.target.value)} required className="mt-2 h-11 bg-slate-50" data-testid="member-birth-date-input" /></div>
            <div className="md:col-span-2" data-testid="member-address-wrapper"><Label data-testid="member-address-label">العنوان</Label><Input value={form.address} onChange={(event) => updateForm("address", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="member-address-input" /></div>
            <div className="md:col-span-2" data-testid="member-death-beneficiary-wrapper"><Label data-testid="member-death-beneficiary-label">في حالة الوفاة يتم تسليم قيمة مبلغ الإعانة إلى</Label><Input value={form.death_beneficiary} onChange={(event) => updateForm("death_beneficiary", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="member-death-beneficiary-input" /></div>
            <Button type="submit" disabled={saving} className="h-11 bg-slate-950 text-white md:col-span-2" data-testid="save-membership-button"><UserRoundPlus className="h-4 w-4" /> حفظ العضوية</Button>
          </form>
          <div className="my-6 h-px bg-slate-200" data-testid="membership-import-divider" />
          <form onSubmit={importMembers} className="space-y-4" data-testid="membership-import-form">
            <div className="flex items-center gap-3" data-testid="membership-import-heading"><FileUp className="h-5 w-5 text-emerald-700" /><h3 className="text-xl font-extrabold" data-testid="membership-import-title">استيراد بيانات خارجية</h3></div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="membership-import-location-grid">
              <div data-testid="membership-import-governorate-wrapper"><Label data-testid="membership-import-governorate-label">المحافظة التي سيتم الاستيراد فيها</Label><select value={importForm.governorate} onChange={(event) => updateImportForm("governorate", event.target.value)} required className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="membership-import-governorate-select"><option value="">اختر المحافظة</option>{governorates.map((item) => <option key={item} value={item}>{item}</option>)}<option value="__new__">إضافة محافظة جديدة</option></select>{importForm.governorate === "__new__" && <Input value={importForm.governorate_new} onChange={(event) => updateImportForm("governorate_new", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" placeholder="اكتب اسم المحافظة" data-testid="membership-import-new-governorate-input" />}</div>
              <div data-testid="membership-import-committee-wrapper"><Label data-testid="membership-import-committee-label">اسم اللجنة التي سيتم الاستيراد فيها</Label><select value={importForm.union_committee} onChange={(event) => updateImportForm("union_committee", event.target.value)} required className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="membership-import-committee-select"><option value="">اختر اللجنة</option>{importCommittees.map((item) => <option key={item} value={item}>{item}</option>)}<option value="__new__">إضافة لجنة جديدة</option></select>{importForm.union_committee === "__new__" && <Input value={importForm.union_committee_new} onChange={(event) => updateImportForm("union_committee_new", event.target.value)} required className="mt-2 h-11 bg-slate-50 text-right" placeholder="اكتب اسم اللجنة" data-testid="membership-import-new-committee-input" />}</div>
            </div>
            <div data-testid="membership-import-file-wrapper"><Label data-testid="membership-import-file-label">ملف PDF / Word / Excel</Label><Input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.csv" onChange={(event) => updateImportForm("file", event.target.files?.[0] || null)} required className="mt-2 h-11 bg-slate-50" data-testid="membership-import-file-input" /></div>
            <div className="rounded-lg bg-emerald-50 p-3 text-sm font-extrabold text-emerald-800" data-testid="membership-import-auto-note">سيتم تنزيل البيانات المطلوبة فقط في أماكنها تلقائياً: رقم العضوية، الاسم، الرقم القومي، تاريخ الميلاد، العنوان، ومستلم إعانة الوفاة. أي بيانات إضافية في الملف سيتم تجاهلها.</div>
            <Button type="submit" disabled={saving} variant="outline" className="h-11 w-full bg-white" data-testid="membership-import-button"><FileUp className="h-4 w-4" /> استيراد البيانات</Button>
            {importResult && <div className="rounded-xl border border-slate-200 bg-slate-50 p-4" data-testid="membership-import-result"><p className="font-extrabold" data-testid="membership-import-result-summary">تم استيراد {importResult.imported_count} عضوية — تم تجاهل {importResult.skipped_count} صف من إجمالي {importResult.total_rows_detected}</p>{importResult.skipped_rows?.length > 0 && <p className="mt-2 text-sm font-bold text-slate-600" data-testid="membership-import-result-skipped">أول سبب للتجاهل: صف {importResult.skipped_rows[0].row_number} — {importResult.skipped_rows[0].reason}</p>}</div>}
          </form>
        </section>}

        <section className="space-y-6" data-testid="membership-tools-column">
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="membership-current-size-section"><h2 className="mb-5 text-2xl font-extrabold" data-testid="membership-current-size-title">حجم العضوية الحالي</h2><div className="grid grid-cols-1 gap-4 md:grid-cols-3" data-testid="membership-current-size-grid"><div className="rounded-xl bg-slate-950 p-4 text-white" data-testid="membership-total-card"><p className="text-xs font-bold text-slate-300" data-testid="membership-total-label">إجمالي المسجل</p><p className="text-xl font-extrabold" data-testid="membership-total-value">{currentSize?.total_members || 0}</p></div><div className="rounded-xl bg-amber-50 p-4" data-testid="membership-retired-card"><p className="text-xs font-bold text-amber-700" data-testid="membership-retired-label">خروج معاش حتى الآن</p><p className="text-xl font-extrabold" data-testid="membership-retired-value">{currentSize?.retired_members || 0}</p></div><div className="rounded-xl bg-emerald-50 p-4" data-testid="membership-current-card"><p className="text-xs font-bold text-emerald-700" data-testid="membership-current-label">حجم العضوية الحالي</p><p className="text-xl font-extrabold" data-testid="membership-current-value">{currentSize?.current_membership_size || 0}</p></div></div></section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="membership-annual-report-section"><div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between" data-testid="membership-annual-report-heading"><div className="flex items-center gap-3" data-testid="membership-annual-report-title-block"><BarChart3 className="h-6 w-6 text-emerald-700" /><h2 className="text-2xl font-extrabold" data-testid="membership-annual-report-title">التقرير السنوي للعضوية</h2></div><Button type="button" onClick={() => window.print()} variant="outline" className="h-10 bg-white print:hidden" data-testid="print-annual-membership-report-button"><Printer className="h-4 w-4" /> طباعة</Button></div><div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto] print:hidden" data-testid="membership-annual-report-controls"><select value={annualYear} onChange={(event) => setAnnualYear(event.target.value)} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="membership-annual-report-year-select">{yearOptions.map((year) => <option key={year} value={year}>{year}</option>)}</select><Button type="button" onClick={loadAnnualReport} className="h-11 bg-slate-950 text-white" data-testid="load-annual-membership-report-button">عرض التقرير</Button></div><div className="mt-5 overflow-x-auto rounded-xl border border-slate-200" data-testid="membership-annual-report-table-wrapper"><Table data-testid="membership-annual-report-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">المحافظة</TableHead><TableHead className="text-right text-white">اللجنة</TableHead><TableHead className="text-right text-white">إجمالي المسجل</TableHead><TableHead className="text-right text-white">الداخلين الجدد</TableHead><TableHead className="text-right text-white">الخارجين معاش</TableHead><TableHead className="text-right text-white">صافي العضوية</TableHead></TableRow></TableHeader><TableBody>{!annualReport && <TableRow data-testid="membership-annual-report-empty-row"><TableCell colSpan={6} className="py-6 text-center font-bold text-slate-500">اختر السنة ثم اضغط عرض التقرير</TableCell></TableRow>}{annualReport?.rows?.map((row) => <TableRow key={`${row.governorate}-${row.union_committee}`} data-testid={`membership-annual-report-row-${row.governorate}-${row.union_committee}`}><TableCell className="font-extrabold" data-testid={`membership-annual-report-row-${row.governorate}-${row.union_committee}-governorate`}>{row.governorate}</TableCell><TableCell data-testid={`membership-annual-report-row-${row.governorate}-${row.union_committee}-committee`}>{row.union_committee}</TableCell><TableCell data-testid={`membership-annual-report-row-${row.governorate}-${row.union_committee}-total`}>{row.total_registered}</TableCell><TableCell data-testid={`membership-annual-report-row-${row.governorate}-${row.union_committee}-new`}>{row.new_members}</TableCell><TableCell data-testid={`membership-annual-report-row-${row.governorate}-${row.union_committee}-retired`}>{row.retired_members}</TableCell><TableCell className="font-extrabold" data-testid={`membership-annual-report-row-${row.governorate}-${row.union_committee}-current`}>{row.current_membership_size}</TableCell></TableRow>)}{annualReport && <TableRow className="bg-emerald-50 font-extrabold" data-testid="membership-annual-report-total-row"><TableCell data-testid="membership-annual-report-total-governorate">الإجمالي</TableCell><TableCell data-testid="membership-annual-report-total-committee">كل اللجان</TableCell><TableCell data-testid="membership-annual-report-total-registered">{annualReport.totals.total_registered}</TableCell><TableCell data-testid="membership-annual-report-total-new">{annualReport.totals.new_members}</TableCell><TableCell data-testid="membership-annual-report-total-retired">{annualReport.totals.retired_members}</TableCell><TableCell data-testid="membership-annual-report-total-current">{annualReport.totals.current_membership_size}</TableCell></TableRow>}</TableBody></Table></div></section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="membership-search-section"><h2 className="mb-5 text-2xl font-extrabold" data-testid="membership-search-title">بحث بالاسم</h2><div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto]" data-testid="membership-search-controls"><Input value={searchName} onChange={(event) => setSearchName(event.target.value)} className="h-11 bg-slate-50 text-right" data-testid="membership-search-name-input" /><Button type="button" onClick={searchMembers} className="h-11 bg-slate-950 text-white" data-testid="membership-search-button"><Search className="h-4 w-4" /> بحث</Button></div><div className="mt-4 overflow-x-auto rounded-xl border border-slate-200" data-testid="membership-search-results-wrapper"><Table data-testid="membership-search-results-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">الاسم</TableHead><TableHead className="text-right text-white">رقم العضوية</TableHead><TableHead className="text-right text-white">المحافظة</TableHead><TableHead className="text-right text-white">إجراء</TableHead></TableRow></TableHeader><TableBody>{searchResults.length === 0 && <TableRow data-testid="membership-search-empty-row"><TableCell colSpan={4} className="py-6 text-center font-bold text-slate-500">لا توجد نتائج بحث</TableCell></TableRow>}{searchResults.map((member) => <TableRow key={member.id} data-testid={`membership-search-row-${member.id}`}><TableCell className="font-extrabold" data-testid={`membership-search-row-${member.id}-name`}>{member.name}</TableCell><TableCell data-testid={`membership-search-row-${member.id}-number`}>{member.membership_number}</TableCell><TableCell data-testid={`membership-search-row-${member.id}-governorate`}>{member.governorate}</TableCell><TableCell><Button type="button" onClick={() => setSelectedMember(member)} variant="outline" className="h-9 bg-white" data-testid={`membership-search-row-${member.id}-view-button`}>عرض</Button></TableCell></TableRow>)}</TableBody></Table></div></section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="membership-retirement-filter-section"><div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><h2 className="text-2xl font-extrabold" data-testid="membership-retirement-title">عامل تصفية خروج المعاش</h2><Button type="button" onClick={printRetirement} variant="outline" className="h-10 bg-white print:hidden" data-testid="print-retirement-report-button"><Printer className="h-4 w-4" /> طباعة</Button></div><div className="grid grid-cols-1 gap-3 md:grid-cols-5 print:hidden" data-testid="membership-retirement-controls"><select value={filters.governorate} onChange={(event) => setFilters((current) => ({ ...current, governorate: event.target.value, union_committee: "" }))} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="membership-retirement-governorate-select"><option value="">كل المحافظات</option>{governorates.map((item) => <option key={item} value={item}>{item}</option>)}</select><select value={filters.union_committee} onChange={(event) => setFilters((current) => ({ ...current, union_committee: event.target.value }))} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="membership-retirement-committee-select"><option value="">كل اللجان</option>{committees.map((item) => <option key={item} value={item}>{item}</option>)}</select><select value={filters.year} onChange={(event) => setFilters((current) => ({ ...current, year: event.target.value }))} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="membership-retirement-year-select">{yearOptions.map((year) => <option key={year} value={year}>{year}</option>)}</select><select value={filters.month} onChange={(event) => setFilters((current) => ({ ...current, month: event.target.value }))} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="membership-retirement-month-select">{monthOptions.map((month) => <option key={month} value={month}>{month}</option>)}</select><Button type="button" onClick={applyRetirementFilter} className="h-11 bg-slate-950 text-white" data-testid="apply-retirement-filter-button">تطبيق</Button></div><div className="mt-5 overflow-x-auto rounded-xl border border-slate-200" data-testid="membership-retirement-table-wrapper"><Table data-testid="membership-retirement-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">الاسم</TableHead><TableHead className="text-right text-white">رقم العضوية</TableHead><TableHead className="text-right text-white">محافظة</TableHead><TableHead className="text-right text-white">اللجنة</TableHead><TableHead className="text-right text-white">تاريخ الميلاد</TableHead><TableHead className="text-right text-white">سن المعاش</TableHead></TableRow></TableHeader><TableBody>{retirementRows.length === 0 && <TableRow data-testid="membership-retirement-empty-row"><TableCell colSpan={6} className="py-6 text-center font-bold text-slate-500">لا توجد بيانات خروج معاش</TableCell></TableRow>}{retirementRows.map((member) => <TableRow key={member.id} data-testid={`membership-retirement-row-${member.id}`}><TableCell className="font-extrabold" data-testid={`membership-retirement-row-${member.id}-name`}>{member.name}</TableCell><TableCell data-testid={`membership-retirement-row-${member.id}-number`}>{member.membership_number}</TableCell><TableCell data-testid={`membership-retirement-row-${member.id}-governorate`}>{member.governorate}</TableCell><TableCell data-testid={`membership-retirement-row-${member.id}-committee`}>{member.union_committee}</TableCell><TableCell data-testid={`membership-retirement-row-${member.id}-birth-date`}>{member.birth_date}</TableCell><TableCell data-testid={`membership-retirement-row-${member.id}-age`}>{member.retirement_age}</TableCell></TableRow>)}</TableBody></Table></div><div className="mt-5 rounded-xl border-2 border-slate-950 p-5 text-center text-xl font-extrabold" data-testid="membership-retirement-count-box">عدد الأعضاء خروج معاش: {retirementRows.length}</div></section>
        </section>
      </section>

      {importPreview && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4" data-testid="membership-import-preview-modal"><section className="max-h-[88vh] w-full max-w-5xl overflow-y-auto rounded-xl bg-white p-6 shadow-2xl" data-testid="membership-import-preview-panel"><div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between" data-testid="membership-import-preview-heading"><div data-testid="membership-import-preview-title-block"><h2 className="text-2xl font-extrabold" data-testid="membership-import-preview-title">مراجعة الاستيراد قبل الاعتماد</h2><p className="text-sm font-bold text-slate-500" data-testid="membership-import-preview-summary">صفوف مقبولة: {importPreview.accepted_count} — صفوف مرفوضة: {importPreview.skipped_count} — إجمالي الصفوف: {importPreview.total_rows_detected}</p></div><div className="flex flex-wrap gap-2" data-testid="membership-import-preview-actions"><Button type="button" onClick={commitImportPreview} disabled={saving || importPreview.accepted_count === 0} className="h-10 bg-slate-950 text-white" data-testid="membership-import-preview-commit-button">اعتماد الاستيراد النهائي</Button><Button type="button" onClick={() => setImportPreview(null)} variant="outline" className="h-10 bg-white" data-testid="membership-import-preview-cancel-button"><X className="h-4 w-4" /> إلغاء</Button></div></div><div className="grid grid-cols-1 gap-5 xl:grid-cols-2" data-testid="membership-import-preview-tables"><div data-testid="membership-import-preview-accepted-section"><h3 className="mb-3 text-lg font-extrabold text-emerald-700" data-testid="membership-import-preview-accepted-title">الصفوف المقبولة</h3><div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="membership-import-preview-accepted-table-wrapper"><Table data-testid="membership-import-preview-accepted-table"><TableHeader className="bg-emerald-900"><TableRow className="hover:bg-emerald-900"><TableHead className="text-right text-white">الصف</TableHead><TableHead className="text-right text-white">الاسم</TableHead><TableHead className="text-right text-white">رقم العضوية</TableHead><TableHead className="text-right text-white">الرقم القومي</TableHead></TableRow></TableHeader><TableBody>{importPreview.accepted_rows.length === 0 && <TableRow data-testid="membership-import-preview-accepted-empty-row"><TableCell colSpan={4} className="py-6 text-center font-bold text-slate-500">لا توجد صفوف مقبولة</TableCell></TableRow>}{importPreview.accepted_rows.map((row) => <TableRow key={`accepted-${row.row_number}`} data-testid={`membership-import-preview-accepted-row-${row.row_number}`}><TableCell data-testid={`membership-import-preview-accepted-row-${row.row_number}-number`}>{row.row_number}</TableCell><TableCell className="font-extrabold" data-testid={`membership-import-preview-accepted-row-${row.row_number}-name`}>{row.name}</TableCell><TableCell data-testid={`membership-import-preview-accepted-row-${row.row_number}-membership-number`}>{row.membership_number}</TableCell><TableCell data-testid={`membership-import-preview-accepted-row-${row.row_number}-national-id`}>{row.national_id}</TableCell></TableRow>)}</TableBody></Table></div></div><div data-testid="membership-import-preview-skipped-section"><h3 className="mb-3 text-lg font-extrabold text-red-700" data-testid="membership-import-preview-skipped-title">الصفوف المرفوضة</h3><div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="membership-import-preview-skipped-table-wrapper"><Table data-testid="membership-import-preview-skipped-table"><TableHeader className="bg-red-900"><TableRow className="hover:bg-red-900"><TableHead className="text-right text-white">الصف</TableHead><TableHead className="text-right text-white">سبب الرفض</TableHead></TableRow></TableHeader><TableBody>{importPreview.skipped_rows.length === 0 && <TableRow data-testid="membership-import-preview-skipped-empty-row"><TableCell colSpan={2} className="py-6 text-center font-bold text-slate-500">لا توجد صفوف مرفوضة</TableCell></TableRow>}{importPreview.skipped_rows.map((row) => <TableRow key={`skipped-${row.row_number}`} data-testid={`membership-import-preview-skipped-row-${row.row_number}`}><TableCell data-testid={`membership-import-preview-skipped-row-${row.row_number}-number`}>{row.row_number}</TableCell><TableCell className="font-bold text-red-700" data-testid={`membership-import-preview-skipped-row-${row.row_number}-reason`}>{row.reason}</TableCell></TableRow>)}</TableBody></Table></div></div></div></section></div>}

      {selectedMember && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 print:static print:bg-white" data-testid="membership-member-modal"><section className="w-full max-w-3xl rounded-xl bg-white p-6 shadow-2xl print:shadow-none" data-testid="membership-member-report"><div className="mb-5 flex items-center justify-between gap-3 print:hidden" data-testid="membership-member-modal-actions"><h2 className="text-2xl font-extrabold" data-testid="membership-member-modal-title">تقرير بيانات العضو</h2><div className="flex gap-2"><Button type="button" onClick={printSelected} className="h-10 bg-slate-950 text-white" data-testid="print-member-report-button"><Printer className="h-4 w-4" /> طباعة</Button><Button type="button" onClick={() => setSelectedMember(null)} variant="outline" className="h-10 bg-white" data-testid="close-member-report-button"><X className="h-4 w-4" /> خروج</Button></div></div><div className="text-center print:block" data-testid="membership-member-print-heading"><h2 className="text-3xl font-extrabold" data-testid="membership-member-report-title">تقرير بيانات العضو</h2><p className="font-bold text-slate-500" data-testid="membership-member-report-subtitle">مشروع التكافل الاجتماعي</p></div><div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="membership-member-details-grid">{[["الاسم", selectedMember.name], ["رقم العضوية", selectedMember.membership_number], ["الرقم القومي", selectedMember.national_id], ["محافظة", selectedMember.governorate], ["اللجنة النقابية", selectedMember.union_committee], ["تاريخ الميلاد", selectedMember.birth_date], ["سن المعاش", selectedMember.retirement_age], ["تاريخ خروج المعاش", selectedMember.retirement_date], ["العنوان", selectedMember.address], ["مستلم إعانة الوفاة", selectedMember.death_beneficiary]].map(([label, value]) => <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid={`membership-member-detail-${label}`}><p className="text-xs font-bold text-slate-500" data-testid={`membership-member-detail-${label}-label`}>{label}</p><p className="mt-1 font-extrabold text-slate-950" data-testid={`membership-member-detail-${label}-value`}>{value}</p></div>)}</div></section></div>}

      <footer className="px-4 pb-5 print:hidden" data-testid="membership-footer"><CreditLine testId="membership-creator-credit" /></footer>
    </main>
  );
}