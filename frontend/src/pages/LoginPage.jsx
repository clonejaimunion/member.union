import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { KeyRound, LockKeyhole, ShieldCheck, UserRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { useAppSettings } from "@/contexts/AppSettingsContext";
import { api } from "@/lib/api";
import { CreditLine } from "@/components/CreditLine";
import unionLogo from "@/assets/union-logo.jpg";

const authorityLogos = [
  { name: "مصلحة الضرائب المصرية", mark: "ض" },
  { name: "مصلحة الخزانة العامة", mark: "خ" },
  { name: "وزارة المالية", mark: "م" },
  { name: "وزارة العمل المصرية", mark: "ع" },
  { name: "وزارة الاتصالات وتكنولوجيا المعلومات", mark: "ت" },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();
  const { settings } = useAppSettings();
  const [form, setForm] = useState({ username: "", password: "" });
  const [organizations, setOrganizations] = useState([]);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState(() => window.localStorage.getItem("bank_selected_organization") || "");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    api.get("/organizations/public").then((response) => {
      if (!isMounted) return;
      setOrganizations(response.data);
      setSelectedOrganizationId((current) => current || window.localStorage.getItem("bank_selected_organization") || response.data[0]?.id || "");
    }).catch(() => toast.error("تعذر تحميل الجهات"));
    return () => { isMounted = false; };
  }, []);

  const selectedOrganization = organizations.find((item) => item.id === selectedOrganizationId);

  const selectOrganization = (organizationId) => {
    setSelectedOrganizationId(organizationId);
    window.localStorage.setItem("bank_selected_organization", organizationId);
  };

  const updateField = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  const submitLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    try {
      const payload = { username: form.username, password: form.password };
      if (!selectedOrganizationId) {
        toast.error("اختر الجهة أولاً");
        return;
      }
      payload.organization_id = selectedOrganizationId;
      const response = await api.post("/auth/login", payload);
      loginWithToken(response.data.token, response.data.user);
      toast.success(response.data.message);
      if (["admin", "super_admin"].includes(response.data.user?.role)) {
        navigate("/secure-admin-control-panel");
      } else {
        navigate("/");
      }
    } catch (error) {
      toast.error(error?.response?.data?.detail || "تعذر تسجيل الدخول");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_18%_18%,rgba(16,185,129,0.24),transparent_34%),linear-gradient(135deg,#07140f_0%,#0f172a_42%,#13251d_100%)] text-white" onContextMenu={(event) => event.preventDefault()} data-testid="login-page">
      <div className="mx-auto grid min-h-screen max-w-6xl grid-cols-1 items-center gap-10 px-4 py-10 lg:grid-cols-[0.9fr_1.1fr] lg:px-8">
        <section className="order-2 rounded-2xl border border-white/10 bg-white p-6 text-slate-950 shadow-2xl sm:p-8 lg:order-1" data-testid="login-form-card">
          <div className="mb-8 flex items-center gap-4" data-testid="login-card-heading">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="login-card-icon"><LockKeyhole className="h-6 w-6" /></div>
            <div>
              <p className="text-sm font-extrabold text-emerald-700" data-testid="login-eyebrow">دخول آمن للنظام</p>
              <h1 className="text-3xl font-extrabold text-slate-950" data-testid="login-title">تسجيل الدخول</h1>
            </div>
          </div>
          <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="login-organization-selector">
            {organizations.map((organization) => (
              <button
                key={organization.id}
                type="button"
                onClick={() => selectOrganization(organization.id)}
                className={`min-h-24 rounded-xl border p-4 text-right transition-[transform,background-color,border-color,box-shadow] hover:-translate-y-0.5 ${selectedOrganizationId === organization.id ? "border-emerald-300 bg-emerald-50 shadow-lg shadow-emerald-100" : "border-slate-200 bg-slate-50 hover:bg-white"}`}
                data-testid={`login-organization-button-${organization.id}`}
              >
                <span className="block text-lg font-extrabold text-slate-950" data-testid={`login-organization-label-${organization.id}`}>{organization.login_label}</span>
                <span className="mt-2 block text-xs font-bold leading-5 text-slate-500" data-testid={`login-organization-name-${organization.id}`}>{organization.name}</span>
              </button>
            ))}
          </div>
          {selectedOrganization && <p className="mb-5 rounded-lg bg-slate-50 p-3 text-sm font-extrabold text-emerald-700" data-testid="login-selected-organization-label">الدخول على: {selectedOrganization.name}</p>}
          <form onSubmit={submitLogin} className="space-y-5" data-testid="login-form">
            <div className="space-y-2" data-testid="login-username-wrapper">
              <Label htmlFor="username" data-testid="login-username-label">اسم المستخدم</Label>
              <div className="relative">
                <UserRound className="absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input id="username" value={form.username} onChange={(event) => updateField("username", event.target.value)} required className="h-12 rounded-lg bg-slate-50 pr-11 text-right" data-testid="login-username-input" />
              </div>
            </div>
            <div className="space-y-2" data-testid="login-password-wrapper">
              <Label htmlFor="password" data-testid="login-password-label">كلمة المرور</Label>
              <div className="relative">
                <KeyRound className="absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input id="password" type="password" value={form.password} onChange={(event) => updateField("password", event.target.value)} required className="h-12 rounded-lg bg-slate-50 pr-11 text-right" data-testid="login-password-input" />
              </div>
            </div>
            <Button type="submit" disabled={loading} className="h-12 w-full rounded-lg bg-slate-950 text-white hover:bg-slate-800" data-testid="login-submit-button">
              <ShieldCheck className="h-4 w-4" /> {loading ? "جاري الدخول..." : "دخول البرنامج"}
            </Button>
          </form>
          <Link to="/secure-admin-control-panel" className="mt-5 inline-flex text-sm font-extrabold text-emerald-700 hover:text-emerald-800" data-testid="admin-secure-link">
            رابط لوحة الأدمن الخاص
          </Link>
          <CreditLine className="mt-6 text-center text-xs font-bold text-slate-500" testId="login-creator-credit" />
        </section>
        <section className="order-1 space-y-6 lg:order-2" data-testid="login-hero-section">
          <div className="relative mx-auto flex max-w-sm select-none items-center justify-center py-2 [perspective:1200px]" data-testid="login-union-logo-3d-stage">
            <div className="absolute inset-x-8 bottom-0 h-10 rounded-full bg-emerald-400/20 blur-2xl" data-testid="login-union-logo-glow" />
            <div className="relative rounded-[2rem] border border-emerald-200/25 bg-white/10 p-4 shadow-[0_35px_90px_rgba(16,185,129,0.28)] backdrop-blur-xl transition-transform duration-500 hover:[transform:rotateY(6deg)_translateY(-4px)]" data-testid="login-union-logo-3d-card">
              <div className="absolute inset-0 rounded-[2rem] bg-[linear-gradient(135deg,rgba(255,255,255,0.32),transparent_38%,rgba(16,185,129,0.2))]" data-testid="login-union-logo-glass" />
              <img src={unionLogo} alt="شعار النقابة العامة" draggable={false} className="relative h-40 w-40 rounded-[1.5rem] object-contain mix-blend-screen drop-shadow-[0_18px_30px_rgba(0,0,0,0.42)] sm:h-52 sm:w-52" data-testid="login-union-logo-image" />
              <div className="pointer-events-none absolute inset-3 rounded-[1.5rem] border border-white/20" data-testid="login-union-logo-protection-overlay" />
            </div>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-4 py-2 text-sm font-bold text-emerald-200" data-testid="login-security-badge">
            <ShieldCheck className="h-4 w-4" /> حماية بالصلاحيات وكلمات المرور
          </div>
          <div className="space-y-4" data-testid="login-hero-title-block">
            <h2 className="max-w-2xl text-3xl font-extrabold leading-tight sm:text-4xl" data-testid="login-hero-organization">{selectedOrganization?.name || "اختر الجهة التابعة لك"}</h2>
            <p className="max-w-2xl text-2xl font-extrabold leading-tight text-emerald-200 sm:text-3xl" data-testid="login-hero-title">{settings.system_name}</p>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2" data-testid="login-authority-logos-strip">
            {authorityLogos.map((authority) => (
              <div key={authority.name} className="flex min-h-14 items-center gap-3 rounded-xl border border-white/10 bg-white/[0.08] px-3 py-2 backdrop-blur-xl" data-testid={`login-authority-logo-${authority.mark}`}>
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-emerald-200/30 bg-emerald-300/15 text-sm font-black text-emerald-100 shadow-inner" data-testid={`login-authority-logo-${authority.mark}-mark`}>{authority.mark}</span>
                <span className="text-sm font-extrabold leading-5 text-slate-100" data-testid={`login-authority-logo-${authority.mark}-name`}>{authority.name}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
