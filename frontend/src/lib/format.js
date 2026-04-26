export const formatCurrency = (value) =>
  new Intl.NumberFormat("ar-EG", {
    style: "currency",
    currency: "EGP",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));

export const formatNumber = (value) =>
  new Intl.NumberFormat("ar-EG", { maximumFractionDigits: 2 }).format(Number(value || 0));

export const formatDateTime = (value) => {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ar-EG", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
};

export const toDateTimeLocal = (date) => {
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const easternArabicDigits = {
  0: "٠",
  1: "١",
  2: "٢",
  3: "٣",
  4: "٤",
  5: "٥",
  6: "٦",
  7: "٧",
  8: "٨",
  9: "٩",
};

const westernArabicDigits = {
  "٠": "0",
  "١": "1",
  "٢": "2",
  "٣": "3",
  "٤": "4",
  "٥": "5",
  "٦": "6",
  "٧": "7",
  "٨": "8",
  "٩": "9",
};

export const toEasternArabicNumerals = (value) => String(value ?? "").replace(/[0-9]/g, (digit) => easternArabicDigits[digit]);

export const toWesternArabicNumerals = (value) => String(value ?? "").replace(/[٠-٩]/g, (digit) => westernArabicDigits[digit]);

export const sanitizeDecimalInput = (value) => {
  const normalized = toWesternArabicNumerals(value).replace(/[٬,]/g, "").replace(/٫/g, ".");
  const cleaned = normalized.replace(/[^0-9.]/g, "");
  const [integerPart, ...decimalParts] = cleaned.split(".");
  return decimalParts.length ? `${integerPart}.${decimalParts.join("")}` : integerPart;
};

export const sanitizeDigitsInput = (value) => toWesternArabicNumerals(value).replace(/[^0-9]/g, "");

export const sanitizeDayMonthInput = (value) => {
  const normalized = toWesternArabicNumerals(value).replace(/[.-]/g, "/");
  return normalized.replace(/[^0-9/]/g, "").replace(/\/{2,}/g, "/").slice(0, 5);
};

export const applyEasternArabicNumeralsToDocument = () => {
  const excludedTags = new Set(["INPUT", "TEXTAREA", "SCRIPT", "STYLE", "NOSCRIPT"]);

  const convertNode = (node) => {
    if (!node) return;
    if (node.nodeType === Node.TEXT_NODE) {
      if (node.parentElement && excludedTags.has(node.parentElement.tagName)) return;
      const nextValue = toEasternArabicNumerals(node.nodeValue);
      if (nextValue !== node.nodeValue) node.nodeValue = nextValue;
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE || excludedTags.has(node.tagName) || node.dataset?.preserveWesternDigits === "true") return;
    Array.from(node.childNodes).forEach(convertNode);
  };

  convertNode(document.body);
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === "characterData") convertNode(mutation.target);
      mutation.addedNodes.forEach(convertNode);
    });
  });
  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  return () => observer.disconnect();
};
