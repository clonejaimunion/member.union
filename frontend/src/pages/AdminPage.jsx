import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Building2, FileImage, FileUp, KeyRound, LockKeyhole, Plus, QrCode, Save, ShieldCheck, ToggleLeft, ToggleRight, Trash2, UserCog, UsersRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import { useAppSettings } from "@/contexts/AppSettingsContext";
import { api } from "@/lib/api";
import { CreditLine } from "@/components/CreditLine";

const permissionLabels = {
  enter_deposits: "إدخال ودائع",
  view_reports: "مشاهدة التقارير",
  edit_deposits: "تعديل الودائع",
  manage_reconciliations: "إدارة التسويات البنكية",
  manage_revenues: "إدارة الإيرادات",
  manage_expenses: "إدارة المصروفات",
  manage_users: "إدارة مستخدمين",
  add_revenue: "إضافة إيراد",
  approve_revenue: "اعتماد إيراد",
  add_expense: "إضافة مصروف",
  approve_reports: "اعتماد تقرير",
  lock_periods: "إقفال فترة",
  edit_revenue: "تعديل إيراد",
  delete_revenue: "حذف إيراد",
  edit_expense: "تعديل مصروف",
  delete_expense: "حذف مصروف",
  unlock_periods: "فتح فترة",
  manage_einvoice: "إدارة الفاتورة الإلكترونية",
  manage_backups: "إدارة النسخ الاحتياطي",
};

const defaultUserForm = {
  username: "",
  password: "",
  permissions: { enter_deposits: true, view_reports: true, edit_deposits: false, manage_reconciliations: true, manage_revenues: true, manage_expenses: true, manage_users: false, add_revenue: true, approve_revenue: false, add_expense: true, approve_reports: false, lock_periods: false, edit_revenue: false, delete_revenue: false, edit_expense: false, delete_expense: false, unlock_periods: false, manage_einvoice: false, manage_backups: false },
  is_active: true,
};

const currentAdminDate = new Date();
const adminYearOptions = Array.from({ length: 16 }, (_, index) => String(currentAdminDate.getFullYear() - 5 + index));
const adminMonthOptions = Array.from({ length: 12 }, (_, index) => String(index + 1).padStart(2, "0"));
const adminHourOptions = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0"));
const defaultPeriodForm = { period_type: "monthly", year: String(currentAdminDate.getFullYear()), month: String(currentAdminDate.getMonth() + 1), action: "lock", reason: "" };
const defaultApprovalForm = { report_type: "عام", report_name: "", report_reference: "", period_label: "", status: "approved", approver_title: "", notes: "" };

const adminSections = [
  { id: "general-settings", title: "الإعدادات العامة", subtitle: "اسم النظام والجهة وشعار الاختصار", icon: FileImage },
  { id: "add-user", title: "إضافة مستخدم", subtitle: "إضافة مستخدم لإدخال البيانات", icon: Plus },
  { id: "users", title: "المستخدمون", subtitle: "المستخدمون المسجلون", icon: UsersRound },
  { id: "admin-password", title: "تغيير كلمة مرور الأدمن", subtitle: "كلمة المرور و Google Authenticator", icon: LockKeyhole },
  { id: "add-bank", title: "إضافة بنك", subtitle: "إضافة بنك جديد", icon: Building2 },
  { id: "opening-balances", title: "الأرصدة الافتتاحية", subtitle: "رصيد افتتاحي لكل بنك", icon: Save },
  { id: "security-review", title: "المراجعة الأمنية", subtitle: "ضوابط الاقتراب من الاعتماد", icon: ShieldCheck },
  { id: "audit-log", title: "سجل التدقيق", subtitle: "عرض بالشهر والسنة والساعة", icon: KeyRound },
];

