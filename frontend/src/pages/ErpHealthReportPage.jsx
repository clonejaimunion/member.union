import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity, ArrowRight, Download, FileCheck2, Home, LogOut, RefreshCcw, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

export default function ErpHealthReportPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadReport = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get("/erp-health-report");
      setReport(response.data);
      toast.success("تم إنشاء تقرير تقييم النظام للعرض فقط");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إنشاء تقرير تقييم النظام");
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadReport(); }, [loadReport]);

  return (
    <main className="min-h-screen bg-[#f4f8fb] text-slate-950" data-testid="erp-health-report-page">
      <header className="border-b border-slate-200 bg-white/95 backdrop-blur-xl" data-testid="erp-health-report-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-5 sm:px-6 lg:px-8" data-testid="erp-health-report-header-inner">
          <div className="flex items-center gap-3" data-testid="erp-health-report-brand">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-950 text-white" data-testid="erp-health-report-brand-icon"><Activity className="h-6 w-6" /></div>
            <div data-testid="erp-health-report-brand-text"><p className="text-xs font-extrabold text-sky-700" data-testid="erp-health-report-eyebrow">Read Only ERP Health</p><h1 className="text-2xl font-black" data-testid="erp-health-report-title">تقرير تقييم النظام</h1></div>
          </div>
          <div className="flex flex-wrap gap-3" data-testid="erp-health-report-actions">
            <Badge className="bg-white text-slate-700" data-testid="erp-health-report-user-badge">{user?.username}</Badge>
            <Button asChild variant="outline" className="h-11 bg-white" data-testid="erp-health-report-home-button"><Link to="/"><Home className="h-4 w-4" /> الرئيسية</Link></Button>
            <Button onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="erp-health-report-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button>
            <Button onClick={logout} variant="outline" className="h-11 bg-white" data-testid="erp-health-report-logout-button"><LogOut className="h-4 w-4" /> خروج</Button>
          </div>
        </div>
      </header>
      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="erp-health-report-content">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="erp-health-report-summary-card">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between" data-testid="erp-health-report-summary-layout">
            <div data-testid="erp-health-report-summary-text"><p className="text-sm font-extrabold text-sky-700" data-testid="erp-health-report-summary-mode"><ShieldCheck className="ml-1 inline h-4 w-4" /> تحليل فقط بدون تعديل بيانات</p><h2 className="mt-2 text-4xl font-black sm:text-5xl lg:text-6xl" data-testid="erp-health-report-score">{loading ? "..." : `${report?.overall_score || 0}/100`}</h2><p className="mt-3 text-base font-bold text-slate-500 md:text-lg" data-testid="erp-health-report-generated-at">{report?.generated_at ? `تم الإنشاء: ${formatDateTime(report.generated_at)}` : "جاري إنشاء التقرير"}</p></div>
            <div className="flex flex-wrap gap-3" data-testid="erp-health-report-summary-buttons"><Button type="button" onClick={loadReport} disabled={loading} variant="outline" className="h-12 bg-white" data-testid="erp-health-report-regenerate-button"><RefreshCcw className="h-4 w-4" /> إعادة توليد</Button><Button asChild disabled={!report?.direct_download_url} className="h-12 bg-sky-800 text-white" data-testid="erp-health-report-download-button"><a href={report?.direct_download_url || "#"} target="_blank" rel="noreferrer"><Download className="h-4 w-4" /> تحميل PDF مباشر</a></Button></div>
          </div>
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="erp-health-report-metrics-section">
          <h2 className="text-3xl font-black" data-testid="erp-health-report-metrics-title">مؤشرات التقييم</h2>
          <div className="mt-5 overflow-x-auto rounded-xl border border-slate-200" data-testid="erp-health-report-metrics-table-wrapper"><Table data-testid="erp-health-report-metrics-table"><TableHeader className="bg-slate-950"><TableRow><TableHead className="text-right text-white">البند</TableHead><TableHead className="text-right text-white">Score</TableHead><TableHead className="text-right text-white">الحالة</TableHead><TableHead className="text-right text-white">التفاصيل</TableHead></TableRow></TableHeader><TableBody>{loading && <TableRow data-testid="erp-health-report-loading-row"><TableCell colSpan={4} className="py-8 text-center font-bold">جاري تحليل النظام...</TableCell></TableRow>}{!loading && (report?.metrics || []).map((metric) => <TableRow key={metric.key} data-testid={`erp-health-report-metric-${metric.key}`}><TableCell className="font-black" data-testid={`erp-health-report-metric-${metric.key}-title`}>{metric.title}</TableCell><TableCell className="font-black text-sky-800" data-testid={`erp-health-report-metric-${metric.key}-score`}>{metric.score}</TableCell><TableCell data-testid={`erp-health-report-metric-${metric.key}-status`}>{metric.status}</TableCell><TableCell data-testid={`erp-health-report-metric-${metric.key}-details`}>{metric.details}</TableCell></TableRow>)}</TableBody></Table></div>
        </section>
        <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 shadow-sm" data-testid="erp-health-report-recommendations-section"><h2 className="text-3xl font-black text-emerald-950" data-testid="erp-health-report-recommendations-title">التوصيات التلقائية</h2><div className="mt-4 space-y-3" data-testid="erp-health-report-recommendations-list">{(report?.recommendations || []).map((item, index) => <p key={`${item}-${index}`} className="rounded-xl bg-white p-3 text-sm font-bold text-emerald-900" data-testid={`erp-health-report-recommendation-${index}`}>{item}</p>)}</div></section>
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm font-bold text-amber-950" data-testid="erp-health-report-readonly-note"><FileCheck2 className="ml-1 inline h-4 w-4" /> هذا التقرير يقرأ من القيود اليومية ودفتر الأستاذ وميزان المراجعة والتسويات وسجل الحركات فقط، ولا يعدّل أي قيد أو رصيد أو تسوية.</section>
      </section>
      <footer className="px-4 pb-5" data-testid="erp-health-report-footer"><CreditLine testId="erp-health-report-creator-credit" /></footer>
    </main>
  );
}