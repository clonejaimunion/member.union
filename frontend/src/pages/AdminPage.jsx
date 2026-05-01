import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Building2, FileImage, FileUp, KeyRound, LockKeyhole, PlugZap, Plus, Save, ShieldCheck, SlidersHorizontal, ToggleLeft, ToggleRight, Trash2, UserCog, UsersRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import { useAppSettings } from "@/contexts/AppSettingsContext";
import { api } from "@/lib/api";
import { CreditLine } from "@/components/CreditLine";
import { moduleDefinitions } from "@/lib/modules";

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
  full_name: "",
  password: "",
  role: "user",
  organization_id: "",
  permissions: { enter_deposits: true, view_reports: true, edit_deposits: false, manage_reconciliations: true, manage_revenues: true, manage_expenses: true, manage_users: false, add_revenue: true, approve_revenue: false, add_expense: true, approve_reports: false, lock_periods: false, edit_revenue: false, delete_revenue: false, edit_expense: false, delete_expense: false, unlock_periods: false, manage_einvoice: false, manage_backups: false },
  is_active: true,
};

const currentAdminDate = new Date();
const adminYearOptions = Array.from({ length: 16 }, (_, index) => String(currentAdminDate.getFullYear() - 5 + index));
const adminMonthOptions = Array.from({ length: 12 }, (_, index) => String(index + 1).padStart(2, "0"));
const adminHourOptions = Array.from({ length: 24 }, (_, index) => String(index).padStart(2, "0"));
const defaultPeriodForm = { period_type: "monthly", year: String(currentAdminDate.getFullYear()), month: String(currentAdminDate.getMonth() + 1), action: "lock", reason: "" };
const defaultApprovalForm = { report_type: "عام", report_name: "", report_reference: "", period_label: "", status: "approved", approver_title: "", notes: "" };
const defaultEtaIntegration = {
  environment: "preprod",
  issuer_tax_number: "",
  issuer_name: "",
  branch_code: "0",
  activity_code: "",
  client_id: "",
  client_secret: "",
  sdk_command_template: "",
  certificate_label: "",
  token_pin: "",
  auto_submit_after_generation: false,
  portal_url: "",
  notes: "",
};

const defaultAuthorityLogoSettings = [
  { name: "مصلحة الضرائب المصرية", enabled: true, src: "" },
  { name: "مصلحة الخزانة العامة", enabled: true, src: "" },
  { name: "وزارة المالية", enabled: true, src: "" },
  { name: "وزارة العمل المصرية", enabled: true, src: "" },
  { name: "وزارة الاتصالات وتكنولوجيا المعلومات", enabled: true, src: "" },
];

const adminSections = [
  { id: "general-settings", title: "الإعدادات العامة", subtitle: "اسم النظام والجهة وشعار الاختصار", icon: FileImage },
  { id: "feature-settings", title: "إعدادات الخواص", subtitle: "تفعيل وتعطيل وحدات الجهة", icon: SlidersHorizontal },
  { id: "eta-integration", title: "منظومة الضرائب المصرية", subtitle: "ERP API و SDK التوقيع الرقمي", icon: PlugZap },
  { id: "fixed-asset-rates", title: "نسب إهلاك الأصول", subtitle: "تعديل نسب التصنيفات الثابتة", icon: SlidersHorizontal },
  { id: "add-user", title: "إضافة مستخدم", subtitle: "إضافة مستخدم لإدخال البيانات", icon: Plus },
  { id: "users", title: "المستخدمون", subtitle: "المستخدمون المسجلون", icon: UsersRound },
  { id: "admin-password", title: "تغيير كلمة مرور الأدمن", subtitle: "إدارة كلمة المرور فقط", icon: LockKeyhole },
  { id: "add-bank", title: "إضافة بنك", subtitle: "إضافة بنك جديد", icon: Building2 },
  { id: "opening-balances", title: "الأرصدة الافتتاحية", subtitle: "رصيد افتتاحي لكل بنك", icon: Save },
  { id: "security-review", title: "المراجعة الأمنية", subtitle: "ضوابط الاقتراب من الاعتماد", icon: ShieldCheck },
  { id: "audit-log", title: "سجل التدقيق", subtitle: "عرض بالشهر والسنة والساعة", icon: KeyRound },
];

const superAdminOnlySectionIds = new Set(["general-settings", "add-user", "users", "eta-integration"]);