export default function AdminPage() {
  const navigate = useNavigate();
  const { user, logout, refreshMe } = useAuth();
  const { refreshSettings } = useAppSettings();
  const [users, setUsers] = useState([]);
  const [newUser, setNewUser] = useState(defaultUserForm);
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "" });
  const [resetPasswords, setResetPasswords] = useState({});
  const [twoFactor, setTwoFactor] = useState(null);
  const [otpCode, setOtpCode] = useState("");
  const [bankForm, setBankForm] = useState({ name: "", code: "", swift_code: "", logo_url: "", color: "#0f172a" });
  const [banks, setBanks] = useState([]);
  const [openingBalances, setOpeningBalances] = useState({});
  const [auditLogs, setAuditLogs] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [backups, setBackups] = useState([]);
  const [periodForm, setPeriodForm] = useState(defaultPeriodForm);
  const [approvalForm, setApprovalForm] = useState(defaultApprovalForm);
  const [backupPassword, setBackupPassword] = useState("");
  const [restorePassword, setRestorePassword] = useState("");
  const [restoreFile, setRestoreFile] = useState(null);
  const [appSettings, setAppSettings] = useState(null);
  const [systemName, setSystemName] = useState("نظام محاسبي متكامل");
  const [organizationName, setOrganizationName] = useState("");
  const [shortcutIconFile, setShortcutIconFile] = useState(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [securityLoading, setSecurityLoading] = useState(false);
  const [activeAdminSection, setActiveAdminSection] = useState("add-user");
  const [auditFilter, setAuditFilter] = useState({ year: String(currentAdminDate.getFullYear()), month: "all", hour: "all" });

  const loadUsers = useCallback(() => {
    api.get("/admin/users").then((response) => setUsers(response.data)).catch(() => toast.error("تعذر تحميل المستخدمين"));
  }, []);

  const loadBanks = useCallback(async () => {
    try {
      const banksResponse = await api.get("/banks");
      setBanks(banksResponse.data);
      setOpeningBalances(banksResponse.data.reduce((acc, bank) => ({ ...acc, [bank.id]: String(bank.opening_balance || "") }), {}));
    } catch (error) {
      toast.error("تعذر تحميل البنوك");
    }
  }, []);

  const loadSecurityReview = useCallback(async () => {
    try {
      const auditParams = new URLSearchParams({ limit: "200" });
      if (auditFilter.year !== "all") auditParams.set("year", auditFilter.year);
      if (auditFilter.month !== "all") auditParams.set("month", String(Number(auditFilter.month)));
      if (auditFilter.hour !== "all") auditParams.set("hour", String(Number(auditFilter.hour)));
      const [auditResponse, periodsResponse, approvalsResponse, backupsResponse] = await Promise.all([
        api.get(`/admin/security/audit-logs?${auditParams.toString()}`),
        api.get("/admin/security/periods"),
        api.get("/admin/security/report-approvals"),
        api.get("/admin/security/backups"),
      ]);
      setAuditLogs(auditResponse.data);
      setPeriods(periodsResponse.data);
      setApprovals(approvalsResponse.data);
      setBackups(backupsResponse.data);
    } catch (error) {
      toast.error("تعذر تحميل المراجعة الأمنية");
    }
  }, [auditFilter]);

  const loadAppSettings = useCallback(async () => {
    try {
      const response = await api.get("/admin/app-settings");
      setAppSettings(response.data);
      setSystemName(response.data.system_name || "نظام محاسبي متكامل");
      setOrganizationName(response.data.organization_name || "");
    } catch (error) {
      toast.error("تعذر تحميل إعدادات النظام العامة");
    }
  }, []);

  useEffect(() => {
    loadUsers();
    loadBanks();
    loadSecurityReview();
    loadAppSettings();
  }, [loadBanks, loadSecurityReview, loadUsers, loadAppSettings]);

  const toggleNewPermission = (permission) => {
    setNewUser((current) => ({
      ...current,
      permissions: { ...current.permissions, [permission]: !current.permissions[permission] },
    }));
  };

  const createUser = async (event) => {
    event.preventDefault();
    try {
      await api.post("/admin/users", newUser);
      toast.success("تم إنشاء المستخدم");
      setNewUser(defaultUserForm);
      loadUsers();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إنشاء المستخدم");
    }
  };

  const updateUser = async (targetUser, updates) => {
    try {
      await api.put(`/admin/users/${targetUser.id}`, updates);
      toast.success("تم تحديث المستخدم");
      loadUsers();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تحديث المستخدم");
    }
  };

  const toggleExistingPermission = async (targetUser, permission) => {
    await updateUser(targetUser, {
      permissions: {
        ...targetUser.permissions,
        [permission]: !targetUser.permissions?.[permission],
      },
    });
  };

  const deleteUser = async (targetUser) => {
    const confirmed = window.confirm(`هل أنت متأكد من حذف المستخدم ${targetUser.username}؟`);
    if (!confirmed) return;
    try {
      await api.delete(`/admin/users/${targetUser.id}`);
      toast.success("تم حذف المستخدم");
      loadUsers();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حذف المستخدم");
    }
  };

  const changeAdminPassword = async (event) => {
    event.preventDefault();
    try {
      await api.post("/admin/change-password", passwordForm);
      toast.success("تم تغيير كلمة مرور الأدمن");
      setPasswordForm({ current_password: "", new_password: "" });
      await refreshMe();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تغيير كلمة المرور");
    }
  };

  const setup2FA = async () => {
    try {
      const response = await api.post("/admin/2fa/setup");
      setTwoFactor(response.data);
      toast.success("امسح QR Code من تطبيق Google Authenticator");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر بدء إعداد المصادقة الثنائية");
    }
  };

  const verify2FA = async () => {
    try {
      await api.post("/admin/2fa/verify", { otp_code: otpCode });
      toast.success("تم تفعيل المصادقة الثنائية للأدمن");
      setOtpCode("");
      setTwoFactor(null);
      await refreshMe();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "كود التحقق غير صحيح");
    }
  };

  const createBank = async (event) => {
    event.preventDefault();
    try {
      await api.post("/admin/banks", bankForm);
      toast.success("تمت إضافة البنك الجديد");
      setBankForm({ name: "", code: "", swift_code: "", logo_url: "", color: "#0f172a" });
      loadBanks();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إضافة البنك");
    }
  };

  const updateOpeningBalanceInput = (bankId, value) => {
    const clean = value.replace(/[^0-9.-]/g, "").replace(/(?!^)-/g, "");
    setOpeningBalances((current) => ({ ...current, [bankId]: clean }));
  };

  const saveOpeningBalance = async (bankId) => {
    try {
      await api.put(`/admin/banks/${bankId}/opening-balance`, { opening_balance: Number(openingBalances[bankId] || 0) });
      toast.success("تم حفظ الرصيد الافتتاحي");
      await loadBanks();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ الرصيد الافتتاحي");
    }
  };

  const savePeriodLock = async () => {
    setSecurityLoading(true);
    try {
      await api.post("/admin/security/periods", {
        period_type: periodForm.period_type,
        year: Number(periodForm.year),
        month: periodForm.period_type === "monthly" ? Number(periodForm.month) : null,
        action: periodForm.action,
        reason: periodForm.reason,
      });
      toast.success(periodForm.action === "lock" ? "تم إقفال الفترة" : "تم فتح الفترة وتسجيل السبب");
      setPeriodForm(defaultPeriodForm);
      await loadSecurityReview();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ الفترة");
    } finally {
      setSecurityLoading(false);
    }
  };

  const saveReportApproval = async () => {
    if (!approvalForm.report_name.trim() || !approvalForm.approver_title.trim()) return toast.error("أدخل اسم التقرير وصفة المعتمد");
    setSecurityLoading(true);
    try {
      await api.post("/admin/security/report-approvals", approvalForm);
      toast.success("تم حفظ اعتماد التقرير");
      setApprovalForm(defaultApprovalForm);
      await loadSecurityReview();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر اعتماد التقرير");
    } finally {
      setSecurityLoading(false);
    }
  };

  const createBackup = async () => {
    if (backupPassword.length < 6) return toast.error("كلمة مرور النسخة يجب ألا تقل عن 6 أحرف");
    setSecurityLoading(true);
    try {
      await api.post("/admin/security/backups", { password: backupPassword });
      toast.success("تم إنشاء نسخة احتياطية مشفرة");
      setBackupPassword("");
      await loadSecurityReview();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إنشاء النسخة الاحتياطية");
    } finally {
      setSecurityLoading(false);
    }
  };

  const restoreBackup = async () => {
    if (!restoreFile || restorePassword.length < 6) return toast.error("اختر ملف النسخة وأدخل كلمة المرور");
    setSecurityLoading(true);
    try {
      const data = new FormData();
      data.append("password", restorePassword);
      data.append("backup_file", restoreFile);
      await api.post("/admin/security/backups/restore", data);
      toast.success("تمت استعادة النسخة الاحتياطية");
      setRestorePassword("");
      setRestoreFile(null);
      await loadSecurityReview();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر استعادة النسخة الاحتياطية");
    } finally {
      setSecurityLoading(false);
    }
  };

  const downloadBackup = async (item) => {
    try {
      const response = await api.get(`/admin/security/backups/${item.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = item.file_name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error("تعذر تحميل النسخة الاحتياطية");
    }
  };

  const saveAppSystemName = async (event) => {
    event.preventDefault();
    if (!systemName.trim()) return toast.error("أدخل اسم النظام");
    setSettingsLoading(true);
    try {
      const response = await api.put("/admin/app-settings", { system_name: systemName.trim(), organization_name: organizationName.trim() });
      setAppSettings(response.data);
      setOrganizationName(response.data.organization_name || organizationName.trim());
      await refreshSettings();
      toast.success("تم تحديث اسم النظام واسم الجهة");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ إعدادات الاسم");
    } finally {
      setSettingsLoading(false);
    }
  };

  const saveShortcutIcon = async () => {
    if (!shortcutIconFile) return toast.error("اختر ملف أيقونة أولاً");
    setSettingsLoading(true);
    try {
      const data = new FormData();
      data.append("icon_file", shortcutIconFile);
      const response = await api.post("/admin/app-settings/icon", data);
      setAppSettings(response.data);
      setShortcutIconFile(null);
      await refreshSettings();
      toast.success("تم تحديث شعار الاختصار");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تحديث الأيقونة");
    } finally {
      setSettingsLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="admin-page">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur" data-testid="admin-header">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-4" data-testid="admin-heading-block">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="admin-heading-icon"><UserCog className="h-6 w-6" /></div>
            <div>
              <p className="text-sm font-extrabold text-emerald-700" data-testid="admin-eyebrow">الرابط الخاص للأدمن</p>
              <h1 className="text-3xl font-extrabold" data-testid="admin-title">لوحة التحكم الآمنة</h1>
            </div>
          </div>
          <div className="flex flex-wrap gap-3" data-testid="admin-header-actions">
            <Badge className="border-emerald-200 bg-emerald-50 px-3 py-1 text-emerald-700 hover:bg-emerald-50" data-testid="admin-logged-user-badge">{user?.username}</Badge>
            <Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="admin-back-app-button"><Link to="/">العودة للبرنامج</Link></Button>
            <Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="admin-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button>
            <Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="admin-logout-button">خروج</Button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8" data-testid="admin-section-menu">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="admin-section-menu-grid">
          {adminSections.map((section) => {
            const Icon = section.icon;
            const active = activeAdminSection === section.id;
            return (
              <button key={section.id} type="button" onClick={() => setActiveAdminSection(section.id)} className={`min-h-32 rounded-xl border p-5 text-right transition-[transform,background-color,border-color,box-shadow] hover:-translate-y-0.5 ${active ? "border-emerald-300 bg-emerald-50 shadow-lg shadow-emerald-100" : "border-slate-200 bg-white hover:bg-slate-50"}`} data-testid={`admin-section-button-${section.id}`}>
                <Icon className={`mb-4 h-6 w-6 ${active ? "text-emerald-700" : "text-slate-500"}`} />
                <span className="block text-lg font-extrabold text-slate-950" data-testid={`admin-section-title-${section.id}`}>{section.title}</span>
                <span className="mt-2 block text-xs font-bold leading-5 text-slate-500" data-testid={`admin-section-subtitle-${section.id}`}>{section.subtitle}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="admin-content-grid">
        <div className="space-y-6" data-testid="admin-users-column">
          {activeAdminSection === "add-user" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="create-user-section">
            <div className="mb-5 flex items-center gap-3" data-testid="create-user-heading">
              <UsersRound className="h-6 w-6 text-emerald-700" />
              <h2 className="text-2xl font-extrabold" data-testid="create-user-title">إضافة مستخدم لإدخال البيانات</h2>
            </div>
            <form onSubmit={createUser} className="grid grid-cols-1 gap-4 md:grid-cols-2" data-testid="create-user-form">
              <div className="space-y-2" data-testid="new-user-username-wrapper">
                <Label htmlFor="new_username" data-testid="new-user-username-label">اسم المستخدم</Label>
                <Input id="new_username" value={newUser.username} onChange={(event) => setNewUser((current) => ({ ...current, username: event.target.value }))} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="new-user-username-input" />
              </div>
              <div className="space-y-2" data-testid="new-user-password-wrapper">
                <Label htmlFor="new_password" data-testid="new-user-password-label">كلمة المرور</Label>
                <Input id="new_password" type="password" value={newUser.password} onChange={(event) => setNewUser((current) => ({ ...current, password: event.target.value }))} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="new-user-password-input" />
              </div>
              <div className="md:col-span-2 grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="new-user-permissions-grid">
                {Object.entries(permissionLabels).map(([key, label]) => (
                  <button key={key} type="button" onClick={() => toggleNewPermission(key)} className={`flex items-center justify-between rounded-lg border p-4 text-sm font-extrabold transition-colors ${newUser.permissions[key] ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-slate-50 text-slate-500"}`} data-testid={`new-user-permission-${key}-toggle`}>
                    {label}
                    {newUser.permissions[key] ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                  </button>
                ))}
              </div>
              <Button type="submit" className="h-12 rounded-lg bg-slate-950 text-white md:col-span-2" data-testid="create-user-submit-button"><Plus className="h-4 w-4" /> إضافة المستخدم</Button>
            </form>
          </section>}

          {activeAdminSection === "add-bank" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="create-bank-section">
            <div className="mb-5 flex items-center gap-3" data-testid="create-bank-heading">
              <Building2 className="h-6 w-6 text-emerald-700" />
              <h2 className="text-2xl font-extrabold" data-testid="create-bank-title">إضافة بنك جديد</h2>
            </div>
            <form onSubmit={createBank} className="grid grid-cols-1 gap-4 md:grid-cols-2" data-testid="create-bank-form">
              <div className="space-y-2" data-testid="new-bank-name-wrapper">
                <Label htmlFor="new_bank_name" data-testid="new-bank-name-label">اسم البنك</Label>
                <Input id="new_bank_name" value={bankForm.name} onChange={(event) => setBankForm((current) => ({ ...current, name: event.target.value }))} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="new-bank-name-input" />
              </div>
              <div className="space-y-2" data-testid="new-bank-code-wrapper">
                <Label htmlFor="new_bank_code" data-testid="new-bank-code-label">كود البنك</Label>
                <Input id="new_bank_code" value={bankForm.code} onChange={(event) => setBankForm((current) => ({ ...current, code: event.target.value }))} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="new-bank-code-input" />
              </div>
              <div className="space-y-2" data-testid="new-bank-swift-wrapper">
                <Label htmlFor="new_bank_swift" data-testid="new-bank-swift-label">SWIFT CODE</Label>
                <Input id="new_bank_swift" value={bankForm.swift_code} onChange={(event) => setBankForm((current) => ({ ...current, swift_code: event.target.value }))} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="new-bank-swift-input" />
              </div>
              <div className="space-y-2" data-testid="new-bank-logo-wrapper">
                <Label htmlFor="new_bank_logo" data-testid="new-bank-logo-label">رابط اللوجو اختياري</Label>
                <Input id="new_bank_logo" value={bankForm.logo_url} onChange={(event) => setBankForm((current) => ({ ...current, logo_url: event.target.value }))} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="new-bank-logo-input" />
              </div>
              <div className="space-y-2" data-testid="new-bank-color-wrapper">
                <Label htmlFor="new_bank_color" data-testid="new-bank-color-label">لون مميز</Label>
                <Input id="new_bank_color" type="color" value={bankForm.color} onChange={(event) => setBankForm((current) => ({ ...current, color: event.target.value }))} className="h-12 rounded-lg bg-slate-50 p-1" data-testid="new-bank-color-input" />
              </div>
              <Button type="submit" className="h-12 rounded-lg bg-slate-950 text-white md:col-span-2" data-testid="create-bank-submit-button"><Plus className="h-4 w-4" /> إضافة البنك</Button>
            </form>
          </section>}

          {activeAdminSection === "opening-balances" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="opening-balances-section">
            <div className="mb-5" data-testid="opening-balances-heading">
              <p className="text-sm font-extrabold text-emerald-700" data-testid="opening-balances-eyebrow">الأرصدة الافتتاحية</p>
              <h2 className="text-2xl font-extrabold" data-testid="opening-balances-title">رصيد افتتاحي لكل بنك</h2>
            </div>
            <div className="space-y-3" data-testid="opening-balances-list">
              {banks.map((bank) => (
                <div key={bank.id} className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 md:grid-cols-[1fr_220px_auto] md:items-end" data-testid={`opening-balance-row-${bank.id}`}>
                  <div data-testid={`opening-balance-bank-${bank.id}`}>
                    <p className="font-extrabold text-slate-950" data-testid={`opening-balance-bank-name-${bank.id}`}>{bank.name}</p>
                    <p className="text-xs font-bold text-slate-500" data-testid={`opening-balance-bank-code-${bank.id}`}>{bank.code}</p>
                  </div>
                  <div className="space-y-2" data-testid={`opening-balance-input-wrapper-${bank.id}`}>
                    <Label data-testid={`opening-balance-label-${bank.id}`}>الرصيد الافتتاحي</Label>
                    <Input inputMode="decimal" value={openingBalances[bank.id] || ""} onChange={(event) => updateOpeningBalanceInput(bank.id, event.target.value)} className="h-11 rounded-lg bg-white text-right" data-testid={`opening-balance-input-${bank.id}`} />
                  </div>
                  <Button type="button" onClick={() => saveOpeningBalance(bank.id)} className="h-11 rounded-lg bg-slate-950 text-white" data-testid={`save-opening-balance-button-${bank.id}`}><Save className="h-4 w-4" /> حفظ</Button>
                </div>
              ))}
            </div>
          </section>}

          {(activeAdminSection === "security-review" || activeAdminSection === "audit-log") && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="security-review-section">
            <div className="mb-5 flex items-center gap-3" data-testid="security-review-heading">
              <ShieldCheck className="h-6 w-6 text-emerald-700" />
              <div><p className="text-sm font-extrabold text-emerald-700" data-testid="security-review-eyebrow">{activeAdminSection === "audit-log" ? "سجل التدقيق" : "المراجعة الأمنية"}</p><h2 className="text-2xl font-extrabold" data-testid="security-review-title">{activeAdminSection === "audit-log" ? "سجل التدقيق Audit Log" : "ضوابط الاقتراب من الاعتماد"}</h2></div>
            </div>
            {activeAdminSection === "security-review" && <div className="grid grid-cols-1 gap-5 xl:grid-cols-2" data-testid="security-review-grid">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid="period-lock-card"><h3 className="mb-3 font-extrabold" data-testid="period-lock-title">إقفال وفتح الفترات المالية</h3><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><select value={periodForm.period_type} onChange={(e) => setPeriodForm((c) => ({ ...c, period_type: e.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-white px-3" data-testid="period-lock-type-select"><option value="monthly">شهري</option><option value="yearly">سنوي</option></select><Input value={periodForm.year} onChange={(e) => setPeriodForm((c) => ({ ...c, year: e.target.value.replace(/[^0-9]/g, '').slice(0,4) }))} placeholder="السنة" data-testid="period-lock-year-input" />{periodForm.period_type === "monthly" && <Input value={periodForm.month} onChange={(e) => setPeriodForm((c) => ({ ...c, month: e.target.value.replace(/[^0-9]/g, '').slice(0,2) }))} placeholder="الشهر" data-testid="period-lock-month-input" />}<select value={periodForm.action} onChange={(e) => setPeriodForm((c) => ({ ...c, action: e.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-white px-3" data-testid="period-lock-action-select"><option value="lock">إقفال</option><option value="unlock">فتح</option></select><Input value={periodForm.reason} onChange={(e) => setPeriodForm((c) => ({ ...c, reason: e.target.value }))} placeholder="سبب الفتح/الإقفال" className="md:col-span-2" data-testid="period-lock-reason-input" /></div><Button onClick={savePeriodLock} disabled={securityLoading} className="mt-3 h-10 bg-slate-950 text-white" data-testid="save-period-lock-button"><Save className="h-4 w-4" /> حفظ الفترة</Button><div className="mt-3 max-h-40 overflow-y-auto space-y-2" data-testid="period-lock-list">{periods.slice(0, 8).map((item) => <p key={item.id} className="rounded bg-white p-2 text-xs font-bold" data-testid={`period-lock-row-${item.id}`}>{item.period_type === 'monthly' ? `${item.month}/${item.year}` : item.year} — {item.is_locked ? 'مقفلة' : 'مفتوحة'} — {item.reason || 'بدون ملاحظات'}</p>)}</div></div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid="report-approval-card"><h3 className="mb-3 font-extrabold" data-testid="report-approval-title">اعتماد التقارير</h3><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><Input value={approvalForm.report_name} onChange={(e) => setApprovalForm((c) => ({ ...c, report_name: e.target.value }))} placeholder="اسم التقرير" data-testid="approval-report-name-input" /><Input value={approvalForm.report_reference} onChange={(e) => setApprovalForm((c) => ({ ...c, report_reference: e.target.value }))} placeholder="رقم التقرير/الإذن" data-testid="approval-report-reference-input" /><Input value={approvalForm.period_label} onChange={(e) => setApprovalForm((c) => ({ ...c, period_label: e.target.value }))} placeholder="الفترة" data-testid="approval-period-label-input" /><Input value={approvalForm.approver_title} onChange={(e) => setApprovalForm((c) => ({ ...c, approver_title: e.target.value }))} placeholder="صفة المعتمد" data-testid="approval-approver-title-input" /><select value={approvalForm.status} onChange={(e) => setApprovalForm((c) => ({ ...c, status: e.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-white px-3" data-testid="approval-status-select"><option value="unapproved">غير معتمد</option><option value="approved">معتمد</option><option value="cancelled">تم إلغاء الاعتماد</option></select><Input value={approvalForm.notes} onChange={(e) => setApprovalForm((c) => ({ ...c, notes: e.target.value }))} placeholder="ملاحظات" data-testid="approval-notes-input" /></div><Button onClick={saveReportApproval} disabled={securityLoading} className="mt-3 h-10 bg-slate-950 text-white" data-testid="save-report-approval-button"><Save className="h-4 w-4" /> اعتماد التقرير</Button><div className="mt-3 max-h-40 overflow-y-auto space-y-2" data-testid="report-approvals-list">{approvals.slice(0, 8).map((item) => <p key={item.id} className="rounded bg-white p-2 text-xs font-bold" data-testid={`approval-row-${item.id}`}>{item.approval_number} — {item.report_name} — {item.approver_name} — {item.status}</p>)}</div></div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid="backup-card"><h3 className="mb-3 font-extrabold" data-testid="backup-title">النسخ الاحتياطي والاستعادة</h3><div className="grid grid-cols-1 gap-3 md:grid-cols-2"><Input type="password" value={backupPassword} onChange={(e) => setBackupPassword(e.target.value)} placeholder="كلمة مرور النسخة" data-testid="backup-password-input" /><Button onClick={createBackup} disabled={securityLoading} className="h-10 bg-slate-950 text-white" data-testid="create-backup-button">إنشاء نسخة مشفرة</Button><Input type="file" accept=".enc" onChange={(e) => setRestoreFile(e.target.files?.[0] || null)} data-testid="restore-backup-file-input" /><Input type="password" value={restorePassword} onChange={(e) => setRestorePassword(e.target.value)} placeholder="كلمة مرور الاستعادة" data-testid="restore-backup-password-input" /></div><Button onClick={restoreBackup} disabled={securityLoading} variant="outline" className="mt-3 h-10 bg-white" data-testid="restore-backup-button">استعادة النسخة</Button><div className="mt-3 max-h-40 overflow-y-auto space-y-2" data-testid="backups-list">{backups.slice(0, 8).map((item) => <div key={item.id} className="flex items-center justify-between rounded bg-white p-2 text-xs font-bold" data-testid={`backup-row-${item.id}`}><span>{item.file_name} — {item.file_size} بايت</span><button type="button" onClick={() => downloadBackup(item)} className="text-emerald-700" data-testid={`download-backup-link-${item.id}`}>تحميل</button></div>)}</div></div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid="security-checklist-card"><h3 className="mb-3 font-extrabold" data-testid="security-checklist-title">مؤشرات المراجعة والأمان</h3><ul className="space-y-2 text-sm font-bold text-slate-700" data-testid="security-checklist"><li>✓ سجل تدقيق لكل عمليات API المؤثرة.</li><li>✓ إقفال شهري وسنوي ومنع تعديل الفترات المقفلة.</li><li>✓ اعتماد تقارير برقم اعتماد واسم معتمد وملاحظات.</li><li>✓ نسخ احتياطي مشفر بكلمة مرور يحددها الأدمن.</li><li>✓ دليل إجراءات: الإدخال للمستخدم، المراجعة للأدمن، الاعتماد عبر هذه الصفحة، الإقفال بعد نهاية الفترة، وفتح الفترة بسبب مكتوب.</li><li>⚠ مراجعة محاسب قانوني ومراجعة أمنية خارجية لا تتم آلياً ويجب تنفيذها بواسطة مختص.</li></ul></div>
            </div>}
            {activeAdminSection === "audit-log" && <div className="mt-5 rounded-lg border border-slate-200 bg-white p-4" data-testid="audit-log-card"><h3 className="mb-3 font-extrabold" data-testid="audit-log-title">سجل التدقيق Audit Log</h3><div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_1fr_auto]" data-testid="audit-log-filter-grid"><select value={auditFilter.year} onChange={(event) => setAuditFilter((current) => ({ ...current, year: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-slate-50 px-3 font-extrabold" data-testid="audit-log-year-filter"><option value="all">كل السنوات</option>{adminYearOptions.map((year) => <option key={year} value={year}>{year}</option>)}</select><select value={auditFilter.month} onChange={(event) => setAuditFilter((current) => ({ ...current, month: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-slate-50 px-3 font-extrabold" data-testid="audit-log-month-filter"><option value="all">كل الشهور</option>{adminMonthOptions.map((month) => <option key={month} value={month}>{month}</option>)}</select><select value={auditFilter.hour} onChange={(event) => setAuditFilter((current) => ({ ...current, hour: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-slate-50 px-3 font-extrabold" data-testid="audit-log-hour-filter"><option value="all">كل الساعات</option>{adminHourOptions.map((hour) => <option key={hour} value={hour}>{hour}:00</option>)}</select><Button type="button" onClick={loadSecurityReview} className="h-11 rounded-lg bg-slate-950 text-white" data-testid="apply-audit-log-filter-button">تطبيق الفلتر</Button></div><div className="max-h-[520px] overflow-y-auto space-y-2" data-testid="audit-log-list">{auditLogs.map((item) => <div key={item.id} className="grid grid-cols-1 gap-2 rounded bg-slate-50 p-3 text-xs font-bold md:grid-cols-[120px_110px_90px_120px_1fr_70px]" data-testid={`audit-log-row-${item.id}`}><span data-testid={`audit-log-row-${item.id}-date`}>{new Date(item.created_at).toLocaleDateString('ar-EG')}</span><span data-testid={`audit-log-row-${item.id}-time`}>{new Date(item.created_at).toLocaleTimeString('ar-EG')}</span><span data-testid={`audit-log-row-${item.id}-hour`}>{new Date(item.created_at).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}</span><span data-testid={`audit-log-row-${item.id}-username`}>{item.username || 'غير معروف'}</span><span data-testid={`audit-log-row-${item.id}-action`}>{item.action}</span><span data-testid={`audit-log-row-${item.id}-status`}>{item.status_code}</span></div>)}</div></div>}
          </section>}

          {activeAdminSection === "users" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="users-list-section">
            <h2 className="mb-5 text-2xl font-extrabold" data-testid="users-list-title">المستخدمون المسجلون</h2>
            <div className="space-y-3" data-testid="users-list">
              {users.map((item) => (
                <div key={item.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4" data-testid={`user-row-${item.id}`}>
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div data-testid={`user-row-${item.id}-identity`}>
                      <p className="text-lg font-extrabold" data-testid={`user-row-${item.id}-username`}>{item.username}</p>
                      <p className="text-sm font-bold text-slate-500" data-testid={`user-row-${item.id}-role`}>{item.role === "admin" ? "أدمن" : "مستخدم إدخال"}</p>
                    </div>
                    <div className="flex flex-wrap gap-2" data-testid={`user-row-${item.id}-badges`}>
                      <Badge className={item.is_active ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-50" : "bg-red-50 text-red-700 hover:bg-red-50"} data-testid={`user-row-${item.id}-status`}>{item.is_active ? "نشط" : "موقوف"}</Badge>
                      {Object.entries(item.permissions || {}).filter(([, enabled]) => enabled).map(([key]) => (
                        <Badge key={key} variant="outline" data-testid={`user-row-${item.id}-permission-${key}`}>{permissionLabels[key]}</Badge>
                      ))}
                    </div>
                  </div>
                  {item.role !== "admin" && (
                    <div className="mt-4 space-y-3" data-testid={`user-row-${item.id}-actions`}>
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2" data-testid={`user-row-${item.id}-permissions-editor`}>
                        {Object.entries(permissionLabels).map(([key, label]) => (
                          <button key={key} type="button" onClick={() => toggleExistingPermission(item, key)} className={`flex items-center justify-between rounded-lg border p-3 text-sm font-extrabold transition-colors ${item.permissions?.[key] ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-white text-slate-500"}`} data-testid={`user-row-${item.id}-permission-${key}-toggle`}>
                            {label}
                            {item.permissions?.[key] ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                          </button>
                        ))}
                      </div>
                      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto_auto_auto]" data-testid={`user-row-${item.id}-security-actions`}>
                      <Input type="password" placeholder="كلمة مرور جديدة" value={resetPasswords[item.id] || ""} onChange={(event) => setResetPasswords((current) => ({ ...current, [item.id]: event.target.value }))} className="h-11 rounded-lg bg-white text-right" data-testid={`user-row-${item.id}-reset-password-input`} />
                      <Button type="button" variant="outline" className="h-11 rounded-lg bg-white" onClick={() => updateUser(item, { password: resetPasswords[item.id] })} data-testid={`user-row-${item.id}-reset-password-button`}>تغيير كلمة المرور</Button>
                      <Button type="button" variant="outline" className="h-11 rounded-lg bg-white" onClick={() => updateUser(item, { is_active: !item.is_active })} data-testid={`user-row-${item.id}-toggle-active-button`}>{item.is_active ? "إيقاف" : "تفعيل"}</Button>
                      <Button type="button" variant="outline" className="h-11 rounded-lg border-red-200 bg-red-50 text-red-700 hover:bg-red-100" onClick={() => deleteUser(item)} data-testid={`user-row-${item.id}-delete-button`}><Trash2 className="h-4 w-4" /> حذف المستخدم</Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>}
        </div>

        <aside className="space-y-6" data-testid="admin-security-column">
          {activeAdminSection === "general-settings" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="general-app-settings-section">
            <div className="mb-5 flex items-center gap-3" data-testid="general-app-settings-heading">
              <FileImage className="h-6 w-6 text-emerald-700" />
              <div>
                <p className="text-sm font-extrabold text-emerald-700" data-testid="general-app-settings-eyebrow">الإعدادات العامة</p>
                <h2 className="text-2xl font-extrabold" data-testid="general-app-settings-title">اسم النظام وشعار الاختصار</h2>
              </div>
            </div>
            <form onSubmit={saveAppSystemName} className="space-y-3" data-testid="general-app-name-form">
              <div className="space-y-2" data-testid="app-system-name-wrapper">
                <Label htmlFor="app_system_name" data-testid="app-system-name-label">اسم النظام</Label>
                <Input id="app_system_name" value={systemName} onChange={(event) => setSystemName(event.target.value)} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="app-system-name-input" />
              </div>
              <div className="space-y-2" data-testid="app-organization-name-wrapper">
                <Label htmlFor="app_organization_name" data-testid="app-organization-name-label">اسم الجهة/النقابة</Label>
                <Input id="app_organization_name" value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="app-organization-name-input" />
              </div>
              <Button type="submit" disabled={settingsLoading} className="h-11 w-full rounded-lg bg-slate-950 text-white" data-testid="save-app-system-name-button"><Save className="h-4 w-4" /> حفظ الاسم والجهة</Button>
            </form>
            <div className="mt-5 space-y-3" data-testid="shortcut-icon-settings-panel">
              <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3" data-testid="shortcut-icon-preview-card">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-white ring-1 ring-slate-200" data-testid="shortcut-icon-preview-frame">
                  {appSettings?.shortcut_icon_url ? <img src={appSettings.shortcut_icon_url} alt="شعار الاختصار الحالي" className="h-10 w-10 object-contain" data-testid="shortcut-icon-preview-image" /> : <FileImage className="h-7 w-7 text-slate-500" data-testid="shortcut-icon-preview-placeholder" />}
                </div>
                <div className="min-w-0" data-testid="shortcut-icon-status-block">
                  <p className="font-extrabold text-slate-950" data-testid="shortcut-icon-status-title">أيقونة اختصار سطح المكتب</p>
                  <p className="text-xs font-bold text-slate-500" data-testid="shortcut-icon-status-text">{appSettings?.shortcut_update_status || "لم يتم رفع أيقونة مخصصة بعد"}</p>
                </div>
              </div>
              <div className="space-y-2" data-testid="shortcut-icon-file-wrapper">
                <Label htmlFor="shortcut_icon_file" data-testid="shortcut-icon-file-label">رفع PNG / JPG / ICO</Label>
                <Input id="shortcut_icon_file" type="file" accept=".png,.jpg,.jpeg,.ico,image/png,image/jpeg,image/x-icon,image/vnd.microsoft.icon" onChange={(event) => setShortcutIconFile(event.target.files?.[0] || null)} className="h-12 rounded-lg bg-slate-50 text-right" data-testid="shortcut-icon-file-input" />
              </div>
              <Button type="button" onClick={saveShortcutIcon} disabled={settingsLoading} variant="outline" className="h-11 w-full rounded-lg bg-white" data-testid="save-shortcut-icon-button"><FileUp className="h-4 w-4" /> تحديث شعار الاختصار</Button>
            </div>
          </section>}

          {activeAdminSection === "admin-password" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="admin-password-section">
            <div className="mb-5 flex items-center gap-3" data-testid="admin-password-heading">
              <LockKeyhole className="h-6 w-6 text-slate-950" />
              <h2 className="text-2xl font-extrabold" data-testid="admin-password-title">تغيير كلمة مرور الأدمن</h2>
            </div>
            <form onSubmit={changeAdminPassword} className="space-y-4" data-testid="admin-password-form">
              <div className="space-y-2" data-testid="admin-current-password-wrapper">
                <Label htmlFor="current_password" data-testid="admin-current-password-label">كلمة المرور الحالية</Label>
                <Input id="current_password" type="password" value={passwordForm.current_password} onChange={(event) => setPasswordForm((current) => ({ ...current, current_password: event.target.value }))} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="admin-current-password-input" />
              </div>
              <div className="space-y-2" data-testid="admin-new-password-wrapper">
                <Label htmlFor="admin_new_password" data-testid="admin-new-password-label">كلمة المرور الجديدة</Label>
                <Input id="admin_new_password" type="password" value={passwordForm.new_password} onChange={(event) => setPasswordForm((current) => ({ ...current, new_password: event.target.value }))} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="admin-new-password-input" />
              </div>
              <Button type="submit" className="h-12 w-full rounded-lg bg-slate-950 text-white" data-testid="admin-change-password-button"><Save className="h-4 w-4" /> حفظ كلمة المرور</Button>
            </form>
          </section>}

          {activeAdminSection === "admin-password" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="admin-2fa-section">
            <div className="mb-5 flex items-center gap-3" data-testid="admin-2fa-heading">
              <QrCode className="h-6 w-6 text-emerald-700" />
              <h2 className="text-2xl font-extrabold" data-testid="admin-2fa-title">Google Authenticator</h2>
            </div>
            <Badge className={user?.totp_enabled ? "mb-4 bg-emerald-50 text-emerald-700 hover:bg-emerald-50" : "mb-4 bg-amber-50 text-amber-700 hover:bg-amber-50"} data-testid="admin-2fa-status">
              {user?.totp_enabled ? "المصادقة الثنائية مفعلة" : "المصادقة الثنائية غير مفعلة"}
            </Badge>
            <Button type="button" onClick={setup2FA} variant="outline" className="h-12 w-full rounded-lg bg-white" data-testid="admin-2fa-setup-button">إظهار QR Code / إعادة الضبط</Button>
            {twoFactor && (
              <div className="mt-5 space-y-4" data-testid="admin-2fa-setup-panel">
                <img src={twoFactor.qr_data_url} alt="QR Code Google Authenticator" className="mx-auto h-48 w-48 rounded-xl border border-slate-200 bg-white p-2" data-testid="admin-2fa-qr-image" />
                <p className="break-all rounded-lg bg-slate-50 p-3 text-center text-sm font-bold text-slate-600" data-testid="admin-2fa-manual-secret">{twoFactor.manual_secret}</p>
                <Input value={otpCode} onChange={(event) => setOtpCode(event.target.value)} placeholder="أدخل كود التطبيق" className="h-12 rounded-lg bg-emerald-50 text-center text-lg font-extrabold tracking-widest" data-testid="admin-2fa-code-input" />
                <Button type="button" onClick={verify2FA} className="h-12 w-full rounded-lg bg-emerald-700 text-white hover:bg-emerald-800" data-testid="admin-2fa-verify-button"><ShieldCheck className="h-4 w-4" /> تفعيل المصادقة الثنائية</Button>
              </div>
            )}
          </section>}
        </aside>
      </section>
      <footer className="mx-auto max-w-7xl px-4 pb-8 sm:px-6 lg:px-8" data-testid="admin-footer">
        <CreditLine testId="admin-creator-credit" />
      </footer>
    </main>
  );
}
