"use client";

import React, { useState, useEffect, useMemo } from "react";
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

const getMealTitle = (meal, fallback = "No recipe set") => {
  if (!meal) return fallback;
  if (typeof meal === "string") return meal || fallback;
  return meal.name || meal.title || meal.recipe_name || fallback;
};

const getMealIngredients = (meal) => {
  if (!meal || typeof meal === "string") return [];
  if (Array.isArray(meal.ingredients)) return meal.ingredients;
  if (Array.isArray(meal.ingredient_list)) return meal.ingredient_list;
  if (Array.isArray(meal.recipe?.ingredients)) return meal.recipe.ingredients;
  return [];
};

// Default welcome messaging
const INITIAL_CHAT = [
  {
    sender: "agent",
    text: `👋 **Welcome back to Kitch!** I am your GenAI Culinary Companion.\n\nI am synced to your **${DEFAULT_HOUSEHOLD_SIZE}-person household**. \n\n✨ **Live Capabilities Active:**\n1. **Individual Macro Logs:** Select your active user in the header. We track macros separately for each housemate in Supabase!\n2. **Shared Pantry:** Click **Scan Fridge** to upload a photo, or type *'We have 6 eggs'* to update the household inventory.\n3. **Grocery Prep:** Ask me to compile the grocery list. Blinkit MCP cart insertion is intentionally pending until the provider connection is configured.`,
    time: "09:00 AM"
  }
];

