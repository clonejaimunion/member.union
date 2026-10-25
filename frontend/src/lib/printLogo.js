export const PRINT_LOGO_PATH = "/assets/union-logo.jpeg";

const LOGO_STYLE = "html,body{position:relative}.union-print-logo{position:absolute;top:0;left:0;width:16mm;height:16mm;object-fit:contain;z-index:9999;print-color-adjust:exact;-webkit-print-color-adjust:exact}";

// يضيف شعار النقابة أعلى يسار أول صفحة في نوافذ الطباعة المنفصلة
export const injectPrintLogo = (win) => {
  const doc = win?.document;
  if (!doc?.body || doc.querySelector(".union-print-logo")) return;
  const style = doc.createElement("style");
  style.textContent = LOGO_STYLE;
  doc.head.appendChild(style);
  const img = doc.createElement("img");
  img.className = "union-print-logo";
  img.alt = "";
  img.src = `${window.location.origin}${PRINT_LOGO_PATH}`;
  doc.body.insertBefore(img, doc.body.firstChild);
};
