import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Building2, KeyRound, LockKeyhole, Plus, QrCode, Save, ShieldCheck, ToggleLeft, ToggleRight, Trash2, UserCog, UsersRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
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
};

const defaultUserForm = {
  username: "",
  password: "",
  permissions: { enter_deposits: true, view_reports: true, edit_deposits: false, manage_reconciliations: true, manage_revenues: true, manage_expenses: true, manage_users: false },
  is_active: true,
};

export default function AdminPage() {
  const navigate = useNavigate();
  const { user, logout, refreshMe } = useAuth();
  const [users, setUsers] = useState([]);
  const [newUser, setNewUser] = useState(defaultUserForm);
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "" });
  const [resetPasswords, setResetPasswords] = useState({});
  const [twoFactor, setTwoFactor] = useState(null);
  const [otpCode, setOtpCode] = useState("");
  const [bankForm, setBankForm] = useState({ name: "", code: "", swift_code: "", logo_url: "", color: "#0f172a" });

  const loadUsers = () => {
    api.get("/admin/users").then((response) => setUsers(response.data)).catch(() => toast.error("تعذر تحميل المستخدمين"));
  };

  useEffect(() => {
    loadUsers();
  }, []);

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
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر إضافة البنك");
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

      <section className="mx-auto grid max-w-7xl grid-cols-1 gap-6 px-4 py-8 sm:px-6 xl:grid-cols-[1fr_0.85fr] lg:px-8" data-testid="admin-content-grid">
        <div className="space-y-6" data-testid="admin-users-column">
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="create-user-section">
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
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="create-bank-section">
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
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="users-list-section">
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
          </section>
        </div>

        <aside className="space-y-6" data-testid="admin-security-column">
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="admin-password-section">
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
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="admin-2fa-section">
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
          </section>
        </aside>
      </section>
      <footer className="mx-auto max-w-7xl px-4 pb-8 sm:px-6 lg:px-8" data-testid="admin-footer">
        <CreditLine testId="admin-creator-credit" />
      </footer>
    </main>
  );
}
