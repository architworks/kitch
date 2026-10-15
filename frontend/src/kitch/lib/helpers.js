import React from "react";
import { MEAL_SLOTS } from "../../app/householdConfig.js";

// Pure helpers shared by the Kitch controller and views. Moved verbatim from the
// previous single-file page so request, formatting, and provider-normalisation
// behaviour stays identical.
export const MEAL_SLOT_LABELS = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner"
};

export const DEFAULT_MEAL_SLOT = "breakfast";
export const NUTRITION_MEALS = [
  { id: "breakfast", label: "Breakfast", icon: "☀", defaultTime: "08:30" },
  { id: "lunch", label: "Lunch", icon: "◐", defaultTime: "13:00" },
  { id: "snack", label: "Snack", icon: "◉", defaultTime: "17:00" },
  { id: "dinner", label: "Dinner", icon: "☾", defaultTime: "20:30" }
];
export const EMPTY_NUTRITION_ENTRY = {
  id: null, meal_name: "", quantity: 1, unit: "serving", meal_type: "breakfast",
  calories: 0, protein: 0, carbs: 0, fat: 0, fiber: 0, consumed_at: ""
};
export const currentNutritionMealType = (timezone = "Asia/Kolkata") => {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: timezone, hour: "2-digit", hourCycle: "h23"
  }).formatToParts(new Date());
  const hour = Number(parts.find(part => part.type === "hour")?.value || 0);
  if (hour >= 5 && hour <= 10) return "breakfast";
  if (hour >= 11 && hour <= 15) return "lunch";
  if (hour >= 16 && hour <= 18) return "snack";
  return "dinner";
};
export const formatNutritionNumber = (value) => {
  const numeric = Number(value || 0);
  return Number.isInteger(numeric) ? numeric : numeric.toFixed(1);
};
export const INITIAL_VISIBLE_CHAT_COUNT = 6;
export const CHAT_HISTORY_BATCH_SIZE = 6;
export const PERSISTENCE_FAILURE_MESSAGE = "Kitch couldn’t save this change because durable storage is unavailable. Nothing was saved.";
export const DEFAULT_ORDERING_PROVIDER = "";
export const PROVIDER_REVALIDATE_AFTER_MS = 60 * 1000;
export const SWIGGY_LOGO_URL = "/swiggy-logo.svg";
export const safeProviderPaymentUrl = (value) => {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const url = new URL(raw);
    return [
      "https:", "http:", "upi:", "gpay:", "phonepe:", "paytmmp:",
      "bhim:", "credpay:", "super:", "fpupi:"
    ].includes(url.protocol) ? raw : "";
  } catch {
    return "";
  }
};

export const withProviderRoutes = (provider) => {
  const base = provider?.api_base;
  if (!base) return { ...provider, routes: null };
  return {
    ...provider,
    brandLabel: provider.brand_label || provider.label,
    routes: {
      addresses: `${base}/addresses`,
      liveCart: `${base}/cart`,
      syncCart: `${base}/checkout/sync`,
      checkoutDraft: `${base}/checkout`,
      revalidateCart: `${base}/checkout/revalidate`,
      placeOrder: `${base}/checkout/place-order`,
      paymentStatus: `${base}/checkout/payment-status`,
      connectionStart: `${base}/connection/start`,
      connection: `${base}/connection`
    }
  };
};

export const GROCERY_CATEGORY_DESCRIPTIONS = {
  "Fresh Produce": "Fruits, vegetables and fresh ingredients",
  "Proteins & Dairy": "Dairy, eggs and household proteins",
  "Grains & Bakery": "Bread, grains and everyday staples",
  "Pantry & Spices": "Pantry staples, spices and cooking essentials",
  General: "Pantry staples, spices, cooking essentials and more"
};

export class ApiResponseError extends Error {
  constructor(status, detail) {
    const message = typeof detail === "string"
      ? detail
      : detail?.message || `Request failed with status ${status}`;
    super(message);
    this.name = "ApiResponseError";
    this.status = status;
    this.detail = detail;
  }

  get isPersistenceFailure() {
    return this.status === 503 && (
      this.detail?.code === "persistence_unavailable"
      || this.detail?.code === "persistence_misconfigured"
    );
  }
}

export const requireSuccessfulResponse = async (response) => {
  if (response.ok) return response;
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  throw new ApiResponseError(response.status, body?.detail || body);
};

