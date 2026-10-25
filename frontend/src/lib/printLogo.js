export const PRINT_LOGO_PATH = "/assets/union-logo-white.jpeg";

const logoStyle = (sizeMm) => `html,body{position:relative}.union-print-logo{position:absolute;top:0;left:0;width:${sizeMm}mm;height:${sizeMm}mm;object-fit:contain;z-index:9999;print-color-adjust:exact;-webkit-print-color-adjust:exact}.union-print-logo-space{height:${sizeMm}mm}`;

// يضيف شعار النقابة أعلى يسار أول صفحة في نوافذ الطباعة المنفصلة؛ reserve يحجز مساحة بارتفاع الشعار حتى لا يتداخل مع النص
export const injectPrintLogo = (win, sizeMm = 38, reserve = true) => {
  const doc = win?.document;
  if (!doc?.body || doc.querySelector(".union-print-logo")) return;
  const style = doc.createElement("style");
  style.textContent = logoStyle(sizeMm);
  doc.head.appendChild(style);
  const img = doc.createElement("img");
  img.className = "union-print-logo";
  img.alt = "";
  img.src = `${window.location.origin}${PRINT_LOGO_PATH}`;
  doc.body.insertBefore(img, doc.body.firstChild);
  if (reserve) {
    const space = doc.createElement("div");
    space.className = "union-print-logo-space";
    img.after(space);
  }
};
