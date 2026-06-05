import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, BellRing, CheckCheck, ExternalLink, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const POLL_INTERVAL_MS = 60_000;
const RENOTIFY_INTERVAL_MS = 5 * 60_000; // re-show the same unread toast every 5 min

const formatAmount = (value) => {
  const numeric = Number(value || 0);
  return numeric.toLocaleString("ar-EG", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
};

const requestDesktopPermission = () => {
  if (typeof window === "undefined" || !("Notification" in window)) return Promise.resolve("unsupported");
  if (Notification.permission === "granted" || Notification.permission === "denied") return Promise.resolve(Notification.permission);
  try {
    return Notification.requestPermission().catch(() => "denied");
  } catch {
    return Promise.resolve("denied");
  }
};

export const NotificationBell = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const panelRef = useRef(null);
  const desktopShownRef = useRef(new Map()); // notification_id -> last shown timestamp

  useEffect(() => {
    // Ask for desktop permission once after login — silent if already decided.
    if (user) requestDesktopPermission();
  }, [user]);

  const fireDesktopNotification = useCallback((notification) => {
    if (typeof window === "undefined" || !("Notification" in window)) return;
    if (Notification.permission !== "granted") return;
    const now = Date.now();
    const lastShown = desktopShownRef.current.get(notification.id) || 0;
    if (now - lastShown < RENOTIFY_INTERVAL_MS) return; // throttle re-notify
    try {
      const days = Number(notification.days_remaining || 0);
      const title = days <= 7 ? "⚠️ استحقاق وديعة عاجل" : "تنبيه استحقاق وديعة";
      const body = `وديعة ${notification.deposit_number} — ${notification.bank_name}\n${formatAmount(notification.amount)} جنيه\nتاريخ الاستحقاق: ${notification.maturity_date} — متبقي ${days} يوم`;
      const toast = new Notification(title, {
        body,
        tag: `deposit-${notification.id}`, // replace previous toast for same id
        requireInteraction: true, // sticky — stays until user interacts
        renotify: true,
        silent: false,
      });
      toast.onclick = () => {
        window.focus();
        if (notification.bank_id) navigate(`/bank/${notification.bank_id}/register`);
        toast.close();
      };
      desktopShownRef.current.set(notification.id, now);
    } catch {
      /* silent: never break the host UI */
    }
  }, [navigate]);

  const loadNotifications = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      // Force a fresh scan first so any newly-added deposit shows immediately,
      // even if the running backend is missing the auto_scan optimization.
      try {
        await api.post("/notifications/deposits/scan?threshold_days=10");
      } catch {
        /* scan endpoint may not exist on very old builds — fall through to GET */
      }
      const response = await api.get("/notifications/deposits", { params: { limit: 50 } });
      const list = response.data.items || [];
      setItems(list);
      setUnreadCount(response.data.unread_count || 0);
      // Desktop toast for every unread item (throttled per-id).
      list.filter((row) => row.status === "unread").forEach(fireDesktopNotification);
    } catch {
      /* silent: never break the host UI */
    } finally {
      setLoading(false);
    }
  }, [user, fireDesktopNotification]);

  useEffect(() => {
    loadNotifications();
    const id = window.setInterval(loadNotifications, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [loadNotifications]);

  useEffect(() => {
    if (!open) return;
    const handler = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) setOpen(false);
    };
    window.addEventListener("mousedown", handler);
    return () => window.removeEventListener("mousedown", handler);
  }, [open]);

  const markRead = async (notification) => {
    try {
      const response = await api.post(`/notifications/deposits/${notification.id}/read`);
      if (response?.data?.notification) {
        setItems((current) => current.map((row) => (row.id === notification.id ? response.data.notification : row)));
        setUnreadCount((current) => Math.max(0, current - 1));
      }
    } catch {
      /* silent */
    }
  };

  const openDeposit = (notification) => {
    markRead(notification);
    setOpen(false);
    navigate(`/bank/${notification.bank_id}/register?deposit=${encodeURIComponent(notification.deposit_id || "")}&highlight=${encodeURIComponent(notification.deposit_id || "")}`);
  };

  const hasUnread = unreadCount > 0;
  const BellIcon = hasUnread ? BellRing : Bell;
  const sortedItems = useMemo(() => items.slice().sort((a, b) => {
    if (a.status !== b.status) return a.status === "unread" ? -1 : 1;
    return Number(a.days_remaining || 0) - Number(b.days_remaining || 0);
  }), [items]);

  return (
    <div className="relative" ref={panelRef} data-testid="notification-bell-wrapper">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="relative inline-flex h-11 w-11 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-700 transition-transform hover:-translate-y-0.5 hover:bg-slate-100"
        aria-label="مركز التنبيهات"
        data-testid="notification-bell-button"
      >
        <BellIcon className={`h-5 w-5 ${hasUnread ? "text-amber-600" : ""}`} />
        {hasUnread && (
          <span className="absolute -top-1 -right-1 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-extrabold text-white" data-testid="notification-bell-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
        )}
      </button>
      {open && (
        <div className="absolute left-0 mt-2 w-[420px] origin-top-left rounded-xl border border-slate-200 bg-white shadow-2xl ring-1 ring-black/5 z-50" data-testid="notification-bell-panel">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3" data-testid="notification-bell-header">
            <h4 className="text-sm font-extrabold text-slate-950" data-testid="notification-bell-title">تنبيهات استحقاق الودائع</h4>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)} className="h-8 w-8 p-0" data-testid="notification-bell-close-button"><X className="h-4 w-4" /></Button>
          </div>
          <div className="max-h-[420px] overflow-y-auto" data-testid="notification-bell-list">
            {loading && items.length === 0 && (
              <p className="px-4 py-6 text-center text-xs font-bold text-slate-500" data-testid="notification-bell-loading">جاري التحميل...</p>
            )}
            {!loading && sortedItems.length === 0 && (
              <p className="px-4 py-6 text-center text-xs font-bold text-slate-500" data-testid="notification-bell-empty">لا توجد تنبيهات استحقاق حالياً</p>
            )}
            {sortedItems.map((notification) => {
              const isUnread = notification.status === "unread";
              const days = Number(notification.days_remaining || 0);
              const isUrgent = days <= 7;
              const isSoon = days > 7 && days <= 30;
              const bgUnread = isUrgent ? "bg-rose-50/70" : isSoon ? "bg-amber-50/60" : "bg-sky-50/60";
              const titleColor = isUrgent ? "text-rose-700" : isSoon ? "text-amber-700" : "text-sky-700";
              const dotColor = isUrgent ? "bg-rose-600" : isSoon ? "bg-amber-500" : "bg-sky-500";
              const label = isUrgent ? "⚠️ استحقاق عاجل" : isSoon ? "تنبيه استحقاق وديعة" : "وديعة نشطة";
              return (
                <div
                  key={notification.id}
                  className={`border-b border-slate-100 px-4 py-3 ${isUnread ? bgUnread : "bg-white"}`}
                  data-testid={`notification-bell-item-${notification.id}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <p className={`flex items-center gap-2 text-xs font-extrabold ${titleColor}`} data-testid={`notification-bell-item-${notification.id}-title`}>
                        {isUnread && <span className={`inline-block h-2 w-2 rounded-full ${dotColor}`} data-testid={`notification-bell-item-${notification.id}-dot`} />}
                        {label}
                      </p>
                      <p className="mt-1 text-sm font-bold text-slate-900" data-testid={`notification-bell-item-${notification.id}-deposit`}>وديعة {notification.deposit_number} — {notification.bank_name}</p>
                      <p className="text-xs font-bold text-slate-600" data-testid={`notification-bell-item-${notification.id}-amount`}>{formatAmount(notification.amount)} جنيه</p>
                      <p className="mt-1 text-xs font-bold text-slate-500" data-testid={`notification-bell-item-${notification.id}-meta`}>تاريخ الاستحقاق: {notification.maturity_date} — متبقي {days} يوم</p>
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2" data-testid={`notification-bell-item-${notification.id}-actions`}>
                    <Button type="button" onClick={() => openDeposit(notification)} className="h-8 rounded-lg bg-slate-950 px-3 text-xs text-white" data-testid={`notification-bell-item-${notification.id}-open-button`}>
                      <ExternalLink className="h-3.5 w-3.5" /> فتح الوديعة
                    </Button>
                    {isUnread && (
                      <Button type="button" variant="outline" onClick={() => markRead(notification)} className="h-8 rounded-lg bg-white px-3 text-xs" data-testid={`notification-bell-item-${notification.id}-read-button`}>
                        <CheckCheck className="h-3.5 w-3.5" /> تم القراءة
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationBell;
