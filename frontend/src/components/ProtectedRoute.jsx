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
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;
  if (permission && user.role !== "admin" && !user.permissions?.[permission]) return <Navigate to="/" replace />;
  if (anyPermissions.length > 0 && user.role !== "admin" && !anyPermissions.some((item) => user.permissions?.[item])) return <Navigate to="/" replace />;

  return children;
};
