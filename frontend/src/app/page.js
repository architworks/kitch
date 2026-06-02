"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import Image from "next/image";
import { DIET_TYPES } from "./mockData.js";
import {
  DEFAULT_ACTIVE_USER,
  DEFAULT_HOUSEHOLD_SIZE,
  HOUSEHOLD_MEMBERS,
  MEAL_SLOTS,
  WEEK_DAYS,
  createEmptyPlanningWeekDates,
  createEmptyWeeklyPlan,
  createUserProfiles,
  getUpcomingPlanningWeekDates
} from "./householdConfig.js";

const MEAL_SLOT_LABELS = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  dinner: "Dinner"
};

const DEFAULT_MEAL_SLOT = "breakfast";
const INITIAL_VISIBLE_CHAT_COUNT = 6;
const CHAT_HISTORY_BATCH_SIZE = 6;

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

const cartItemKey = (item) => String(item?.id || item?.name || "");

const INITIAL_CHAT = [];

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
  const [weeklyPlan, setWeeklyPlan] = useState(createEmptyWeeklyPlan);
  const [chatHistory, setChatHistory] = useState([...INITIAL_CHAT]);
  const [visibleChatCount, setVisibleChatCount] = useState(INITIAL_VISIBLE_CHAT_COUNT);
  const chatMessagesRef = useRef(null);
  const [customGroceryItems, setCustomGroceryItems] = useState([]);
  const [latestRecipeGroceryPlan, setLatestRecipeGroceryPlan] = useState(null);
  const [planningWeekDates, setPlanningWeekDates] = useState(createEmptyPlanningWeekDates);

  // UI state variables
  const [chatInput, setChatInput] = useState("");
  const [isChatTyping, setIsChatTyping] = useState(false);
  const [smartDockExpanded, setSmartDockExpanded] = useState(false);
  const [pendingPhoto, setPendingPhoto] = useState(null);
  const [zeptoCartReview, setZeptoCartReview] = useState(null);
  const [zeptoConnectionStatus, setZeptoConnectionStatus] = useState(null);
  const [selectedZeptoAddress, setSelectedZeptoAddress] = useState("");
  const [selectedZeptoPaymentMethod, setSelectedZeptoPaymentMethod] = useState("");
  const [zeptoReviewAcknowledged, setZeptoReviewAcknowledged] = useState(false);
  const [isUpdatingZeptoReview, setIsUpdatingZeptoReview] = useState(false);
  const [excludedZeptoItemIds, setExcludedZeptoItemIds] = useState([]);
  const [isZeptoSyncing, setIsZeptoSyncing] = useState(false);
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

  const applyLiveState = (userName, data) => {
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
    if (data.weekly_plan) {
      setWeeklyPlan(data.weekly_plan);
    }
    if (data.grocery_cart) {
      setCustomGroceryItems(data.grocery_cart);
    }
  };

  const fetchLiveState = async (userName) => {
    const res = await fetch(apiUrl(`/api/state/${userName}`));
    if (!res.ok) {
      throw new Error(`State sync failed with status ${res.status}`);
    }
    return res.json();
  };

  const syncLatestRecipeGroceryPlan = async () => {
    try {
      const res = await fetch(apiUrl("/api/recipe-grocery/plans/latest"));
      if (!res.ok) {
        throw new Error(`Recipe sync failed with status ${res.status}`);
      }
      const data = await res.json();
      setLatestRecipeGroceryPlan(data.plan || null);
      return data.plan || null;
    } catch (e) {
      console.error("Failed to sync latest recipe+grocery plan", e);
      return null;
    }
  };

  const syncZeptoStatus = async () => {
    try {
      const res = await fetch(apiUrl("/api/grocery/zepto/status"));
      if (!res.ok) {
        throw new Error(`Zepto status failed with status ${res.status}`);
      }
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
  }, [activeUser]);

  useEffect(() => {
    if (activeTab !== "groceries") return undefined;
    const timer = window.setTimeout(() => {
      syncZeptoStatus();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activeTab]);

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

  const switchDiet = (dietType) => {
    if (DIET_TYPES[dietType]) {
      setDietPreference(dietType);
      triggerBannerAlert(`Switched dietary profile to ${DIET_TYPES[dietType].name}!`);
    }
  };

  const updateHouseholdSize = (size) => {
    const val = Math.max(1, parseInt(size) || 1);
    setHouseholdSize(val);
  };

  const switchActiveUser = (userName) => {
    setActiveUser(userName);
    triggerBannerAlert(`Switched active profile to ${userName}. Viewing macro logs for ${userName}.`);
  };

  const toggleZeptoItemSelection = (item) => {
    if (!item || item.alreadyStocked) return;
    const key = cartItemKey(item);
    if (!key) return;
    setExcludedZeptoItemIds(prev => (
      prev.includes(key)
        ? prev.filter(id => id !== key)
        : [...prev, key]
    ));
  };

  const updateGroceryCartItemDetails = async (item, updates) => {
    if (!item) return;

    setCustomGroceryItems(prev => prev.map(current => (
      current.id === item.id
        ? { ...current, ...updates }
        : current
    )));

    if (!item.id) return;

    try {
      const res = await fetch(apiUrl(`/api/grocery/cart/items/${item.id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates)
      });
      if (res.ok) {
        const data = await res.json();
        if (data.grocery_cart) {
          setCustomGroceryItems(data.grocery_cart);
        }
      }
    } catch (e) {
      console.error("Failed to update grocery cart item", e);
    }
  };

  const deleteGroceryCartItem = async (item) => {
    if (!item) return;

    setCustomGroceryItems(prev => prev.filter(current => current.id !== item.id));
    if (!item.id) return;

    try {
      const res = await fetch(apiUrl(`/api/grocery/cart/items/${item.id}`), {
        method: "DELETE"
      });
      if (res.ok) {
        const data = await res.json();
        if (data.grocery_cart) {
          setCustomGroceryItems(data.grocery_cart);
        }
      }
    } catch (e) {
      console.error("Failed to delete grocery cart item", e);
    }
  };

  const clearPlannedGroceryRows = async () => {
    try {
      const res = await fetch(apiUrl("/api/grocery/cart/planned"), {
        method: "DELETE"
      });
      if (res.ok) {
        const data = await res.json();
        if (data.grocery_cart) {
          setCustomGroceryItems(data.grocery_cart);
        }
      }
      triggerBannerAlert("Cleared recipe-planned grocery rows.");
    } catch (e) {
      console.error("Failed to clear planned grocery rows", e);
      triggerBannerAlert("Could not clear planned grocery rows.");
    }
  };

  const addCustomGroceryItem = async (name, category, amount = 1, unit = "piece") => {
    if (!name.trim()) return;

    const optimisticItem = {
      id: `pending-${Date.now()}`,
      name: name.trim(),
      amount: parseFloat(amount) || 1,
      unit: unit || "piece",
      category,
      source: "manual",
      checked: false,
      alreadyStocked: false,
      stockNote: ""
    };

    setCustomGroceryItems(prev => [...prev, optimisticItem]);
    setGroceryCustomName("");
    setGroceryCustomAmount(1);
    setGroceryCustomUnit("piece");
    triggerBannerAlert(`Added custom item: "${name}" to ${category}!`);

    try {
      const res = await fetch(apiUrl("/api/grocery/cart/items"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(optimisticItem)
      });
      if (res.ok) {
        const data = await res.json();
        if (data.grocery_cart) {
          setCustomGroceryItems(data.grocery_cart);
        }
      }
    } catch (e) {
      console.error("Failed to add grocery cart item", e);
    }
  };

  const syncNativeCartToZepto = async () => {
    if (checkoutItems.length === 0) {
      triggerBannerAlert("Select at least one native cart item for Zepto.");
      return;
    }

    setIsZeptoSyncing(true);
    setZeptoCartReview(null);
    try {
      const res = await fetch(apiUrl("/api/grocery/zepto/sync-cart"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cart_item_ids: checkoutItems.map(item => item.id).filter(Boolean) })
      });
      const data = await res.json();
      const review = data.review || data;
      setZeptoCartReview(review);
      setSelectedZeptoAddress(review.selected_address_id || "");
      setSelectedZeptoPaymentMethod(review.selected_payment_method_id || "");
      setZeptoReviewAcknowledged(Boolean(review.order_review_acknowledged));
      triggerBannerAlert(data.status === "success" ? "Zepto cart sync completed for review." : "Zepto cart sync needs attention.");
    } catch (e) {
      console.error("Failed to sync Zepto cart", e);
      setZeptoCartReview({
        status: "error",
        message: "Failed to contact the backend Zepto cart sync endpoint.",
        matched_items: [],
        unavailable_items: []
      });
    } finally {
      setIsZeptoSyncing(false);
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
      const data = await res.json();
      if (res.ok && data.review) {
        setZeptoCartReview(data.review);
        setSelectedZeptoAddress(data.review.selected_address_id || "");
        setSelectedZeptoPaymentMethod(data.review.selected_payment_method_id || "");
        setZeptoReviewAcknowledged(Boolean(data.review.order_review_acknowledged));
        return data.review;
      }
    } catch (e) {
      console.error("Failed to update Zepto review", e);
      triggerBannerAlert("Could not update Zepto review selection.");
    } finally {
      setIsUpdatingZeptoReview(false);
    }
    return null;
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
        selected_address_id: selectedZeptoAddress || null,
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
      const data = await res.json();
      setZeptoCartReview(data.review || data);
      triggerBannerAlert(data.status === "success" ? "Zepto order placement request completed." : "Zepto order could not be placed.");
    } catch (e) {
      console.error("Failed to place Zepto order", e);
      triggerBannerAlert("Failed to contact the backend Zepto order endpoint.");
    } finally {
      setIsPlacingZeptoOrder(false);
    }
  };

  const logMeal = (name, calories, protein, carbs, fat, fiber) => {
    const meal = {
      name,
      calories,
      macros: { protein, carbs, fat, fiber },
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setUserProfiles(prev => {
      const current = prev[activeUser] || { name: activeUser, loggedMeals: [] };
      const updatedMeals = [...current.loggedMeals, meal];
      return {
        ...prev,
        [activeUser]: { ...current, loggedMeals: updatedMeals }
      };
    });
  };

  const resetDailyLogs = async () => {
    setUserProfiles(prev => {
      const current = prev[activeUser] || { name: activeUser, loggedMeals: [] };
      return {
        ...prev,
        [activeUser]: { ...current, loggedMeals: [] }
      };
    });
    triggerBannerAlert(`Cleared today's plate logs for ${activeUser}.`);

    try {
      await fetch(apiUrl(`/api/diary/clear/${activeUser}`), {
        method: "POST"
      });
    } catch (e) {
      console.error("Failed to clear macro logs in DB", e);
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

      if (!res.ok) {
        throw new Error(`Server returned status ${res.status}`);
      }

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
      setChatHistory(prev => [
        ...prev,
        {
          sender: "agent",
          text: `⚠️ **Connection Error:** I was unable to reach the Kitch backend server on \`${API_BASE_URL}\`. Please make sure the FastAPI server is running!`,
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

      if (!res.ok) {
        throw new Error(`Server returned status ${res.status}`);
      }

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
      
      setChatHistory(prev => [
        ...prev,
        {
          sender: "agent",
          text: `⚠️ **Upload Connection Error:** Failed to reach \`/api/upload-photo\` on \`${API_BASE_URL}\`. Is your FastAPI backend running?`,
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
  const zeptoAddressOptions = collectObjectsWithAnyKey(zeptoCheckoutContext.addresses, ["address", "address_line", "addressLine", "id"]);
  const zeptoPaymentOptions = collectObjectsWithAnyKey(zeptoCheckoutContext.payment_methods, ["payment", "method", "payment_method", "id"]);
  const zeptoOrderBlockers = Array.isArray(zeptoCartReview?.order_blockers) ? zeptoCartReview.order_blockers : [];
  const canPlaceZeptoOrder = zeptoCartReview?.can_place_order
    && Boolean(zeptoCartReview?.confirmation_token)
    && Boolean(zeptoCartReview?.snapshot_hash)
    && zeptoOrderBlockers.length === 0
    && zeptoReviewAcknowledged
    && !isUpdatingZeptoReview;
  const zeptoState = zeptoConnectionStatus?.state || "unknown";
  const zeptoStatusLabel = {
    configured: "Configured",
    oauth_bridge_ready: "OAuth bridge ready",
    browser_login_required: "Browser login required",
    not_connected: "Not connected",
    disabled: "Disabled",
    failed: "Failed",
    unknown: "Unknown"
  }[zeptoState] || zeptoState;

  const currentMealLabel = MEAL_SLOT_LABELS[currentMealSlot];
  const firstPlannedFocusMeal = WEEK_DAYS.map(day => ({
    day,
    date: planningWeekDates[day] || {},
    slot: currentMealSlot,
    title: getMealTitle(weeklyPlan[day]?.[currentMealSlot], "")
  })).find(item => item.title) || {
    day: "Monday",
    date: planningWeekDates.Monday || {},
    slot: currentMealSlot,
    title: `Ask Kitch to plan the first household ${currentMealLabel.toLowerCase()}`
  };

  const pantryPreview = pantryStock.slice(0, 3);
  const selectedDayDate = planningWeekDates[selectedPlannerDay] || {};
  const selectedDayMealList = MEAL_SLOTS.map(slot => ({
    slot,
    key: `${selectedPlannerDay}-${slot}`,
    title: getMealTitle(weeklyPlan[selectedPlannerDay]?.[slot], `${MEAL_SLOT_LABELS[slot]} not set`)
  }));
  const focusMealDateText = firstPlannedFocusMeal.date.longLabel || firstPlannedFocusMeal.date.label || "Upcoming week";
  const focusMealTitle = firstPlannedFocusMeal.title;
  const heroGreeting = `${getTimeBasedGreeting()}, ${activeUser}!`;
  const focusMealContext = `${currentMealLabel} for ${focusMealDateText}`;
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
            ["analytics", "nutrition", "Nutrition"]
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
                      <button type="button" className="primary-action" onClick={() => setChatInput(`Show me the recipe for ${focusMealTitle}`)}>
                        View details →
                      </button>
                      <button type="button" onClick={() => draftMealSwapPrompt(firstPlannedFocusMeal.day, currentMealSlot)}>
                        Swap meal
                      </button>
                      <button type="button" onClick={() => setChatInput(`Log ${focusMealTitle} for ${activeUser}`)}>
                        Log meal
                      </button>
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
                    <p>{planningWeekDates.Monday?.label && planningWeekDates.Sunday?.label ? `${planningWeekDates.Monday.label} - ${planningWeekDates.Sunday.label}` : "Upcoming Monday - Sunday"}</p>
                  </div>
                  <div id="weekly-plan-grid" className="weekly-plan-board">
                    <div className="week-date-rail" aria-label="Select planning day">
                      {WEEK_DAYS.map(day => {
                        const dateMeta = planningWeekDates[day] || {};
                        return (
                          <button
                            key={day}
                            type="button"
                            className={`week-date-card ${selectedPlannerDay === day ? "active" : ""}`}
                            onClick={() => {
                              setSelectedPlannerDay(day);
                              setExpandedMealKey(`${day}-${currentMealSlot}`);
                            }}
                          >
                            <span>{day.slice(0, 3)}</span>
                            <div>
                              <strong>{dateMeta.label || "Soon"}</strong>
                              <em>{selectedPlannerDay === day ? "Selected" : ""}</em>
                            </div>
                          </button>
                        );
                      })}
                    </div>

                    <article className="selected-week-meals">
                      <div className="selected-week-heading">
                        <div>
                          <h3>{selectedDayDate.longLabel || selectedPlannerDay}</h3>
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
                              setChatInput(`Show details for ${title} on ${selectedPlannerDay}`);
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
                  <button type="button" onClick={() => setActiveTab("recipes")}>Import from recipe</button>
                  <button type="button" onClick={() => setChatInput("Add groceries for tomorrow to the native grocery cart")}>Ask Kitch</button>
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
                                    disabled={item.alreadyStocked}
                                    onChange={() => toggleZeptoItemSelection(item)}
                                  />
                                </label>
                                <div className="native-cart-name">
                                  <strong>{item.name}</strong>
                                  <span>{item.source === "manual" ? "Manual" : "Recipe planned"}{item.stockNote ? ` · ${item.stockNote}` : ""}</span>
                                </div>
                                <div className="native-cart-quantity">
                                  <button type="button" onClick={() => updateGroceryCartItemDetails(item, { amount: Math.max(0.1, itemAmount - 1) })}>−</button>
                                  <input
                                    aria-label={`Quantity for ${item.name}`}
                                    type="number"
                                    min="0.1"
                                    step="0.1"
                                    value={item.amount}
                                    onChange={(e) => {
                                      const nextAmount = parseFloat(e.target.value) || 1;
                                      setCustomGroceryItems(prev => prev.map(current => current.id === item.id ? { ...current, amount: nextAmount } : current));
                                    }}
                                    onBlur={(e) => updateGroceryCartItemDetails(item, { amount: parseFloat(e.target.value) || 1 })}
                                  />
                                  <button type="button" onClick={() => updateGroceryCartItemDetails(item, { amount: itemAmount + 1 })}>+</button>
                                  <input
                                    aria-label={`Unit for ${item.name}`}
                                    type="text"
                                    value={item.unit || ""}
                                    onChange={(e) => setCustomGroceryItems(prev => prev.map(current => current.id === item.id ? { ...current, unit: e.target.value } : current))}
                                    onBlur={(e) => updateGroceryCartItemDetails(item, { unit: e.target.value || "piece" })}
                                  />
                                </div>
                                <span className="native-cart-have">{haveText}</span>
                                <span className="native-cart-buy">{toBuyText}</span>
                                <div className="native-cart-actions">
                                  <button type="button" aria-label={`Delete ${item.name}`} onClick={() => deleteGroceryCartItem(item)}>×</button>
                                </div>
                              </div>
                            );
                          })}
                        </article>
                      ))}
                    </div>
                  )}

                  <div className="cart-add-row">
                    <input type="text" placeholder="Add custom item..." value={groceryCustomName} onChange={(e) => setGroceryCustomName(e.target.value)} />
                    <input type="number" min="0.1" step="0.1" value={groceryCustomAmount} onChange={(e) => setGroceryCustomAmount(parseFloat(e.target.value) || 1)} />
                    <input type="text" value={groceryCustomUnit} onChange={(e) => setGroceryCustomUnit(e.target.value)} />
                    <select value={groceryCustomCat} onChange={(e) => setGroceryCustomCat(e.target.value)}>
                      <option value="Fresh Produce">Fresh Produce</option>
                      <option value="Proteins & Dairy">Proteins & Dairy</option>
                      <option value="Grains & Bakery">Grains & Bakery</option>
                      <option value="Pantry & Spices">Pantry & Spices</option>
                      <option value="General">General</option>
                    </select>
                    <button type="button" onClick={() => addCustomGroceryItem(groceryCustomName, groceryCustomCat, groceryCustomAmount, groceryCustomUnit)}>Add item</button>
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
                      <span>{zeptoConnectionStatus?.message || "Zepto status has not been checked yet."}</span>
                    </div>
                    {zeptoConnectionStatus?.setup_command && (
                      <code>{zeptoConnectionStatus.setup_command}</code>
                    )}
                    <ul>
                      <li>Instant delivery depends on live Zepto availability.</li>
                      <li>Native cart rows stay as Kitch’s source of truth.</li>
                      <li>Sync replaces the current Zepto cart.</li>
                    </ul>
                    <button type="button" onClick={syncNativeCartToZepto} disabled={isZeptoSyncing || checkoutItems.length === 0}>
                      {isZeptoSyncing ? "Moving to Zepto..." : "Move to Zepto cart"}
                    </button>
                    <small>Browser login may open on first Zepto MCP use.</small>
                  </article>

                  <article className="grocery-side-card quick-actions-card">
                    <h3>Quick actions</h3>
                    <button type="button" onClick={() => setCustomGroceryItems(prev => [...prev].sort((a, b) => (a.category || "").localeCompare(b.category || "")))}>Sort by category</button>
                    <button type="button" onClick={() => setExcludedZeptoItemIds([])}>Select all for Zepto</button>
                    <button type="button" onClick={() => setExcludedZeptoItemIds(groceryList.filter(item => !item.alreadyStocked).map(cartItemKey).filter(Boolean))}>Clear Zepto selection</button>
                    <button type="button" onClick={clearPlannedGroceryRows}>Clear planned rows</button>
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
                    <p>Move eligible native cart rows to Zepto to see matched products, unavailable items, address/payment state, and the final approval button.</p>
                  </div>
                ) : (
                  <div className="zepto-review-grid">
                    <article className={`zepto-review-status ${zeptoStatus === "success" ? "success" : "error"}`}>
                      <span className="eyebrow">Zepto cart</span>
                      <h3>{zeptoStatus === "success" ? "Cart ready for review" : "Sync needs attention"}</h3>
                      <p>{zeptoCartReview.message || "Review the latest Zepto MCP result."}</p>
                      <div className="zepto-review-stats">
                        <div><strong>{zeptoMatchedItems.length}</strong><span>Matched</span></div>
                        <div><strong>{zeptoUnavailableItems.length}</strong><span>Unavailable</span></div>
                      </div>
                    </article>

                    <article className="zepto-review-list">
                      <h3>Matched products</h3>
                      {zeptoMatchedItems.length === 0 ? (
                        <p>No Zepto products were matched yet.</p>
                      ) : zeptoMatchedItems.map((match, idx) => {
                        const product = match.matched_product || {};
                        const native = match.native_item || {};
                        return (
                          <div key={`${native.id || native.name || idx}-zepto-match`} className="zepto-product-row">
                            <span>{native.name || "Native row"}</span>
                            <strong>{product.name || product.title || product.product_name || "Matched Zepto product"}</strong>
                          </div>
                        );
                      })}
                    </article>

                    <article className="zepto-review-list">
                      <h3>Unavailable or unresolved</h3>
                      {zeptoUnavailableItems.length === 0 ? (
                        <p>No unavailable items reported by Zepto MCP.</p>
                      ) : zeptoUnavailableItems.map((item, idx) => (
                        <div key={`${item.name || idx}-zepto-unavailable`} className="zepto-product-row unavailable">
                          <strong>{item.name || "Unknown item"}</strong>
                          <span>{item.reason || "Zepto did not return a usable match."}</span>
                        </div>
                      ))}
                    </article>

                    <article className="zepto-approval-card">
                      <h3>Address and payment</h3>
                      {zeptoAddressOptions.length > 0 ? (
                        <label>
                          Address
                          <select
                            value={selectedZeptoAddress}
                            onChange={(e) => {
                              const value = e.target.value;
                              setSelectedZeptoAddress(value);
                              updateZeptoReview({ selected_address_id: value || null });
                            }}
                          >
                            <option value="">Use Zepto default</option>
                            {zeptoAddressOptions.map((option, idx) => {
                              const value = optionValue(option, ["id", "address_id", "addressId"], `address-${idx}`);
                              const label = optionValue(option, ["label", "name", "address", "address_line", "addressLine", "title"], JSON.stringify(option).slice(0, 90));
                              return <option key={`${value}-${idx}`} value={value}>{label}</option>;
                            })}
                          </select>
                        </label>
                      ) : (
                        <p>Zepto MCP did not expose selectable address options. Kitch will use the current/default Zepto account address if you confirm.</p>
                      )}

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
                        <p>Zepto MCP did not expose selectable payment options. Kitch will use the current/default Zepto account payment method if you confirm.</p>
                      )}

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
                  {msg.text.split("\n").slice(0, 6).map((line, lidx) => {
                    const boldRegex = /\*\*(.*?)\*\*/g;
                    const parts = line.split(boldRegex);
                    return (
                      <p key={lidx}>
                        {parts.map((part, pidx) => pidx % 2 === 1 ? <strong key={pidx}>{part}</strong> : part)}
                      </p>
                    );
                  })}
                </div>
                <span>{msg.time}</span>
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
