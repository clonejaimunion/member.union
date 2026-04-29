import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { KeyRound, LockKeyhole, ShieldCheck, UserRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { CreditLine } from "@/components/CreditLine";

export default function LoginPage() {
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();
  const [form, setForm] = useState({ username: "", password: "", otp_code: "" });
  const [requires2fa, setRequires2fa] = useState(false);
  const [loading, setLoading] = useState(false);

  const updateField = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  const submitLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    try {
      const payload = { username: form.username, password: form.password };
      if (requires2fa) payload.otp_code = form.otp_code;
      const response = await api.post("/auth/login", payload);
      if (response.data.requires_2fa) {
        setRequires2fa(true);
        toast.info(response.data.message);
        return;
      }
      loginWithToken(response.data.token, response.data.user);
      toast.success(response.data.message);
      if (response.data.user?.role === "admin" && response.data.requires_2fa_setup) {
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
    <main className="min-h-screen bg-slate-950 text-white" data-testid="login-page">
      <div className="mx-auto grid min-h-screen max-w-6xl grid-cols-1 items-center gap-10 px-4 py-10 lg:grid-cols-[0.9fr_1.1fr] lg:px-8">
        <section className="order-2 rounded-2xl border border-white/10 bg-white p-6 text-slate-950 shadow-2xl sm:p-8 lg:order-1" data-testid="login-form-card">
          <div className="mb-8 flex items-center gap-4" data-testid="login-card-heading">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-950 text-white" data-testid="login-card-icon"><LockKeyhole className="h-6 w-6" /></div>
            <div>
              <p className="text-sm font-extrabold text-emerald-700" data-testid="login-eyebrow">دخول آمن للنظام</p>
              <h1 className="text-3xl font-extrabold text-slate-950" data-testid="login-title">تسجيل الدخول</h1>
            </div>
          </div>
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
            {requires2fa && (
              <div className="space-y-2" data-testid="login-otp-wrapper">
                <Label htmlFor="otp_code" data-testid="login-otp-label">كود Google Authenticator</Label>
                <Input id="otp_code" value={form.otp_code} onChange={(event) => updateField("otp_code", event.target.value)} required className="h-12 rounded-lg bg-emerald-50 text-center text-lg font-extrabold tracking-widest" data-testid="login-otp-input" />
              </div>
            )}
            <Button type="submit" disabled={loading} className="h-12 w-full rounded-lg bg-slate-950 text-white hover:bg-slate-800" data-testid="login-submit-button">
              <ShieldCheck className="h-4 w-4" /> {loading ? "جاري الدخول..." : requires2fa ? "تأكيد الكود" : "دخول البرنامج"}
            </Button>
          </form>
          <Link to="/secure-admin-control-panel" className="mt-5 inline-flex text-sm font-extrabold text-emerald-700 hover:text-emerald-800" data-testid="admin-secure-link">
            رابط لوحة الأدمن الخاص
          </Link>
          <CreditLine className="mt-6 text-center text-xs font-bold text-slate-500" testId="login-creator-credit" />
        </section>
        <section className="order-1 space-y-6 lg:order-2" data-testid="login-hero-section">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-4 py-2 text-sm font-bold text-emerald-200" data-testid="login-security-badge">
            <ShieldCheck className="h-4 w-4" /> حماية بالصلاحيات والمصادقة الثنائية
          </div>
          <div className="space-y-4" data-testid="login-hero-title-block">
            <h2 className="max-w-2xl text-3xl font-extrabold leading-tight sm:text-4xl" data-testid="login-hero-organization">النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الارادي</h2>
            <p className="max-w-2xl text-2xl font-extrabold leading-tight text-emerald-200 sm:text-3xl" data-testid="login-hero-title">نظام محاسبي متكامل</p>
          </div>
        </section>
      </div>
    </main>
  );
}