export default function Home() {
  // Application core state variables
  const [activeTab, setActiveTab] = useState("planner"); // planner, analytics, groceries
  const [selectedPlannerDay, setSelectedPlannerDay] = useState("Monday");
  const [expandedMealKey, setExpandedMealKey] = useState("Monday-dinner");
  const [dietPreference, setDietPreference] = useState("balanced");
  const [householdSize, setHouseholdSize] = useState(DEFAULT_HOUSEHOLD_SIZE);
  const [activeUser, setActiveUser] = useState(DEFAULT_ACTIVE_USER);
  const [userProfiles, setUserProfiles] = useState(createUserProfiles);
  const [pantryStock, setPantryStock] = useState([]);
  const [weeklyPlan, setWeeklyPlan] = useState(createEmptyWeeklyPlan);
  const [chatHistory, setChatHistory] = useState([...INITIAL_CHAT]);
  const [customGroceryItems, setCustomGroceryItems] = useState([]);
  const [planningWeekDates, setPlanningWeekDates] = useState(createEmptyPlanningWeekDates);

  // UI state variables
  const [chatInput, setChatInput] = useState("");
  const [isChatTyping, setIsChatTyping] = useState(false);
  const [smartDockExpanded, setSmartDockExpanded] = useState(false);
  const [mcpModalOpen, setMcpModalOpen] = useState(false);
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
  };

  const fetchLiveState = async (userName) => {
    const res = await fetch(`http://localhost:8000/api/state/${userName}`);
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
      await fetch("http://localhost:8000/api/pantry/add", {
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
      await fetch(`http://localhost:8000/api/pantry/remove/${activeUser}/${encodeURIComponent(item.name)}`, {
        method: "DELETE"
      });
    } catch (e) {
      console.error("Failed to remove pantry item from DB", e);
    }
  };

  const toggleGroceryItem = (itemName) => {
    const key = itemName.toLowerCase().trim();
    
    // Check if it is a manual custom item
    const customIdx = customGroceryItems.findIndex(i => i.name.toLowerCase() === key);
    if (customIdx > -1) {
      const updated = [...customGroceryItems];
      updated[customIdx] = { ...updated[customIdx], checked: !updated[customIdx].checked };
      setCustomGroceryItems(updated);
    }
  };

  const addCustomGroceryItem = (name, category) => {
    if (name.trim()) {
      setCustomGroceryItems(prev => [
        ...prev,
        {
          name: name.trim(),
          amount: 1,
          unit: "piece",
          category,
          checked: false,
          alreadyStocked: false
        }
      ]);
      setGroceryCustomName("");
      triggerBannerAlert(`Added custom item: "${name}" to ${category}!`);
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
      await fetch(`http://localhost:8000/api/diary/clear/${activeUser}`, {
        method: "POST"
      });
    } catch (e) {
      console.error("Failed to clear macro logs in DB", e);
    }
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

      const res = await fetch("http://localhost:8000/api/chat", {
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
        }
      }
    } catch (e) {
      console.error("Real API chat processing error", e);
      setChatHistory(prev => [
        ...prev,
        {
          sender: "agent",
          text: "⚠️ **Connection Error:** I was unable to reach the Kitch backend server on `http://localhost:8000`. Please make sure the FastAPI server is running!",
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setIsChatTyping(false);
    }
  };

  const handleChatSubmit = (e) => {
    e.preventDefault();
    if (chatInput.trim()) {
      const text = chatInput;
      setChatInput("");
      sendChatMessage(text);
    }
  };

  // 5. Real Vision Camera scanning & upload workflow
  const handleRealPhotoUpload = async (file, isFridgeScan) => {
    if (!file) return;

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setChatHistory(prev => [
      ...prev,
      {
        sender: "user",
        text: `📷 *Uploaded photo: ${file.name}*`,
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

      setScanningOverlay(prev => ({
        ...prev,
        steps: [...prev.steps, "🧠 Running ADK multimodal vision analysis..."]
      }));

      const res = await fetch("http://localhost:8000/api/upload-photo", {
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
          text: "⚠️ **Upload Connection Error:** Failed to reach `/api/upload-photo` on `http://localhost:8000`. Is your FastAPI backend running?",
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
  const checkoutItems = useMemo(() => {
    return groceryList
      .filter(item => !item.checked)
      .map(item => ({
        name: item.name,
        amount: Math.round(item.amount * 100) / 100,
        unit: item.unit
      }));
  }, [groceryList]);

  const firstPlannedDinner = WEEK_DAYS.map(day => ({
    day,
    date: planningWeekDates[day] || {},
    dinner: getMealTitle(weeklyPlan[day]?.dinner, "")
  })).find(item => item.dinner) || {
    day: "Monday",
    date: planningWeekDates.Monday || {},
    dinner: "Ask Kitch to plan the first household dinner"
  };

  const tomorrowDay = WEEK_DAYS[1];
  const tomorrowDinner = getMealTitle(weeklyPlan[tomorrowDay]?.dinner, "No dinner selected yet");
  const selectedDayMeals = weeklyPlan[selectedPlannerDay] || {};
  const selectedDayDate = planningWeekDates[selectedPlannerDay] || {};
  const selectedDayMealList = MEAL_SLOTS.map(slot => ({
    slot,
    key: `${selectedPlannerDay}-${slot}`,
    meal: selectedDayMeals[slot],
    title: getMealTitle(selectedDayMeals[slot]),
    ingredients: getMealIngredients(selectedDayMeals[slot])
  }));
  const selectedDayDinner = selectedDayMealList.find(item => item.slot === "dinner");
  const pantryPreview = pantryStock.slice(0, 3);
  const recentActivity = [
    `${activeUser} is viewing personal macro logs`,
    weeklyPlan.Monday?.dinner ? "Weekly plan is ready for the household" : "Weekly plan is waiting for Kitch",
    pantryStock.length ? `${pantryStock.length} pantry items available` : "Pantry has not been scanned yet"
  ];
  const quickPrompts = [
    "Plan next week for the whole household",
    "What are we cooking tomorrow?",
    "What groceries should I order for tomorrow?",
    "Log what I just ate"
  ];
  const hasStartedConversation = chatHistory.some(msg => msg.sender === "user");

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
          <div className="rail-logo-mark" aria-hidden="true">
            <span>K</span>
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
            <div className="logo-icon">🥗</div>
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
              <div className="planner-hero-grid">
                <article className="dinner-hero-card">
                  <div className="meal-hero-art">
                    <div className="meal-hero-illustration" aria-hidden="true"></div>
                    <span>{firstPlannedDinner.date.label || "Next week"}</span>
                  </div>
                  <div className="meal-hero-copy">
                    <span className="eyebrow">What&apos;s for dinner?</span>
                    <h2>{firstPlannedDinner.dinner}</h2>
                    <p>{firstPlannedDinner.day} dinner for the shared household plan. Tap a meal in the calendar to ask Kitch for swaps.</p>
                    <div className="chip-row">
                      <span>Household</span>
                      <span>{householdSize} people</span>
                      <span>{dietMeta.name}</span>
                    </div>
                    <div className="hero-footer">
                      <div className="avatar-stack">
                        {HOUSEHOLD_MEMBERS.map(member => (
                          <span key={member.value}>{member.value[0]}</span>
                        ))}
                      </div>
                      <button type="button" onClick={() => setChatInput(`Show me the recipe for ${firstPlannedDinner.dinner}`)}>
                        View recipe →
                      </button>
                    </div>
                  </div>
                </article>

                <article className="nutrition-widget">
                  <div className="widget-title-row">
                    <h3>Your Nutrition</h3>
                    <button type="button" onClick={() => setActiveTab("analytics")}>⋮</button>
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
                </article>
              </div>

              <section className="weekly-calendar-feature">
                <div className="section-heading">
                  <div>
                    <span className="eyebrow">Upcoming household week</span>
                    <h2 id="planner-household-heading">{`Weekly Plan for ${householdSize} ${householdSize === 1 ? "Person" : "People"}`}</h2>
                  </div>
                  <p>{planningWeekDates.Monday?.label && planningWeekDates.Sunday?.label ? `${planningWeekDates.Monday.label} - ${planningWeekDates.Sunday.label}` : "Upcoming Monday - Sunday"}</p>
                </div>
                <div id="weekly-plan-grid" className="calendar-board">
                  <div className="week-selector-strip">
                    {WEEK_DAYS.map(day => {
                      const dateMeta = planningWeekDates[day] || {};
                      const dinnerTitle = getMealTitle(weeklyPlan[day]?.dinner, "Dinner not set");
                      return (
                        <button
                          key={day}
                          type="button"
                          className={`week-selector-card ${selectedPlannerDay === day ? "active" : ""}`}
                          onClick={() => {
                            setSelectedPlannerDay(day);
                            setExpandedMealKey(`${day}-dinner`);
                          }}
                        >
                          <span>{day.slice(0, 3)}</span>
                          <strong>{dateMeta.label || "Soon"}</strong>
                          <em>{dinnerTitle}</em>
                        </button>
                      );
                    })}
                  </div>

                  <article className="selected-day-planner">
                    <div className="selected-day-glance">
                      <div>
                        <span className="eyebrow">{selectedDayDate.label || "Selected day"} at a glance</span>
                        <h3>{selectedPlannerDay}</h3>
                        <p>{selectedDayDate.longLabel || "Upcoming planning week"}</p>
                      </div>
                      <div className="glance-dinner-card">
                        <span>Dinner focus</span>
                        <strong>{selectedDayDinner?.title || "No dinner set"}</strong>
                        <button type="button" onClick={() => setChatInput(`Show ingredients and cooking steps for ${selectedDayDinner?.title || `${selectedPlannerDay} dinner`}`)}>
                          Ask for ingredients →
                        </button>
                      </div>
                    </div>

                    <div className="meal-accordion-list">
                      {selectedDayMealList.map(({ slot, key, title, ingredients }) => {
                        const isExpanded = expandedMealKey === key;
                        return (
                          <div key={key} className={`meal-accordion ${isExpanded ? "expanded" : ""}`}>
                            <button
                              type="button"
                              className="meal-accordion-trigger"
                              onClick={() => setExpandedMealKey(isExpanded ? "" : key)}
                            >
                              <span className={`meal-label ${slot}`}>{slot}</span>
                              <strong>{title}</strong>
                              <em>{isExpanded ? "−" : "+"}</em>
                            </button>
                            {isExpanded && (
                              <div className="meal-accordion-body">
                                {ingredients.length > 0 ? (
                                  <ul>
                                    {ingredients.map((ingredient, idx) => (
                                      <li key={`${key}-${idx}`}>{typeof ingredient === "string" ? ingredient : `${ingredient.amount || ""} ${ingredient.unit || ""} ${ingredient.name || ""}`.trim()}</li>
                                    ))}
                                  </ul>
                                ) : (
                                  <p>Kitch has the meal name saved, but ingredients are not attached to this structured plan yet.</p>
                                )}
                                <div className="meal-detail-actions">
                                  <button type="button" onClick={() => setChatInput(`Show full ingredients for ${title} on ${selectedPlannerDay}`)}>Get ingredients</button>
                                  <button type="button" onClick={() => draftMealSwapPrompt(selectedPlannerDay, slot)}>Swap this meal</button>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </article>
                </div>
              </section>

              <div className="planner-bottom-grid">
                <section className="snapshot-panel">
                  <h3>Household Snapshot</h3>
                  <div className="snapshot-grid">
                    <div className="snapshot-card">
                      <span className="snapshot-icon">⚠️</span>
                      <h4>Pantry status</h4>
                      {pantryPreview.length ? pantryPreview.map(item => (
                        <p key={item.name}>{item.name} <b>{item.amount} {item.unit}</b></p>
                      )) : <p>Scan the fridge to understand what is already available.</p>}
                    </div>
                    <div className="snapshot-card">
                      <span className="snapshot-icon">🛒</span>
                      <h4>Grocery list</h4>
                      <p><b>{totalCount}</b> required items</p>
                      <button type="button" onClick={() => setActiveTab("groceries")}>View full list</button>
                    </div>
                  </div>
                </section>
                <section className="activity-panel">
                  <h3>Recent Activity</h3>
                  <div className="activity-timeline">
                    {recentActivity.map((item, idx) => (
                      <div key={item} className="activity-item">
                        <span>{idx + 1}</span>
                        <p>{item}</p>
                      </div>
                    ))}
                  </div>
                </section>
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
                <button className="grocery-checkout-btn" onClick={() => checkoutItems.length === 0 ? triggerBannerAlert("🛒 Your cart has no pending items to checkout!") : setMcpModalOpen(true)}>
                  Preview Blinkit Payload
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
                        <div key={idx} className={`grocery-item-row ${item.checked ? "completed" : ""}`}>
                          <label className="grocery-checkbox-label">
                            <input type="checkbox" name={`grocery-${idx}`} checked={item.checked} disabled={item.alreadyStocked} onChange={() => toggleGroceryItem(item.name)} />
                            <span className="item-name">{item.name}</span>
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
                  <div className="grocery-summary-stats"><div><span>Required items:</span><strong>{totalCount}</strong></div><div><span>Stocked / Met:</span><strong>{checkedCount}</strong></div></div>
                </aside>
              </div>
            </section>
          )}
        </main>
      </div>

      <form id="chat-input-form" className={`smart-input-dock ${smartDockExpanded ? "expanded" : ""}`} onSubmit={handleChatSubmit}>
        <div className="smart-chat-thread" aria-live="polite">
          <div className="smart-chat-header">
            <div>
              <span className="smart-agent-avatar">🥗</span>
              <div>
                <strong>Kitch</strong>
                <small>Household meal agent</small>
              </div>
            </div>
            <button type="button" aria-label="Close chat panel" onClick={() => setSmartDockExpanded(false)}>×</button>
          </div>
          <div className="smart-chat-messages">
            {chatHistory.slice(-2).map((msg, index) => (
              <div key={`${msg.time}-${index}`} className={`smart-chat-bubble ${msg.sender}`}>
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
          <button type="button" className="input-icon-btn" aria-label="Voice input">🎙️</button>
          <input
            type="text"
            id="chat-user-input"
            name="chat-user-input"
            placeholder="Ask Kitch to plan, log, or add items..."
            autoComplete="off"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
          />
          <label className="input-icon-btn" aria-label="Upload plate image">
            🖼️
            <input name="plate-image-upload" type="file" accept="image/*" className="hidden-file-input" onChange={(e) => handleRealPhotoUpload(e.target.files[0], false)} />
          </label>
          <label className="input-icon-btn" aria-label="Open camera to scan fridge">
            📷
            <input name="camera-fridge-upload" type="file" accept="image/*" capture="environment" className="hidden-file-input" onChange={(e) => handleRealPhotoUpload(e.target.files[0], true)} />
          </label>
          <button type="submit" className="smart-send-btn" disabled={isChatTyping}>↑</button>
        </div>
      </form>

      {/* PROVIDER PAYLOAD REVIEW DIALOG */}
      {mcpModalOpen && (
        <div id="mcp-modal" className="modal-overlay active">
          <div className="modal-box">
            <div className="modal-header">
              <h3>
                📦 Provider Payload Review
              </h3>
              <button className="modal-close-btn" onClick={() => setMcpModalOpen(false)}>&times;</button>
            </div>
            <div className="modal-body">
              <p className="modal-note">
                Review the provider payload below. The live Blinkit MCP cart connection is not configured yet.
              </p>
              
              <div className="payload-preview">
                <span>{"// Blinkit provider payload preview"}</span><br/>
                <strong>blinkit_payload.prepare</strong>({`{`}<br/>
                &nbsp;&nbsp;items: <span id="mcp-items-json">{JSON.stringify(checkoutItems, null, 2)}</span>,<br/>
                &nbsp;&nbsp;household_size: <span id="mcp-household-val">{householdSize}</span><br/>
                {`})`}
              </div>
              
              <div className="modal-actions">
                <button
                  id="mcp-reject-btn"
                  className="modal-reject"
                  onClick={() => {
                    setMcpModalOpen(false);
                    triggerBannerAlert("Blinkit payload preview dismissed.");
                  }}
                >
                  Dismiss
                </button>
                <button
                  id="mcp-approve-btn"
                  className="modal-approve"
                  onClick={async () => {
                    setMcpModalOpen(false);
                    
                    try {
                      const res = await fetch("http://localhost:8000/api/grocery/export", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          items: checkoutItems,
                          provider: "blinkit"
                        })
                      });
                      if (res.ok) {
                        const data = await res.json();
                        triggerBannerAlert(`Payload prepared. ${data.result}`);
                      } else {
                        throw new Error("API call failed");
                      }
                    } catch (e) {
                      triggerBannerAlert("❌ Failed to contact the backend checkout exporter.");
                      console.error(e);
                    }
                    
                    const updatedCustom = customGroceryItems.map(item => ({ ...item, checked: true }));
                    setCustomGroceryItems(updatedCustom);
                  }}
                >
                  Prepare Payload
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