export const apiErrorMessage = (error, fallback) => {
  if (error instanceof ApiResponseError && error.isPersistenceFailure) {
    return PERSISTENCE_FAILURE_MESSAGE;
  }
  if (error?.name === "AbortError") {
    return "Kitch took longer than expected to respond. Refresh the relevant page before retrying because the requested change may still have completed.";
  }
  const message = String(error?.message || "").trim();
  if (!message || /^(failed to fetch|load failed|networkerror)/i.test(message)) {
    return fallback;
  }
  return message;
};

export const getTimeBasedMealSlot = (date = new Date()) => {
  const hour = date.getHours();
  if (hour < 11) return "breakfast";
  if (hour < 16) return "lunch";
  return "dinner";
};

export const getTimeBasedGreeting = (date = new Date()) => {
  const hour = date.getHours();
  // Late night still reads as evening; "Good morning" at 1 am feels wrong.
  if (hour < 5) return "Good evening";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
};

export const CONFIGURED_API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim().replace(/\/$/, "");
export const API_REQUEST_TIMEOUT_MS = 20_000;
export const AGENT_REQUEST_TIMEOUT_MS = 120_000;
export const PROVIDER_OPERATION_TIMEOUT_MS = 240_000;

export const apiUrl = (path) => {
  if (CONFIGURED_API_BASE_URL) return `${CONFIGURED_API_BASE_URL}${path}`;
  if (typeof window !== "undefined" && !["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    return `/backend${path}`;
  }
  return `http://localhost:8000${path}`;
};

export const apiFetch = (url, options = {}) => {
  const { timeoutMs = API_REQUEST_TIMEOUT_MS, ...requestOptions } = options;
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  return globalThis.fetch(url, {
    credentials: "include",
    ...requestOptions,
    signal: requestOptions.signal || controller.signal
  }).finally(() => globalThis.clearTimeout(timeout));
};

export const getMealTitle = (meal, fallback = "No recipe set") => {
  if (!meal) return fallback;
  if (typeof meal === "string") return meal || fallback;
  return meal.name || meal.title || meal.recipe_name || fallback;
};

export const hasMealTitle = (meal) => Boolean(String(getMealTitle(meal, "")).trim());
export const hasPlannedMeals = (day) => MEAL_SLOTS.some(slot => hasMealTitle(day?.[slot]));

export const getRecipeCardTitle = (recipe, fallback = "Recipe") => {
  if (!recipe) return fallback;
  if (typeof recipe === "string") return recipe || fallback;
  return recipe.title || recipe.name || recipe.recipeName || recipe.recipe_name || fallback;
};

export const formatRelativeCheckedTime = (value, now = new Date()) => {
  if (!value) return "Unknown update time";
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return "Unknown update time";
  const elapsedSeconds = Math.max(0, Math.floor((now.getTime() - timestamp.getTime()) / 1000));
  if (elapsedSeconds < 60) return "just now";
  const elapsedMinutes = Math.floor(elapsedSeconds / 60);
  if (elapsedMinutes < 60) return `${elapsedMinutes} min ago`;
  const elapsedHours = Math.floor(elapsedMinutes / 60);
  if (elapsedHours < 24) return `${elapsedHours} hr${elapsedHours === 1 ? "" : "s"} ago`;
  const elapsedDays = Math.floor(elapsedHours / 24);
  if (elapsedDays < 7) return `${elapsedDays} day${elapsedDays === 1 ? "" : "s"} ago`;
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: timestamp.getFullYear() === now.getFullYear() ? undefined : "numeric"
  }).format(timestamp);
};

export const normalizeList = (value) => {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === "string") {
    return value
      .split(/\n+/)
      .map(item => item.replace(/^[-*\d.\s]+/, "").trim())
      .filter(Boolean);
  }
  return [value];
};

export const getIngredientName = (ingredient) => {
  if (!ingredient) return "";
  if (typeof ingredient === "string") return ingredient;
  return ingredient.name || ingredient.ingredient_name || ingredient.item || ingredient.ingredient || "";
};

export const getIngredientQuantity = (ingredient) => {
  if (!ingredient || typeof ingredient === "string") return "";
  const amount = ingredient.amount ?? ingredient.quantity ?? ingredient.qty ?? "";
  const unit = ingredient.unit || "";
  const note = ingredient.note || ingredient.notes || "";
  const amountText = `${amount}`.trim();
  const unitText = `${unit}`.trim();
  const lowerUnit = unitText.toLowerCase();
  if (lowerUnit === "to taste") return "To taste";
  if (lowerUnit === "as needed") return "As needed";
  const qty = [amountText, unitText].filter(Boolean).join(" ");
  return qty || note || "";
};

