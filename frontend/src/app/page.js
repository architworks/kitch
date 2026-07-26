"use client";

import React, { useState, useEffect, useMemo, useRef, useCallback } from "react";
import Image from "next/image";
import { DIET_TYPES } from "./mockData.js";
import {
  DEFAULT_ACTIVE_USER,
  DEFAULT_HOUSEHOLD_SIZE,
  HOUSEHOLD_MEMBERS,
  MEAL_SLOTS,
  WEEK_DAYS,
  createEmptyPlanningWeekDates,
  createUserProfiles,
  getUpcomingPlanningWeekDates
} from "./householdConfig.js";

const MEAL_SLOT_LABELS = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner"
};

const ABOUT_WORKFLOW_STEPS = [
  {
    number: "1",
    icon: "calendar",
    title: "Plan meals",
    body: "Create your weekly plan in seconds."
  },
  {
    number: "2",
    icon: "pot",
    title: "Get recipes",
    body: "View step-by-step recipes for any meal."
  },
  {
    number: "3",
    icon: "bag",
    title: "Add ingredients",
    body: "Ingredients from recipes are added to your native cart."
  },
  {
    number: "4",
    icon: "cart",
    title: "Review groceries",
    body: "Review, edit, and add anything you need."
  },
  {
    number: "5",
    icon: "scooter",
    title: "Order with confidence",
    body: "Move to Zepto and place the order only after approval."
  }
];

const ABOUT_STEP_TONES = {
  calendar: "sage",
  pot: "amber",
  bag: "green",
  cart: "violet",
  scooter: "rose"
};

const DEFAULT_MEAL_SLOT = "breakfast";
const INITIAL_VISIBLE_CHAT_COUNT = 6;
const CHAT_HISTORY_BATCH_SIZE = 6;
const PERSISTENCE_FAILURE_MESSAGE = "Kitch couldn’t save this change because durable storage is unavailable. Nothing was saved.";

