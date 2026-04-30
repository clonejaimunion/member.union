import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

export const ProtectedRoute = ({ children, adminOnly = false, permission = null, anyPermissions = [] }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50" data-testid="auth-loading-page">
        <p className="text-lg font-extrabold text-slate-700" data-testid="auth-loading-text">جاري تأمين الجلسة...</p>
      </main>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  const privilegedAdmin = user.role === "admin" || user.role === "super_admin";
  if (adminOnly && !privilegedAdmin) return <Navigate to="/" replace />;
  if (permission && !privilegedAdmin && !user.permissions?.[permission]) return <Navigate to="/" replace />;
  if (anyPermissions.length > 0 && !privilegedAdmin && !anyPermissions.some((item) => user.permissions?.[item])) return <Navigate to="/" replace />;

  return children;
};
