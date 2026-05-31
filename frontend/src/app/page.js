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

const INITIAL_CHAT = [];

export default function Home() {
  // Application core state variables
  const [activeTab, setActiveTab] = useState("planner"); // planner, analytics, groceries
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
  const [planningWeekDates, setPlanningWeekDates] = useState(createEmptyPlanningWeekDates);

  // UI state variables
  const [chatInput, setChatInput] = useState("");
  const [isChatTyping, setIsChatTyping] = useState(false);
  const [smartDockExpanded, setSmartDockExpanded] = useState(false);
  const [pendingPhoto, setPendingPhoto] = useState(null);
  const [mcpModalOpen, setMcpModalOpen] = useState(false);
  const [zeptoCartReview, setZeptoCartReview] = useState(null);
  const [isZeptoSyncing, setIsZeptoSyncing] = useState(false);
  const [isPlacingZeptoOrder, setIsPlacingZeptoOrder] = useState(false);
  const [alertBanner, setAlertBanner] = useState({ show: false, text: "" });
  const [scanningOverlay, setScanningOverlay] = useState({
    active: false,
    title: "",
    steps: [],
    fileName: ""
  });

  // Custom ingredient add inputs
  const [groceryCustomName, setGroceryCustomName] = useState("");
  const [groceryCustomCat, setGroceryCustomCat] = useState("Fresh Produce");

  // Pantry add inputs
  const [pantryAddName, setPantryAddName] = useState("");
  const [pantryAddAmount, setPantryAddAmount] = useState(1);
  const [pantryAddUnit, setPantryAddUnit] = useState("piece");

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

  const syncLiveState = async (userName) => {
    try {
      const data = await fetchLiveState(userName);
      applyLiveState(userName, data);
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
  const checkedCount = groceryList.filter(item => item.checked).length;
  const stockedCount = groceryList.filter(item => item.alreadyStocked).length;

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

  const addPantryItem = async (name, amount, unit = "piece") => {
    if (!name.trim()) return;
    const key = name.toLowerCase().trim();
    
    setPantryStock(prev => {
      const updated = [...prev];
      const existing = updated.find(i => i.name.toLowerCase() === key);
      
      if (existing) {
        existing.amount += parseFloat(amount) || 1;
      } else {
        updated.push({
          name: name.trim(),
          amount: parseFloat(amount) || 1,
          unit
        });
      }
      return updated;
    });

    try {
      await fetch(apiUrl("/api/pantry/add"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_name: activeUser,
          name: name.trim(),
          amount: parseFloat(amount) || 1,
          unit
        })
      });
    } catch (e) {
      console.error("Failed to add pantry item to DB", e);
    }
  };

  const removePantryItem = async (idx) => {
    const item = pantryStock[idx];
    if (!item) return;

    setPantryStock(prev => {
      const updated = [...prev];
      updated.splice(idx, 1);
      return updated;
    });

    try {
      await fetch(apiUrl(`/api/pantry/remove/${activeUser}/${encodeURIComponent(item.name)}`), {
        method: "DELETE"
      });
    } catch (e) {
      console.error("Failed to remove pantry item from DB", e);
    }
  };

  const toggleGroceryItem = async (item) => {
    if (!item || item.alreadyStocked) return;
    const nextChecked = !item.checked;

    setCustomGroceryItems(prev => prev.map(current => (
      current.id === item.id || current.name === item.name
        ? { ...current, checked: nextChecked }
        : current
    )));

    if (!item.id) return;

    try {
      const res = await fetch(apiUrl(`/api/grocery/cart/items/${item.id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ checked: nextChecked })
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

  const addCustomGroceryItem = async (name, category) => {
    if (!name.trim()) return;

    const optimisticItem = {
      id: `pending-${Date.now()}`,
      name: name.trim(),
      amount: 1,
      unit: "piece",
      category,
      source: "manual",
      checked: false,
      alreadyStocked: false,
      stockNote: ""
    };

    setCustomGroceryItems(prev => [...prev, optimisticItem]);
    setGroceryCustomName("");
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
      triggerBannerAlert("Your native grocery cart has no pending items for Zepto.");
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
      setZeptoCartReview(data);
      setMcpModalOpen(true);
      triggerBannerAlert(data.status === "success" ? "Zepto cart sync completed for review." : "Zepto cart sync needs attention.");
    } catch (e) {
      console.error("Failed to sync Zepto cart", e);
      setZeptoCartReview({
        status: "error",
        result: {
          code: "frontend_sync_failed",
          message: "Failed to contact the backend Zepto cart sync endpoint."
        }
      });
      setMcpModalOpen(true);
    } finally {
      setIsZeptoSyncing(false);
    }
  };

  const placeZeptoOrder = async () => {
    if (!zeptoCartReview?.confirmation_token) {
      triggerBannerAlert("Final Zepto approval token is missing. Sync the cart again before placing the order.");
      return;
    }

    setIsPlacingZeptoOrder(true);
    try {
      const res = await fetch(apiUrl("/api/grocery/zepto/place-order"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation_token: zeptoCartReview.confirmation_token })
      });
      const data = await res.json();
      setZeptoCartReview(data);
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

  // Consolidated group category calculator
  const groupedGroceries = useMemo(() => {
    const grouped = {};
    groceryList.forEach(item => {
      if (!grouped[item.category]) {
        grouped[item.category] = [];
      }
      grouped[item.category].push(item);
    });
    return grouped;
  }, [groceryList]);

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
    .filter(item => !item.checked && !item.alreadyStocked)
    .map(item => ({
      id: item.id,
      name: item.name,
      amount: Math.round(item.amount * 100) / 100,
      unit: item.unit,
      category: item.category,
      source: item.source
    }));

  const zeptoResult = zeptoCartReview?.result || {};
  const zeptoStatus = zeptoCartReview?.status || zeptoResult.status;
  const zeptoMatchedItems = Array.isArray(zeptoResult.items) ? zeptoResult.items : [];
  const zeptoUnavailableItems = Array.isArray(zeptoResult.unavailable_items) ? zeptoResult.unavailable_items : [];
  const zeptoCartDetails = zeptoResult.zepto_cart || zeptoResult.order_result || zeptoResult;
  const canPlaceZeptoOrder = zeptoStatus === "success" && zeptoMatchedItems.length > 0 && Boolean(zeptoCartReview?.confirmation_token);

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
            ["groceries", "pantry", "Pantry"],
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
                    <small>{checkedCount} already stocked or marked complete</small>
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

          {activeTab === "groceries" && (
            <section className="page-view groceries-page" aria-label="Grocery cart">
              <div className="section-heading page-heading">
                <div>
                  <span className="eyebrow">Shared household cart</span>
                  <h2>Grocery Cart</h2>
                </div>
                <button
                  className="grocery-checkout-btn"
                  onClick={syncNativeCartToZepto}
                  disabled={isZeptoSyncing || checkoutItems.length === 0}
                >
                  {isZeptoSyncing ? "Syncing Zepto..." : "Add to Zepto Cart"}
                </button>
              </div>
              <div className="grocery-page-grid">
                <section className="grocery-list-container">
                  {totalCount === 0 ? (
                    <div className="diary-empty-state">🛒 Your shopping cart is empty. Ask Kitch what groceries to order for tomorrow.</div>
                  ) : Object.keys(groupedGroceries).map(category => (
                    <div key={category} className="grocery-category">
                      <div className="grocery-category-title">{category}</div>
                      {groupedGroceries[category].map((item, idx) => (
                        <div key={item.id || `${category}-${idx}`} className={`grocery-item-row ${item.checked ? "completed" : ""} ${item.alreadyStocked ? "stocked" : ""}`}>
                          <label className="grocery-checkbox-label">
                            <input type="checkbox" name={`grocery-${idx}`} checked={item.checked} disabled={item.alreadyStocked} onChange={() => toggleGroceryItem(item)} />
                            <span className="item-name">
                              {item.name}
                              {item.source === "manual" && <small>Manual</small>}
                              {item.alreadyStocked && item.stockNote && <small>{item.stockNote}</small>}
                            </span>
                          </label>
                          <span className={item.alreadyStocked ? "stocked-badge" : "grocery-item-qty"}>{item.alreadyStocked ? "Met (Pantry)" : `${Math.round(item.amount * 100) / 100} ${item.unit}`}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </section>
                <section className="pantry-card">
                  <div><h3 className="section-title section-title-sage">Pantry Stock</h3><p className="section-note">Stock levels subtract from your cart required totals.</p></div>
                  <div className="pantry-add-box">
                    <h4>Quick Add Fridge Stock</h4>
                    <input id="pantry-item-name" name="pantry-item-name" type="text" placeholder="Item name..." value={pantryAddName} onChange={(e) => setPantryAddName(e.target.value)} />
                    <div className="pantry-amount-row">
                      <input id="pantry-item-qty" name="pantry-item-qty" type="number" placeholder="Qty" value={pantryAddAmount} min="0.1" step="0.1" onChange={(e) => setPantryAddAmount(parseFloat(e.target.value) || 1)} />
                      <input id="pantry-item-unit" name="pantry-item-unit" type="text" placeholder="Unit" value={pantryAddUnit} onChange={(e) => setPantryAddUnit(e.target.value)} />
                    </div>
                    <button onClick={() => { addPantryItem(pantryAddName, pantryAddAmount, pantryAddUnit); triggerBannerAlert(`Manually added ${pantryAddAmount} ${pantryAddUnit} of "${pantryAddName}" to Fridge Stock.`); setPantryAddName(""); }}>Add Stock</button>
                  </div>
                  <div className="pantry-list">
                    {pantryStock.length === 0 ? <div className="diary-empty-state diary-empty-state-compact">❄️ Fridge inventory is empty. Use the camera button below to scan it.</div> : pantryStock.map((pantryItem, idx) => (
                      <div key={idx} className="pantry-item-row">
                        <div className="pantry-item-row-info"><strong>{pantryItem.name}</strong><span>{pantryItem.amount} {pantryItem.unit} available</span></div>
                        <button className="pantry-item-delete" onClick={() => { removePantryItem(idx); triggerBannerAlert(`Removed "${pantryItem.name}" from your fridge inventory.`); }}>&times;</button>
                      </div>
                    ))}
                  </div>
                </section>
                <aside className="grocery-summary-sidebar">
                  <div className="grocery-add-form">
                    <h4>Add Custom Cart Item</h4>
                    <input id="custom-grocery-name" name="custom-grocery-name" type="text" placeholder="E.g. Sparkling water, napkins..." value={groceryCustomName} onChange={(e) => setGroceryCustomName(e.target.value)} />
                    <select id="custom-grocery-category" name="custom-grocery-category" value={groceryCustomCat} onChange={(e) => setGroceryCustomCat(e.target.value)}>
                      <option value="Fresh Produce">Fresh Produce</option>
                      <option value="Proteins & Dairy">Proteins & Dairy</option>
                      <option value="Grains & Bakery">Grains & Bakery</option>
                      <option value="Pantry & Spices">Pantry & Spices</option>
                    </select>
                    <button className="grocery-add-btn" onClick={() => addCustomGroceryItem(groceryCustomName, groceryCustomCat)}>Add to Cart</button>
                  </div>
                  <hr className="soft-divider" />
                  <div className="grocery-summary-stats">
                    <div><span>Total rows:</span><strong>{totalCount}</strong></div>
                    <div><span>Ready for Zepto:</span><strong>{checkoutItems.length}</strong></div>
                    <div><span>Covered by pantry:</span><strong>{stockedCount}</strong></div>
                    <div><span>Checked off:</span><strong>{checkedCount}</strong></div>
                  </div>
                </aside>
              </div>
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

      {/* ZEPTO CART REVIEW DIALOG */}
      {mcpModalOpen && (
        <div id="mcp-modal" className="modal-overlay active">
          <div className="modal-box">
            <div className="modal-header">
              <h3>
                Zepto Cart Review
              </h3>
              <button className="modal-close-btn" onClick={() => setMcpModalOpen(false)}>&times;</button>
            </div>
            <div className="modal-body">
              <p className="modal-note">
                Kitch keeps the native grocery cart as the source of truth. Zepto sync replaces the Zepto cart with unchecked, non-stocked items only.
              </p>

              {!zeptoCartReview ? (
                <div className="zepto-empty-review">
                  <strong>No Zepto cart sync has run yet.</strong>
                  <span>Use Add to Zepto Cart from the grocery page after Kitch has planned groceries.</span>
                </div>
              ) : (
                <div className={`zepto-review-card ${zeptoStatus === "success" ? "success" : "error"}`}>
                  <div>
                    <span className="eyebrow">Provider status</span>
                    <h4>{zeptoStatus === "success" ? "Cart synced" : "Sync needs attention"}</h4>
                    <p>{zeptoResult.message || zeptoResult.result?.message || "Review the latest provider response below."}</p>
                  </div>
                  <div className="zepto-review-stats">
                    <div><strong>{zeptoMatchedItems.length}</strong><span>Matched</span></div>
                    <div><strong>{zeptoUnavailableItems.length}</strong><span>Unavailable</span></div>
                  </div>
                </div>
              )}

              {zeptoMatchedItems.length > 0 && (
                <div className="zepto-match-list">
                  <h4>Matched items</h4>
                  {zeptoMatchedItems.map((match, idx) => {
                    const product = match.matched_product || {};
                    const native = match.native_item || {};
                    return (
                      <div key={`${native.id || native.name || idx}-matched`} className="zepto-match-row">
                        <span>{native.name || "Cart item"}</span>
                        <strong>{product.name || product.title || product.product_name || "Matched Zepto product"}</strong>
                      </div>
                    );
                  })}
                </div>
              )}

              {zeptoUnavailableItems.length > 0 && (
                <div className="zepto-unavailable-list">
                  <h4>Unavailable items</h4>
                  {zeptoUnavailableItems.map((item, idx) => (
                    <div key={`${item.name || idx}-unavailable`} className="zepto-unavailable-row">
                      <strong>{item.name || "Unknown item"}</strong>
                      <span>{item.reason || "Zepto did not return a usable match."}</span>
                    </div>
                  ))}
                </div>
              )}

              {zeptoCartReview ? (
                <div className="payload-preview">
                  <span>Zepto MCP cart response</span>
                  <pre>{JSON.stringify(zeptoCartDetails, null, 2)}</pre>
                </div>
              ) : (
                <div className="payload-preview">
                  <span>Native cart rows pending Zepto sync</span>
                  <pre>{JSON.stringify(checkoutItems, null, 2)}</pre>
                </div>
              )}
              
              <div className="modal-actions">
                <button
                  id="mcp-reject-btn"
                  className="modal-reject"
                  onClick={() => {
                    setMcpModalOpen(false);
                    triggerBannerAlert("Zepto cart review closed.");
                  }}
                >
                  Close
                </button>
                <button
                  id="mcp-approve-btn"
                  className="modal-approve"
                  disabled={!canPlaceZeptoOrder || isPlacingZeptoOrder}
                  onClick={placeZeptoOrder}
                >
                  {isPlacingZeptoOrder ? "Placing..." : "Place Zepto Order"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* DYNAMIC ALERT BANNER */}
      {alertBanner.show && (
        <div className="ai-banner-alert show">
          <span>✨ Agent Sync: {alertBanner.text}</span>
        </div>
      )}
    </div>
  );
}