class ApiResponseError extends Error {
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

const requireSuccessfulResponse = async (response) => {
  if (response.ok) return response;
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  throw new ApiResponseError(response.status, body?.detail || body);
};

const apiErrorMessage = (error, fallback) => (
  error instanceof ApiResponseError && error.isPersistenceFailure
    ? PERSISTENCE_FAILURE_MESSAGE
    : error?.message || fallback
);

const AboutIconBadge = ({ name, tone = "sage", className = "" }) => {
  const badgeClass = `about-icon-badge tone-${tone} about-icon-${name} ${className}`.trim();

  let icon = null;

  if (name === "people") {
    icon = (
      <>
        <circle className="icon-fill-soft" cx="14" cy="21" r="5" />
        <circle className="icon-fill-soft" cx="34" cy="21" r="5" />
        <circle className="icon-fill-main" cx="24" cy="18" r="6" />
        <path className="icon-fill-soft" d="M5 38c1.2-7.1 5-11 11.8-11 2.5 0 4.7.8 6.4 2.2-2.3 1.8-3.7 4.8-4.2 8.8H5Z" />
        <path className="icon-fill-soft" d="M29 38c-.5-4-1.9-7-4.2-8.8 1.7-1.4 3.9-2.2 6.4-2.2 5.8 0 9.6 3.9 10.8 11H29Z" />
        <path className="icon-fill-main" d="M13 39c1.2-8.4 5.2-12.2 11-12.2S33.8 30.6 35 39H13Z" />
      </>
    );
  } else if (name === "pantry") {
    icon = (
      <>
        <path className="icon-fill-soft" d="M17 17h14l-1.1 22H18.1L17 17Z" />
        <path className="icon-stroke" d="M16 17h16M19 12h10l2 5H17l2-5ZM18 22h12M20 39h8" />
        <path className="icon-fill-accent" d="M17 31c4.4-3.9 8.2-4 11.3-.2-3.8 3.8-7.6 4-11.3.2Z" />
        <circle className="icon-fill-main" cx="25" cy="28" r="2.5" />
        <circle className="icon-fill-main" cx="30" cy="31" r="2.2" />
      </>
    );
  } else if (name === "nutrition") {
    icon = (
      <>
        <circle className="icon-fill-soft" cx="24" cy="18" r="7" />
        <path className="icon-fill-accent" d="M12 40c1.4-8.3 5.7-12.5 12-12.5S34.6 31.7 36 40H12Z" />
        <path className="icon-stroke" d="M17 39c1.1-5.1 3.5-7.7 7-7.7s5.9 2.6 7 7.7" />
      </>
    );
  } else if (name === "calendar") {
    icon = (
      <>
        <rect className="icon-fill-soft" x="11" y="13" width="26" height="25" rx="5" />
        <path className="icon-stroke" d="M16 9v8M32 9v8M11 21h26M18 28h4M26 28h4M18 34h4" />
        <circle className="icon-fill-main" cx="36" cy="36" r="7" />
        <path className="icon-stroke-light" d="m32.8 36 2 2 4.2-5" />
      </>
    );
  } else if (name === "pot") {
    icon = (
      <>
        <path className="icon-stroke" d="M18 10c-1.9 2-1.9 4 0 6M24 8.5c-2 2.2-2 4.9 0 7.1M30 10c-1.9 2-1.9 4 0 6" />
        <path className="icon-fill-soft" d="M14 25h20l-1.8 11.5a4.3 4.3 0 0 1-4.2 3.6h-8a4.3 4.3 0 0 1-4.2-3.6L14 25Z" />
        <path className="icon-stroke" d="M13 22h22M11 26H7M37 26h4M20 22v-3h8v3" />
        <circle className="icon-fill-accent" cx="24" cy="31.5" r="3" />
      </>
    );
  } else if (name === "bag") {
    icon = (
      <>
        <path className="icon-fill-soft" d="M12 19h24l-2 21H14l-2-21Z" />
        <path className="icon-stroke" d="M12 19h24l-2 21H14l-2-21ZM18 19c0-5.2 2.4-8.2 6-8.2s6 3 6 8.2" />
        <circle className="icon-fill-main" cx="20" cy="28" r="3.8" />
        <circle className="icon-fill-accent" cx="28" cy="27" r="4.3" />
        <path className="icon-fill-main" d="M24 35c-5-1.1-7.3-4.6-4.6-8.1 5.2 1 7.2 4.4 4.6 8.1Z" />
        <path className="icon-fill-accent" d="M28 35c5.3-1.5 6.5-5.2 3.2-8.2-4.6 1.1-5.9 4.7-3.2 8.2Z" />
      </>
    );
  } else if (name === "cart") {
    icon = (
      <>
        <path className="icon-fill-soft" d="M17 18h22l-4 14H20l-3-14Z" />
        <path className="icon-stroke" d="M8 12h5l4.5 20h17l4.5-14H17M21 24h15M25 18v14M33 18v14" />
        <circle className="icon-fill-main" cx="21" cy="38" r="3.2" />
        <circle className="icon-fill-main" cx="35" cy="38" r="3.2" />
      </>
    );
  } else if (name === "scooter") {
    icon = (
      <>
        <path className="icon-fill-soft" d="M13 31h19l5-8h-9l-5-7h-8l-2 15Z" />
        <path className="icon-stroke" d="M12 31h20l5-8h-9l-5-7h-8M29 23h8l2-7h4M20 23h-7" />
        <circle className="icon-fill-main" cx="15" cy="36" r="4" />
        <circle className="icon-fill-main" cx="34" cy="36" r="4" />
        <path className="icon-stroke" d="M22 14c2-4 5.2-5.1 9-3.2" />
      </>
    );
  } else if (name === "chef") {
    icon = (
      <>
        <path className="icon-stroke" d="M17 30.5h14v7H17v-7Z" />
        <path className="icon-stroke" d="M16.5 30.5c-4.8-1.4-6.7-8.4-.8-10.7 1.2-5.9 8.9-6.9 11.5-1.8 5.7-1.8 10.3 4.9 6.8 9.4-1 1.4-2.4 2.4-4 3.1" />
        <path className="icon-stroke" d="M20 35h8" />
      </>
    );
  } else if (name === "chat") {
    icon = (
      <>
        <path className="icon-fill-soft" d="M11 16h26v17H22l-8 5v-5h-3V16Z" />
        <path className="icon-stroke" d="M11 16h26v17H22l-8 5v-5h-3V16Z" />
        <circle className="icon-fill-main" cx="20" cy="24.5" r="2" />
        <circle className="icon-fill-main" cx="26" cy="24.5" r="2" />
        <circle className="icon-fill-main" cx="32" cy="24.5" r="2" />
      </>
    );
  } else if (name === "brain") {
    icon = (
      <>
        <path className="icon-stroke" d="M19 12c-4 0-7 3.1-7 7 0 1.2.3 2.3.8 3.2A6.4 6.4 0 0 0 11 27c0 4.2 3.3 7.5 7.5 7.5H21V12h-2Z" />
        <path className="icon-stroke" d="M29 12c4 0 7 3.1 7 7 0 1.2-.3 2.3-.8 3.2A6.4 6.4 0 0 1 37 27c0 4.2-3.3 7.5-7.5 7.5H27V12h2Z" />
        <path className="icon-stroke" d="M17 22h4M27 22h4M18 29h3M27 29h3M24 13v23" />
      </>
    );
  } else if (name === "suggestions") {
    icon = (
      <>
        <circle className="icon-fill-soft" cx="24" cy="21" r="7" />
        <path className="icon-stroke" d="M24 8v4M24 31v4M11 21H7M41 21h-4M14.8 11.8l2.8 2.8M33.2 29.2l2.8 2.8M36 11.8l-2.8 2.8M17.6 29.2 14.8 32" />
        <path className="icon-stroke" d="M20 38h8M21.5 34h5" />
      </>
    );
  } else if (name === "shield") {
    icon = (
      <>
        <path className="icon-fill-soft" d="M24 8 38 14v10c0 9-5.4 15.2-14 18-8.6-2.8-14-9-14-18V14l14-6Z" />
        <path className="icon-stroke" d="M24 8 38 14v10c0 9-5.4 15.2-14 18-8.6-2.8-14-9-14-18V14l14-6Z" />
        <path className="icon-stroke" d="m18 25 4 4 8-9" />
      </>
    );
  } else {
    icon = (
      <>
        <path className="icon-fill-soft" d="M14 12h20v25H14V12Z" />
        <path className="icon-stroke" d="M14 12h20v25H14V12ZM18 19h12M18 25h12M18 31h7" />
      </>
    );
  }

  return (
    <span className={badgeClass} aria-hidden="true">
      <svg viewBox="0 0 48 48">{icon}</svg>
    </span>
  );
};

const getTimeBasedMealSlot = (date = new Date()) => {
  const hour = date.getHours();
  if (hour < 11) return "breakfast";
  if (hour < 16) return "lunch";
  return "dinner";
};

const getTimeBasedGreeting = (date = new Date()) => {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const apiUrl = (path) => `${API_BASE_URL}${path}`;

const getMealTitle = (meal, fallback = "No recipe set") => {
  if (!meal) return fallback;
  if (typeof meal === "string") return meal || fallback;
  return meal.name || meal.title || meal.recipe_name || fallback;
};

const hasMealTitle = (meal) => Boolean(String(getMealTitle(meal, "")).trim());

const getRecipeCardTitle = (recipe, fallback = "Recipe details pending") => {
  if (!recipe) return fallback;
  if (typeof recipe === "string") return recipe || fallback;
  return recipe.title || recipe.name || recipe.recipeName || recipe.recipe_name || fallback;
};

const normalizeList = (value) => {
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

const getIngredientName = (ingredient) => {
  if (!ingredient) return "";
  if (typeof ingredient === "string") return ingredient;
  return ingredient.name || ingredient.ingredient_name || ingredient.item || ingredient.ingredient || "";
};

const getIngredientQuantity = (ingredient) => {
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

const getRecipeSteps = (recipe) => {
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

const formatCartQuantity = (amount, unit) => {
  const amountText = `${amount ?? ""}`.trim();
  const unitText = `${unit || ""}`.trim();
  if (!amountText && !unitText) return "—";
  if (unitText.toLowerCase() === "to taste") return "To taste";
  if (unitText.toLowerCase() === "as needed") return "As needed";
  return [amountText, unitText].filter(Boolean).join(" ");
};

const parseJsonText = (value) => {
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
};

const collectObjectsWithAnyKey = (value, keys, results = []) => {
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

const optionValue = (option, keys, fallback = "") => {
  for (const key of keys) {
    if (option?.[key]) return option[key];
  }
  return fallback;
};

const textOptionValue = (option, keys, fallback = "") => {
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

const uniqueParts = (parts) => {
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

const findNestedTextValue = (value, keys, depth = 0) => {
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

const formatZeptoAddressLabel = (option, fallback = "Saved address") => {
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

const formatZeptoAddressParts = (option, fallback = "Saved address") => {
  const display = formatZeptoAddressLabel(option, fallback);
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

const zeptoValue = (sources, keys) => {
  for (const source of sources) {
    if (!source || typeof source !== "object") continue;
    for (const key of keys) {
      const value = source[key];
      if (value !== undefined && value !== null && value !== "") return value;
    }
  }
  return "";
};

const formatZeptoPrice = (value) => {
  if (value === undefined || value === null || value === "") return "";
  if (typeof value === "string" && value.includes("₹")) return value;
  const normalized = typeof value === "string" ? value.replace(/[^\d.]/g, "") : value;
  const numeric = Number(normalized);
  if (!Number.isFinite(numeric)) return String(value);
  const rupees = numeric >= 100 ? numeric / 100 : numeric;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: rupees % 1 === 0 ? 0 : 2
  }).format(rupees);
};

const formatZeptoCartQuantity = (match) => {
  const quantity = zeptoValue(
    [match?.cart_item, match?.add_result, match?.matched_product],
    ["quantity", "qty", "count"]
  );
  if (quantity === "") return "";
  return String(quantity);
};

const getZeptoProductMeta = (match) => {
  const product = match?.matched_product || {};
  const cartItem = match?.cart_item || {};
  const native = match?.native_item || {};
  const price = formatZeptoPrice(zeptoValue([cartItem, product], ["price", "sellingPrice", "selling_price", "discountedPrice"]));
  const quantity = formatZeptoCartQuantity(match);
  const packSize = zeptoValue([cartItem, product], ["packSize", "pack_size", "unit", "unitOfQuantity", "unit_of_quantity", "quantityUnit"]);
  const company = zeptoValue([product, cartItem], [
    "manufacturer",
    "manufacturerName",
    "manufacturer_name",
    "company",
    "companyName",
    "brand",
    "brandName",
    "seller",
    "sellerName"
  ]);
  const requested = formatCartQuantity(native.amount, native.unit);

  return [
    company && ["Company", company],
    price && ["Price", price],
    quantity && ["Qty", quantity],
    packSize && ["Unit of qty", packSize],
    requested && ["Kitch needed", requested]
  ].filter(Boolean);
};

const cartItemKey = (item) => String(item?.id || item?.name || "");

const INITIAL_CHAT = [];

const renderInlineMarkdown = (text, keyPrefix) => {
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

const renderMarkdownContent = (text) => {
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

export default function Home() {
  // Application core state variables
  const [activeTab, setActiveTab] = useState("planner");
  const [selectedPlannerDay, setSelectedPlannerDay] = useState("Monday");
  const [currentMealSlot, setCurrentMealSlot] = useState(DEFAULT_MEAL_SLOT);
  const [expandedMealKey, setExpandedMealKey] = useState(`Monday-${DEFAULT_MEAL_SLOT}`);
  const [dietPreference, setDietPreference] = useState("balanced");
  const [householdSize, setHouseholdSize] = useState(DEFAULT_HOUSEHOLD_SIZE);
  const [activeUser, setActiveUser] = useState(DEFAULT_ACTIVE_USER);
  const [userProfiles, setUserProfiles] = useState(createUserProfiles);
  const [pantryStock, setPantryStock] = useState([]);
  const [weeklyPlan, setWeeklyPlan] = useState({});
  const [chatHistory, setChatHistory] = useState([...INITIAL_CHAT]);
  const [visibleChatCount, setVisibleChatCount] = useState(INITIAL_VISIBLE_CHAT_COUNT);
  const chatMessagesRef = useRef(null);
  const [customGroceryItems, setCustomGroceryItems] = useState([]);
  const confirmedGroceryItemsRef = useRef([]);
  const [latestRecipeGroceryPlan, setLatestRecipeGroceryPlan] = useState(null);
  const [planningWeekDates, setPlanningWeekDates] = useState(createEmptyPlanningWeekDates);

  // UI state variables
  const [chatInput, setChatInput] = useState("");
  const [isChatTyping, setIsChatTyping] = useState(false);
  const [smartDockExpanded, setSmartDockExpanded] = useState(false);
  const [pendingPhoto, setPendingPhoto] = useState(null);
  const [zeptoCartReview, setZeptoCartReview] = useState(null);
  const [zeptoConnectionStatus, setZeptoConnectionStatus] = useState(null);
  const [zeptoSavedAddresses, setZeptoSavedAddresses] = useState(null);
  const [isZeptoAddressLoading, setIsZeptoAddressLoading] = useState(false);
  const [zeptoAddressLoadError, setZeptoAddressLoadError] = useState("");
  const [selectedZeptoAddress, setSelectedZeptoAddress] = useState("");
  const [selectedZeptoPaymentMethod, setSelectedZeptoPaymentMethod] = useState("");
  const [zeptoReviewAcknowledged, setZeptoReviewAcknowledged] = useState(false);
  const [isUpdatingZeptoReview, setIsUpdatingZeptoReview] = useState(false);
  const [excludedZeptoItemIds, setExcludedZeptoItemIds] = useState([]);
  const [isZeptoSyncing, setIsZeptoSyncing] = useState(false);
  const [zeptoSyncStage, setZeptoSyncStage] = useState("idle");
  const [groceryMutationCount, setGroceryMutationCount] = useState(0);
  const [isPlacingZeptoOrder, setIsPlacingZeptoOrder] = useState(false);
  const [alertBanner, setAlertBanner] = useState({ show: false, text: "" });
  const [scanningOverlay, setScanningOverlay] = useState({
    active: false,
    title: "",
    steps: [],
    fileName: ""
  });
  const [recipeSidebarTab, setRecipeSidebarTab] = useState("ingredients");
  const [recipeBodyTab, setRecipeBodyTab] = useState("recipe");

  // Custom ingredient add inputs
  const [groceryCustomName, setGroceryCustomName] = useState("");
  const [groceryCustomAmount, setGroceryCustomAmount] = useState(1);
  const [groceryCustomUnit, setGroceryCustomUnit] = useState("piece");
  const [groceryCustomCat, setGroceryCustomCat] = useState("Fresh Produce");
  const groceryMutationCountRef = useRef(0);
  const zeptoSyncInFlightRef = useRef(false);
  const zeptoSyncTimersRef = useRef([]);
  const zeptoSyncDialogRef = useRef(null);

  const applyConfirmedGroceryCart = useCallback((items) => {
    const confirmedItems = Array.isArray(items) ? items : [];
    confirmedGroceryItemsRef.current = confirmedItems;
    setCustomGroceryItems(confirmedItems);
  }, []);

  const applyLiveState = useCallback((userName, data) => {
    if (data.pantry_stock) {
      setPantryStock(data.pantry_stock);
    }
    if (data.macro_diary) {
      setUserProfiles(prev => ({
        ...prev,
        [userName]: {
          name: userName,
          loggedMeals: data.macro_diary
        }
      }));
    }
    if (data.profile) {
      if (data.profile.diet_preference) {
        setDietPreference(data.profile.diet_preference);
      }
      if (data.profile.household_size) {
        setHouseholdSize(data.profile.household_size);
      }
    }
    if (Object.prototype.hasOwnProperty.call(data, "weekly_plan")) {
      setWeeklyPlan(data.weekly_plan || {});
    }
    if (data.grocery_cart) {
      applyConfirmedGroceryCart(data.grocery_cart);
    }
  }, [applyConfirmedGroceryCart]);

  const fetchLiveState = async (userName) => {
    const res = await fetch(apiUrl(`/api/state/${userName}`));
    await requireSuccessfulResponse(res);
    return res.json();
  };

  const syncLatestRecipeGroceryPlan = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("/api/recipe-grocery/plans/latest"));
      await requireSuccessfulResponse(res);
      const data = await res.json();
      setLatestRecipeGroceryPlan(data.plan || null);
      return data.plan || null;
    } catch (e) {
      console.error("Failed to sync latest recipe+grocery plan", e);
      return null;
    }
  }, []);

  const syncZeptoStatus = async () => {
    try {
      const res = await fetch(apiUrl("/api/grocery/zepto/status"));
      await requireSuccessfulResponse(res);
      const data = await res.json();
      setZeptoConnectionStatus(data);
      return data;
    } catch (e) {
      console.error("Failed to sync Zepto status", e);
      const status = {
        provider: "zepto",
        state: "failed",
        message: "Could not contact the backend Zepto status endpoint."
      };
      setZeptoConnectionStatus(status);
      return status;
    }
  };

  const syncZeptoAddresses = async () => {
    setIsZeptoAddressLoading(true);
    setZeptoAddressLoadError("");
    try {
      const res = await fetch(apiUrl("/api/grocery/zepto/addresses"));
      await requireSuccessfulResponse(res);
      const data = await res.json();
      const addresses = data.addresses || null;
      const options = collectObjectsWithAnyKey(addresses, ["address", "address_line", "addressLine", "id"]);
      setZeptoSavedAddresses(addresses);
      setSelectedZeptoAddress(current => (
        options.some((option, idx) => optionValue(option, ["id", "address_id", "addressId"], `address-${idx}`) === current)
          ? current
          : ""
      ));
      if (options.length === 0) {
        setZeptoAddressLoadError("Zepto did not return any saved delivery addresses.");
      }
      return addresses;
    } catch (e) {
      console.error("Failed to load Zepto delivery addresses", e);
      setZeptoSavedAddresses(null);
      setSelectedZeptoAddress("");
      setZeptoAddressLoadError(e?.message || "Could not load Zepto delivery addresses.");
      return null;
    } finally {
      setIsZeptoAddressLoading(false);
    }
  };

  const syncLiveState = async (userName) => {
    try {
      const data = await fetchLiveState(userName);
      applyLiveState(userName, data);
      await syncLatestRecipeGroceryPlan();
      return data;
    } catch (e) {
      console.error("Failed to sync live state with Supabase backend", e);
      return null;
    }
  };

  useEffect(() => {
    let ignore = false;

    async function loadState() {
      try {
        const data = await fetchLiveState(activeUser);
        if (!ignore) {
          applyLiveState(activeUser, data);
          await syncLatestRecipeGroceryPlan();
        }
      } catch (e) {
        console.error("Failed to sync live state with Supabase backend", e);
      }
    }

    loadState();
    return () => {
      ignore = true;
    };
  }, [activeUser, applyLiveState, syncLatestRecipeGroceryPlan]);

  useEffect(() => {
    if (activeTab !== "groceries") return undefined;
    const timer = window.setTimeout(() => {
      syncZeptoStatus();
      syncZeptoAddresses();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activeTab]);

  useEffect(() => {
    if (!isZeptoSyncing) return undefined;

    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    const focusFrame = window.requestAnimationFrame(() => {
      zeptoSyncDialogRef.current?.focus();
    });
    const keepFocusInDialog = (event) => {
      if (event.key === "Escape" || event.key === "Tab") {
        event.preventDefault();
        zeptoSyncDialogRef.current?.focus();
      }
    };

    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", keepFocusInDialog);

    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", keepFocusInDialog);
      if (previousFocus instanceof HTMLElement) {
        previousFocus.focus();
      }
    };
  }, [isZeptoSyncing]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPlanningWeekDates(getUpcomingPlanningWeekDates());
    }, 0);

    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const syncMealFocus = () => {
      const nextMealSlot = getTimeBasedMealSlot();
      setCurrentMealSlot(previousMealSlot => {
        if (previousMealSlot !== nextMealSlot) {
          setExpandedMealKey(currentKey => (
            currentKey === `${selectedPlannerDay}-${previousMealSlot}`
              ? `${selectedPlannerDay}-${nextMealSlot}`
              : currentKey
          ));
        }

        return nextMealSlot;
      });
    };

    syncMealFocus();
    const interval = window.setInterval(syncMealFocus, 60 * 1000);
    return () => window.clearInterval(interval);
  }, [selectedPlannerDay]);

  useEffect(() => {
    if (!smartDockExpanded || !chatMessagesRef.current) return undefined;

    const frame = window.requestAnimationFrame(() => {
      const messages = chatMessagesRef.current;
      if (messages) {
        messages.scrollTop = messages.scrollHeight;
      }
    });

    return () => window.cancelAnimationFrame(frame);
  }, [chatHistory.length, isChatTyping, smartDockExpanded]);

  // Sync alert auto-dismiss timer
  useEffect(() => {
    if (alertBanner.show) {
      const timer = setTimeout(() => {
        setAlertBanner(prev => ({ ...prev, show: false }));
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [alertBanner.show]);

  // 2. Computed values - Reactive Shopping Cart List
  const groceryList = useMemo(() => {
    return customGroceryItems;
  }, [customGroceryItems]);

  // Sync count statistics
  const totalCount = groceryList.length;
  const zeptoSelectedCount = groceryList.filter(item => !item.alreadyStocked && !excludedZeptoItemIds.includes(cartItemKey(item))).length;

  // 3. Application operations
  const triggerBannerAlert = (text) => {
    setAlertBanner({ show: true, text });
  };

  const beginGroceryMutation = () => {
    groceryMutationCountRef.current += 1;
    setGroceryMutationCount(groceryMutationCountRef.current);
  };

  const endGroceryMutation = () => {
    groceryMutationCountRef.current = Math.max(0, groceryMutationCountRef.current - 1);
    setGroceryMutationCount(groceryMutationCountRef.current);
  };

  const clearZeptoSyncTimers = () => {
    zeptoSyncTimersRef.current.forEach(timer => window.clearTimeout(timer));
    zeptoSyncTimersRef.current = [];
  };

  const startZeptoSyncProgress = () => {
    clearZeptoSyncTimers();
    setZeptoSyncStage("preparing");
    zeptoSyncTimersRef.current = [
      window.setTimeout(() => setZeptoSyncStage("transferring"), 700),
      window.setTimeout(() => setZeptoSyncStage("finalizing"), 6000)
    ];
  };

  const saveHouseholdProfile = async (dietType, size) => {
    const res = await fetch(apiUrl("/api/household/profile"), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        diet_preference: dietType,
        household_size: size
      })
    });
    await requireSuccessfulResponse(res);
    return res.json();
  };

  const switchDiet = async (dietType) => {
    if (!DIET_TYPES[dietType]) return;
    try {
      const data = await saveHouseholdProfile(dietType, householdSize);
      setDietPreference(data.profile.diet_preference);
      triggerBannerAlert(`Switched dietary profile to ${DIET_TYPES[dietType].name}!`);
    } catch (e) {
      console.error("Failed to update dietary profile", e);
      triggerBannerAlert(apiErrorMessage(e, "Could not update the dietary profile."));
    }
  };

  const updateHouseholdSize = async (size) => {
    const val = Math.max(1, parseInt(size) || 1);
    try {
      const data = await saveHouseholdProfile(dietPreference, val);
      setHouseholdSize(data.profile.household_size);
      triggerBannerAlert(`Updated household size to ${data.profile.household_size}.`);
    } catch (e) {
      console.error("Failed to update household size", e);
      triggerBannerAlert(apiErrorMessage(e, "Could not update the household size."));
    }
  };

  const switchActiveUser = (userName) => {
    setActiveUser(userName);
    triggerBannerAlert(`Switched active profile to ${userName}. Viewing macro logs for ${userName}.`);
  };

  const toggleZeptoItemSelection = (item) => {
    if (zeptoSyncInFlightRef.current || !item || item.alreadyStocked) return;
    const key = cartItemKey(item);
    if (!key) return;
    setExcludedZeptoItemIds(prev => (
      prev.includes(key)
        ? prev.filter(id => id !== key)
        : [...prev, key]
    ));
  };

  const updateGroceryCartItemDetails = async (item, updates) => {
    if (zeptoSyncInFlightRef.current || !item?.id) return;

    beginGroceryMutation();
    try {
      const res = await fetch(apiUrl(`/api/grocery/cart/items/${item.id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates)
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      if (data.grocery_cart) {
        applyConfirmedGroceryCart(data.grocery_cart);
      }
    } catch (e) {
      console.error("Failed to update grocery cart item", e);
      setCustomGroceryItems(confirmedGroceryItemsRef.current);
      triggerBannerAlert(apiErrorMessage(e, "Could not update the grocery item."));
    } finally {
      endGroceryMutation();
    }
  };

  const deleteGroceryCartItem = async (item) => {
    if (zeptoSyncInFlightRef.current || !item?.id) return;

    beginGroceryMutation();
    try {
      const res = await fetch(apiUrl(`/api/grocery/cart/items/${item.id}`), {
        method: "DELETE"
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      if (data.grocery_cart) {
        applyConfirmedGroceryCart(data.grocery_cart);
      }
    } catch (e) {
      console.error("Failed to delete grocery cart item", e);
      triggerBannerAlert(apiErrorMessage(e, "Could not delete the grocery item."));
    } finally {
      endGroceryMutation();
    }
  };

  const clearPlannedGroceryRows = async () => {
    if (zeptoSyncInFlightRef.current) return;

    beginGroceryMutation();
    try {
      const res = await fetch(apiUrl("/api/grocery/cart/planned"), {
        method: "DELETE"
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      if (data.grocery_cart) {
        applyConfirmedGroceryCart(data.grocery_cart);
      }
      triggerBannerAlert("Cleared recipe-planned grocery rows.");
    } catch (e) {
      console.error("Failed to clear planned grocery rows", e);
      triggerBannerAlert(apiErrorMessage(e, "Could not clear planned grocery rows."));
    } finally {
      endGroceryMutation();
    }
  };

  const addCustomGroceryItem = async (name, category, amount = 1, unit = "piece") => {
    if (zeptoSyncInFlightRef.current || !name.trim()) return;

    const requestedItem = {
      name: name.trim(),
      amount: parseFloat(amount) || 1,
      unit: unit || "piece",
      category,
      source: "manual",
      checked: false,
      alreadyStocked: false,
      stockNote: ""
    };

    beginGroceryMutation();
    try {
      const res = await fetch(apiUrl("/api/grocery/cart/items"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestedItem)
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      if (data.grocery_cart) {
        applyConfirmedGroceryCart(data.grocery_cart);
      }
      setGroceryCustomName("");
      setGroceryCustomAmount(1);
      setGroceryCustomUnit("piece");
      triggerBannerAlert(`Added custom item: "${name}" to ${category}!`);
    } catch (e) {
      console.error("Failed to add grocery cart item", e);
      triggerBannerAlert(apiErrorMessage(e, "Could not add the grocery item."));
    } finally {
      endGroceryMutation();
    }
  };

  const syncNativeCartToZepto = async () => {
    if (zeptoSyncInFlightRef.current) return;
    if (groceryMutationCountRef.current > 0) {
      triggerBannerAlert("Please wait for the native cart to finish saving before moving items to Zepto.");
      return;
    }
    if (checkoutItems.length === 0) {
      triggerBannerAlert("Select at least one native cart item for Zepto.");
      return;
    }
    if (!selectedZeptoAddress) {
      triggerBannerAlert("Select a Zepto delivery address before moving items to the cart.");
      return;
    }

    zeptoSyncInFlightRef.current = true;
    setIsZeptoSyncing(true);
    startZeptoSyncProgress();
    try {
      const res = await fetch(apiUrl("/api/grocery/zepto/sync-cart"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cart_item_ids: checkoutItems.map(item => item.id).filter(Boolean),
          selected_address_id: selectedZeptoAddress
        })
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      const review = data.review || data;
      setZeptoCartReview(review);
      setSelectedZeptoAddress(review.selected_address_id || "");
      setSelectedZeptoPaymentMethod(review.selected_payment_method_id || "");
      setZeptoReviewAcknowledged(Boolean(review.order_review_acknowledged));
      clearZeptoSyncTimers();
      setZeptoSyncStage("complete");
      await new Promise(resolve => window.setTimeout(resolve, 450));
      triggerBannerAlert(data.status === "success" ? "Zepto cart sync completed for review." : "Zepto cart sync needs attention.");
    } catch (e) {
      console.error("Failed to sync Zepto cart", e);
      clearZeptoSyncTimers();
      setZeptoSyncStage("failed");
      await new Promise(resolve => window.setTimeout(resolve, 650));
      triggerBannerAlert(apiErrorMessage(e, "Failed to sync the native cart to Zepto."));
    } finally {
      clearZeptoSyncTimers();
      zeptoSyncInFlightRef.current = false;
      setIsZeptoSyncing(false);
      setZeptoSyncStage("idle");
      syncZeptoStatus();
    }
  };

  const updateZeptoReview = async (updates) => {
    if (!zeptoCartReview?.review_id) return null;
    setIsUpdatingZeptoReview(true);
    try {
      const res = await fetch(apiUrl(`/api/grocery/zepto/review/${zeptoCartReview.review_id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates)
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      if (data.review) {
        setZeptoCartReview(data.review);
        setSelectedZeptoAddress(data.review.selected_address_id || "");
        setSelectedZeptoPaymentMethod(data.review.selected_payment_method_id || "");
        setZeptoReviewAcknowledged(Boolean(data.review.order_review_acknowledged));
        return data.review;
      }
    } catch (e) {
      console.error("Failed to update Zepto review", e);
      triggerBannerAlert(apiErrorMessage(e, "Could not update Zepto review selection."));
    } finally {
      setIsUpdatingZeptoReview(false);
    }
    return null;
  };

  const selectZeptoSyncAddress = (value) => {
    if (zeptoSyncInFlightRef.current) return;
    setSelectedZeptoAddress(value);
    setZeptoCartReview(null);
    setSelectedZeptoPaymentMethod("");
    setZeptoReviewAcknowledged(false);
  };

  const placeZeptoOrder = async () => {
    if (!zeptoCartReview?.review_id || !zeptoCartReview?.confirmation_token) {
      triggerBannerAlert("Final Zepto approval token is missing. Sync the cart again before placing the order.");
      return;
    }
    if (!zeptoReviewAcknowledged) {
      triggerBannerAlert("Review and acknowledge the exact Zepto cart before confirming the order.");
      return;
    }

    setIsPlacingZeptoOrder(true);
    try {
      const latestReview = await updateZeptoReview({
        selected_payment_method_id: selectedZeptoPaymentMethod || null,
        order_review_acknowledged: true
      }) || zeptoCartReview;
      const res = await fetch(apiUrl("/api/grocery/zepto/place-order"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          review_id: latestReview.review_id,
          confirmation_token: latestReview.confirmation_token,
          approved_snapshot_hash: latestReview.snapshot_hash,
          order_review_acknowledged: true
        })
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      setZeptoCartReview(data.review || data);
      triggerBannerAlert(data.status === "success" ? "Zepto order placement request completed." : "Zepto order could not be placed.");
    } catch (e) {
      console.error("Failed to place Zepto order", e);
      triggerBannerAlert(apiErrorMessage(e, "Failed to contact the backend Zepto order endpoint."));
    } finally {
      setIsPlacingZeptoOrder(false);
    }
  };

  const resetDailyLogs = async () => {
    try {
      const res = await fetch(apiUrl(`/api/diary/clear/${activeUser}`), {
        method: "POST"
      });
      await requireSuccessfulResponse(res);
      const data = await fetchLiveState(activeUser);
      applyLiveState(activeUser, data);
      triggerBannerAlert(`Cleared today's plate logs for ${activeUser}.`);
    } catch (e) {
      console.error("Failed to clear macro logs in DB", e);
      triggerBannerAlert(apiErrorMessage(e, "Could not clear the plate logs."));
    }
  };

  const stagePhotoForInput = (file, isFridgeScan) => {
    if (!file) return;

    setPendingPhoto({
      file,
      isFridgeScan
    });
    setSmartDockExpanded(true);
  };

  const clearPendingPhoto = () => {
    setPendingPhoto(null);
  };

  // 4. Send chat message to real FastAPI backend agent
  const sendChatMessage = async (prompt) => {
    if (!prompt.trim() || isChatTyping) return;

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setSmartDockExpanded(true);
    setChatHistory(prev => [...prev, { sender: "user", text: prompt, time }]);
    
    setIsChatTyping(true);

    try {
      const chatPayload = {
        message: prompt,
        active_user: activeUser,
        diet_preference: dietPreference,
        household_size: householdSize,
        weekly_plan: weeklyPlan,
        pantry_stock: pantryStock,
        grocery_list: groceryList
      };

      const res = await fetch(apiUrl("/api/chat"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(chatPayload)
      });

      await requireSuccessfulResponse(res);

      const response = await res.json();
      const responseTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      setChatHistory(prev => [
        ...prev,
        {
          sender: "agent",
          text: response.text,
          time: responseTime
        }
      ]);

      await syncLiveState(activeUser);

      if (response.action) {
        const act = response.action;
        if (act.type === "SWITCH_DIET") {
          const textLower = response.text.toLowerCase();
          let newDiet = dietPreference;
          if (textLower.includes("keto")) newDiet = "keto";
          else if (textLower.includes("vegan")) newDiet = "vegan";
          else if (textLower.includes("high-protein") || textLower.includes("active")) newDiet = "high-protein";
          else if (textLower.includes("balanced")) newDiet = "balanced";

          setDietPreference(newDiet);
          triggerBannerAlert(`Switched dietary profile to ${DIET_TYPES[newDiet].name}!`);
        } else if (act.type === "UPDATE_PLANNER") {
          triggerBannerAlert("Planner modified by Kitch Agent!");
        } else if (act.type === "UPDATE_PANTRY") {
          triggerBannerAlert("Pantry inventory updated by Kitch Agent!");
        } else if (act.type === "UPDATE_GROCERY_CART") {
          triggerBannerAlert("Grocery cart updated by Kitch Agent!");
        }
      }
    } catch (e) {
      console.error("Real API chat processing error", e);
      const message = apiErrorMessage(
        e,
        `I was unable to reach the Kitch backend server on \`${API_BASE_URL}\`. Please make sure the FastAPI server is running.`
      );
      if (e instanceof ApiResponseError && e.isPersistenceFailure) {
        triggerBannerAlert(PERSISTENCE_FAILURE_MESSAGE);
      }
      setChatHistory(prev => [
        ...prev,
        {
          sender: "agent",
          text: `⚠️ ${message}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setIsChatTyping(false);
    }
  };

  const handleChatSubmit = (e) => {
    e.preventDefault();
    const text = chatInput.trim();

    if (pendingPhoto) {
      const photo = pendingPhoto;
      setChatInput("");
      setPendingPhoto(null);
      handleRealPhotoUpload(photo.file, photo.isFridgeScan, text);
      return;
    }

    if (text) {
      setChatInput("");
      sendChatMessage(text);
    }
  };

  // 5. Real Vision Camera scanning & upload workflow
  const handleRealPhotoUpload = async (file, isFridgeScan, accompanyingText = "") => {
    if (!file) return;

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const trimmedText = accompanyingText.trim();
    const scanLabel = isFridgeScan ? "fridge scan" : "plate photo";

    setSmartDockExpanded(true);
    setChatHistory(prev => [
      ...prev,
      {
        sender: "user",
        text: trimmedText
          ? `📷 *Attached ${scanLabel}: ${file.name}*\n\n${trimmedText}`
          : `📷 *Attached ${scanLabel}: ${file.name}*`,
        time
      }
    ]);

    // Show live scanning overlay
    setScanningOverlay({
      active: true,
      title: isFridgeScan ? "Fridge Camera Scanner (Live)" : "Culinary Plate Scanner (Live)",
      steps: [
        "🔍 Establishing connection to Kitch backend...",
        `⚡ Uploading image bytes: ${file.name}...`
      ],
      fileName: file.name
    });

    setIsChatTyping(true);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("active_user", activeUser);
      formData.append("is_fridge_scan", isFridgeScan ? "true" : "false");
      formData.append("message", trimmedText);

      setScanningOverlay(prev => ({
        ...prev,
        steps: [...prev.steps, "🧠 Running ADK multimodal vision analysis..."]
      }));

      const res = await fetch(apiUrl("/api/upload-photo"), {
        method: "POST",
        body: formData
      });

      await requireSuccessfulResponse(res);

      setScanningOverlay(prev => ({
        ...prev,
        steps: [...prev.steps, "✅ Success! Parsing OCR payload outcomes..."]
      }));

      const data = await res.json();
      
      // Refresh DB state to get OCR ingredients added to pantry or macro plates logged
      await syncLiveState(activeUser);
      
      await new Promise(r => setTimeout(r, 600));
      setScanningOverlay({ active: false, title: "", steps: [], fileName: "" });

      const responseTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      setChatHistory(prev => [
        ...prev,
        {
          sender: "agent",
          text: data.result,
          time: responseTime
        }
      ]);

      triggerBannerAlert(isFridgeScan ? "Fridge scanned successfully!" : "Plate logged successfully!");

    } catch (e) {
      console.error("Real photo upload error", e);
      setScanningOverlay({ active: false, title: "", steps: [], fileName: "" });
      const message = apiErrorMessage(
        e,
        `Failed to reach \`/api/upload-photo\` on \`${API_BASE_URL}\`. Is your FastAPI backend running?`
      );
      if (e instanceof ApiResponseError && e.isPersistenceFailure) {
        triggerBannerAlert(PERSISTENCE_FAILURE_MESSAGE);
      }
      setChatHistory(prev => [
        ...prev,
        {
          sender: "agent",
          text: `⚠️ ${message}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setIsChatTyping(false);
    }
  };

  const draftMealSwapPrompt = (day, slot) => {
    setActiveTab("planner");
    setSelectedPlannerDay(day);
    setExpandedMealKey(`${day}-${slot}`);
    setChatInput(`Change ${day} ${slot} to `);
  };

  // Daily target calorie values per person
  const targetCalories = DIET_TYPES[dietPreference].dailyCalorieTargetPerPerson;
  const dietMeta = DIET_TYPES[dietPreference];
  const targetProtein = Math.round((targetCalories * (dietMeta.targetMacros.protein / 100)) / 4);
  const targetCarbs = Math.round((targetCalories * (dietMeta.targetMacros.carbs / 100)) / 4);
  const targetFat = Math.round((targetCalories * (dietMeta.targetMacros.fat / 100)) / 9);

  // Active user's aggregated daily values
  const activeUserProfile = userProfiles[activeUser] || { name: activeUser, loggedMeals: [] };
  const loggedMeals = activeUserProfile.loggedMeals;

  let loggedCal = 0;
  let loggedProt = 0;
  let loggedCarb = 0;
  let loggedFat = 0;

  loggedMeals.forEach(meal => {
    loggedCal += meal.calories;
    loggedProt += meal.macros.protein;
    loggedCarb += meal.macros.carbs;
    loggedFat += meal.macros.fat;
  });

  const calPercentage = Math.min(100, Math.round((loggedCal / targetCalories) * 100));
  const strokeDashoffset = 471.2 - (471.2 * calPercentage) / 100;

  const protPerc = Math.min(100, Math.round((loggedProt / targetProtein) * 100));
  const carbPerc = Math.min(100, Math.round((loggedCarb / targetCarbs) * 100));
  const fatPerc = Math.min(100, Math.round((loggedFat / targetFat) * 100));

  // Items checkout checklist
  const checkoutItems = groceryList
    .filter(item => !item.alreadyStocked && !excludedZeptoItemIds.includes(cartItemKey(item)))
    .map(item => ({
      id: item.id,
      name: item.name,
      amount: Math.round(item.amount * 100) / 100,
      unit: item.unit,
      category: item.category,
      source: item.source
    }));

  const recipeCards = normalizeList(latestRecipeGroceryPlan?.recipeCards);
  const activeRecipeCard = recipeCards[0] || null;
  const activeRecipeTitle = getRecipeCardTitle(activeRecipeCard, latestRecipeGroceryPlan ? "Recipe details pending" : "");
  const activeRecipeIngredients = normalizeList(
    activeRecipeCard?.ingredients ||
    activeRecipeCard?.ingredientList ||
    activeRecipeCard?.ingredient_list ||
    latestRecipeGroceryPlan?.ingredients
  ).filter(ingredient => getIngredientName(ingredient));
  const activeRecipeSteps = getRecipeSteps(activeRecipeCard);
  const recipePlanScope = latestRecipeGroceryPlan?.scope || {};
  const recipePlanLabel = latestRecipeGroceryPlan?.scopeLabel || recipePlanScope.label || latestRecipeGroceryPlan?.request || "Latest recipe plan";
  const recipeServings = activeRecipeCard?.servings || activeRecipeCard?.serves || latestRecipeGroceryPlan?.householdSize || householdSize;
  const recipeCookTime = activeRecipeCard?.cookTime || activeRecipeCard?.cook_time || activeRecipeCard?.time || "";
  const recipeCalories = activeRecipeCard?.calories || activeRecipeCard?.caloriesPerServing || activeRecipeCard?.calories_per_serving || "";
  const recipeDescription = activeRecipeCard?.shortDescription || activeRecipeCard?.description || activeRecipeCard?.summary || latestRecipeGroceryPlan?.notes || "";
  const recipePantryNotes = normalizeList(latestRecipeGroceryPlan?.pantryConsiderations);
  const recipeLinkedCartItems = latestRecipeGroceryPlan?.id
    ? groceryList.filter(item => item.recipeGroceryPlanId === latestRecipeGroceryPlan.id || item.recipe_grocery_plan_id === latestRecipeGroceryPlan.id)
    : groceryList;
  const recipeCartItems = recipeLinkedCartItems.length > 0 || latestRecipeGroceryPlan?.updatesCart
    ? recipeLinkedCartItems
    : [];
  const recipeNeededCartItems = recipeCartItems.filter(item => !item.alreadyStocked);

  const groupedGroceryCart = groceryList.reduce((groups, item) => {
    const category = item.category || "General";
    if (!groups[category]) groups[category] = [];
    groups[category].push(item);
    return groups;
  }, {});
  const groceryCategoryCount = Object.keys(groupedGroceryCart).length;
  const stockedCount = groceryList.filter(item => item.alreadyStocked).length;
  const pendingBuyCount = checkoutItems.length;
  const eligibleBuyCount = groceryList.filter(item => !item.alreadyStocked).length;
  const zeptoStatus = zeptoCartReview?.status;
  const zeptoMatchedItems = Array.isArray(zeptoCartReview?.matched_items)
    ? zeptoCartReview.matched_items
    : Array.isArray(zeptoCartReview?.result?.items) ? zeptoCartReview.result.items : [];
  const zeptoUnavailableItems = Array.isArray(zeptoCartReview?.unavailable_items)
    ? zeptoCartReview.unavailable_items
    : Array.isArray(zeptoCartReview?.result?.unavailable_items) ? zeptoCartReview.result.unavailable_items : [];
  const zeptoCartDetails = zeptoCartReview?.zepto_cart || zeptoCartReview?.result?.zepto_cart || zeptoCartReview?.result || null;
  const zeptoCheckoutContext = zeptoCartReview?.checkout_context || zeptoCartReview?.result?.checkout_context || {};
  const zeptoSavedAddressOptions = collectObjectsWithAnyKey(zeptoSavedAddresses, ["address", "address_line", "addressLine", "id"]);
  const selectedZeptoAddressOption = zeptoSavedAddressOptions.find((option, idx) => (
    optionValue(option, ["id", "address_id", "addressId"], `address-${idx}`) === selectedZeptoAddress
  ));
  const selectedZeptoAddressDisplay = selectedZeptoAddressOption
    ? formatZeptoAddressParts(selectedZeptoAddressOption, "Selected Zepto address")
    : null;
  const zeptoPaymentOptions = collectObjectsWithAnyKey(zeptoCheckoutContext.payment_methods, ["payment", "method", "payment_method", "id"]);
  const zeptoOrderBlockers = Array.isArray(zeptoCartReview?.order_blockers) ? zeptoCartReview.order_blockers : [];
  const canPlaceZeptoOrder = zeptoCartReview?.can_place_order
    && Boolean(zeptoCartReview?.confirmation_token)
    && Boolean(zeptoCartReview?.snapshot_hash)
    && Boolean(selectedZeptoAddress)
    && zeptoOrderBlockers.length === 0
    && zeptoReviewAcknowledged
    && !isUpdatingZeptoReview;
  const zeptoState = zeptoConnectionStatus?.state || "unknown";
  const zeptoStatusLabel = zeptoCartReview?.store_context?.state === "store_context_ready"
    ? "Zepto store ready"
    : zeptoSavedAddressOptions.length > 0
      ? "Zepto connected"
      : ({
    configured: "Zepto configured",
    browser_login_required: "Browser login required",
    not_connected: "Not connected",
    disabled: "Disabled",
    failed: "Zepto sign-in needs attention",
    unknown: "Checking Zepto sign-in"
  }[zeptoState] || zeptoState);
  const zeptoStatusDescription = zeptoCartReview?.store_context?.state === "store_context_ready"
    ? "Products were resolved for the selected delivery address."
    : zeptoSavedAddressOptions.length > 0
      ? selectedZeptoAddress
        ? "Address selected. Zepto will confirm the serviceable store before searching products."
        : "Select a delivery address before moving items to Zepto."
      : ({
    configured: "Loading saved addresses to verify the Zepto connection.",
    browser_login_required: "Sign in to Zepto in the browser to continue.",
    not_connected: "Connect Zepto before moving items to cart.",
    disabled: "Zepto cart sync is not enabled right now.",
    failed: "Reconnect Zepto and try again.",
    unknown: "Checking whether Zepto is ready."
  }[zeptoState] || "");

  const plannedWeekDays = useMemo(() => (
    WEEK_DAYS.filter(day => MEAL_SLOTS.some(slot => hasMealTitle(weeklyPlan[day]?.[slot])))
  ), [weeklyPlan]);
  const hasWeeklyPlan = plannedWeekDays.length > 0;
  const activePlannerDay = hasWeeklyPlan && plannedWeekDays.includes(selectedPlannerDay)
    ? selectedPlannerDay
    : plannedWeekDays[0] || selectedPlannerDay;
  const plannedDateLabels = plannedWeekDays
    .map(day => planningWeekDates[day]?.label)
    .filter(Boolean);
  const plannerDateRangeLabel = !hasWeeklyPlan
    ? "No saved plan yet"
    : plannedDateLabels.length > 1
      ? `${plannedDateLabels[0]} - ${plannedDateLabels[plannedDateLabels.length - 1]}`
      : plannedDateLabels[0] || "Saved plan";

  const currentMealLabel = MEAL_SLOT_LABELS[currentMealSlot];
  const firstPlannedFocusMeal = plannedWeekDays.map(day => ({
    day,
    date: planningWeekDates[day] || {},
    slot: currentMealSlot,
    title: getMealTitle(weeklyPlan[day]?.[currentMealSlot], "")
  })).find(item => item.title) || plannedWeekDays.flatMap(day => (
    MEAL_SLOTS.map(slot => ({
      day,
      date: planningWeekDates[day] || {},
      slot,
      title: getMealTitle(weeklyPlan[day]?.[slot], "")
    }))
  )).find(item => item.title) || {
    day: "",
    date: {},
    slot: currentMealSlot,
    title: `Ask Kitch to plan the first household ${currentMealLabel.toLowerCase()}`
  };

  const pantryPreview = pantryStock.slice(0, 3);
  const selectedDayDate = planningWeekDates[activePlannerDay] || {};
  const selectedDayMealList = MEAL_SLOTS.map(slot => ({
    slot,
    key: `${activePlannerDay}-${slot}`,
    title: getMealTitle(weeklyPlan[activePlannerDay]?.[slot], `${MEAL_SLOT_LABELS[slot]} not set`)
  }));
  const focusMealDateText = firstPlannedFocusMeal.date.longLabel || firstPlannedFocusMeal.date.label || "Upcoming week";
  const focusMealTitle = firstPlannedFocusMeal.title;
  const focusMealSlotLabel = MEAL_SLOT_LABELS[firstPlannedFocusMeal.slot] || currentMealLabel;
  const heroGreeting = `${getTimeBasedGreeting()}, ${activeUser}!`;
  const focusMealContext = hasWeeklyPlan
    ? `${focusMealSlotLabel} for ${focusMealDateText}`
    : "No household meal plan yet";
  const nutritionSummary = loggedCal > 0
    ? `${calPercentage}% of daily target`
    : "No meals logged yet";
  const quickPrompts = [
    "Plan next week for the whole household",
    "What are we cooking tomorrow?",
    "What groceries should I order for tomorrow?"
  ];
  const hasStartedConversation = chatHistory.some(msg => msg.sender === "user");
  const visibleChatStartIndex = Math.max(0, chatHistory.length - visibleChatCount);
  const visibleChatMessages = chatHistory.slice(visibleChatStartIndex);
  const hasOlderChatMessages = visibleChatStartIndex > 0;
  const revealEarlierMessages = () => {
    setVisibleChatCount(prev => Math.min(chatHistory.length, prev + CHAT_HISTORY_BATCH_SIZE));
  };
  const handleChatScroll = (event) => {
    if (event.currentTarget.scrollTop <= 16 && hasOlderChatMessages) {
      revealEarlierMessages();
    }
  };

  return (
    <div id="app">
      {/* SVG gradients for visual nutrition dial */}
      <svg className="visually-hidden-svg" width="0" height="0">
        <defs>
          <linearGradient id="emeraldGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#34D399" />
            <stop offset="100%" stopColor="#10B981" />
          </linearGradient>
          <linearGradient id="amberGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FBBF24" />
            <stop offset="100%" stopColor="#F59E0B" />
          </linearGradient>
        </defs>
      </svg>

      {isZeptoSyncing && (
        <div className="zepto-transfer-overlay">
          <section
            ref={zeptoSyncDialogRef}
            className={`zepto-transfer-dialog stage-${zeptoSyncStage}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="zepto-transfer-title"
            aria-describedby="zepto-transfer-description"
            tabIndex={-1}
          >
            <div className="zepto-transfer-visual" aria-hidden="true">
              <svg viewBox="0 0 680 220">
                <defs>
                  <linearGradient id="transferGlow" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#eff7df" />
                    <stop offset="100%" stopColor="#fff8ec" />
                  </linearGradient>
                  <linearGradient id="bagPaper" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#e9c78b" />
                    <stop offset="100%" stopColor="#cfa45e" />
                  </linearGradient>
                  <linearGradient id="zeptoPurple" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#8c62d8" />
                    <stop offset="100%" stopColor="#573099" />
                  </linearGradient>
                </defs>
                <path className="transfer-glow" d="M90 184C130 55 260 18 366 71c89 44 141-9 223 45v68H90Z" fill="url(#transferGlow)" />
                <g className="kitch-transfer-bag">
                  <path d="M91 87h128l17 112H75L91 87Z" fill="url(#bagPaper)" />
                  <path d="M113 95c2-35 17-52 42-52s40 17 42 52" fill="none" stroke="#b98a47" strokeWidth="10" strokeLinecap="round" />
                  <circle cx="115" cy="73" r="25" fill="#76a35a" />
                  <circle cx="148" cy="65" r="31" fill="#557f45" />
                  <circle cx="183" cy="75" r="25" fill="#8aad63" />
                  <path d="M102 75c-20-31-12-52-1-57 17 9 22 29 12 57M137 57c-4-34 7-50 21-53 13 17 10 38-5 57M184 68c8-29 23-39 36-36 6 20-6 36-25 46" fill="#638b4d" />
                  <circle cx="166" cy="92" r="19" fill="#df6645" />
                  <path d="m156 75 10 8 10-8-4 12" fill="#3c713a" />
                  <path d="M126 132c18-17 38-17 56 0v34h-56v-34Z" fill="none" stroke="#69834d" strokeWidth="6" />
                  <path d="M139 145v15m14-19v19m14-15v15" stroke="#69834d" strokeWidth="4" strokeLinecap="round" />
                </g>
                <path className="transfer-dash-path" d="M245 112c72-58 130-58 196 0" fill="none" stroke="#82915b" strokeWidth="4" strokeDasharray="10 12" strokeLinecap="round" />
                <path d="m430 96 15 18-23 5" fill="none" stroke="#82915b" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
                <g className="zepto-flying-grocery">
                  <circle cx="273" cy="81" r="13" fill="#dd6543" />
                  <path d="m266 67 7 7 8-8" fill="none" stroke="#4f7f43" strokeWidth="4" />
                  <path d="M296 63c18-9 30-4 34 4-9 14-21 17-34 9Z" fill="#6d9e55" />
                </g>
                <g className="zepto-transfer-basket">
                  <path d="M460 100h150l-13 92H473l-13-92Z" fill="url(#zeptoPurple)" />
                  <path d="M483 113c8-55 94-55 103 0" fill="none" stroke="#3f246f" strokeWidth="11" strokeLinecap="round" />
                  <path d="M466 113h138" stroke="#a985ea" strokeWidth="9" strokeLinecap="round" />
                  <circle cx="493" cy="100" r="20" fill="#df6645" />
                  <path d="m485 83 8 8 9-9" fill="none" stroke="#477b3e" strokeWidth="5" />
                  <path d="M527 98c-8-27 2-43 15-47 14 15 12 34-2 51M557 101c8-30 23-39 36-34 4 18-6 33-26 42" fill="#6b9852" />
                  <text x="535" y="160" textAnchor="middle" fill="#fff" fontSize="29" fontWeight="800">zepto</text>
                </g>
                <circle className="transfer-spark spark-one" cx="334" cy="42" r="5" fill="#b8ce75" />
                <circle className="transfer-spark spark-two" cx="425" cy="55" r="4" fill="#d1df9c" />
                <path className="transfer-spark spark-three" d="m626 53 5 10 10 5-10 5-5 10-5-10-10-5 10-5Z" fill="#b8ce75" />
              </svg>
            </div>

            <div className="zepto-transfer-copy">
              <span className="zepto-transfer-kicker">Secure cart handoff</span>
              <h2 id="zepto-transfer-title">
                {zeptoSyncStage === "complete"
                  ? "Your Zepto cart is ready"
                  : zeptoSyncStage === "failed"
                    ? "The transfer needs attention"
                    : "Moving your items to Zepto…"}
              </h2>
              <p id="zepto-transfer-description">
                {zeptoSyncStage === "complete"
                  ? "The reviewed products and unavailable items are ready for you to inspect."
                  : zeptoSyncStage === "failed"
                    ? "Kitch could not complete the handoff. Your native cart was left unchanged."
                    : "We’ve paused cart editing while Zepto selects your store, matches products, and builds the review."}
              </p>
            </div>

            <div className="zepto-transfer-progress" aria-label="Zepto cart transfer progress">
              {[
                ["preparing", "Preparing your list"],
                ["transferring", "Matching Zepto items"],
                ["finalizing", "Building cart review"]
              ].map(([stage, label], index, stages) => {
                const currentIndex = stages.findIndex(([candidate]) => candidate === zeptoSyncStage);
                const isComplete = zeptoSyncStage === "complete" || currentIndex > index;
                const isActive = currentIndex === index;
                return (
                  <div key={stage} className={`zepto-transfer-step ${isComplete ? "complete" : ""} ${isActive ? "active" : ""}`}>
                    <span className="zepto-step-indicator">{isComplete ? "✓" : index + 1}</span>
                    <strong>{label}</strong>
                  </div>
                );
              })}
            </div>

            <div className="zepto-transfer-note">
              <span className="zepto-transfer-note-icon" aria-hidden="true">
                <i></i><i></i><i></i>
              </span>
              <div>
                <strong>{zeptoSyncStage === "finalizing" ? "Almost there!" : "Your cart is locked for consistency"}</strong>
                <span>
                  {checkoutItems.length} selected {checkoutItems.length === 1 ? "item is" : "items are"} being processed.
                  Please keep this window open.
                </span>
              </div>
            </div>
          </section>
        </div>
      )}

      {scanningOverlay.active && (
        <div id="vision-scanner" className="vision-scanner-overlay active">
          <div className="scanning-image-box">
            <div className="scan-laser-line"></div>
            <div className="scan-emoji">
              {scanningOverlay.fileName.includes("fridge") ? "❄️" :
               scanningOverlay.fileName.includes("salmon") ? "🐟" :
               scanningOverlay.fileName.includes("chicken") ? "🍗" :
               scanningOverlay.fileName.includes("salad") ? "🥗" : "🍓"}
            </div>
          </div>
          <h4 id="scanner-title-text" className="scanner-title">{scanningOverlay.title}</h4>
          <div id="scan-terminal-log" className="scan-log-box">
            {scanningOverlay.steps.map((step, idx) => (
              <div key={idx} className="scan-log-line">{step}</div>
            ))}
          </div>
        </div>
      )}

      <aside className="kitch-rail" aria-label="Kitch navigation">
        <div className="rail-brand">
          <div className="rail-logo-mark">
            <Image src="/kitch-chef-hat.svg" alt="" width={46} height={46} aria-hidden="true" />
          </div>
          <div>
            <h1>Kitch</h1>
            <span>AI Household</span>
          </div>
        </div>
        <nav className="rail-nav">
          {[
            ["planner", "household", "Household"],
            ["recipes", "recipes", "Recipes"],
            ["groceries", "pantry", "Groceries"],
            ["analytics", "nutrition", "Nutrition"],
            ["about", "about", "About Kitch"]
          ].map(([key, icon, label]) => (
            <button
              key={key}
              className={`rail-link ${activeTab === key ? "active" : ""}`}
              onClick={() => setActiveTab(key)}
            >
              <span className={`rail-line-icon ${icon}`} aria-hidden="true">
                {icon === "household" && (
                  <svg viewBox="0 0 24 24"><path d="M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM3.5 19c.6-3.1 2.2-5 4.5-5s3.9 1.9 4.5 5M11.5 19c.6-3.1 2.2-5 4.5-5s3.9 1.9 4.5 5"/></svg>
                )}
                {icon === "pantry" && (
                  <svg viewBox="0 0 24 24"><path d="M6 8h12l-1 12H7L6 8Zm2-4h8l2 4H6l2-4Zm2 8h4"/></svg>
                )}
                {icon === "recipes" && (
                  <svg viewBox="0 0 24 24"><path d="M6 4h10a2 2 0 0 1 2 2v14H8a2 2 0 0 1-2-2V4Zm3 4h6M9 12h6M9 16h4"/></svg>
                )}
                {icon === "nutrition" && (
                  <svg viewBox="0 0 24 24"><path d="M4 19h16M5 15l4-4 3 3 6-8M5 5v14"/></svg>
                )}
                {icon === "about" && (
                  <svg viewBox="0 0 24 24"><path d="M12 19v-8M12 7h.01M4 12a8 8 0 1 0 16 0 8 8 0 0 0-16 0Z"/></svg>
                )}
              </span>
              {label}
            </button>
          ))}
        </nav>
        <div className="rail-member-card">
          <div className="rail-member-avatar">
            {HOUSEHOLD_MEMBERS.map(member => (
              <span key={member.value}>{member.value[0]}</span>
            ))}
          </div>
          <div>
            <span>Active member</span>
            <strong>{activeUser}</strong>
          </div>
          <button type="button" aria-label="Change active member" onClick={() => setChatInput("Switch active member to ")}>
            ▾
          </button>
        </div>
      </aside>

      <div className="kitch-workspace">
        <header className="app-header">
          <div className="mobile-brand">
            <div className="logo-icon">
              <Image src="/kitch-chef-hat.svg" alt="" width={48} height={48} aria-hidden="true" />
            </div>
            <div>
              <h1>Kitch</h1>
              <span>Household assistant</span>
            </div>
          </div>
          <div className="controls-section">
            <div className="control-group">
              <label htmlFor="profile-selector">Active User</label>
              <select id="profile-selector" name="profile-selector" value={activeUser} onChange={(e) => switchActiveUser(e.target.value)}>
                {HOUSEHOLD_MEMBERS.map(member => (
                  <option key={member.value} value={member.value}>{member.label}</option>
                ))}
              </select>
            </div>
            <div className="control-group">
              <label htmlFor="diet-selector">Diet Profile</label>
              <select id="diet-selector" name="diet-selector" value={dietPreference} onChange={(e) => switchDiet(e.target.value)}>
                <option value="balanced">Balanced Diet</option>
                <option value="keto">Keto / Low-Carb</option>
                <option value="vegan">Vegan / Plant-Based</option>
                <option value="high-protein">High-Protein Active</option>
              </select>
            </div>
            <div className="control-group">
              <span className="control-label">Household Size</span>
              <div className="household-stepper" aria-label="Household size">
                <button type="button" aria-label="Decrease household size" onClick={() => updateHouseholdSize(householdSize - 1)}>−</button>
                <input
                  type="number"
                  id="household-size"
                  name="household-size"
                  min="1"
                  max="12"
                  value={householdSize}
                  onChange={(e) => updateHouseholdSize(e.target.value)}
                />
                <button type="button" aria-label="Increase household size" onClick={() => updateHouseholdSize(householdSize + 1)}>+</button>
              </div>
              <span className="control-unit-label">People</span>
            </div>
          </div>
        </header>

        <main className="page-canvas">
          {activeTab === "about" && (
            <section className="page-view about-page" aria-label="About Kitch">
              <section className="about-hero">
                <div className="about-hero-copy">
                  <span className="eyebrow">About Kitch</span>
                  <h2>Your AI kitchen companion for real life.</h2>
                  <p>Kitch helps your household plan meals, cook better, shop smarter, and track nutrition without turning the kitchen into another spreadsheet.</p>
                  <div className="about-hero-actions">
                    <button type="button" className="primary-action" onClick={() => setActiveTab("planner")}>
                      Open household plan
                    </button>
                    <button type="button" onClick={() => setChatInput("Plan next week for the whole household")}>
                      Ask Kitch to plan
                    </button>
                  </div>
                </div>
                <div className="about-hero-visual" aria-hidden="true">
                  <div className="about-blob"></div>
                  <Image src="/group_of_people.png" alt="" fill sizes="(max-width: 900px) 92vw, 50vw" priority unoptimized />
                </div>
              </section>

              <section className="about-card about-household-card">
                <div>
                  <h3>Built for real households</h3>
                  <p>Food is shared, but goals are personal. Kitch keeps household planning together and individual nutrition separate.</p>
                </div>
                <div className="about-feature-grid">
                  <article>
                    <AboutIconBadge name="people" tone="sage" />
                    <h4>Shared planning</h4>
                    <p>One meal plan for breakfast, lunch, and dinner across the whole home.</p>
                  </article>
                  <article>
                    <AboutIconBadge name="pantry" tone="green" />
                    <h4>Shared pantry</h4>
                    <p>Track what is stocked, avoid duplicate buys, and waste less.</p>
                  </article>
                  <article>
                    <AboutIconBadge name="nutrition" tone="amber" />
                    <h4>Individual nutrition</h4>
                    <p>Each member keeps their own macro diary and daily progress.</p>
                  </article>
                </div>
              </section>

              <section className="about-card about-steps-card">
                <div className="about-section-heading">
                  <h3>How Kitch works</h3>
                  <p>From planning to checkout prep, Kitch keeps every step reviewable.</p>
                </div>
                <div className="about-step-row">
                  {ABOUT_WORKFLOW_STEPS.map(({ number, icon, title, body }) => (
                    <article key={title}>
                      <AboutIconBadge name={icon} tone={ABOUT_STEP_TONES[icon]} className="about-step-icon" />
                      <div className="about-step-title">
                        <span className="about-step-number">{number}</span>
                        <h4>{title}</h4>
                      </div>
                      <p>{body}</p>
                    </article>
                  ))}
                </div>
              </section>

              <section className="about-conversation-grid">
                <article className="about-card about-chat-card">
                  <div>
                    <h3>Talk to Kitch like you talk to family</h3>
                    <p>Use natural language, share photos, scan the fridge, or ask what to cook next.</p>
                  </div>
                  <div className="about-chat-thread" aria-label="Example Kitch conversation">
                    <div className="about-chat-message assistant">
                      <AboutIconBadge name="chef" tone="orange" className="about-chat-avatar" />
                      <p>What can we cook for dinner?</p>
                    </div>
                    <div className="about-chat-message user">
                      <p>We have paneer, capsicum, and peas.</p>
                    </div>
                    <div className="about-chat-message assistant">
                      <AboutIconBadge name="chef" tone="orange" className="about-chat-avatar" />
                      <p>I can suggest recipes and add missing ingredients to your cart.</p>
                    </div>
                  </div>
                </article>

                <article className="about-card about-intelligence-card">
                  <div className="about-mini-feature">
                    <AboutIconBadge name="chat" tone="sage" className="about-mini-icon" />
                    <div>
                      <h4>Natural conversations</h4>
                      <p>Ask in your own words.</p>
                    </div>
                  </div>
                  <div className="about-mini-feature">
                    <AboutIconBadge name="brain" tone="violet" className="about-mini-icon" />
                    <div>
                      <h4>Household context</h4>
                      <p>Kitch remembers food preferences during a session.</p>
                    </div>
                  </div>
                  <div className="about-mini-feature">
                    <AboutIconBadge name="suggestions" tone="amber" className="about-mini-icon" />
                    <div>
                      <h4>Helpful suggestions</h4>
                      <p>Plans adapt to pantry, taste, and goals.</p>
                    </div>
                  </div>
                </article>
              </section>

              <section className="about-card about-control-card">
                <div className="about-control-art" aria-hidden="true">
                  <AboutIconBadge name="shield" tone="sage" className="about-control-shield" />
                  <div className="about-phone-mock">
                    <AboutIconBadge name="cart" tone="violet" className="about-phone-icon" />
                    <span>Zepto Cart</span>
                    <strong>Review before order</strong>
                    <em>Never automatic</em>
                  </div>
                </div>
                <div className="about-control-copy">
                  <h3>You are always in control</h3>
                  <ul>
                    <li>Kitch prepares your native cart.</li>
                    <li>You review and make changes.</li>
                    <li>You approve and place the order on Zepto.</li>
                  </ul>
                  <p>Kitch never places orders on your behalf from chat.</p>
                </div>
              </section>

              <section className="about-cta">
                <div>
                  <h3>Ready to make your kitchen easier?</h3>
                  <p>Plan your first meal and let Kitch handle the rest.</p>
                </div>
                <button type="button" className="primary-action" onClick={() => setChatInput("Create a balanced meal plan for next week")}>
                  Create your first meal plan →
                </button>
                <div className="about-bowl-art" aria-hidden="true">
                  <Image src="/food_bowl.png" alt="" fill sizes="(max-width: 900px) 38vw, 220px" unoptimized />
                </div>
              </section>
            </section>
          )}

          {activeTab === "planner" && (
            <section className="page-view planner-page" aria-label="Weekly meal planner">
              <section className="meal-landing-hero">
                <article className="dinner-hero-card">
                  <div className="meal-hero-copy">
                    <h2>{heroGreeting}</h2>
                    <p>{"I'm here to help you plan meals, groceries, pantry, and kitchen needs."}</p>
                    <div className="hero-meal-card">
                      <span className={`meal-time-icon ${currentMealSlot}`} aria-hidden="true"><span></span></span>
                      <div>
                        <small>{focusMealContext}</small>
                        <strong>{focusMealTitle}</strong>
                      </div>
                    </div>
                    <div className="hero-actions">
                      {hasWeeklyPlan ? (
                        <>
                          <button type="button" className="primary-action" onClick={() => setChatInput(`Show me the recipe for ${focusMealTitle}`)}>
                            View details →
                          </button>
                          <button type="button" onClick={() => draftMealSwapPrompt(firstPlannedFocusMeal.day, firstPlannedFocusMeal.slot)}>
                            Swap meal
                          </button>
                          <button type="button" onClick={() => setChatInput(`Log ${focusMealTitle} for ${activeUser}`)}>
                            Log meal
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="primary-action"
                            onClick={() => {
                              setChatInput("Plan next week for the whole household");
                              setSmartDockExpanded(true);
                            }}
                          >
                            Plan next week
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setChatInput("Help me choose meals for this household");
                              setSmartDockExpanded(true);
                            }}
                          >
                            Ask Kitch to plan
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="meal-hero-art">
                    <Image src="/countertop-cropped.png" alt="" fill sizes="(max-width: 900px) 100vw, 60vw" priority unoptimized />
                    <div className="chip-row">
                      <span>{householdSize} people</span>
                      <span>{dietMeta.name}</span>
                    </div>
                    <div className="hero-footer">
                      <div className="avatar-stack">
                        {HOUSEHOLD_MEMBERS.map(member => (
                          <span key={member.value}>{member.value[0]}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                </article>
              </section>

              <div className="planner-main-grid">
                <section className="weekly-calendar-feature">
                  <div className="section-heading">
                    <div>
                      <span className="eyebrow">Your household plan</span>
                      <h2 id="planner-household-heading">{`Weekly Plan for ${householdSize} ${householdSize === 1 ? "Person" : "People"}`}</h2>
                    </div>
                    <p>{plannerDateRangeLabel}</p>
                  </div>
                  {hasWeeklyPlan ? (
                    <div id="weekly-plan-grid" className="weekly-plan-board">
                      <div className="week-date-rail" aria-label="Select planning day">
                        {plannedWeekDays.map(day => {
                          const dateMeta = planningWeekDates[day] || {};
                          return (
                            <button
                              key={day}
                              type="button"
                              className={`week-date-card ${activePlannerDay === day ? "active" : ""}`}
                              onClick={() => {
                                setSelectedPlannerDay(day);
                                setExpandedMealKey(`${day}-${currentMealSlot}`);
                              }}
                            >
                              <span>{day.slice(0, 3)}</span>
                              <div>
                                <strong>{dateMeta.label || day}</strong>
                                <em>{activePlannerDay === day ? "Selected" : ""}</em>
                              </div>
                            </button>
                          );
                        })}
                      </div>

                      <article className="selected-week-meals">
                        <div className="selected-week-heading">
                          <div>
                            <h3>{selectedDayDate.longLabel || activePlannerDay}</h3>
                          </div>
                        </div>

                        <div className="selected-meal-list">
                          {selectedDayMealList.map(({ slot, key, title }) => (
                            <button
                              key={key}
                              type="button"
                              className={`selected-meal-row ${slot} ${expandedMealKey === key ? "active" : ""}`}
                              onClick={() => {
                                setExpandedMealKey(key);
                                setChatInput(`Show details for ${title} on ${activePlannerDay}`);
                              }}
                            >
                              <span className={`meal-time-icon ${slot}`} aria-hidden="true"><span></span></span>
                              <span>{MEAL_SLOT_LABELS[slot]}</span>
                              <strong>{title}</strong>
                              <em>+</em>
                            </button>
                          ))}
                        </div>
                      </article>
                    </div>
                  ) : (
                    <article id="weekly-plan-grid" className="planner-empty-state" aria-label="No saved household meal plan">
                      <div className="planner-empty-copy">
                        <span className="eyebrow">No plan yet</span>
                        <h3>Start with a weekly household plan.</h3>
                        <p>Planned days will appear here after Kitch creates meals for the household.</p>
                        <button
                          type="button"
                          className="planner-empty-cta"
                          onClick={() => {
                            setChatInput("Plan next week for the whole household");
                            setSmartDockExpanded(true);
                          }}
                        >
                          Plan next week
                        </button>
                      </div>
                      <div className="planner-empty-preview" aria-hidden="true">
                        <AboutIconBadge name="calendar" tone="sage" />
                        <div>
                          <span>Breakfast</span>
                          <span>Lunch</span>
                          <span>Dinner</span>
                        </div>
                      </div>
                    </article>
                  )}
                </section>

                <aside className="weekly-side-rail" aria-label="Household planning status">
                  <article className="nutrition-widget">
                    <div className="widget-title-row">
                      <h3>Your Nutrition</h3>
                      <button type="button" onClick={() => setActiveTab("analytics")} aria-label="Open nutrition logs">›</button>
                    </div>
                    <div className="nutrition-stat">
                      <div>
                        <span>Calories</span>
                        <strong>{loggedCal} <small>/ {targetCalories} kcal</small></strong>
                      </div>
                      <div className="progress-track"><div className="progress-fill protein" style={{ width: `${calPercentage}%` }}></div></div>
                    </div>
                    <div className="mini-macros">
                      <div><span>Protein ({loggedProt}g / {targetProtein}g)</span><div><b style={{ width: `${protPerc}%` }}></b></div></div>
                      <div><span>Carbs ({loggedCarb}g / {targetCarbs}g)</span><div><b style={{ width: `${carbPerc}%` }}></b></div></div>
                      <div><span>Fats ({loggedFat}g / {targetFat}g)</span><div><b style={{ width: `${fatPerc}%` }}></b></div></div>
                    </div>
                    <p>{nutritionSummary}</p>
                  </article>

                  <article className="side-status-card pantry-status-card">
                    <button type="button" onClick={() => setActiveTab("groceries")} aria-label="Open groceries">›</button>
                    <span className="side-card-icon">▣</span>
                    <h3>Pantry Update</h3>
                    {pantryPreview.length ? pantryPreview.map(item => (
                      <p key={item.name}>{item.name} <b>{item.amount} {item.unit}</b></p>
                    )) : <p>Scan the fridge to understand what is already available.</p>}
                  </article>

                  <article className="side-status-card grocery-status-card">
                    <button type="button" onClick={() => setActiveTab("groceries")} aria-label="Open grocery list">›</button>
                    <span className="side-card-icon">□</span>
                    <h3>Grocery List</h3>
                    <p><strong>{totalCount}</strong> required items</p>
                    <small>{stockedCount} already stocked, {zeptoSelectedCount} selected for Zepto</small>
                  </article>

                </aside>
              </div>
            </section>
          )}

          {activeTab === "analytics" && (
            <section className="page-view analytics-page" aria-label="Macro logs">
              <div className="section-heading page-heading">
                <div>
                  <span className="eyebrow">Personal nutrition</span>
                  <h2>Macro Logs for {activeUser}</h2>
                </div>
                <button id="clear-diary-btn" className="clear-diary-btn" onClick={resetDailyLogs}>Clear Logs</button>
              </div>
              <div className="nutrition-page-grid">
                <article className="calorie-focus-card">
                  <h3>Calories Today</h3>
                  <div className="calorie-dial">
                    <svg width="180" height="180" viewBox="0 0 180 180">
                      <circle className="calorie-dial-ring-bg" cx="90" cy="90" r="75" />
                      <circle id="calorie-dial-fill" className="calorie-dial-ring-fill" cx="90" cy="90" r="75" strokeDasharray="471.2" style={{ strokeDashoffset: strokeDashoffset }} />
                    </svg>
                    <div className="calorie-dial-info">
                      <h2 id="logged-calories-num">{loggedCal}</h2>
                      <p id="target-calories-num">/ {targetCalories} kcal</p>
                    </div>
                  </div>
                  <span id="calorie-percentage-badge" className="calorie-percentage-badge">{calPercentage}% Met</span>
                </article>
                <article className="macro-breakdown-card">
                  <h3 className="tracker-title">Macros Breakdown</h3>
                  {[
                    ["Protein", loggedProt, targetProtein, protPerc, "protein"],
                    ["Carbohydrates", loggedCarb, targetCarbs, carbPerc, "carbs"],
                    ["Fats", loggedFat, targetFat, fatPerc, "fat"]
                  ].map(([label, logged, target, percent, klass]) => (
                    <div key={label} className="macro-bar-group">
                      <div className="macro-bar-header"><span>{label} (Target: {target}g)</span><span>{logged}g</span></div>
                      <div className="progress-track"><div className={`progress-fill ${klass}`} style={{ width: `${percent}%` }}></div></div>
                    </div>
                  ))}
                </article>
                <article className="diary-section">
                  <div className="diary-header"><h3 className="diary-heading" id="diary-user-heading">Plate Logs</h3></div>
                  <div id="diary-list" className="diary-list">
                    {loggedMeals.length === 0 ? (
                      <div className="diary-empty-state">🍳 {activeUser} has not logged any plates today. Use the camera button below to scan a plate.</div>
                    ) : loggedMeals.map((meal, idx) => (
                      <div key={idx} className="diary-item">
                        <div className="diary-item-info"><h4>{meal.name}</h4><span>Log Time: {meal.time}</span></div>
                        <div className="diary-item-macros">🔥 {meal.calories} kcal<span>P: {meal.macros.protein}g | C: {meal.macros.carbs}g | F: {meal.macros.fat}g</span></div>
                      </div>
                    ))}
                  </div>
                </article>
              </div>
            </section>
          )}

          {activeTab === "recipes" && (
            <section className="page-view recipe-grocery-page" aria-label="Recipe and grocery planning">
              <button type="button" className="back-to-today-btn" onClick={() => setActiveTab("planner")}>
                ← Back to Today
              </button>

              {latestRecipeGroceryPlan ? (
                <div className="recipe-grocery-layout">
                  <section className="recipe-workspace-card">
                    <div className="recipe-hero-panel">
                      <div className="recipe-hero-copy">
                        <span className="recipe-plan-pill">{recipePlanLabel}</span>
                        <h2>{activeRecipeTitle}</h2>
                        {recipeDescription && <p>{recipeDescription}</p>}
                        <div className="recipe-stat-row">
                          {recipeCookTime && <span><b aria-hidden="true">◷</b>{recipeCookTime}</span>}
                          {recipeCalories && <span><b aria-hidden="true">▥</b>{recipeCalories} kcal</span>}
                          <span><b aria-hidden="true">♙</b>Serves {recipeServings}</span>
                        </div>
                        <div className="recipe-action-row">
                          <button
                            type="button"
                            className="recipe-primary-btn"
                            onClick={() => {
                              setChatInput(`Swap ${activeRecipeTitle} with another suitable meal`);
                              setSmartDockExpanded(false);
                            }}
                          >
                            Swap this meal
                          </button>
                          <button type="button" onClick={() => setChatInput(`Log ${activeRecipeTitle} for ${activeUser}`)}>
                            Log meal
                          </button>
                          <button type="button" aria-label="Save recipe" onClick={() => triggerBannerAlert("Recipe is already saved in Kitch history.")}>
                            ♡
                          </button>
                          <button type="button" aria-label="Share recipe" onClick={() => setChatInput(`Share the recipe for ${activeRecipeTitle}`)}>
                            ↗
                          </button>
                        </div>
                      </div>
                      <div className="recipe-hero-visual" aria-hidden="true">
                        <Image src="/countertop-cropped.png" alt="" fill sizes="(max-width: 900px) 100vw, 48vw" unoptimized />
                      </div>
                    </div>

                    <div className="recipe-detail-tabs" role="tablist" aria-label="Recipe details">
                      {[
                        ["recipe", "Recipe"],
                        ["ingredients", "Ingredients"],
                        ["nutrition", "Nutrition"],
                        ["notes", "Tips & Notes"]
                      ].map(([key, label]) => (
                        <button
                          key={key}
                          type="button"
                          className={recipeBodyTab === key ? "active" : ""}
                          onClick={() => setRecipeBodyTab(key)}
                        >
                          {label}
                        </button>
                      ))}
                    </div>

                    <div className="recipe-detail-body">
                      {recipeBodyTab === "recipe" && (
                        <>
                          <h3>How to make it</h3>
                          {activeRecipeSteps.length === 0 ? (
                            <div className="recipe-empty-note">No cooking steps were saved for this recipe yet.</div>
                          ) : (
                            <div className="recipe-step-list">
                              {activeRecipeSteps.map((step, index) => (
                                <details key={`${step.title}-${index}`} className="recipe-step-item" open={index < 4}>
                                  <summary>
                                    <span>{index + 1}</span>
                                    <strong>{step.title}</strong>
                                  </summary>
                                  {step.body && <p>{step.body}</p>}
                                </details>
                              ))}
                            </div>
                          )}
                        </>
                      )}

                      {recipeBodyTab === "ingredients" && (
                        <>
                          <h3>Ingredients</h3>
                          {activeRecipeIngredients.length === 0 ? (
                            <div className="recipe-empty-note">No structured ingredients were saved for this recipe yet.</div>
                          ) : (
                            <div className="recipe-inline-ingredient-grid">
                              {activeRecipeIngredients.map((ingredient, index) => (
                                <div key={`${getIngredientName(ingredient)}-${index}`}>
                                  <span>{getIngredientName(ingredient)}</span>
                                  <strong>{getIngredientQuantity(ingredient)}</strong>
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      )}

                      {recipeBodyTab === "nutrition" && (
                        <>
                          <h3>Nutrition</h3>
                          <div className="recipe-empty-note">
                            {recipeCalories
                              ? `${recipeCalories} kcal was saved for this recipe. Detailed macros can be logged on the Nutrition page after eating.`
                              : "Detailed recipe nutrition was not saved for this artifact."}
                          </div>
                        </>
                      )}

                      {recipeBodyTab === "notes" && (
                        <>
                          <h3>Tips & Notes</h3>
                          {recipePantryNotes.length === 0 && !latestRecipeGroceryPlan.notes ? (
                            <div className="recipe-empty-note">No pantry notes or recipe tips were saved for this plan.</div>
                          ) : (
                            <div className="recipe-note-list">
                              {latestRecipeGroceryPlan.notes && <p>{latestRecipeGroceryPlan.notes}</p>}
                              {recipePantryNotes.map((note, index) => (
                                <p key={`${note}-${index}`}>{typeof note === "string" ? note : JSON.stringify(note)}</p>
                              ))}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </section>

                  <aside className="recipe-ingredients-panel">
                    <div className="recipe-panel-tabs" role="tablist" aria-label="Ingredients and grocery list">
                      <button
                        type="button"
                        className={recipeSidebarTab === "ingredients" ? "active" : ""}
                        onClick={() => setRecipeSidebarTab("ingredients")}
                      >
                        Ingredients
                      </button>
                      <button
                        type="button"
                        className={recipeSidebarTab === "grocery" ? "active" : ""}
                        onClick={() => setRecipeSidebarTab("grocery")}
                      >
                        Grocery List <span>{recipeNeededCartItems.length}</span>
                      </button>
                    </div>

                    {recipeSidebarTab === "ingredients" ? (
                      <div className="ingredient-side-list">
                        <div className="ingredient-side-header">
                          <strong>Ingredients you need</strong>
                          <span>Serves {recipeServings}</span>
                        </div>
                        {activeRecipeIngredients.length === 0 ? (
                          <div className="recipe-empty-note">Ask Kitch for a recipe or grocery plan to populate ingredients.</div>
                        ) : activeRecipeIngredients.map((ingredient, index) => (
                          <div key={`${getIngredientName(ingredient)}-side-${index}`} className="ingredient-side-row">
                            <span className="ingredient-check" aria-hidden="true">✓</span>
                            <strong>{getIngredientName(ingredient)}</strong>
                            <em>{getIngredientQuantity(ingredient)}</em>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="ingredient-side-list">
                        <div className="ingredient-side-header grocery">
                          <div>
                            <strong>Grocery list ({recipeNeededCartItems.length} items)</strong>
                            <span>Pantry-covered items stay muted.</span>
                          </div>
                        </div>
                        {recipeCartItems.length === 0 ? (
                          <div className="recipe-empty-note">This recipe has not populated the native grocery cart yet.</div>
                        ) : recipeCartItems.map((item, index) => (
                          <div key={item.id || `${item.name}-${index}`} className={`ingredient-cart-row ${item.alreadyStocked ? "stocked" : ""}`}>
                            <span className="ingredient-cart-dot" aria-hidden="true">{item.alreadyStocked ? "✓" : ""}</span>
                            <strong>{item.name}</strong>
                            <em>{item.alreadyStocked ? "In pantry" : `${Math.round(item.amount * 100) / 100} ${item.unit}`}</em>
                          </div>
                        ))}
                      </div>
                    )}

                    <button
                      type="button"
                      className="add-all-groceries-btn"
                      onClick={() => {
                        if (recipeCartItems.length > 0) {
                          setActiveTab("groceries");
                        } else {
                          sendChatMessage(`Add groceries for ${activeRecipeTitle} to the native grocery cart`);
                        }
                      }}
                      disabled={!activeRecipeTitle && recipeCartItems.length === 0}
                    >
                      {recipeCartItems.length > 0 ? "View grocery cart" : "Add all to groceries"}
                    </button>
                  </aside>
                </div>
              ) : (
                <section className="recipe-empty-state">
                  <div>
                    <span className="eyebrow">No recipe plan yet</span>
                    <h2>Create a recipe and grocery plan</h2>
                    <p>Ask Kitch for a recipe, ingredients for a dish, or groceries for a planned meal. This page will show the latest saved recipe+grocery artifact.</p>
                    <div className="hero-actions">
                      <button type="button" className="primary-action" onClick={() => setChatInput("What groceries do I need for tomorrow?")}>
                        Plan groceries for tomorrow
                      </button>
                      <button type="button" onClick={() => setChatInput("Give me a recipe for paneer butter masala")}>
                        Ask for a recipe
                      </button>
                    </div>
                  </div>
                  <div className="recipe-empty-visual" aria-hidden="true">
                    <Image src="/countertop-cropped.png" alt="" fill sizes="(max-width: 900px) 100vw, 48vw" unoptimized />
                  </div>
                </section>
              )}
            </section>
          )}

          {activeTab === "groceries" && (
            <section className="page-view grocery-management-page" aria-label="Native grocery cart and Zepto checkout">
              <div className="grocery-management-header">
                <div>
                  <span className="eyebrow">Grocery Management</span>
                  <h2>Native cart review</h2>
                  <p>Review Kitch’s household cart before moving eligible items to Zepto.</p>
                </div>
                <div className="grocery-header-actions">
                  <button type="button" disabled={isZeptoSyncing} onClick={() => setActiveTab("recipes")}>Import from recipe</button>
                  <button type="button" disabled={isZeptoSyncing} onClick={() => setChatInput("Add groceries for tomorrow to the native grocery cart")}>Ask Kitch</button>
                </div>
              </div>

              <div className="grocery-execution-layout">
                <section className="native-cart-panel">
                  <div className="cart-tabs-row">
                    <button type="button" className="active">My List <span>{totalCount}</span></button>
                    <button type="button">Pantry <span>{pantryStock.length}</span></button>
                    <button type="button" disabled>Buy Again</button>
                    <button type="button" disabled>Past Orders</button>
                  </div>

                  <div className="native-cart-meta">
                    <strong>{totalCount} items</strong>
                    <span>{groceryCategoryCount} categories</span>
                    <span>{zeptoSelectedCount} selected for Zepto</span>
                  </div>

                  {totalCount === 0 ? (
                    <div className="native-cart-empty">
                      <strong>Your native grocery cart is empty.</strong>
                      <p>Ask Kitch to plan groceries from a recipe or add a custom household item.</p>
                      <button type="button" onClick={() => setActiveTab("recipes")}>Open Recipes</button>
                    </div>
                  ) : (
                    <div className="native-cart-groups">
                      {Object.entries(groupedGroceryCart).map(([category, items]) => (
                        <article key={category} className="native-cart-group">
                          <div className="native-cart-group-header">
                            <h3>{category} <span>({items.length})</span></h3>
                            <div>
                              <span>Add to Zepto</span>
                              <span>Needed</span>
                              <span>Have</span>
                              <span>To buy</span>
                            </div>
                          </div>

                          {items.map((item, index) => {
                            const itemAmount = Number(item.amount) || 1;
                            const haveText = item.alreadyStocked ? formatCartQuantity(item.amount, item.unit) : "0";
                            const toBuyText = item.alreadyStocked ? "—" : formatCartQuantity(item.amount, item.unit);
                            const selectedForZepto = !item.alreadyStocked && !excludedZeptoItemIds.includes(cartItemKey(item));
                            return (
                              <div key={item.id || `${item.name}-${index}`} className={`native-cart-row ${!selectedForZepto ? "excluded" : ""} ${item.alreadyStocked ? "stocked" : ""}`}>
                                <label className="native-cart-check">
                                  <input
                                    type="checkbox"
                                    aria-label={`Add ${item.name} to Zepto`}
                                    checked={selectedForZepto}
                                    disabled={item.alreadyStocked || isZeptoSyncing}
                                    onChange={() => toggleZeptoItemSelection(item)}
                                  />
                                </label>
                                <div className="native-cart-name">
                                  <strong>{item.name}</strong>
                                  <span>{item.source === "manual" ? "Manual" : "Recipe planned"}{item.stockNote ? ` · ${item.stockNote}` : ""}</span>
                                </div>
                                <div className="native-cart-quantity">
                                  <button type="button" disabled={isZeptoSyncing} onClick={() => updateGroceryCartItemDetails(item, { amount: Math.max(0.1, itemAmount - 1) })}>−</button>
                                  <input
                                    aria-label={`Quantity for ${item.name}`}
                                    type="number"
                                    min="0.1"
                                    step="0.1"
                                    value={item.amount}
                                    disabled={isZeptoSyncing}
                                    onChange={(e) => {
                                      const nextAmount = parseFloat(e.target.value) || 1;
                                      setCustomGroceryItems(prev => prev.map(current => current.id === item.id ? { ...current, amount: nextAmount } : current));
                                    }}
                                    onBlur={(e) => updateGroceryCartItemDetails(item, { amount: parseFloat(e.target.value) || 1 })}
                                  />
                                  <button type="button" disabled={isZeptoSyncing} onClick={() => updateGroceryCartItemDetails(item, { amount: itemAmount + 1 })}>+</button>
                                  <input
                                    aria-label={`Unit for ${item.name}`}
                                    type="text"
                                    value={item.unit || ""}
                                    disabled={isZeptoSyncing}
                                    onChange={(e) => setCustomGroceryItems(prev => prev.map(current => current.id === item.id ? { ...current, unit: e.target.value } : current))}
                                    onBlur={(e) => updateGroceryCartItemDetails(item, { unit: e.target.value || "piece" })}
                                  />
                                </div>
                                <span className="native-cart-have">{haveText}</span>
                                <span className="native-cart-buy">{toBuyText}</span>
                                <div className="native-cart-actions">
                                  <button type="button" disabled={isZeptoSyncing} aria-label={`Delete ${item.name}`} onClick={() => deleteGroceryCartItem(item)}>×</button>
                                </div>
                              </div>
                            );
                          })}
                        </article>
                      ))}
                    </div>
                  )}

                  <div className="cart-add-row">
                    <input type="text" disabled={isZeptoSyncing} placeholder="Add custom item..." value={groceryCustomName} onChange={(e) => setGroceryCustomName(e.target.value)} />
                    <input type="number" disabled={isZeptoSyncing} min="0.1" step="0.1" value={groceryCustomAmount} onChange={(e) => setGroceryCustomAmount(parseFloat(e.target.value) || 1)} />
                    <input type="text" disabled={isZeptoSyncing} value={groceryCustomUnit} onChange={(e) => setGroceryCustomUnit(e.target.value)} />
                    <select disabled={isZeptoSyncing} value={groceryCustomCat} onChange={(e) => setGroceryCustomCat(e.target.value)}>
                      <option value="Fresh Produce">Fresh Produce</option>
                      <option value="Proteins & Dairy">Proteins & Dairy</option>
                      <option value="Grains & Bakery">Grains & Bakery</option>
                      <option value="Pantry & Spices">Pantry & Spices</option>
                      <option value="General">General</option>
                    </select>
                    <button type="button" disabled={isZeptoSyncing} onClick={() => addCustomGroceryItem(groceryCustomName, groceryCustomCat, groceryCustomAmount, groceryCustomUnit)}>Add item</button>
                  </div>
                </section>

                <aside className="grocery-execution-sidebar">
                  <article className="grocery-side-card list-summary-card">
                    <h3>List summary</h3>
                    <p><strong>{totalCount}</strong> items</p>
                    <div className="summary-total-row">
                      <span>Est. total</span>
                      <strong>{zeptoCartReview ? "From Zepto response" : "Not synced"}</strong>
                    </div>
                    <small>Prices, fees, and availability appear only after Zepto MCP sync.</small>
                  </article>

                  <article className="grocery-side-card missing-card">
                    <h3>Missing from pantry</h3>
                    <p><strong>{eligibleBuyCount}</strong> items to buy</p>
                    <small>{pendingBuyCount} selected for Zepto. {stockedCount} rows are already stocked or pantry-covered.</small>
                  </article>

                  <article className="grocery-side-card zepto-move-card">
                    <div className="zepto-card-title">
                      <span>Move to Zepto</span>
                      <strong>zepto</strong>
                    </div>
                    <div className={`zepto-connection-state ${zeptoState}`}>
                      <b>{zeptoStatusLabel}</b>
                      <span>{zeptoStatusDescription}</span>
                    </div>
                    <label className="zepto-sync-address">
                      <span>Delivery address</span>
                      <select
                        aria-label="Zepto delivery address for cart sync"
                        value={selectedZeptoAddress}
                        disabled={isZeptoSyncing || isZeptoAddressLoading || zeptoSavedAddressOptions.length === 0}
                        onChange={(e) => selectZeptoSyncAddress(e.target.value)}
                      >
                        <option value="">
                          {isZeptoAddressLoading ? "Loading Zepto addresses..." : "Select delivery address"}
                        </option>
                        {zeptoSavedAddressOptions.map((option, idx) => {
                          const value = optionValue(option, ["id", "address_id", "addressId"], `address-${idx}`);
                          const address = formatZeptoAddressParts(option, `Address ${idx + 1}`);
                          return (
                            <option key={`${value}-${idx}`} value={value}>
                              {address.detail ? `${address.title} — ${address.detail}` : address.title}
                            </option>
                          );
                        })}
                      </select>
                      {zeptoAddressLoadError && (
                        <small className="zepto-address-error">{zeptoAddressLoadError}</small>
                      )}
                    </label>
                    <button
                      type="button"
                      onClick={syncNativeCartToZepto}
                      disabled={isZeptoSyncing || groceryMutationCount > 0 || checkoutItems.length === 0 || !selectedZeptoAddress}
                    >
                      {groceryMutationCount > 0 ? "Saving native cart…" : isZeptoSyncing ? "Moving to Zepto…" : "Move to Zepto cart"}
                    </button>
                  </article>

                  <article className="grocery-side-card quick-actions-card">
                    <h3>Quick actions</h3>
                    <button type="button" disabled={isZeptoSyncing} onClick={() => setCustomGroceryItems(prev => [...prev].sort((a, b) => (a.category || "").localeCompare(b.category || "")))}>Sort by category</button>
                    <button type="button" disabled={isZeptoSyncing} onClick={() => setExcludedZeptoItemIds([])}>Select all for Zepto</button>
                    <button type="button" disabled={isZeptoSyncing} onClick={() => setExcludedZeptoItemIds(groceryList.filter(item => !item.alreadyStocked).map(cartItemKey).filter(Boolean))}>Clear Zepto selection</button>
                    <button type="button" disabled={isZeptoSyncing} onClick={clearPlannedGroceryRows}>Clear planned rows</button>
                  </article>
                </aside>
              </div>

              <section className="zepto-review-workflow" aria-label="Zepto cart review and approval">
                <div className="workflow-step-row">
                  <span className="active">1 Native cart</span>
                  <span className={zeptoCartReview ? "active" : ""}>2 Zepto cart</span>
                  <span className={zeptoCartReview?.can_place_order ? "active" : ""}>3 Order review</span>
                  <span className={canPlaceZeptoOrder ? "active" : ""}>4 Confirm order</span>
                </div>

                {!zeptoCartReview ? (
                  <div className="zepto-review-empty">
                    <strong>No Zepto cart review yet.</strong>
                    <p>Move eligible native cart rows to Zepto to review cart items, unavailable items, address/payment state, and the final approval button.</p>
                  </div>
                ) : (
                  <div className="zepto-review-grid">
                    <article className={`zepto-review-status ${zeptoStatus === "success" ? "success" : "error"}`}>
                      <div>
                        <span className="eyebrow">Zepto cart</span>
                        <h3>{zeptoStatus === "success" ? "Cart ready for review" : "Sync needs attention"}</h3>
                        <p>{zeptoCartReview.message || "Review the latest Zepto cart result."}</p>
                      </div>
                      <div className="zepto-review-stats">
                        <div><strong>{zeptoMatchedItems.length}</strong><span>In cart</span></div>
                        <div><strong>{zeptoUnavailableItems.length}</strong><span>Unavailable</span></div>
                      </div>
                    </article>

                    <article className="zepto-review-list zepto-cart-list">
                      <h3>Zepto Cart</h3>
                      {zeptoMatchedItems.length === 0 ? (
                        <p>No Zepto cart items were added yet.</p>
                      ) : zeptoMatchedItems.map((match, idx) => {
                        const product = match.matched_product || {};
                        const native = match.native_item || {};
                        const productMeta = getZeptoProductMeta(match);
                        return (
                          <div key={`${native.id || native.name || idx}-zepto-match`} className="zepto-product-row">
                            <div className="zepto-product-main">
                              <strong>{product.name || product.title || product.product_name || match.cart_item?.name || "Zepto cart item"}</strong>
                              <span>{native.name ? `From Kitch item: ${native.name}` : "Added to Zepto cart"}</span>
                            </div>
                            {productMeta.length > 0 && (
                              <dl className="zepto-product-meta">
                                {productMeta.map(([label, value]) => (
                                  <div key={`${native.id || native.name || idx}-${label}`}>
                                    <dt>{label}</dt>
                                    <dd>{value}</dd>
                                  </div>
                                ))}
                              </dl>
                            )}
                          </div>
                        );
                      })}
                    </article>

                    <article className="zepto-review-list zepto-unavailable-panel">
                      <h3>Unavailable or unresolved</h3>
                      <div className="zepto-unavailable-content">
                        {zeptoUnavailableItems.length === 0 ? (
                          <p>No unavailable items reported by Zepto.</p>
                        ) : zeptoUnavailableItems.map((item, idx) => (
                          <div key={`${item.name || idx}-zepto-unavailable`} className="zepto-product-row unavailable">
                            <strong>{item.name || "Unknown item"}</strong>
                            <span>{item.reason || "Zepto did not return a usable match."}</span>
                          </div>
                        ))}
                      </div>
                    </article>

                    <article className="zepto-approval-card">
                      <div className="zepto-approval-heading">
                        <h3>Address and payment</h3>
                        <p>This reviewed cart is locked to the address used for product availability.</p>
                      </div>
                      {selectedZeptoAddressDisplay ? (
                        <div className="zepto-locked-address">
                          <strong>{selectedZeptoAddressDisplay.title}</strong>
                          {selectedZeptoAddressDisplay.detail && <span>{selectedZeptoAddressDisplay.detail}</span>}
                          <small>Choose a different address above and sync again to change stores.</small>
                        </div>
                      ) : (
                        <p className="zepto-address-empty">The reviewed cart has no confirmed delivery address. Sync again after selecting one.</p>
                      )}

                      <div className="zepto-payment-control">
                        {zeptoPaymentOptions.length > 0 ? (
                          <label>
                            Payment
                            <select
                              value={selectedZeptoPaymentMethod}
                              onChange={(e) => {
                                const value = e.target.value;
                                setSelectedZeptoPaymentMethod(value);
                                updateZeptoReview({ selected_payment_method_id: value || null });
                              }}
                            >
                              <option value="">Use Zepto default</option>
                              {zeptoPaymentOptions.map((option, idx) => {
                                const value = optionValue(option, ["id", "payment_method_id", "paymentMethodId", "method"], `payment-${idx}`);
                                const label = optionValue(option, ["label", "name", "payment_method", "paymentMethod", "method", "title"], JSON.stringify(option).slice(0, 90));
                                return <option key={`${value}-${idx}`} value={value}>{label}</option>;
                              })}
                            </select>
                          </label>
                        ) : (
                          <p>Zepto did not expose selectable payment options. Kitch will use the current/default Zepto account payment method if you confirm.</p>
                        )}
                      </div>

                      <label className="approval-checkbox">
                        <input
                          type="checkbox"
                          checked={zeptoReviewAcknowledged}
                          onChange={(e) => {
                            const checked = e.target.checked;
                            setZeptoReviewAcknowledged(checked);
                            updateZeptoReview({ order_review_acknowledged: checked });
                          }}
                        />
                        I reviewed the exact Zepto cart, address/payment state, and unavailable items.
                      </label>

                      {zeptoOrderBlockers.length > 0 && (
                        <div className="zepto-blocker-list">
                          <strong>Order blocked</strong>
                          {zeptoOrderBlockers.map((blocker, idx) => (
                            <span key={`${blocker}-${idx}`}>{blocker}</span>
                          ))}
                        </div>
                      )}

                      <button type="button" className="confirm-order-btn" onClick={placeZeptoOrder} disabled={!canPlaceZeptoOrder || isPlacingZeptoOrder}>
                        {isPlacingZeptoOrder ? "Confirming..." : "Confirm Order"}
                      </button>
                      <small>This button is the only path that can call Zepto order placement.</small>
                    </article>

                    <details className="zepto-raw-response">
                      <summary>Zepto MCP cart response</summary>
                      <pre>{JSON.stringify(zeptoCartDetails, null, 2)}</pre>
                    </details>
                  </div>
                )}
              </section>
            </section>
          )}
        </main>
      </div>

      <form id="chat-input-form" className={`smart-input-dock ${smartDockExpanded ? "expanded" : ""}`} onSubmit={handleChatSubmit}>
        <div className="smart-chat-thread" aria-live="polite">
          <div className="smart-chat-header">
            <button type="button" aria-label="Close chat panel" onClick={() => setSmartDockExpanded(false)}>×</button>
          </div>
          <div className="smart-chat-messages" ref={chatMessagesRef} onScroll={handleChatScroll}>
            {hasOlderChatMessages && (
              <button type="button" className="load-earlier-chat" onClick={revealEarlierMessages}>
                Show earlier messages
              </button>
            )}
            {visibleChatMessages.map((msg, index) => (
              <div key={`${visibleChatStartIndex + index}-${msg.sender}-${msg.time}`} className={`smart-chat-bubble ${msg.sender}`}>
                <div className="message-markdown">
                  {renderMarkdownContent(msg.text)}
                </div>
                <span className="msg-time">{msg.time}</span>
              </div>
            ))}
            {isChatTyping && (
              <div className="smart-chat-bubble agent typing-bubble">
                <div className="typing-dots"><span></span><span></span><span></span></div>
              </div>
            )}
          </div>
        </div>
        {!hasStartedConversation && (
          <div className="quick-prompt-row">
            {quickPrompts.map(prompt => (
              <button key={prompt} type="button" onClick={() => setChatInput(prompt)}>
                {prompt}
              </button>
            ))}
          </div>
        )}
        <div className="smart-input-shell">
          <span className="smart-prompt-mark" aria-hidden="true">
            <span></span>
          </span>
          {pendingPhoto && (
            <div className="pending-attachment-chip">
              <span className="pending-attachment-preview" aria-hidden="true">
                {pendingPhoto.isFridgeScan ? "📷" : "🖼️"}
              </span>
              <div>
                <span>{pendingPhoto.isFridgeScan ? "Fridge scan" : "Plate photo"}</span>
                <strong>{pendingPhoto.file.name}</strong>
              </div>
              <button type="button" aria-label="Remove selected image" onClick={clearPendingPhoto}>×</button>
            </div>
          )}
          <input
            type="text"
            id="chat-user-input"
            name="chat-user-input"
            placeholder={pendingPhoto ? "Add context for this image..." : "Ask Kitch to plan, log, or add items..."}
            autoComplete="off"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
          />
          <button
            type="button"
            className={`chat-expand-btn ${smartDockExpanded ? "active" : ""}`}
            aria-label={smartDockExpanded ? "Collapse conversation" : "Expand conversation"}
            onClick={() => setSmartDockExpanded(prev => !prev)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M5 7.5a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v5.5a3 3 0 0 1-3 3h-4l-4 3v-3a3 3 0 0 1-3-3V7.5Z" />
              <path d="M9 9h6" />
              <path d="M9 12h4" />
            </svg>
          </button>
          <label className="input-icon-btn" aria-label="Attach plate image">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <rect x="4" y="5" width="16" height="14" rx="2" />
              <circle cx="9" cy="10" r="1.5" />
              <path d="m5 17 5-5 4 4 2-2 3 3" />
            </svg>
            <input
              name="plate-image-upload"
              type="file"
              accept="image/*"
              className="hidden-file-input"
              onChange={(e) => {
                stagePhotoForInput(e.target.files[0], false);
                e.target.value = "";
              }}
            />
          </label>
          <label className="input-icon-btn" aria-label="Attach fridge scan image">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M7 7.5 8.4 5h7.2L17 7.5h2a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9.5a2 2 0 0 1 2-2h2Z" />
              <circle cx="12" cy="13" r="3.25" />
            </svg>
            <input
              name="camera-fridge-upload"
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden-file-input"
              onChange={(e) => {
                stagePhotoForInput(e.target.files[0], true);
                e.target.value = "";
              }}
            />
          </label>
          <button type="submit" className="smart-send-btn" disabled={isChatTyping || (!chatInput.trim() && !pendingPhoto)}>↑</button>
        </div>
      </form>

      {/* DYNAMIC ALERT BANNER */}
      {alertBanner.show && (
        <div className="ai-banner-alert show">
          <span>✨ Agent Sync: {alertBanner.text}</span>
        </div>
      )}
    </div>
  );
}