export const getRecipeSteps = (recipe) => {
  const rawSteps = recipe?.steps || recipe?.instructions || recipe?.method || recipe?.directions || [];
  return normalizeList(rawSteps).map((step, index) => {
    if (typeof step === "string") {
      return {
        title: `Step ${index + 1}`,
        body: step
      };
    }

    return {
      title: step.title || step.name || `Step ${index + 1}`,
      body: step.body || step.description || step.text || step.instruction || ""
    };
  }).filter(step => step.body || step.title);
};

export const formatCartQuantity = (amount, unit) => {
  const amountText = `${amount ?? ""}`.trim();
  const unitText = `${unit || ""}`.trim();
  if (!amountText && !unitText) return "—";
  if (unitText.toLowerCase() === "to taste") return "To taste";
  if (unitText.toLowerCase() === "as needed") return "As needed";
  return [amountText, unitText].filter(Boolean).join(" ");
};

export const parseJsonText = (value) => {
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
};

export const collectObjectsWithAnyKey = (value, keys, results = []) => {
  const parsed = parseJsonText(value);
  if (Array.isArray(parsed)) {
    parsed.forEach(item => collectObjectsWithAnyKey(item, keys, results));
    return results;
  }
  if (!parsed || typeof parsed !== "object") return results;

  if (typeof parsed.text === "string") {
    collectObjectsWithAnyKey(parsed.text, keys, results);
  }

  const lowerKeys = Object.keys(parsed).map(key => key.toLowerCase());
  if (keys.some(key => lowerKeys.includes(key.toLowerCase()))) {
    results.push(parsed);
  }

  Object.values(parsed).forEach(child => collectObjectsWithAnyKey(child, keys, results));
  return results;
};

export const optionValue = (option, keys, fallback = "") => {
  for (const key of keys) {
    if (option?.[key]) return option[key];
  }
  return fallback;
};

export const formatProviderPaymentLabel = (option, fallback = "Payment method") => {
  const identifier = optionValue(
    option,
    ["id", "payment_method_id", "paymentMethodId", "method"],
    ""
  );
  const providerLabel = optionValue(
    option,
    ["label", "name", "payment_method", "paymentMethod", "method", "title"],
    ""
  );
  const friendlyLabels = {
    "gpay://upi/": "Google Pay",
    "phonepe://": "PhonePe",
    "paytmmp://": "Paytm",
    "bhim://upi/": "BHIM",
    "credpay://upi/": "CRED Pay",
    "super://": "super.money",
    "fpupi://": "Flipkart UPI",
    paywithqr: "Scan QR with any UPI app",
    cash: "Cash on delivery",
    cod: "Cash on delivery",
    swiggypay: "Swiggy Money"
  };
  return friendlyLabels[identifier.toLowerCase()]
    || friendlyLabels[providerLabel.toLowerCase()]
    || providerLabel
    || identifier
    || fallback;
};

export const textOptionValue = (option, keys, fallback = "") => {
  const normalizeText = (value) => {
    if (value === undefined || value === null || value === "") return "";
    if (typeof value === "string" || typeof value === "number") return String(value).trim();
    if (Array.isArray(value)) {
      return value.map(normalizeText).filter(Boolean).join(", ");
    }
    return "";
  };

  for (const key of keys) {
    const direct = normalizeText(option?.[key]);
    if (direct) return direct;
  }
  return fallback;
};

export const uniqueParts = (parts) => {
  const seen = new Set();
  return parts
    .map(part => String(part || "").trim())
    .filter(part => {
      if (!part) return false;
      const normalized = part.toLowerCase();
      if (seen.has(normalized)) return false;
      seen.add(normalized);
      return true;
    });
};

export const findNestedTextValue = (value, keys, depth = 0) => {
  if (!value || depth > 3) return "";
  if (typeof value === "string" || typeof value === "number") return String(value).trim();
  if (Array.isArray(value)) {
    return value.map(item => findNestedTextValue(item, keys, depth + 1)).find(Boolean) || "";
  }
  if (typeof value !== "object") return "";

  const direct = textOptionValue(value, keys);
  if (direct) return direct;
  for (const child of Object.values(value)) {
    const nested = findNestedTextValue(child, keys, depth + 1);
    if (nested) return nested;
  }
  return "";
};

