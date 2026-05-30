"use client";

import React, { useState, useEffect, useMemo } from "react";
import { DIET_TYPES, RECIPES, DEFAULT_WEEKLY_PLAN, IMAGE_CATALOG } from "./mockData.js";

// Default welcome messaging
const INITIAL_CHAT = [
  {
    sender: "agent",
    text: "👋 **Welcome back to Kitch!** I am your GenAI Culinary Companion.\n\nI have scaled your weekly meal plan for your **3-person household**. \n\n✨ **Live Capabilities Active:**\n1. **Individual Macro Logs:** Select your active user in the header. We track macros separately for each housemate in Supabase!\n2. **Pantry Subtraction:** Click the **Scan Fridge** button to upload a photo of your shelves, or type *'We have 6 eggs'* to automatically update your inventory in the database!\n3. **Blinkit MCP:** Export your finalized grocery checklist directly to delivery carts via our backend API.",
    time: "09:00 AM"
  }
];

export default function Home() {
  // Hydration guard state
  const [isMounted, setIsMounted] = useState(false);

  // Application core state variables
  const [activeTab, setActiveTab] = useState("planner"); // planner, analytics, groceries
  const [dietPreference, setDietPreference] = useState("balanced");
  const [householdSize, setHouseholdSize] = useState(3);
  const [activeUser, setActiveUser] = useState("Dynamite");
  const [userProfiles, setUserProfiles] = useState({
    "Dynamite": { name: "Dynamite", loggedMeals: [] },
    "Housemate A": { name: "Housemate A", loggedMeals: [] },
    "Housemate B": { name: "Housemate B", loggedMeals: [] }
  });
  const [pantryStock, setPantryStock] = useState([
    { name: "Cabbage head", amount: 1, unit: "whole" },
    { name: "Whole wheat bread slices", amount: 2, unit: "slice" }
  ]);
  const [chatHistory, setChatHistory] = useState([...INITIAL_CHAT]);
  const [checkedGroceryItems, setCheckedGroceryItems] = useState({});
  const [customGroceryItems, setCustomGroceryItems] = useState([]);

  // UI state variables
  const [chatInput, setChatInput] = useState("");
  const [isChatTyping, setIsChatTyping] = useState(false);
  const [activeModalDay, setActiveModalDay] = useState(null);
  const [activeModalMealType, setActiveModalMealType] = useState(null);
  const [recipeModalOpen, setRecipeModalOpen] = useState(false);
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

  // Helper to load live DB state from backend
  const syncLiveState = async (userName) => {
    try {
      const res = await fetch(`http://localhost:8000/api/state/${userName}`);
      if (res.ok) {
        const data = await res.json();
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
      }
    } catch (e) {
      console.error("Failed to sync live state with Supabase backend", e);
    }
  };

  // 1. Initial mounting & LocalStorage sync
  useEffect(() => {
    setIsMounted(true);
    const saved = localStorage.getItem("kitch_state_v2");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.weeklyPlan) setWeeklyPlan(parsed.weeklyPlan);
        if (parsed.activeUser) setActiveUser(parsed.activeUser);
        if (parsed.chatHistory) setChatHistory(parsed.chatHistory);
        if (parsed.checkedGroceryItems) setCheckedGroceryItems(parsed.checkedGroceryItems);
        if (parsed.customGroceryItems) setCustomGroceryItems(parsed.customGroceryItems);
      } catch (e) {
        console.error("Failed to parse saved state, resetting...", e);
      }
    }
  }, []);

  // Sync state reactively when activeUser changes
  useEffect(() => {
    if (isMounted) {
      syncLiveState(activeUser);
    }
  }, [activeUser, isMounted]);

  // Initialize weekly plan state reactively to default plan
  const [weeklyPlan, setWeeklyPlan] = useState({ ...DEFAULT_WEEKLY_PLAN.balanced });

  // Update weekly plan when dietPreference changes, if we haven't mounted yet
  // Once mounted, user switches diet manually
  useEffect(() => {
    if (!isMounted) {
      setWeeklyPlan({ ...DEFAULT_WEEKLY_PLAN[dietPreference] });
    }
  }, [dietPreference, isMounted]);

  // Save state to localStorage whenever state variables change
  useEffect(() => {
    if (isMounted) {
      const stateToSave = {
        dietPreference,
        householdSize,
        weeklyPlan,
        activeUser,
        userProfiles,
        pantryStock,
        chatHistory,
        checkedGroceryItems,
        customGroceryItems
      };
      localStorage.setItem("kitch_state_v2", JSON.stringify(stateToSave));
    }
  }, [dietPreference, householdSize, weeklyPlan, activeUser, userProfiles, pantryStock, chatHistory, checkedGroceryItems, customGroceryItems, isMounted]);

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
    const scaleFactor = householdSize;
    const aggregated = {};

    // A. Gather all required ingredients from the active plan
    Object.keys(weeklyPlan).forEach(day => {
      const dayMeals = weeklyPlan[day] || {};
      Object.keys(dayMeals).forEach(slot => {
        const recipeId = dayMeals[slot];
        const recipe = RECIPES.find(r => r.id === recipeId);
        
        if (recipe) {
          recipe.ingredients.forEach(ing => {
            const key = ing.name.toLowerCase().trim();
            const scaledAmount = ing.amount * scaleFactor;

            if (aggregated[key]) {
              aggregated[key].amount += scaledAmount;
            } else {
              let category = "Pantry & Spices";
              const name = key;
              if (name.includes("chicken") || name.includes("steak") || name.includes("salmon") || name.includes("beef") || name.includes("egg") || name.includes("tofu")) {
                category = "Proteins & Dairy";
              } else if (name.includes("avocado") || name.includes("broccoli") || name.includes("spinach") || name.includes("asparagus") || name.includes("tomato") || name.includes("cucumber") || name.includes("onion") || name.includes("pepper") || name.includes("berry") || name.includes("raspberries") || name.includes("blueberries")) {
                category = "Fresh Produce";
              } else if (name.includes("bread") || name.includes("oats") || name.includes("quinoa") || name.includes("rice") || name.includes("tortilla") || name.includes("chia")) {
                category = "Grains & Bakery";
              }

              aggregated[key] = {
                name: ing.name,
                amount: scaledAmount,
                unit: ing.unit,
                category,
                checked: false,
                alreadyStocked: false
              };
            }
          });
        }
      });
    });

    // B. Subtract Pantry Inventory stocks from the required list
    pantryStock.forEach(pantryItem => {
      const key = pantryItem.name.toLowerCase().trim();
      if (aggregated[key]) {
        aggregated[key].amount = Math.max(0, aggregated[key].amount - pantryItem.amount);
        
        if (aggregated[key].amount === 0) {
          aggregated[key].alreadyStocked = true;
          aggregated[key].checked = true;
        }
      }
    });

    // C. Merge in manually checked checkmarks
    Object.keys(aggregated).forEach(key => {
      if (checkedGroceryItems[key]) {
        aggregated[key].checked = true;
      }
    });

    const plannedList = Object.values(aggregated);

    // D. Combine with manual custom items
    return [...plannedList, ...customGroceryItems];
  }, [weeklyPlan, householdSize, pantryStock, checkedGroceryItems, customGroceryItems]);

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
      setWeeklyPlan({ ...DEFAULT_WEEKLY_PLAN[dietType] });
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
    } else {
      // It is a planned ingredient
      setCheckedGroceryItems(prev => ({
        ...prev,
        [key]: !prev[key]
      }));
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
          setWeeklyPlan({ ...DEFAULT_WEEKLY_PLAN[newDiet] });
          triggerBannerAlert(`Switched dietary profile to ${DIET_TYPES[newDiet].name}!`);
        } else if (act.type === "UPDATE_PLANNER") {
          triggerBannerAlert("Planner modified by Kitch Agent!");
          syncLiveState(activeUser);
        } else if (act.type === "UPDATE_PANTRY") {
          triggerBannerAlert("Pantry inventory updated by Kitch Agent!");
          syncLiveState(activeUser);
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
        steps: [...prev.steps, "🧠 Running computer vision segmentation in Gemini 3.5..."]
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

  // 6. Modal Meal Swap actions
  const openRecipeSwapModal = (day, slot) => {
    setActiveModalDay(day);
    setActiveModalMealType(slot);
    setRecipeModalOpen(true);
  };

  const handleRecipeSwapSelection = (recipe) => {
    const updatedPlan = { ...weeklyPlan };
    if (!updatedPlan[activeModalDay]) {
      updatedPlan[activeModalDay] = {};
    }
    updatedPlan[activeModalDay][activeModalMealType] = recipe.id;
    
    setWeeklyPlan(updatedPlan);
    setRecipeModalOpen(false);
    triggerBannerAlert(`Successfully set ${recipe.name} as ${activeModalDay}'s ${activeModalMealType}!`);
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
        item: item.name,
        quantity: Math.round(item.amount * 100) / 100,
        unit: item.unit
      }));
  }, [groceryList]);

  return (
    <div id="app">
      {/* SVG gradients for visual nutrition dial */}
      <svg style={{ width: 0, height: 0, position: "absolute" }} width="0" height="0">
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

      {/* HEADER SECTION */}
      <header className="app-header">
        <div className="logo-section">
          <div className="logo-icon">🥗</div>
          <div>
            <h1>Kitch</h1>
            <span>GenAI Culinary Agent</span>
          </div>
        </div>

        <div className="controls-section">
          <div className="control-group">
            <label htmlFor="profile-selector">Active User</label>
            <select
              id="profile-selector"
              value={activeUser}
              onChange={(e) => switchActiveUser(e.target.value)}
            >
              <option value="Dynamite">Dynamite (You)</option>
              <option value="Housemate A">Housemate A</option>
              <option value="Housemate B">Housemate B</option>
            </select>
          </div>

          <div className="control-group">
            <label htmlFor="diet-selector">Diet Profile</label>
            <select
              id="diet-selector"
              value={dietPreference}
              onChange={(e) => switchDiet(e.target.value)}
            >
              <option value="balanced">Balanced Diet</option>
              <option value="keto">Keto / Low-Carb</option>
              <option value="vegan">Vegan / Plant-Based</option>
              <option value="high-protein">High-Protein Active</option>
            </select>
          </div>

          <div className="control-group">
            <label htmlFor="household-size">Household Size</label>
            <input
              type="number"
              id="household-size"
              min="1"
              max="12"
              value={householdSize}
              onChange={(e) => updateHouseholdSize(e.target.value)}
            />
            <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase" }}>People</span>
          </div>
        </div>
      </header>

      {/* MAIN APP CORE GRID */}
      <main className="layout-grid">
        
        {/* LEFT: CHAT SIMULATOR PANEL */}
        <section className="chat-simulator" aria-label="Kitch Chat Agent Sim">
          
          {/* Computer Vision Scanner Scan Overlay */}
          {scanningOverlay.active && (
            <div id="vision-scanner" className="vision-scanner-overlay active">
              <div className="scanning-image-box">
                <div className="scan-laser-line"></div>
                <div style={{ fontSize: "72px", display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "center", height: "100%" }}>
                  {scanningOverlay.fileName.includes("fridge") ? "❄️" : 
                   scanningOverlay.fileName.includes("salmon") ? "🐟" : 
                   scanningOverlay.fileName.includes("chicken") ? "🍗" : 
                   scanningOverlay.fileName.includes("salad") ? "🥗" : "🍓"}
                </div>
              </div>
              <h4 id="scanner-title-text" style={{ color: "var(--accent-primary)", marginBottom: "8px", fontWeight: 700, textTransform: "uppercase", fontSize: "13px" }}>
                {scanningOverlay.title}
              </h4>
              <div id="scan-terminal-log" className="scan-log-box">
                {scanningOverlay.steps.map((step, idx) => (
                  <div key={idx} className="scan-log-line">{step}</div>
                ))}
              </div>
            </div>
          )}

          {/* Chat Header */}
          <div className="chat-header">
            <div className="chat-bot-info">
              <div className="bot-avatar">🤖</div>
              <div className="bot-status">
                <h3>Kitch Companion</h3>
                <span>Online</span>
              </div>
            </div>
          </div>

          {/* Message Bubbles */}
          <div id="chat-messages" className="chat-messages">
            {chatHistory.map((msg, index) => (
              <div key={index} className={`msg-bubble ${msg.sender}`}>
                {msg.image && (
                  <div style={{ background: "rgba(255,255,255,0.08)", width: "100%", height: "110px", display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "8px", marginBottom: "8px", fontSize: "48px" }}>
                    {msg.image.includes("fridge") ? "❄️" : 
                     msg.image.includes("salmon") ? "🐟" : 
                     msg.image.includes("chicken") ? "🍗" : 
                     msg.image.includes("salad") ? "🥗" : "🍓"}
                  </div>
                )}
                <div style={{ whiteSpace: "pre-wrap" }}>
                  {msg.text.split("\n").map((line, lidx) => {
                    // Primitive bold markdown matching
                    const boldRegex = /\*\*(.*?)\*\*/g;
                    const parts = line.split(boldRegex);
                    return (
                      <p key={lidx} style={{ marginBottom: "6px" }}>
                        {parts.map((part, pidx) => pidx % 2 === 1 ? <strong key={pidx}>{part}</strong> : part)}
                      </p>
                    );
                  })}
                </div>
                <span className="msg-time">{msg.time}</span>
              </div>
            ))}

            {isChatTyping && (
              <div className="msg-bubble agent typing-bubble">
                <div className="typing-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            )}
          </div>

          {/* Real Photo Upload & Log Tray */}
          <div className="chat-photo-tray">
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h4 style={{ fontSize: "11px", fontWeight: 600, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "1px" }}>📸 Upload & Scan Live Photo</h4>
                <div style={{ display: "flex", gap: "8px" }}>
                  <label className="photo-btn" style={{ background: "rgba(16, 185, 129, 0.15)", borderColor: "var(--accent-primary)", padding: "4px 8px", fontSize: "10px", height: "auto", width: "auto", display: "flex", alignItems: "center", gap: "4px", cursor: "pointer", borderRadius: "8px", border: "1px solid var(--glass-border)", transition: "var(--transition-smooth)" }}>
                    <span>❄️</span>
                    <strong style={{ cursor: "pointer" }}>Scan Fridge</strong>
                    <input
                      type="file"
                      accept="image/*"
                      style={{ display: "none" }}
                      onChange={(e) => handleRealPhotoUpload(e.target.files[0], true)}
                    />
                  </label>
                  <label className="photo-btn" style={{ background: "rgba(59, 130, 246, 0.15)", borderColor: "#3B82F6", padding: "4px 8px", fontSize: "10px", height: "auto", width: "auto", display: "flex", alignItems: "center", gap: "4px", cursor: "pointer", borderRadius: "8px", border: "1px solid var(--glass-border)", transition: "var(--transition-smooth)" }}>
                    <span>🍽️</span>
                    <strong style={{ cursor: "pointer" }}>Scan Plate</strong>
                    <input
                      type="file"
                      accept="image/*"
                      style={{ display: "none" }}
                      onChange={(e) => handleRealPhotoUpload(e.target.files[0], false)}
                    />
                  </label>
                </div>
              </div>
            </div>
          </div>

          {/* Message Inputs */}
          <form id="chat-input-form" className="chat-input-area" onSubmit={handleChatSubmit}>
            <input
              type="text"
              id="chat-user-input"
              placeholder="Ask chef agent or type command..."
              autoComplete="off"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
            />
            <button type="submit" className="chat-send-btn">Send</button>
          </form>
        </section>

        {/* RIGHT: WEB DASHBOARD TABS */}
        <section className="dashboard-container" aria-label="Interactive Web Dashboard">
          
          {/* Tabs Selector */}
          <nav className="dashboard-tabs">
            <button
              className={`tab-btn ${activeTab === "planner" ? "active" : ""}`}
              onClick={() => setActiveTab("planner")}
            >
              📅 Weekly Planner
            </button>
            <button
              className={`tab-btn ${activeTab === "analytics" ? "active" : ""}`}
              onClick={() => setActiveTab("analytics")}
            >
              📊 Daily Intake Log
            </button>
            <button
              className={`tab-btn ${activeTab === "groceries" ? "active" : ""}`}
              onClick={() => setActiveTab("groceries")}
            >
              🛒 Grocery Cart
            </button>
          </nav>

          {/* Dynamic Panel Wrapper */}
          <div className="dashboard-content">
            
            {/* PANEL 1: WEEKLY PLANNER */}
            <div id="panel-planner" className={`tab-panel ${activeTab === "planner" ? "active" : ""}`}>
              <div className="planner-view">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 id="planner-household-heading">Weekly Plan for {householdSize} {householdSize === 1 ? "Person" : "People"}</h3>
                  <span style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 500 }}>💡 Click any card below to swap meals on the fly!</span>
                </div>
                
                <div id="weekly-plan-grid" className="weekly-grid">
                  {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map(day => {
                    const dayMeals = weeklyPlan[day] || {};
                    let dayCalories = 0;
                    
                    Object.values(dayMeals).forEach(recipeId => {
                      const rec = RECIPES.find(r => r.id === recipeId);
                      if (rec) dayCalories += rec.calories;
                    });

                    const isToday = typeof window !== "undefined" && day === new Date().toLocaleDateString('en-US', { weekday: 'long' });

                    return (
                      <div key={day} className={`day-column ${isToday ? "today" : ""}`}>
                        <div className="day-title">{isToday ? "Today" : day}</div>
                        <div className="day-calories">{dayCalories} kcal</div>

                        {["breakfast", "lunch", "dinner", "snack"].map(slot => {
                          const recipeId = dayMeals[slot];
                          const recipe = RECIPES.find(r => r.id === recipeId);

                          return (
                            <div
                              key={slot}
                              className="meal-card"
                              onClick={() => openRecipeSwapModal(day, slot)}
                            >
                              {recipe ? (
                                <>
                                  <div>
                                    <span className={`meal-label ${slot}`}>{slot}</span>
                                    <div className="meal-name">{recipe.name}</div>
                                  </div>
                                  <div className="meal-stats">
                                    <span>🔥 {recipe.calories} kcal</span>
                                    <span>🥩 {recipe.macros.protein}g P</span>
                                  </div>
                                </>
                              ) : recipeId ? (
                                <>
                                  <div>
                                    <span className={`meal-label ${slot}`}>{slot}</span>
                                    <div className="meal-name">{recipeId}</div>
                                  </div>
                                  <div className="meal-stats">
                                    <span>✨ Custom Recipe</span>
                                  </div>
                                </>
                              ) : (
                                <>
                                  <div>
                                    <span className={`meal-label ${slot}`}>{slot}</span>
                                    <div className="meal-name" style={{ color: "var(--text-muted)", fontStyle: "italic" }}>No recipe set</div>
                                  </div>
                                  <div className="meal-stats">
                                    <span>- kcal</span>
                                  </div>
                                </>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* PANEL 2: DAILY ANALYTICS */}
            <div id="panel-analytics" className={`tab-panel ${activeTab === "analytics" ? "active" : ""}`}>
              <div className="analytics-view">
                
                {/* Circular Calorie Dial */}
                <div className="summary-circle-container">
                  <h3 className="tracker-title" id="calorie-tracker-user-title">Calories Today ({activeUser})</h3>
                  <div className="calorie-dial">
                    <svg width="180" height="180" viewBox="0 0 180 180">
                      <circle className="calorie-dial-ring-bg" cx="90" cy="90" r="75" />
                      <circle
                        id="calorie-dial-fill"
                        className="calorie-dial-ring-fill"
                        cx="90"
                        cy="90"
                        r="75"
                        strokeDasharray="471.2"
                        style={{ strokeDashoffset: strokeDashoffset }}
                      />
                    </svg>
                    <div className="calorie-dial-info">
                      <h2 id="logged-calories-num">{loggedCal}</h2>
                      <p id="target-calories-num">/ {targetCalories} kcal</p>
                    </div>
                  </div>
                  <span id="calorie-percentage-badge" style={{ fontSize: "12px", color: "var(--accent-primary)", fontWeight: 700, background: "rgba(16,185,129,0.1)", padding: "4px 10px", borderRadius: "20px" }}>
                    {calPercentage}% Met
                  </span>
                </div>

                {/* Macro Bars */}
                <div className="macro-breakdown-card">
                  <h3 className="tracker-title">Macros Breakdown</h3>
                  
                  <div className="macro-bar-group">
                    <div className="macro-bar-header">
                      <span>Protein (Target: <span id="protein-target-val">{targetProtein}</span>g)</span>
                      <span><span id="protein-logged-val">{loggedProt}</span>g</span>
                    </div>
                    <div className="progress-track">
                      <div id="protein-bar-fill" className="progress-fill protein" style={{ width: `${protPerc}%` }}></div>
                    </div>
                  </div>

                  <div className="macro-bar-group">
                    <div className="macro-bar-header">
                      <span>Carbohydrates (Target: <span id="carbs-target-val">{targetCarbs}</span>g)</span>
                      <span><span id="carbs-logged-val">{loggedCarb}</span>g</span>
                    </div>
                    <div className="progress-track">
                      <div id="carbs-bar-fill" className="progress-fill carbs" style={{ width: `${carbPerc}%` }}></div>
                    </div>
                  </div>

                  <div className="macro-bar-group">
                    <div className="macro-bar-header">
                      <span>Fats (Target: <span id="fat-target-val">{targetFat}</span>g)</span>
                      <span><span id="fat-logged-val">{loggedFat}</span>g</span>
                    </div>
                    <div className="progress-track">
                      <div id="fat-bar-fill" className="progress-fill fat" style={{ width: `${fatPerc}%` }}></div>
                    </div>
                  </div>
                </div>

                {/* Journal List */}
                <div className="diary-section">
                  <div className="diary-header">
                    <h3 style={{ fontSize: "16px", fontWeight: 600 }} id="diary-user-heading">Plate Logs ({activeUser})</h3>
                    <button id="clear-diary-btn" className="clear-diary-btn" onClick={resetDailyLogs}>Clear Logs</button>
                  </div>
                  
                  <div id="diary-list" className="diary-list">
                    {loggedMeals.length === 0 ? (
                      <div className="diary-empty-state">
                        🍳 {activeUser} has not logged any plates today. Snap a photo in the chat simulator to auto-detect macros!
                      </div>
                    ) : (
                      loggedMeals.map((meal, idx) => (
                        <div key={idx} className="diary-item">
                          <div className="diary-item-info">
                            <h4>{meal.name}</h4>
                            <span>Log Time: {meal.time}</span>
                          </div>
                          <div className="diary-item-macros">
                            🔥 {meal.calories} kcal
                            <span>P: {meal.macros.protein}g | C: {meal.macros.carbs}g | F: {meal.macros.fat}g</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

              </div>
            </div>

            {/* PANEL 3: GROCERY CHECKLIST */}
            <div id="panel-groceries" className={`tab-panel ${activeTab === "groceries" ? "active" : ""}`}>
              <div className="grocery-layout-triple" style={{ display: "grid", gridTemplateColumns: "1.2fr 1.2fr 1fr", gap: "20px" }}>
                
                {/* Dynamic Shopping Cart */}
                <div>
                  <h3 style={{ fontSize: "15px", fontWeight: 700, marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                    🛒 Shopping Cart
                  </h3>
                  <div id="grocery-list-grid" className="grocery-list-container">
                    {totalCount === 0 ? (
                      <div className="diary-empty-state">
                        🛒 Your shopping cart is empty! Check back once a meal plan is configured.
                      </div>
                    ) : (
                      Object.keys(groupedGroceries).map(category => (
                        <div key={category} className="grocery-category">
                          <div className="grocery-category-title">{category}</div>
                          {groupedGroceries[category].map((item, idx) => {
                            const isStocked = item.alreadyStocked;
                            const isChecked = item.checked;
                            
                            return (
                              <div
                                key={idx}
                                className={`grocery-item-row ${isChecked && !isStocked ? "completed" : ""} ${isStocked ? "stocked-in-pantry completed" : ""}`}
                              >
                                <label className="grocery-checkbox-label">
                                  <input
                                    type="checkbox"
                                    checked={isChecked}
                                    disabled={isStocked}
                                    onChange={() => toggleGroceryItem(item.name)}
                                  />
                                  <span className="item-name">{item.name}</span>
                                </label>
                                {isStocked ? (
                                  <span className="stocked-badge">Met (Pantry)</span>
                                ) : (
                                  <span className="grocery-item-qty">
                                    {Math.round(item.amount * 100) / 100} {item.unit}
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Pantry Stock / Fridge Inventory */}
                <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--glass-border)", borderRadius: "16px", padding: "16px", display: "flex", flexDirection: "column", gap: "14px", maxHeight: "600px", overflowY: "auto" }}>
                  <div>
                    <h3 style={{ fontSize: "15px", fontWeight: 700, color: "var(--accent-primary)", display: "flex", alignItems: "center", gap: "6px" }}>
                      ❄️ Pantry Stock (In Fridge)
                    </h3>
                    <p style={{ fontSize: "10px", color: "var(--text-muted)", marginTop: "2px" }}>
                      Stock levels here subtract automatically from your cart required totals!
                    </p>
                  </div>
                  
                  {/* Add Pantry Item Form */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px", padding: "10px", background: "rgba(0,0,0,0.15)", borderRadius: "10px", border: "1px solid rgba(255,255,255,0.03)" }}>
                    <h4 style={{ fontSize: "11px", fontWeight: 600, textTransform: "uppercase", color: "var(--text-muted)" }}>
                      Quick Add Fridge Stock
                    </h4>
                    <input
                      type="text"
                      placeholder="Item name..."
                      value={pantryAddName}
                      onChange={(e) => setPantryAddName(e.target.value)}
                      style={{ background: "rgba(255,255,255,0.04)", border: "1px solid var(--glass-border)", borderRadius: "6px", color: "#fff", padding: "6px 10px", fontSize: "12px", outline: "none" }}
                    />
                    <div style={{ display: "flex", gap: "6px" }}>
                      <input
                        type="number"
                        placeholder="Qty"
                        value={pantryAddAmount}
                        min="0.1"
                        step="0.1"
                        onChange={(e) => setPantryAddAmount(parseFloat(e.target.value) || 1)}
                        style={{ background: "rgba(255,255,255,0.04)", border: "1px solid var(--glass-border)", borderRadius: "6px", color: "#fff", padding: "6px", fontSize: "12px", width: "60px", textAlign: "center", outline: "none" }}
                      />
                      <input
                        type="text"
                        placeholder="Unit"
                        value={pantryAddUnit}
                        onChange={(e) => setPantryAddUnit(e.target.value)}
                        style={{ background: "rgba(255,255,255,0.04)", border: "1px solid var(--glass-border)", borderRadius: "6px", color: "#fff", padding: "6px 8px", fontSize: "12px", flex: 1, outline: "none" }}
                      />
                    </div>
                    <button
                      onClick={() => {
                        addPantryItem(pantryAddName, pantryAddAmount, pantryAddUnit);
                        triggerBannerAlert(`Manually added ${pantryAddAmount} ${pantryAddUnit} of "${pantryAddName}" to Fridge Stock.`);
                        setPantryAddName("");
                      }}
                      style={{ background: "var(--accent-primary)", border: "none", borderRadius: "6px", color: "var(--text-inverse)", fontWeight: 700, fontSize: "12px", padding: "6px 0", cursor: "pointer", transition: "var(--transition-smooth)" }}
                    >
                      Add Stock
                    </button>
                  </div>

                  {/* Pantry Stock List */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {pantryStock.length === 0 ? (
                      <div className="diary-empty-state" style={{ padding: "16px", fontSize: "11px" }}>
                        ❄️ Fridge inventory is empty! Add items manually or click Scan Fridge to upload an image.
                      </div>
                    ) : (
                      pantryStock.map((pantryItem, idx) => (
                        <div key={idx} className="pantry-item-row">
                          <div className="pantry-item-row-info">
                            <strong style={{ color: "#fff", display: "block" }}>{pantryItem.name}</strong>
                            <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>{pantryItem.amount} {pantryItem.unit} available</span>
                          </div>
                          <button
                            className="pantry-item-delete"
                            onClick={() => {
                              removePantryItem(idx);
                              triggerBannerAlert(`Removed "${pantryItem.name}" from your fridge inventory.`);
                            }}
                          >
                            &times;
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Custom list options sidebar */}
                <div className="grocery-summary-sidebar" style={{ height: "fit-content" }}>
                  <div className="grocery-add-form">
                    <h4>Add Custom Cart Item</h4>
                    <input
                      type="text"
                      placeholder="E.g. Sparkling water, napkins..."
                      value={groceryCustomName}
                      onChange={(e) => setGroceryCustomName(e.target.value)}
                    />
                    <select
                      value={groceryCustomCat}
                      onChange={(e) => setGroceryCustomCat(e.target.value)}
                    >
                      <option value="Fresh Produce">Fresh Produce</option>
                      <option value="Proteins & Dairy">Proteins & Dairy</option>
                      <option value="Grains & Bakery">Grains & Bakery</option>
                      <option value="Pantry & Spices">Pantry & Spices</option>
                    </select>
                    <button
                      className="grocery-add-btn"
                      onClick={() => addCustomGroceryItem(groceryCustomName, groceryCustomCat)}
                    >
                      Add to Cart
                    </button>
                  </div>

                  <hr style={{ border: 0, height: "1px", background: "rgba(255,255,255,0.06)" }} />

                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Required items:</span>
                      <strong>{totalCount}</strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
                      <span style={{ color: "var(--text-muted)" }}>Stocked / Met:</span>
                      <strong style={{ color: "var(--accent-primary)" }}>{checkedCount}</strong>
                    </div>
                  </div>

                  <button
                    className="grocery-checkout-btn"
                    onClick={() => {
                      if (checkoutItems.length === 0) {
                        triggerBannerAlert("🛒 Your cart has no pending items to checkout!");
                      } else {
                        setMcpModalOpen(true);
                      }
                    }}
                  >
                    📦 Order via Blinkit MCP
                  </button>
                </div>

              </div>
            </div>

          </div>
        </section>
      </main>

      {/* RECIPE SWAP MODAL */}
      {recipeModalOpen && (
        <div id="recipe-modal" className="modal-overlay active">
          <div className="modal-box">
            <div className="modal-header">
              <h3>Select {activeModalMealType.charAt(0).toUpperCase() + activeModalMealType.slice(1)} Replacement</h3>
              <button className="modal-close-btn" onClick={() => setRecipeModalOpen(false)}>&times;</button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "8px" }}>
                Choose a macro-balanced recipe to swap. Your grocery cart and calories will update automatically!
              </p>
              
              <div className="recipe-options-list">
                {RECIPES.filter(r => r.type === activeModalMealType).map(recipe => {
                  const isMatchingDiet = recipe.diets.includes(dietPreference);
                  
                  return (
                    <div
                      key={recipe.id}
                      className="recipe-select-option"
                      onClick={() => handleRecipeSwapSelection(recipe)}
                    >
                      <div className="recipe-select-details">
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <h4 style={{ color: "#fff", fontWeight: 600, fontSize: "14px" }}>{recipe.name}</h4>
                          {isMatchingDiet && (
                            <span style={{ fontSize: "9px", background: "rgba(16,185,129,0.15)", color: "var(--accent-primary)", padding: "2px 6px", borderRadius: "4px", fontWeight: 600, textTransform: "uppercase" }}>
                              Matches Diet
                            </span>
                          )}
                        </div>
                        <p style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                          ⏳ Prep: {recipe.prepTime} | P: {recipe.macros.protein}g, C: {recipe.macros.carbs}g, F: {recipe.macros.fat}g
                        </p>
                      </div>
                      <div className="recipe-select-macros" style={{ fontSize: "12px", fontWeight: 700, color: "var(--accent-secondary)" }}>
                        🔥 {recipe.calories} Cal
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MCP TOOL CALL HUMAN-IN-THE-LOOP REVIEW DIALOG */}
      {mcpModalOpen && (
        <div id="mcp-modal" className="modal-overlay active">
          <div className="modal-box" style={{ maxWidth: "500px" }}>
            <div className="modal-header" style={{ background: "rgba(245, 158, 11, 0.1)", borderBottomColor: "rgba(245, 158, 11, 0.2)" }}>
              <h3 style={{ color: "var(--accent-secondary)", display: "flex", alignItems: "center", gap: "8px" }}>
                📦 Human-in-the-Loop MCP Review
              </h3>
              <button className="modal-close-btn" onClick={() => setMcpModalOpen(false)}>&times;</button>
            </div>
            <div className="modal-body" style={{ padding: "20px" }}>
              <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "12px" }}>
                An MCP tool execution has been requested. Please review the parameters below before allowing the agent to place the Blinkit order.
              </p>
              
              <div style={{ background: "#020617", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "8px", padding: "12px", fontFamily: "monospace", fontSize: "11px", color: "#a5f3fc", overflowX: "auto", marginBottom: "16px" }}>
                <span style={{ color: "#6ee7b7" }}>// Calling Blinkit MCP Cart Tool...</span><br/>
                <strong>blinkit_mcp.add_to_cart</strong>({`{`}<br/>
                &nbsp;&nbsp;items: <span style={{ color: "#fca5a5" }} id="mcp-items-json">{JSON.stringify(checkoutItems, null, 2)}</span>,<br/>
                &nbsp;&nbsp;household_size: <span style={{ color: "#f59e0b" }} id="mcp-household-val">{householdSize}</span><br/>
                {`})`}
              </div>
              
              <div style={{ display: "flex", gap: "12px", width: "100%" }}>
                <button
                  id="mcp-reject-btn"
                  onClick={() => {
                    setMcpModalOpen(false);
                    triggerBannerAlert("❌ Blinkit MCP Tool execution aborted by user.");
                  }}
                  style={{ flex: 1, padding: "10px 0", borderRadius: "6px", border: "1px solid rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.1)", color: "var(--accent-coral)", fontWeight: "600", cursor: "pointer" }}
                >
                  Reject Tool
                </button>
                <button
                  id="mcp-approve-btn"
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
                        triggerBannerAlert(`✨ Real MCP Call Successful! ${data.result}`);
                      } else {
                        throw new Error("API call failed");
                      }
                    } catch (e) {
                      triggerBannerAlert("❌ Failed to contact the backend checkout exporter.");
                      console.error(e);
                    }
                    
                    // Mark all non-pantry checkout items as checked
                    const newChecked = { ...checkedGroceryItems };
                    groceryList.forEach(item => {
                      if (!item.alreadyStocked) {
                        newChecked[item.name.toLowerCase().trim()] = true;
                      }
                    });
                    setCheckedGroceryItems(newChecked);

                    const updatedCustom = customGroceryItems.map(item => ({ ...item, checked: true }));
                    setCustomGroceryItems(updatedCustom);
                  }}
                  style={{ flex: 1, padding: "10px 0", borderRadius: "6px", border: "none", background: "var(--accent-primary)", color: "var(--text-inverse)", fontWeight: "600", cursor: "pointer" }}
                >
                  Approve MCP Call
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
