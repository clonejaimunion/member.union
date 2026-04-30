import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Home, LogOut, NotebookPen, Plus, Save, Trash2 } from "lucide-react";
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

const today = new Date().toISOString().slice(0, 10);
const createLine = (account_name = "", debit = "", credit = "") => ({ id: `${Date.now()}-${Math.random()}`, account_name, debit, credit });
const sourceLabels = { manual: "يدوي", revenue: "إيراد", expense: "مصروف", banking_expense: "مصروف بنكي", deposit_interest: "عائد وديعة", reconciliation: "تسوية بنكية", fixed_asset: "أصل ثابت", asset_depreciation: "إهلاك أصل", custody_advance: "عهدة/سلفة", custody_advance_settlement: "تسوية عهدة/سلفة" };

export default function JournalEntriesPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [filters, setFilters] = useState({ from_date: "", to_date: "", source_type: "" });
  const [form, setForm] = useState({ entry_date: today, description: "", reference: "", lines: [createLine(), createLine()] });
  const canAddManual = user?.role === "admin";

  const loadEntries = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.from_date) params.set("from_date", filters.from_date);
      if (filters.to_date) params.set("to_date", filters.to_date);
      if (filters.source_type) params.set("source_type", filters.source_type);
      const response = await api.get(`/journal-entries?${params.toString()}`);
      setEntries(response.data);
    } catch (error) {
      toast.error("تعذر تحميل القيود اليومية");
    } finally {
      setLoading(false);
    }
  }, [filters.from_date, filters.to_date, filters.source_type]);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const totals = useMemo(() => form.lines.reduce((acc, line) => ({ debit: acc.debit + Number(line.debit || 0), credit: acc.credit + Number(line.credit || 0) }), { debit: 0, credit: 0 }), [form.lines]);
  const balanced = Math.round(totals.debit * 100) === Math.round(totals.credit * 100) && totals.debit > 0;

  const updateLine = (lineId, field, value) => {
    setForm((current) => ({ ...current, lines: current.lines.map((line) => line.id === lineId ? { ...line, [field]: field === "account_name" ? value : sanitizeDecimalInput(value) } : line) }));
  };

  const addLine = () => setForm((current) => ({ ...current, lines: [...current.lines, createLine()] }));
  const removeLine = (lineId) => setForm((current) => ({ ...current, lines: current.lines.length > 2 ? current.lines.filter((line) => line.id !== lineId) : current.lines }));

  const saveManualEntry = async (event) => {
    event.preventDefault();
    if (!balanced) return toast.error("لا يمكن حفظ قيد غير متوازن");
    setSaving(true);
    try {
      await api.post("/journal-entries", {
        entry_date: form.entry_date,
        description: form.description,
        reference: form.reference || null,
        lines: form.lines.map((line) => ({ account_name: line.account_name, debit: Number(line.debit || 0), credit: Number(line.credit || 0) })),
      });
      toast.success("تم حفظ القيد اليومي");
      setForm({ entry_date: today, description: "", reference: "", lines: [createLine(), createLine()] });
      loadEntries();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ القيد");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="journal-entries-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="journal-entries-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3" data-testid="journal-entries-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white"><NotebookPen className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700">النظام المحاسبي</p><h1 className="text-2xl font-extrabold" data-testid="journal-entries-title">القيود اليومية</h1></div></div>
          <div className="flex flex-wrap items-center gap-3" data-testid="journal-entries-actions"><Badge className="bg-white text-slate-700" data-testid="journal-entries-user-badge">{user?.full_name || user?.username}</Badge><Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="journal-entries-home-button"><Link to="/"><Home className="h-4 w-4" /> الصفحة الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="journal-entries-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="journal-entries-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 sm:px-6 xl:grid-cols-[0.8fr_1.2fr] lg:px-8" data-testid="journal-entries-content">
        {canAddManual && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="manual-journal-entry-section">
          <h2 className="mb-5 text-2xl font-extrabold" data-testid="manual-journal-entry-title">إضافة قيد يدوي</h2>
          <form onSubmit={saveManualEntry} className="space-y-4" data-testid="manual-journal-entry-form">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2"><div><Label>تاريخ القيد</Label><Input type="date" value={form.entry_date} onChange={(e) => setForm((c) => ({ ...c, entry_date: e.target.value }))} required className="mt-2 h-11 bg-slate-50" data-testid="manual-journal-entry-date-input" /></div><div><Label>رقم المستند</Label><Input value={form.reference} onChange={(e) => setForm((c) => ({ ...c, reference: e.target.value }))} className="mt-2 h-11 bg-slate-50 text-right" data-testid="manual-journal-entry-reference-input" /></div></div>
            <div><Label>البيان</Label><Input value={form.description} onChange={(e) => setForm((c) => ({ ...c, description: e.target.value }))} required className="mt-2 h-11 bg-slate-50 text-right" data-testid="manual-journal-entry-description-input" /></div>
            <div className="space-y-3" data-testid="manual-journal-lines">
              {form.lines.map((line, index) => <div key={line.id} className="grid grid-cols-1 gap-2 rounded-lg bg-slate-50 p-3 md:grid-cols-[1fr_120px_120px_auto]" data-testid={`manual-journal-line-${index}`}><Input placeholder="اسم الحساب" value={line.account_name} onChange={(e) => updateLine(line.id, "account_name", e.target.value)} className="h-11 bg-white text-right" data-testid={`manual-journal-line-${index}-account-input`} /><Input placeholder="مدين" inputMode="decimal" value={line.debit} onChange={(e) => updateLine(line.id, "debit", e.target.value)} className="h-11 bg-white text-right" data-testid={`manual-journal-line-${index}-debit-input`} /><Input placeholder="دائن" inputMode="decimal" value={line.credit} onChange={(e) => updateLine(line.id, "credit", e.target.value)} className="h-11 bg-white text-right" data-testid={`manual-journal-line-${index}-credit-input`} /><Button type="button" onClick={() => removeLine(line.id)} variant="outline" className="h-11 bg-white text-red-700" data-testid={`manual-journal-line-${index}-remove-button`}><Trash2 className="h-4 w-4" /></Button></div>)}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-emerald-50 p-3 text-sm font-extrabold" data-testid="manual-journal-entry-totals"><span>إجمالي المدين: {formatCurrency(totals.debit)}</span><span>إجمالي الدائن: {formatCurrency(totals.credit)}</span><span className={balanced ? "text-emerald-700" : "text-red-700"}>{balanced ? "القيد متوازن" : "القيد غير متوازن"}</span></div>
            <div className="flex gap-2"><Button type="button" onClick={addLine} variant="outline" className="h-11 bg-white" data-testid="manual-journal-add-line-button"><Plus className="h-4 w-4" /> سطر</Button><Button type="submit" disabled={saving || !balanced} className="h-11 flex-1 bg-slate-950 text-white" data-testid="manual-journal-save-button"><Save className="h-4 w-4" /> حفظ قيد معتمد</Button></div>
          </form>
        </section>}

        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="journal-entries-list-section">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between"><div><h2 className="text-2xl font-extrabold" data-testid="journal-entries-list-title">دفتر القيود اليومية</h2><p className="text-sm font-bold text-slate-500">رقم القيد تسلسلي لكل جهة ويبدأ من 1.</p></div><div className="grid grid-cols-1 gap-2 md:grid-cols-4"><Input type="date" value={filters.from_date} onChange={(e) => setFilters((c) => ({ ...c, from_date: e.target.value }))} data-testid="journal-filter-from-date" /><Input type="date" value={filters.to_date} onChange={(e) => setFilters((c) => ({ ...c, to_date: e.target.value }))} data-testid="journal-filter-to-date" /><select value={filters.source_type} onChange={(e) => setFilters((c) => ({ ...c, source_type: e.target.value }))} className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm font-bold" data-testid="journal-filter-source-type"><option value="">كل المصادر</option>{Object.entries(sourceLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><Button onClick={loadEntries} variant="outline" className="h-10 bg-white" data-testid="journal-filter-apply-button">تطبيق</Button></div></div>
          <div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="journal-entries-table-wrapper"><Table data-testid="journal-entries-table"><TableHeader className="bg-slate-950"><TableRow className="hover:bg-slate-950"><TableHead className="text-right text-white">رقم القيد</TableHead><TableHead className="text-right text-white">التاريخ</TableHead><TableHead className="text-right text-white">البيان</TableHead><TableHead className="text-right text-white">المصدر</TableHead><TableHead className="text-right text-white">مدين</TableHead><TableHead className="text-right text-white">دائن</TableHead></TableRow></TableHeader><TableBody>{loading && <TableRow><TableCell colSpan={6} className="py-8 text-center font-bold">جاري التحميل...</TableCell></TableRow>}{!loading && entries.length === 0 && <TableRow data-testid="journal-entries-empty-row"><TableCell colSpan={6} className="py-8 text-center font-bold text-slate-500">لا توجد قيود يومية</TableCell></TableRow>}{entries.map((entry) => <TableRow key={entry.id} data-testid={`journal-entry-row-${entry.id}`}><TableCell className="font-extrabold" data-testid={`journal-entry-${entry.id}-number`}>{entry.entry_number}</TableCell><TableCell>{new Date(entry.entry_date).toLocaleDateString('ar-EG')}</TableCell><TableCell><p className="font-extrabold">{entry.description}</p><div className="mt-2 space-y-1 text-xs text-slate-500">{entry.lines.map((line, index) => <p key={`${entry.id}-${index}`}>{line.account_code ? `${line.account_code} - ` : ""}{line.account_name}: مدين {formatCurrency(line.debit)} / دائن {formatCurrency(line.credit)}</p>)}</div></TableCell><TableCell>{sourceLabels[entry.source_type] || entry.source_type}</TableCell><TableCell className="font-extrabold">{formatCurrency(entry.total_debit)}</TableCell><TableCell className="font-extrabold">{formatCurrency(entry.total_credit)}</TableCell></TableRow>)}</TableBody></Table></div>
        </section>
      </section>
      <footer className="px-4 pb-5 print:hidden"><CreditLine testId="journal-entries-creator-credit" /></footer>
    </main>
  );
}