export const formatProviderAddressLabel = (option, fallback = "Saved address") => {
  const label = textOptionValue(option, [
    "label",
    "name",
    "type",
    "addressLabel",
    "address_label",
    "tag",
    "title"
  ], fallback);
  const fullAddress = findNestedTextValue(option, [
    "formattedAddress",
    "formatted_address",
    "fullAddress",
    "full_address",
    "completeAddress",
    "complete_address",
    "displayAddress",
    "display_address",
    "addressLine",
    "address_line",
    "address",
    "line1",
    "line_1",
    "address1"
  ]);
  const addressParts = uniqueParts([
    textOptionValue(option, ["flatDetails", "flat_details", "flat", "house", "houseNumber", "house_number"]),
    textOptionValue(option, ["buildingName", "building_name", "building", "society"]),
    textOptionValue(option, ["floor"]),
    textOptionValue(option, ["landmark"]),
    textOptionValue(option, ["locality", "area", "neighborhood", "neighbourhood"]),
    textOptionValue(option, ["shortAddress", "short_address"]),
    textOptionValue(option, ["city"]),
    textOptionValue(option, ["state"]),
    textOptionValue(option, ["pincode", "pinCode", "postalCode", "postal_code"])
  ]);
  const addressText = fullAddress || addressParts.join(", ");
  if (!addressText) return label;
  if (!label || label.toLowerCase() === addressText.toLowerCase()) return addressText;
  return `${label} — ${addressText}`;
};

export const formatProviderAddressParts = (option, fallback = "Saved address") => {
  const display = formatProviderAddressLabel(option, fallback);
  const separator = " — ";
  const separatorIndex = display.indexOf(separator);
  if (separatorIndex < 0) {
    return { title: display || fallback, detail: "" };
  }
  return {
    title: display.slice(0, separatorIndex) || fallback,
    detail: display.slice(separatorIndex + separator.length)
  };
};

export const providerValue = (sources, keys) => {
  for (const source of sources) {
    if (!source || typeof source !== "object") continue;
    for (const key of keys) {
      const value = source[key];
      if (value !== undefined && value !== null && value !== "") return value;
    }
  }
  return "";
};

export const formatMinorCurrency = (value, currency = "INR") => {
  if (value === null || value === undefined || value === "") return "";
  if (!Number.isFinite(Number(value))) return "";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: Number(value) % 100 === 0 ? 0 : 2
  }).format(Number(value) / 100);
};

export const providerPriceToMinor = (value) => {
  if (value === undefined || value === null || value === "") return null;
  const isCurrencyString = typeof value === "string" && /₹|\b(?:INR|RS\.?)\b/i.test(value);
  const normalized = typeof value === "string" ? value.replace(/[^\d.-]/g, "") : value;
  const numeric = Number(normalized);
  if (!Number.isFinite(numeric)) return null;
  return Math.round(isCurrencyString || Math.abs(numeric) < 100 ? numeric * 100 : numeric);
};

export const getProviderCartLineData = (match) => {
  const product = match?.matched_product || {};
  const cartItem = match?.cart_item || {};
  // Checkout pricing must come from the confirmed provider cart. Search-match
  // prices can be stale and are not proof of what the provider actually added.
  const normalizedPriceMinor = providerValue([cartItem], ["price_minor"]);
  const normalizedLineTotalMinor = providerValue([cartItem], ["line_total_minor"]);
  const rawPrice = providerValue([cartItem], ["price", "sellingPrice", "selling_price", "discountedPrice"]);
  const rawQuantity = providerValue([cartItem, match?.add_result, product], ["quantity", "qty", "count"]);
  const parsedNormalizedPrice = Number(normalizedPriceMinor);
  const priceMinor = normalizedPriceMinor !== "" && Number.isFinite(parsedNormalizedPrice)
    ? Math.round(parsedNormalizedPrice)
    : providerPriceToMinor(rawPrice);
  const parsedQuantity = Number(rawQuantity);
  const quantity = Number.isFinite(parsedQuantity) && parsedQuantity > 0 ? parsedQuantity : 1;
  const parsedNormalizedLineTotal = Number(normalizedLineTotalMinor);
  const subtotalMinor = normalizedLineTotalMinor !== "" && Number.isFinite(parsedNormalizedLineTotal)
    ? Math.round(parsedNormalizedLineTotal)
    : priceMinor === null ? null : Math.round(priceMinor * quantity);

  return {
    priceMinor,
    quantity,
    subtotalMinor,
    packSize: providerValue([cartItem, product], ["pack_size", "packSize", "unit", "unitOfQuantity", "unit_of_quantity", "quantityUnit"]),
    imageUrl: providerValue([cartItem, product], ["image_url", "imageUrl", "thumbnailUrl", "thumbnail_url"])
  };
};

