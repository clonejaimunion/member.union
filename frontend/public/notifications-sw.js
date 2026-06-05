// Bank Deposit System — Notifications Service Worker
// Pure-browser solution: shows REAL Windows desktop toasts via the
// Notification API. No PowerShell, no VBS, no external dependencies.

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type !== "show-deposit-notification" || !data.notification) return;
  const notification = data.notification;
  const days = Number(notification.days_remaining || 0);
  const title = days <= 7 ? "⚠️ استحقاق وديعة عاجل" : "تنبيه استحقاق وديعة";
  const amount = Number(notification.amount || 0).toLocaleString("ar-EG", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  const body = `وديعة ${notification.deposit_number} — ${notification.bank_name}\n${amount} جنيه\nتاريخ الاستحقاق: ${notification.maturity_date} — متبقي ${days} يوم`;
  self.registration.showNotification(title, {
    body,
    tag: `deposit-${notification.id}`,
    renotify: true,
    requireInteraction: true,
    silent: false,
    dir: "rtl",
    lang: "ar",
    data: {
      bank_id: notification.bank_id,
      deposit_id: notification.deposit_id,
      url: notification.bank_id ? `/bank/${notification.bank_id}/register` : "/",
    },
  });
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil((async () => {
    const allClients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of allClients) {
      try {
        await client.focus();
        client.postMessage({ type: "open-deposit", url: targetUrl });
        return;
      } catch {
        /* try next client */
      }
    }
    if (self.clients.openWindow) await self.clients.openWindow(targetUrl);
  })());
});