export default function AdminPage() {
  const navigate = useNavigate();
  const { user, logout, refreshMe } = useAuth();
  const { refreshSettings } = useAppSettings();
  const [users, setUsers] = useState([]);
  const [organizations, setOrganizations] = useState([]);
  const [newUser, setNewUser] = useState(defaultUserForm);
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "" });
  const [adminFullName, setAdminFullName] = useState(user?.full_name || "");
  const [resetPasswords, setResetPasswords] = useState({});
  const [fullNameEdits, setFullNameEdits] = useState({});
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
  const [organizationLoginLabel, setOrganizationLoginLabel] = useState("");
  const [organizationEdits, setOrganizationEdits] = useState({});
  const [organizationLabelEdits, setOrganizationLabelEdits] = useState({});
  const [organizationEmailEdits, setOrganizationEmailEdits] = useState({});
  const [newOrganization, setNewOrganization] = useState({ name: "", login_label: "", email: "", clone_from: "social-solidarity" });
  const [unionLogoVisible, setUnionLogoVisible] = useState(true);
  const [unionLogoDataUrl, setUnionLogoDataUrl] = useState("");
  const [authorityLogoSettings, setAuthorityLogoSettings] = useState(defaultAuthorityLogoSettings);
  const [backupEnabled, setBackupEnabled] = useState(true);
  const [backupAllowedRoles, setBackupAllowedRoles] = useState({ super_admin: true, admin: true, user: false });
  const [twoFactorPolicy, setTwoFactorPolicy] = useState({ super_admin: false, admin: false, user: false });
  const [shortcutIconFile, setShortcutIconFile] = useState(null);
  const [moduleSettings, setModuleSettings] = useState({});
  const [moduleLabels, setModuleLabels] = useState(moduleDefinitions);
  const [fixedAssetRates, setFixedAssetRates] = useState([]);
  const [fixedAssetRateEdits, setFixedAssetRateEdits] = useState({});
  const [etaIntegration, setEtaIntegration] = useState(defaultEtaIntegration);
  const [etaConnection, setEtaConnection] = useState(null);
  const [twoFactorSetup, setTwoFactorSetup] = useState(null);
  const [otpCode, setOtpCode] = useState("");
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [moduleSettingsLoading, setModuleSettingsLoading] = useState(false);
  const [securityLoading, setSecurityLoading] = useState(false);
  const [activeAdminSection, setActiveAdminSection] = useState("add-user");
  const [auditFilter, setAuditFilter] = useState({ year: String(currentAdminDate.getFullYear()), month: "all", hour: "all" });
  const effectiveModuleSettings = Object.keys(moduleSettings).length ? moduleSettings : (user?.organization_modules || {});
  const isSuperAdmin = user?.role === "super_admin";
  const visibleAdminSections = adminSections.filter((section) => isSuperAdmin || !superAdminOnlySectionIds.has(section.id));
  const visiblePermissionEntries = Object.entries(permissionLabels).filter(([key]) => key !== "manage_einvoice" || effectiveModuleSettings.electronic_invoice !== false);
  const visiblePermissionKeys = new Set(visiblePermissionEntries.map(([key]) => key));

  const loadUsers = useCallback(() => {
    if (!isSuperAdmin) {
      setUsers([]);
      return;
    }
    api.get("/admin/users").then((response) => setUsers(response.data)).catch(() => toast.error("تعذر تحميل المستخدمين"));
  }, [isSuperAdmin]);

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
      setOrganizationLoginLabel(response.data.organization_login_label || "");
      const orgs = response.data.organizations || {};
      setOrganizationEdits(Object.fromEntries(Object.entries(orgs).map(([id, item]) => [id, item.name || ""])));
      setOrganizationLabelEdits(Object.fromEntries(Object.entries(orgs).map(([id, item]) => [id, item.login_label || ""])));
      setOrganizationEmailEdits(Object.fromEntries(Object.entries(orgs).map(([id, item]) => [id, item.email || ""])));
      setUnionLogoVisible(response.data.login_union_logo_visible !== false);
      setUnionLogoDataUrl(response.data.login_union_logo_data_url || "");
      setAuthorityLogoSettings((response.data.login_authority_logos?.length ? response.data.login_authority_logos : defaultAuthorityLogoSettings).map((item, index) => ({ ...defaultAuthorityLogoSettings[index], ...item })));
      setBackupEnabled(response.data.backup_enabled !== false);
      setBackupAllowedRoles(response.data.backup_allowed_roles || { super_admin: true, admin: true, user: false });
      setTwoFactorPolicy(response.data.two_factor_role_policy || { super_admin: false, admin: false, user: false });
    } catch (error) {
      toast.error("تعذر تحميل إعدادات النظام العامة");
    }
  }, []);

  const loadModuleSettings = useCallback(async () => {
    try {
      const response = await api.get("/admin/organization/modules");
      setModuleSettings(response.data.modules || {});
      setModuleLabels(response.data.module_labels || moduleDefinitions);
    } catch (error) {
      toast.error("تعذر تحميل إعدادات الخواص");
    }
  }, []);

  const loadFixedAssetRates = useCallback(async () => {
    try {
      const response = await api.get("/admin/fixed-assets/categories");
      setFixedAssetRates(response.data);
      setFixedAssetRateEdits(response.data.reduce((acc, item) => ({ ...acc, [item.code]: String(item.annual_depreciation_rate) }), {}));
    } catch (error) {
      toast.error("تعذر تحميل نسب إهلاك الأصول");
    }
  }, []);

  const loadEtaIntegration = useCallback(async () => {
    if (!isSuperAdmin) return;
    try {
      const response = await api.get("/admin/eta-integration");
      setEtaIntegration({
        ...defaultEtaIntegration,
        ...response.data,
        client_secret: "",
        token_pin: "",
      });
      setEtaConnection(response.data.last_connection_status ? { status: response.data.last_connection_status, message: response.data.last_connection_message, required_items: response.data.required_items || [] } : null);
    } catch (error) {
      toast.error("تعذر تحميل إعدادات منظومة الضرائب");
    }
  }, [isSuperAdmin]);

  const loadOrganizations = useCallback(async () => {
    try {
      const response = await api.get("/organizations/public");
      setOrganizations(response.data);
      setNewUser((current) => ({ ...current, organization_id: current.organization_id || response.data[0]?.id || user?.organization_id || "" }));
    } catch (error) {
      toast.error("تعذر تحميل الجهات");
    }
  }, [user?.organization_id]);

  useEffect(() => {
    loadUsers();
    loadBanks();
    loadSecurityReview();
    loadAppSettings();
    loadModuleSettings();
    loadFixedAssetRates();
    loadOrganizations();
    loadEtaIntegration();
  }, [loadBanks, loadSecurityReview, loadUsers, loadAppSettings, loadModuleSettings, loadFixedAssetRates, loadOrganizations, loadEtaIntegration]);

  useEffect(() => {
    if (!isSuperAdmin && superAdminOnlySectionIds.has(activeAdminSection)) {
      setActiveAdminSection("fixed-asset-rates");
    }
  }, [activeAdminSection, isSuperAdmin]);

  useEffect(() => {
    setAdminFullName(user?.full_name || "");
  }, [user?.full_name]);

  const toggleNewPermission = (permission) => {
    setNewUser((current) => ({
      ...current,
      permissions: { ...current.permissions, [permission]: !current.permissions[permission] },
    }));
  };

  const createUser = async (event) => {
    event.preventDefault();
    if (!isSuperAdmin) {
      toast.error("إدارة المستخدمين متاحة لحساب السوبر أدمن admin فقط");
      return;
    }
    try {
      await api.post("/admin/users", newUser);
      toast.success("تم إنشاء المستخدم");
      setNewUser((current) => ({ ...defaultUserForm, organization_id: current.organization_id || user?.organization_id || "" }));
      loadUsers();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إنشاء المستخدم");
    }
  };

  const updateEtaField = (field, value) => setEtaIntegration((current) => ({ ...current, [field]: value }));

  const readImageAsDataUrl = (file, callback) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => callback(reader.result);
    reader.readAsDataURL(file);
  };

  const createOrganization = async () => {
    if (!newOrganization.name.trim()) return toast.error("أدخل اسم الجهة الجديدة");
    try {
      await api.post("/admin/organizations", newOrganization);
      setNewOrganization({ name: "", login_label: "", email: "", clone_from: "social-solidarity" });
      await loadAppSettings();
      await loadOrganizations();
      toast.success("تمت إضافة الجهة الجديدة مع نسخ الخواص الأساسية");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إضافة الجهة");
    }
  };

  const saveEtaIntegration = async () => {
    if (!isSuperAdmin) return toast.error("إعدادات الربط الضريبي متاحة للسوبر أدمن فقط");
    try {
      const payload = { ...etaIntegration };
      if (!payload.client_secret) payload.client_secret = null;
      if (!payload.token_pin) payload.token_pin = null;
      const response = await api.put("/admin/eta-integration", payload);
      setEtaIntegration({ ...defaultEtaIntegration, ...response.data, client_secret: "", token_pin: "" });
      toast.success("تم حفظ إعدادات الربط الضريبي");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ إعدادات الربط الضريبي");
    }
  };

  const testEtaConnection = async () => {
    try {
      const response = await api.post("/admin/eta-integration/test-connection");
      setEtaConnection(response.data);
      if (response.data.status === "configured") toast.success(response.data.message);
      else toast.error(response.data.message);
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر اختبار الاتصال بمنظومة الضرائب");
    }
  };

  const updateUser = async (targetUser, updates) => {
    if (!isSuperAdmin) {
      toast.error("إدارة المستخدمين متاحة لحساب السوبر أدمن admin فقط");
      return;
    }
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
    if (!isSuperAdmin) {
      toast.error("إدارة المستخدمين متاحة لحساب السوبر أدمن admin فقط");
      return;
    }
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

  const saveAdminFullName = async (event) => {
    event.preventDefault();
    try {
      await api.put("/admin/profile", { full_name: adminFullName });
      toast.success("تم حفظ الاسم بالكامل للأدمن");
      await refreshMe();
      loadUsers();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ الاسم بالكامل");
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

  const clearAuditLogs = async () => {
    if (!window.confirm("سيتم مسح محتويات سجل التدقيق بالكامل. هل تريد المتابعة؟")) return;
    try {
      await api.delete("/admin/security/audit-logs");
      setAuditLogs([]);
      toast.success("تم مسح سجل التدقيق");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر مسح سجل التدقيق");
    }
  };

  const setup2FA = async () => {
    try {
      const response = await api.post("/admin/2fa/setup");
      setTwoFactorSetup(response.data);
      toast.info("امسح QR Code من تطبيق Google Authenticator");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إعداد Google Authenticator");
    }
  };

  const verify2FA = async () => {
    try {
      await api.post("/admin/2fa/verify", { otp_code: otpCode });
      setTwoFactorSetup(null);
      setOtpCode("");
      await refreshMe();
      toast.success("تم تفعيل Google Authenticator للحساب");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "كود التحقق غير صحيح");
    }
  };

  const disable2FA = async () => {
    try {
      await api.post("/admin/2fa/disable");
      await refreshMe();
      toast.success("تم تعطيل Google Authenticator لهذا الحساب");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تعطيل الخدمة");
    }
  };

  const downloadProtectedFile = async (url, filename) => {
    try {
      const response = await api.get(url, { responseType: "blob" });
      const objectUrl = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      link.click();
      window.URL.revokeObjectURL(objectUrl);
    } catch (error) {
      toast.error("تعذر تصدير الملف");
    }
  };

  const saveAppSystemName = async (event) => {
    event.preventDefault();
    if (!systemName.trim()) return toast.error("أدخل اسم النظام");
    setSettingsLoading(true);
    try {
      const response = await api.put("/admin/app-settings", {
        system_name: systemName.trim(),
        organization_name: organizationName.trim(),
        organization_login_label: organizationLoginLabel.trim(),
        organization_names: organizationEdits,
        organization_login_labels: organizationLabelEdits,
        organization_emails: organizationEmailEdits,
        login_union_logo_visible: unionLogoVisible,
        login_union_logo_data_url: unionLogoDataUrl,
        login_authority_logos: authorityLogoSettings,
        backup_enabled: backupEnabled,
        backup_allowed_roles: backupAllowedRoles,
        two_factor_role_policy: twoFactorPolicy,
      });
      setAppSettings(response.data);
      setSystemName(response.data.system_name || systemName.trim());
      setOrganizationName(response.data.organization_name || organizationName.trim());
      setOrganizationLoginLabel(response.data.organization_login_label || organizationLoginLabel.trim());
      const orgs = response.data.organizations || {};
      setOrganizationEdits(Object.fromEntries(Object.entries(orgs).map(([id, item]) => [id, item.name || ""])));
      setOrganizationLabelEdits(Object.fromEntries(Object.entries(orgs).map(([id, item]) => [id, item.login_label || ""])));
      setOrganizationEmailEdits(Object.fromEntries(Object.entries(orgs).map(([id, item]) => [id, item.email || ""])));
      setUnionLogoVisible(response.data.login_union_logo_visible !== false);
      setUnionLogoDataUrl(response.data.login_union_logo_data_url || "");
      setAuthorityLogoSettings((response.data.login_authority_logos?.length ? response.data.login_authority_logos : defaultAuthorityLogoSettings).map((item, index) => ({ ...defaultAuthorityLogoSettings[index], ...item })));
      setBackupEnabled(response.data.backup_enabled !== false);
      setBackupAllowedRoles(response.data.backup_allowed_roles || { super_admin: true, admin: true, user: false });
      setTwoFactorPolicy(response.data.two_factor_role_policy || { super_admin: false, admin: false, user: false });
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

  const toggleModuleSetting = (moduleKey) => {
    setModuleSettings((current) => ({ ...current, [moduleKey]: current[moduleKey] === false }));
  };

  const saveModuleSettings = async () => {
    setModuleSettingsLoading(true);
    try {
      const response = await api.put("/admin/organization/modules", { modules: moduleSettings });
      setModuleSettings(response.data.modules || {});
      setModuleLabels(response.data.module_labels || moduleDefinitions);
      await refreshMe();
      toast.success("تم حفظ إعدادات الخواص");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ إعدادات الخواص");
    } finally {
      setModuleSettingsLoading(false);
    }
  };

  const saveFixedAssetRate = async (category) => {
    try {
      const rate = Number(fixedAssetRateEdits[category.code] || 0);
      await api.put(`/admin/fixed-assets/categories/${category.code}`, { annual_depreciation_rate: rate });
      toast.success("تم حفظ نسبة الإهلاك");
      await loadFixedAssetRates();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر حفظ نسبة الإهلاك");
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="admin-page">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur" data-testid="admin-header">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-4" data-testid="admin-heading-block">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="admin-heading-icon"><UserCog className="h-6 w-6" /></div>
            <div>
              <p className="text-sm font-extrabold text-emerald-700" data-testid="admin-eyebrow">لوحة إدارة النظام</p>
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
          {visibleAdminSections.map((section) => {
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
          {isSuperAdmin && activeAdminSection === "add-user" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="create-user-section">
            <div className="mb-5 flex items-center gap-3" data-testid="create-user-heading">
              <UsersRound className="h-6 w-6 text-emerald-700" />
              <h2 className="text-2xl font-extrabold" data-testid="create-user-title">إضافة مستخدم لإدخال البيانات</h2>
            </div>
            <form onSubmit={createUser} className="grid grid-cols-1 gap-4 md:grid-cols-2" data-testid="create-user-form">
              <div className="space-y-2" data-testid="new-user-username-wrapper">
                <Label htmlFor="new_username" data-testid="new-user-username-label">اسم المستخدم</Label>
                <Input id="new_username" value={newUser.username} onChange={(event) => setNewUser((current) => ({ ...current, username: event.target.value }))} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="new-user-username-input" />
              </div>
              <div className="space-y-2" data-testid="new-user-full-name-wrapper">
                <Label htmlFor="new_full_name" data-testid="new-user-full-name-label">الاسم بالكامل (باللغة العربية)</Label>
                <Input id="new_full_name" value={newUser.full_name} onChange={(event) => setNewUser((current) => ({ ...current, full_name: event.target.value }))} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="new-user-full-name-input" />
              </div>
              <div className="space-y-2" data-testid="new-user-password-wrapper">
                <Label htmlFor="new_password" data-testid="new-user-password-label">كلمة المرور</Label>
                <Input id="new_password" type="password" value={newUser.password} onChange={(event) => setNewUser((current) => ({ ...current, password: event.target.value }))} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="new-user-password-input" />
              </div>
              {isSuperAdmin && <div className="space-y-2" data-testid="new-user-role-wrapper">
                <Label data-testid="new-user-role-label">نوع الحساب</Label>
                <select value={newUser.role} onChange={(event) => setNewUser((current) => ({ ...current, role: event.target.value }))} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="new-user-role-select"><option value="user" label="مستخدم" /><option value="admin" label="أدمن" /></select>
              </div>}
              {isSuperAdmin && <div className="space-y-2" data-testid="new-user-organization-wrapper">
                <Label data-testid="new-user-organization-label">الجهة</Label>
                <select value={newUser.organization_id} onChange={(event) => setNewUser((current) => ({ ...current, organization_id: event.target.value }))} className="h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="new-user-organization-select">{organizations.map((organization) => <option key={organization.id} value={organization.id} label={organization.name} />)}</select>
              </div>}
              <div className="md:col-span-2 grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="new-user-permissions-grid">
                {visiblePermissionEntries.map(([key, label]) => (
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
            {activeAdminSection === "audit-log" && <div className="mt-5 rounded-lg border border-slate-200 bg-white p-4" data-testid="audit-log-card"><div className="mb-3 flex items-center justify-between gap-3"><h3 className="font-extrabold" data-testid="audit-log-title">سجل التدقيق Audit Log</h3>{isSuperAdmin && <Button type="button" variant="outline" onClick={clearAuditLogs} className="border-red-200 bg-red-50 text-red-700" data-testid="clear-audit-logs-button">مسح سجل التدقيق</Button>}</div><div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_1fr_auto]" data-testid="audit-log-filter-grid"><select value={auditFilter.year} onChange={(event) => setAuditFilter((current) => ({ ...current, year: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-slate-50 px-3 font-extrabold" data-testid="audit-log-year-filter"><option value="all">كل السنوات</option>{adminYearOptions.map((year) => <option key={year} value={year}>{year}</option>)}</select><select value={auditFilter.month} onChange={(event) => setAuditFilter((current) => ({ ...current, month: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-slate-50 px-3 font-extrabold" data-testid="audit-log-month-filter"><option value="all">كل الشهور</option>{adminMonthOptions.map((month) => <option key={month} value={month}>{month}</option>)}</select><select value={auditFilter.hour} onChange={(event) => setAuditFilter((current) => ({ ...current, hour: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-slate-50 px-3 font-extrabold" data-testid="audit-log-hour-filter"><option value="all">كل الساعات</option>{adminHourOptions.map((hour) => <option key={hour} value={hour}>{hour}:00</option>)}</select><Button type="button" onClick={loadSecurityReview} className="h-11 rounded-lg bg-slate-950 text-white" data-testid="apply-audit-log-filter-button">تطبيق الفلتر</Button></div><div className="max-h-[520px] overflow-y-auto space-y-2" data-testid="audit-log-list">{auditLogs.map((item) => <div key={item.id} className="rounded bg-slate-50 p-3 text-xs font-bold" data-testid={`audit-log-row-${item.id}`}><div className="grid grid-cols-1 gap-2 md:grid-cols-[110px_105px_180px_80px]" data-testid={`audit-log-row-${item.id}-summary`}><span data-testid={`audit-log-row-${item.id}-date`}>{new Date(item.created_at).toLocaleDateString('ar-EG')}</span><span data-testid={`audit-log-row-${item.id}-time`}>{new Date(item.created_at).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}</span><span data-testid={`audit-log-row-${item.id}-actor-full-name`}>{item.actor_full_name || item.username || 'غير معروف'}</span><span data-testid={`audit-log-row-${item.id}-status`}>{item.status_code}</span></div><p className="mt-2 leading-6 text-slate-700" data-testid={`audit-log-row-${item.id}-arabic-description`}>{item.arabic_description || item.action}</p></div>)}</div></div>}
          </section>}

          {isSuperAdmin && activeAdminSection === "users" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="users-list-section">
            <h2 className="mb-5 text-2xl font-extrabold" data-testid="users-list-title">المستخدمون المسجلون</h2>
            <div className="space-y-3" data-testid="users-list">
              {users.map((item) => (
                <div key={item.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4" data-testid={`user-row-${item.id}`}>
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div data-testid={`user-row-${item.id}-identity`}>
                      <p className="text-lg font-extrabold" data-testid={`user-row-${item.id}-username`}>{item.username}</p>
                      <p className="text-sm font-extrabold text-emerald-700" data-testid={`user-row-${item.id}-full-name`}>{item.full_name}</p>
                      <p className="text-sm font-bold text-slate-500" data-testid={`user-row-${item.id}-role`}>{item.role === "admin" ? "أدمن عادي" : "مستخدم إدخال"}</p>
                      {isSuperAdmin && <p className="text-xs font-bold text-slate-500" data-testid={`user-row-${item.id}-organization`}>{item.organization_name}</p>}
                    </div>
                    <div className="flex flex-wrap gap-2" data-testid={`user-row-${item.id}-badges`}>
                      <Badge className={item.is_active ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-50" : "bg-red-50 text-red-700 hover:bg-red-50"} data-testid={`user-row-${item.id}-status`}>{item.is_active ? "نشط" : "موقوف"}</Badge>
                      {Object.entries(item.permissions || {}).filter(([key, enabled]) => enabled && visiblePermissionKeys.has(key)).map(([key]) => (
                        <Badge key={key} variant="outline" data-testid={`user-row-${item.id}-permission-${key}`}>{permissionLabels[key]}</Badge>
                      ))}
                    </div>
                  </div>
                    <div className="mt-4 space-y-3" data-testid={`user-row-${item.id}-actions`}>
                      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[220px_1fr]" data-testid={`user-row-${item.id}-role-editor`}>
                        <div className="space-y-2" data-testid={`user-row-${item.id}-role-select-wrapper`}>
                          <Label data-testid={`user-row-${item.id}-role-select-label`}>نوع الحساب</Label>
                          <select value={item.role} onChange={(event) => updateUser(item, { role: event.target.value })} className="h-11 w-full rounded-lg border border-slate-300 bg-white px-3 font-bold" data-testid={`user-row-${item.id}-role-select`}>
                            <option value="user">مستخدم</option>
                            <option value="admin">أدمن عادي</option>
                          </select>
                        </div>
                        <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-3 text-sm font-bold text-emerald-800" data-testid={`user-row-${item.id}-super-admin-note`}>
                          المسح والتعطيل والتفعيل والتعديل متاح هنا لحساب السوبر أدمن admin فقط.
                        </div>
                      </div>
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2" data-testid={`user-row-${item.id}-permissions-editor`}>
                        {visiblePermissionEntries.map(([key, label]) => (
                          <button key={key} type="button" onClick={() => toggleExistingPermission(item, key)} className={`flex items-center justify-between rounded-lg border p-3 text-sm font-extrabold transition-colors ${item.permissions?.[key] ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-white text-slate-500"}`} data-testid={`user-row-${item.id}-permission-${key}-toggle`}>
                            {label}
                            {item.permissions?.[key] ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                          </button>
                        ))}
                      </div>
                      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto]" data-testid={`user-row-${item.id}-full-name-actions`}>
                        <Input placeholder="الاسم بالكامل باللغة العربية" value={fullNameEdits[item.id] ?? item.full_name ?? ""} onChange={(event) => setFullNameEdits((current) => ({ ...current, [item.id]: event.target.value }))} className="h-11 rounded-lg bg-white text-right" data-testid={`user-row-${item.id}-full-name-input`} />
                        <Button type="button" variant="outline" className="h-11 rounded-lg bg-white" onClick={() => updateUser(item, { full_name: fullNameEdits[item.id] ?? item.full_name })} data-testid={`user-row-${item.id}-save-full-name-button`}>حفظ الاسم بالكامل</Button>
                      </div>
                      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto_auto_auto]" data-testid={`user-row-${item.id}-security-actions`}>
                      <Input type="password" placeholder="كلمة مرور جديدة" value={resetPasswords[item.id] || ""} onChange={(event) => setResetPasswords((current) => ({ ...current, [item.id]: event.target.value }))} className="h-11 rounded-lg bg-white text-right" data-testid={`user-row-${item.id}-reset-password-input`} />
                      <Button type="button" variant="outline" className="h-11 rounded-lg bg-white" onClick={() => updateUser(item, { password: resetPasswords[item.id] })} data-testid={`user-row-${item.id}-reset-password-button`}>تغيير كلمة المرور</Button>
                      <Button type="button" variant="outline" className="h-11 rounded-lg bg-white" onClick={() => updateUser(item, { is_active: !item.is_active })} data-testid={`user-row-${item.id}-toggle-active-button`}>{item.is_active ? "تعطيل" : "تفعيل"}</Button>
                      <Button type="button" variant="outline" className="h-11 rounded-lg border-red-200 bg-red-50 text-red-700 hover:bg-red-100" onClick={() => deleteUser(item)} data-testid={`user-row-${item.id}-delete-button`}><Trash2 className="h-4 w-4" /> مسح</Button>
                      </div>
                    </div>
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
                <Label htmlFor="app_system_name" data-testid="app-system-name-label">اسم البرنامج بالكامل</Label>
                <Input id="app_system_name" value={systemName} onChange={(event) => setSystemName(event.target.value)} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="app-system-name-input" />
              </div>
              <div className="space-y-2" data-testid="app-organization-name-wrapper">
                <Label htmlFor="app_organization_name" data-testid="app-organization-name-label">اسم الجهة/النقابة</Label>
                <Input id="app_organization_name" value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="app-organization-name-input" />
              </div>
              <div className="space-y-2" data-testid="app-organization-login-label-wrapper">
                <Label htmlFor="app_organization_login_label" data-testid="app-organization-login-label-label">اسم الجهة المختصر في شاشة الدخول</Label>
                <Input id="app_organization_login_label" value={organizationLoginLabel} onChange={(event) => setOrganizationLoginLabel(event.target.value)} required className="h-12 rounded-lg bg-slate-50 text-right" data-testid="app-organization-login-label-input" />
              </div>
              <div className="space-y-3 rounded-lg border border-emerald-100 bg-emerald-50 p-4" data-testid="all-organizations-names-editor">
                <p className="text-sm font-extrabold text-emerald-800" data-testid="all-organizations-names-title">تعديل أسماء الجهات في كل البرنامج</p>
                {Object.entries(appSettings?.organizations || {}).map(([orgId, organization]) => (
                  <div key={orgId} className="grid grid-cols-1 gap-3 lg:grid-cols-3" data-testid={`organization-global-editor-${orgId}`}>
                    <div className="space-y-2" data-testid={`organization-name-wrapper-${orgId}`}>
                      <Label data-testid={`organization-name-label-${orgId}`}>الاسم الكامل - {organization.login_label}</Label>
                      <Input value={organizationEdits[orgId] || ""} onChange={(event) => setOrganizationEdits((current) => ({ ...current, [orgId]: event.target.value }))} className="h-11 bg-white text-right" data-testid={`organization-name-input-${orgId}`} />
                    </div>
                    <div className="space-y-2" data-testid={`organization-login-label-wrapper-${orgId}`}>
                      <Label data-testid={`organization-login-label-label-${orgId}`}>الاسم المختصر</Label>
                      <Input value={organizationLabelEdits[orgId] || ""} onChange={(event) => setOrganizationLabelEdits((current) => ({ ...current, [orgId]: event.target.value }))} className="h-11 bg-white text-right" data-testid={`organization-login-label-input-${orgId}`} />
                    </div>
                    <div className="space-y-2" data-testid={`organization-email-wrapper-${orgId}`}>
                      <Label data-testid={`organization-email-label-${orgId}`}>البريد الإلكتروني للمطبوعات</Label>
                      <Input value={organizationEmailEdits[orgId] || ""} onChange={(event) => setOrganizationEmailEdits((current) => ({ ...current, [orgId]: event.target.value }))} className="h-11 bg-white text-right" data-testid={`organization-email-input-${orgId}`} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid="new-organization-panel">
                <p className="text-sm font-extrabold text-slate-800" data-testid="new-organization-title">إضافة جهة جديدة مع نسخ كل الخواص</p>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <Input placeholder="اسم الجهة الجديدة" value={newOrganization.name} onChange={(event) => setNewOrganization((current) => ({ ...current, name: event.target.value }))} data-testid="new-organization-name-input" />
                  <Input placeholder="الاسم المختصر" value={newOrganization.login_label} onChange={(event) => setNewOrganization((current) => ({ ...current, login_label: event.target.value }))} data-testid="new-organization-label-input" />
                  <Input placeholder="البريد الإلكتروني" value={newOrganization.email} onChange={(event) => setNewOrganization((current) => ({ ...current, email: event.target.value }))} data-testid="new-organization-email-input" />
                  <select value={newOrganization.clone_from} onChange={(event) => setNewOrganization((current) => ({ ...current, clone_from: event.target.value }))} className="h-11 rounded-lg border border-slate-300 bg-white px-3 font-bold" data-testid="new-organization-clone-select">
                    {organizations.map((item) => <option key={item.id} value={item.id}>{item.login_label}</option>)}
                  </select>
                </div>
                <Button type="button" onClick={createOrganization} variant="outline" className="h-11 w-full bg-white" data-testid="create-new-organization-button"><Plus className="h-4 w-4" /> إضافة الجهة</Button>
              </div>
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid="login-logo-settings-panel">
                <p className="text-sm font-extrabold text-slate-800" data-testid="login-logo-settings-title">شعارات صفحة تسجيل الدخول</p>
                <label className="flex items-center justify-between rounded-lg bg-white p-3 font-bold" data-testid="toggle-union-login-logo-label"><span>إظهار شعار النقابة الكبير</span><input type="checkbox" checked={unionLogoVisible} onChange={(event) => setUnionLogoVisible(event.target.checked)} data-testid="toggle-union-login-logo-checkbox" /></label>
                <Input type="file" accept="image/*" onChange={(event) => readImageAsDataUrl(event.target.files?.[0], setUnionLogoDataUrl)} data-testid="union-login-logo-file-input" />
                {authorityLogoSettings.map((logo, index) => <div key={logo.name} className="grid grid-cols-1 gap-2 rounded-lg bg-white p-3 md:grid-cols-[auto_1fr_1fr]" data-testid={`authority-logo-editor-${index}`}><label className="flex items-center gap-2 font-bold"><input type="checkbox" checked={logo.enabled !== false} onChange={(event) => setAuthorityLogoSettings((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, enabled: event.target.checked } : item))} data-testid={`authority-logo-enabled-${index}`} /> إظهار</label><Input value={logo.name} onChange={(event) => setAuthorityLogoSettings((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, name: event.target.value } : item))} data-testid={`authority-logo-name-${index}`} /><Input type="file" accept="image/*" onChange={(event) => readImageAsDataUrl(event.target.files?.[0], (url) => setAuthorityLogoSettings((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, src: url } : item)))} data-testid={`authority-logo-file-${index}`} /></div>)}
              </div>
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid="security-policy-settings-panel">
                <p className="text-sm font-extrabold text-slate-800">النسخ الاحتياطي و Google Authenticator</p>
                <label className="flex items-center justify-between rounded-lg bg-white p-3 font-bold"><span>تشغيل خدمة النسخ الاحتياطي</span><input type="checkbox" checked={backupEnabled} onChange={(event) => setBackupEnabled(event.target.checked)} data-testid="backup-enabled-checkbox" /></label>
                {['super_admin','admin','user'].map((role) => <div key={role} className="grid grid-cols-2 gap-2 rounded-lg bg-white p-3 text-sm font-bold" data-testid={`role-policy-${role}`}><label><input type="checkbox" checked={backupAllowedRoles[role] !== false} onChange={(event) => setBackupAllowedRoles((current) => ({ ...current, [role]: event.target.checked }))} /> نسخ احتياطي: {role}</label><label><input type="checkbox" checked={twoFactorPolicy[role] === true} onChange={(event) => setTwoFactorPolicy((current) => ({ ...current, [role]: event.target.checked }))} /> Google Authenticator: {role}</label></div>)}
                <p className="text-xs font-bold text-amber-700">تنبيه: تفعيل Google Authenticator يحتاج اتصال إنترنت وقت تثبيت التطبيق أو مسح الرمز أول مرة فقط.</p>
              </div>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-3" data-testid="training-export-buttons"><Button type="button" variant="outline" className="bg-white" onClick={() => downloadProtectedFile('/admin/training/manual.pdf', 'دليل-استخدام-البرنامج.pdf')} data-testid="download-training-manual-link">كتيب PDF</Button><Button type="button" variant="outline" className="bg-white" onClick={() => downloadProtectedFile('/admin/training/video-guide.gif', 'فيديو-استرشادي.gif')} data-testid="download-training-video-link">فيديو Slideshow</Button><Button type="button" variant="outline" className="bg-white" onClick={() => downloadProtectedFile('/admin/training/screenshots.zip', 'لقطات-صفحات-البرنامج.zip')} data-testid="download-screenshots-zip-link">Screenshots ZIP</Button></div>
              <Button type="submit" disabled={settingsLoading} className="h-11 w-full rounded-lg bg-slate-950 text-white" data-testid="save-app-system-name-button"><Save className="h-4 w-4" /> حفظ أسماء البرنامج والجهات</Button>
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

          {activeAdminSection === "feature-settings" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="feature-settings-section">
            <div className="mb-5 flex items-center gap-3" data-testid="feature-settings-heading">
              <SlidersHorizontal className="h-6 w-6 text-emerald-700" />
              <div>
                <p className="text-sm font-extrabold text-emerald-700" data-testid="feature-settings-eyebrow">إعدادات الخواص</p>
                <h2 className="text-2xl font-extrabold" data-testid="feature-settings-title">تفعيل وتعطيل وحدات الجهة</h2>
              </div>
            </div>
            <p className="mb-4 rounded-lg bg-slate-50 p-3 text-sm font-bold text-slate-600" data-testid="feature-settings-note">التغييرات تطبق على الجهة الحالية فقط: {user?.organization_name}</p>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="feature-settings-grid">
              {Object.entries(moduleLabels).map(([moduleKey, label]) => {
                const enabled = moduleSettings[moduleKey] !== false;
                return (
                  <button key={moduleKey} type="button" onClick={() => toggleModuleSetting(moduleKey)} className={`flex items-center justify-between rounded-lg border p-4 text-sm font-extrabold transition-colors ${enabled ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-slate-50 text-slate-500"}`} data-testid={`feature-module-${moduleKey}-toggle`}>
                    <span data-testid={`feature-module-${moduleKey}-label`}>{label}</span>
                    {enabled ? <ToggleRight className="h-5 w-5" /> : <ToggleLeft className="h-5 w-5" />}
                  </button>
                );
              })}
            </div>
            <Button type="button" onClick={saveModuleSettings} disabled={moduleSettingsLoading} className="mt-5 h-11 w-full rounded-lg bg-slate-950 text-white" data-testid="save-feature-settings-button"><Save className="h-4 w-4" /> حفظ إعدادات الخواص</Button>
          </section>}

          {isSuperAdmin && activeAdminSection === "eta-integration" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="eta-integration-section">
            <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between" data-testid="eta-integration-heading">
              <div className="flex items-center gap-3">
                <PlugZap className="h-6 w-6 text-emerald-700" />
                <div>
                  <p className="text-sm font-extrabold text-emerald-700" data-testid="eta-integration-eyebrow">ERP System / API Integration</p>
                  <h2 className="text-2xl font-extrabold" data-testid="eta-integration-title">الربط والتكامل مع منظومة الضرائب المصرية</h2>
                </div>
              </div>
              <Badge className={etaIntegration.is_configured ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-50" : "bg-amber-50 text-amber-800 hover:bg-amber-50"} data-testid="eta-integration-status-badge">
                {etaIntegration.is_configured ? "جاهز للاختبار" : "بيانات ناقصة"}
              </Badge>
            </div>
            <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-3" data-testid="eta-integration-summary-grid">
              <div className="rounded-lg bg-slate-950 p-4 text-white" data-testid="eta-summary-environment"><p className="text-xs font-bold text-slate-300">بيئة التشغيل</p><p className="text-xl font-extrabold">{etaIntegration.environment === "production" ? "Production" : "Preprod"}</p></div>
              <div className="rounded-lg bg-emerald-50 p-4 text-emerald-900" data-testid="eta-summary-secret"><p className="text-xs font-bold text-emerald-700">Client Secret</p><p className="text-xl font-extrabold">{etaIntegration.has_client_secret ? "محفوظ مشفر" : "غير محفوظ"}</p></div>
              <div className="rounded-lg bg-amber-50 p-4 text-amber-900" data-testid="eta-summary-sdk"><p className="text-xs font-bold text-amber-700">SDK التوقيع</p><p className="text-xl font-extrabold">{etaIntegration.sdk_command_template ? "محدد" : "مطلوب"}</p></div>
            </div>
            {etaIntegration.required_items?.length > 0 && <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm font-bold text-amber-900" data-testid="eta-required-items-alert">استكمل: {etaIntegration.required_items.join("، ")}</div>}
            {etaConnection?.message && <div className={`mb-5 rounded-lg border p-4 text-sm font-bold ${etaConnection.status === "configured" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-red-200 bg-red-50 text-red-800"}`} data-testid="eta-connection-message">{etaConnection.message}</div>}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2" data-testid="eta-integration-form-grid">
              <div data-testid="eta-environment-wrapper"><Label data-testid="eta-environment-label">البيئة</Label><select value={etaIntegration.environment || "preprod"} onChange={(event) => updateEtaField("environment", event.target.value)} className="mt-2 h-12 w-full rounded-lg border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="eta-environment-select"><option value="preprod">Preprod / Sandbox</option><option value="production">Production / الاعتماد الفعلي</option></select></div>
              <div data-testid="eta-portal-url-wrapper"><Label data-testid="eta-portal-url-label">رابط البوابة</Label><Input value={etaIntegration.portal_url || ""} onChange={(event) => updateEtaField("portal_url", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="eta-portal-url-input" /></div>
              <div data-testid="eta-issuer-name-wrapper"><Label data-testid="eta-issuer-name-label">اسم الممول/الجهة</Label><Input value={etaIntegration.issuer_name || ""} onChange={(event) => updateEtaField("issuer_name", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="eta-issuer-name-input" /></div>
              <div data-testid="eta-tax-number-wrapper"><Label data-testid="eta-tax-number-label">الرقم الضريبي</Label><Input value={etaIntegration.issuer_tax_number || ""} onChange={(event) => updateEtaField("issuer_tax_number", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="eta-tax-number-input" /></div>
              <div data-testid="eta-branch-code-wrapper"><Label data-testid="eta-branch-code-label">كود الفرع</Label><Input value={etaIntegration.branch_code || ""} onChange={(event) => updateEtaField("branch_code", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="eta-branch-code-input" /></div>
              <div data-testid="eta-activity-code-wrapper"><Label data-testid="eta-activity-code-label">كود النشاط</Label><Input value={etaIntegration.activity_code || ""} onChange={(event) => updateEtaField("activity_code", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="eta-activity-code-input" /></div>
              <div data-testid="eta-client-id-wrapper"><Label data-testid="eta-client-id-label">Client ID</Label><Input value={etaIntegration.client_id || ""} onChange={(event) => updateEtaField("client_id", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="eta-client-id-input" /></div>
              <div data-testid="eta-client-secret-wrapper"><Label data-testid="eta-client-secret-label">Client Secret</Label><Input type="password" value={etaIntegration.client_secret || ""} onChange={(event) => updateEtaField("client_secret", event.target.value)} placeholder={etaIntegration.has_client_secret ? "محفوظ مشفر - اتركه فارغاً للإبقاء عليه" : "أدخل السر"} className="mt-2 h-12 bg-slate-50 text-right" data-testid="eta-client-secret-input" /></div>
              <div data-testid="eta-certificate-label-wrapper"><Label data-testid="eta-certificate-label-label">اسم شهادة/توكن التوقيع</Label><Input value={etaIntegration.certificate_label || ""} onChange={(event) => updateEtaField("certificate_label", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="eta-certificate-label-input" /></div>
              <div data-testid="eta-token-pin-wrapper"><Label data-testid="eta-token-pin-label">PIN التوكن إن احتاجه SDK</Label><Input type="password" value={etaIntegration.token_pin || ""} onChange={(event) => updateEtaField("token_pin", event.target.value)} placeholder={etaIntegration.has_token_pin ? "محفوظ مشفر - اتركه فارغاً للإبقاء عليه" : "اختياري حسب SDK"} className="mt-2 h-12 bg-slate-50 text-right" data-testid="eta-token-pin-input" /></div>
              <div className="md:col-span-2" data-testid="eta-sdk-template-wrapper"><Label data-testid="eta-sdk-template-label">أمر SDK للتوقيع الرقمي</Label><Input value={etaIntegration.sdk_command_template || ""} onChange={(event) => updateEtaField("sdk_command_template", event.target.value)} placeholder={'مثال: C:\\ETA-SDK\\signer.exe --input {input} --output {output} --pin {pin}'} className="mt-2 h-12 bg-slate-50 text-right" data-testid="eta-sdk-template-input" /><p className="mt-2 text-xs font-bold text-slate-500" data-testid="eta-sdk-template-help">النظام يرسل الفاتورة بعد توقيعها عبر SDK الرسمي/أداة التوقيع التي تحددها هنا. لا يوجد إرسال MOCKED.</p></div>
              <div className="md:col-span-2" data-testid="eta-notes-wrapper"><Label data-testid="eta-notes-label">ملاحظات الاعتماد</Label><Input value={etaIntegration.notes || ""} onChange={(event) => updateEtaField("notes", event.target.value)} className="mt-2 h-12 bg-slate-50 text-right" data-testid="eta-notes-input" /></div>
            </div>
            <div className="mt-5 flex flex-wrap gap-3" data-testid="eta-integration-actions">
              <Button type="button" onClick={saveEtaIntegration} className="h-11 rounded-lg bg-slate-950 text-white" data-testid="save-eta-integration-button"><Save className="h-4 w-4" /> حفظ إعدادات ERP/API</Button>
              <Button type="button" onClick={testEtaConnection} variant="outline" className="h-11 rounded-lg bg-white" data-testid="test-eta-connection-button"><PlugZap className="h-4 w-4" /> اختبار الاتصال</Button>
              <Button asChild type="button" variant="outline" className="h-11 rounded-lg bg-white" data-testid="open-electronic-invoice-page-button"><Link to="/electronic-invoice">فتح صفحة الفاتورة الإلكترونية</Link></Button>
            </div>
          </section>}

          {activeAdminSection === "fixed-asset-rates" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="fixed-asset-rates-section">
            <div className="mb-5 flex items-center gap-3" data-testid="fixed-asset-rates-heading">
              <SlidersHorizontal className="h-6 w-6 text-emerald-700" />
              <div>
                <p className="text-sm font-extrabold text-emerald-700" data-testid="fixed-asset-rates-eyebrow">الأصول الثابتة</p>
                <h2 className="text-2xl font-extrabold" data-testid="fixed-asset-rates-title">تعديل نسب إهلاك التصنيفات</h2>
              </div>
            </div>
            <div className="space-y-3" data-testid="fixed-asset-rates-list">
              {fixedAssetRates.map((category) => (
                <div key={category.code} className="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 md:grid-cols-[1fr_160px_auto] md:items-end" data-testid={`fixed-asset-rate-row-${category.code}`}>
                  <div data-testid={`fixed-asset-rate-row-${category.code}-info`}><p className="font-extrabold" data-testid={`fixed-asset-rate-row-${category.code}-name`}>{category.code} - {category.name}</p><p className="text-xs font-bold text-slate-500" data-testid={`fixed-asset-rate-row-${category.code}-items`}>{category.items?.length || 0} أصل داخل التصنيف</p></div>
                  <div data-testid={`fixed-asset-rate-row-${category.code}-input-wrapper`}><Label data-testid={`fixed-asset-rate-row-${category.code}-label`}>النسبة %</Label><Input value={fixedAssetRateEdits[category.code] || ""} onChange={(event) => setFixedAssetRateEdits((current) => ({ ...current, [category.code]: event.target.value.replace(/[^0-9.]/g, "") }))} className="mt-2 h-11 bg-white text-right" data-testid={`fixed-asset-rate-row-${category.code}-input`} /></div>
                  <Button type="button" onClick={() => saveFixedAssetRate(category)} className="h-11 bg-slate-950 text-white" data-testid={`save-fixed-asset-rate-${category.code}-button`}><Save className="h-4 w-4" /> حفظ</Button>
                </div>
              ))}
            </div>
          </section>}

          {activeAdminSection === "admin-password" && <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="admin-password-section">
            <div className="mb-5 flex items-center gap-3" data-testid="admin-password-heading">
              <LockKeyhole className="h-6 w-6 text-slate-950" />
              <h2 className="text-2xl font-extrabold" data-testid="admin-password-title">تغيير كلمة مرور الأدمن</h2>
            </div>
            <form onSubmit={saveAdminFullName} className="mb-5 space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid="admin-full-name-form">
              <Label htmlFor="admin_full_name" data-testid="admin-full-name-label">الاسم بالكامل (باللغة العربية)</Label>
              <Input id="admin_full_name" value={adminFullName} onChange={(event) => setAdminFullName(event.target.value)} required className="h-12 rounded-lg bg-white text-right" data-testid="admin-full-name-input" />
              <Button type="submit" variant="outline" className="h-11 w-full rounded-lg bg-white" data-testid="save-admin-full-name-button"><Save className="h-4 w-4" /> حفظ الاسم بالكامل</Button>
            </form>
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
            <div className="mt-5 space-y-3 rounded-lg border border-emerald-100 bg-emerald-50 p-4" data-testid="admin-2fa-role-service-panel">
              <p className="font-extrabold text-emerald-900" data-testid="admin-2fa-role-service-title">Google Authenticator</p>
              <p className="text-xs font-bold text-amber-700" data-testid="admin-2fa-internet-warning">تنبيه: يجب أن يكون الجهاز متصلاً بالإنترنت عند تثبيت تطبيق Google Authenticator أو مسح الرمز أول مرة.</p>
              <Badge className={user?.totp_enabled ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700"} data-testid="admin-2fa-current-status">{user?.totp_enabled ? "مفعل لهذا الحساب" : "غير مفعل لهذا الحساب"}</Badge>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2"><Button type="button" onClick={setup2FA} variant="outline" className="bg-white" data-testid="admin-2fa-start-button">إظهار QR</Button><Button type="button" onClick={disable2FA} variant="outline" className="bg-white" data-testid="admin-2fa-disable-button">تعطيل للحساب</Button></div>
              {twoFactorSetup && <div className="space-y-3" data-testid="admin-2fa-setup-box"><img src={twoFactorSetup.qr_data_url} alt="QR" className="mx-auto h-44 w-44 rounded-lg bg-white p-2" data-testid="admin-2fa-qr-image" /><Input value={otpCode} onChange={(event) => setOtpCode(event.target.value)} placeholder="كود التطبيق" className="text-center font-extrabold tracking-widest" data-testid="admin-2fa-code-input" /><Button type="button" onClick={verify2FA} className="w-full bg-emerald-700 text-white" data-testid="admin-2fa-verify-button">تفعيل</Button></div>}
            </div>
          </section>}
        </aside>
      </section>
      <footer className="mx-auto max-w-7xl px-4 pb-8 sm:px-6 lg:px-8" data-testid="admin-footer">
        <CreditLine testId="admin-creator-credit" />
      </footer>
    </main>
  );
}