export const cartItemKey = (item) => String(item?.id || item?.name || "");
export const cartPurchaseAmount = (item) => Math.max(0, Number(item?.purchaseAmount ?? item?.amount ?? 0));
export const cartPantryAmount = (item) => Math.max(0, Number(item?.pantryAllocation?.allocated_amount ?? 0));

export const INITIAL_CHAT = [];

export const renderInlineMarkdown = (text, keyPrefix) => {
  const segments = String(text).split(/(`[^`]+`|\*\*[^*]+?\*\*|\*[^*]+?\*)/g);
  return segments.map((segment, index) => {
    const key = `${keyPrefix}-inline-${index}`;
    if (segment.startsWith("`") && segment.endsWith("`")) {
      return <code key={key}>{segment.slice(1, -1)}</code>;
    }
    if (segment.startsWith("**") && segment.endsWith("**")) {
      return <strong key={key}>{segment.slice(2, -2)}</strong>;
    }
    if (segment.startsWith("*") && segment.endsWith("*")) {
      return <em key={key}>{segment.slice(1, -1)}</em>;
    }
    return segment;
  });
};

export const renderMarkdownContent = (text) => {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let index = 0;
  let codeFence = null;
  let codeLines = [];

  const readList = (startIndex, ordered) => {
    const items = [];
    let cursor = startIndex;
    const listRegex = ordered ? /^\s*\d+\.\s+(.+)$/ : /^\s*[-*]\s+(.+)$/;
    while (cursor < lines.length) {
      const match = lines[cursor].match(listRegex);
      if (!match) break;
      items.push(match[1]);
      cursor += 1;
    }
    return { items, cursor };
  };

  while (index < lines.length) {
    const line = lines[index];

    if (line.trim().startsWith("```")) {
      if (codeFence) {
        blocks.push(
          <pre key={`code-${index}`}><code>{codeLines.join("\n")}</code></pre>
        );
        codeFence = null;
        codeLines = [];
      } else {
        codeFence = line.trim();
      }
      index += 1;
      continue;
    }

    if (codeFence) {
      codeLines.push(line);
      index += 1;
      continue;
    }

    if (!line.trim()) {
      index += 1;
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      const level = Math.min(heading[1].length + 2, 6);
      const Tag = `h${level}`;
      blocks.push(
        <Tag key={`heading-${index}`}>{renderInlineMarkdown(heading[2], `heading-${index}`)}</Tag>
      );
      index += 1;
      continue;
    }

    const unordered = line.match(/^\s*[-*]\s+(.+)$/);
    if (unordered) {
      const { items, cursor } = readList(index, false);
      blocks.push(
        <ul key={`ul-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`ul-${index}-${itemIndex}`}>{renderInlineMarkdown(item, `ul-${index}-${itemIndex}`)}</li>
          ))}
        </ul>
      );
      index = cursor;
      continue;
    }

    const ordered = line.match(/^\s*\d+\.\s+(.+)$/);
    if (ordered) {
      const { items, cursor } = readList(index, true);
      blocks.push(
        <ol key={`ol-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`ol-${index}-${itemIndex}`}>{renderInlineMarkdown(item, `ol-${index}-${itemIndex}`)}</li>
          ))}
        </ol>
      );
      index = cursor;
      continue;
    }

    const quote = line.match(/^\s*>\s+(.+)$/);
    if (quote) {
      blocks.push(
        <blockquote key={`quote-${index}`}>{renderInlineMarkdown(quote[1], `quote-${index}`)}</blockquote>
      );
      index += 1;
      continue;
    }

    blocks.push(
      <p key={`paragraph-${index}`}>{renderInlineMarkdown(line, `paragraph-${index}`)}</p>
    );
    index += 1;
  }

  if (codeFence && codeLines.length) {
    blocks.push(
      <pre key="code-open"><code>{codeLines.join("\n")}</code></pre>
    );
  }

  return blocks;
};
