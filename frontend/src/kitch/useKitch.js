"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import {
  DEFAULT_ACTIVE_USER,
  DEFAULT_HOUSEHOLD_SIZE,
  HOUSEHOLD_MEMBERS,
  MEAL_SLOTS,
  createUserProfiles,
  formatPlanDate,
  getWeekStartForDate,
  shiftIsoDate
} from "../app/householdConfig.js";
import {
  MEAL_SLOT_LABELS,
  DEFAULT_MEAL_SLOT,
  NUTRITION_MEALS,
  EMPTY_NUTRITION_ENTRY,
  INITIAL_VISIBLE_CHAT_COUNT,
  CHAT_HISTORY_BATCH_SIZE,
  PERSISTENCE_FAILURE_MESSAGE,
  DEFAULT_ORDERING_PROVIDER,
  PROVIDER_REVALIDATE_AFTER_MS,
  safeProviderPaymentUrl,
  withProviderRoutes,
  ApiResponseError,
  requireSuccessfulResponse,
  apiErrorMessage,
  getTimeBasedMealSlot,
  getTimeBasedGreeting,
  AGENT_REQUEST_TIMEOUT_MS,
  PROVIDER_OPERATION_TIMEOUT_MS,
  apiUrl,
  apiFetch,
  getMealTitle,
  hasMealTitle,
  hasPlannedMeals,
  getRecipeCardTitle,
  normalizeList,
  getIngredientName,
  getRecipeSteps,
  collectObjectsWithAnyKey,
  optionValue,
  formatProviderPaymentLabel,
  formatProviderAddressParts,
  formatMinorCurrency,
  getProviderCartLineData,
  cartItemKey,
  cartPurchaseAmount,
  INITIAL_CHAT
} from "./lib/helpers.js";

const SESSION_REQUEST_TIMEOUT_MS = 90_000;
const STARTUP_WAKE_WINDOW_MS = 150_000;

// The household controller: every piece of state, request, and derived value the
// views render. Moved from the previous single-file page with behaviour intact.
export function useKitch() {
  // Application core state variables
  const [activeTab, setActiveTab] = useState("planner");
  const [selectedPlanDate, setSelectedPlanDate] = useState("");
  const [currentMealSlot, setCurrentMealSlot] = useState(DEFAULT_MEAL_SLOT);
  const [expandedMealKey, setExpandedMealKey] = useState("");
  const [householdSize, setHouseholdSize] = useState(DEFAULT_HOUSEHOLD_SIZE);
  const [householdMembers, setHouseholdMembers] = useState(HOUSEHOLD_MEMBERS);
  const [activeUser, setActiveUser] = useState(DEFAULT_ACTIVE_USER);
  const [userProfiles, setUserProfiles] = useState(createUserProfiles);
  const [pantryStock, setPantryStock] = useState([]);
  const [pantryRevision, setPantryRevision] = useState(0);
  const [pantryReviewedAt, setPantryReviewedAt] = useState("");
  const [groceryWorkspaceTab, setGroceryWorkspaceTab] = useState("cart");
  const [collapsedGroceryCategories, setCollapsedGroceryCategories] = useState({});
  const [pantryTableCollapsed, setPantryTableCollapsed] = useState(false);
  const [editingGroceryItemId, setEditingGroceryItemId] = useState(null);
  const [groceryItemNameDraft, setGroceryItemNameDraft] = useState("");
  const [pantryDrafts, setPantryDrafts] = useState({});
  const [editingPantryItemId, setEditingPantryItemId] = useState(null);
  const [pantryNewItem, setPantryNewItem] = useState({ name: "", amount: 1, unit: "piece" });
  const [confirmationDialog, setConfirmationDialog] = useState(null);
  const [mealPlan, setMealPlan] = useState({ days: [] });
  const [chatHistory, setChatHistory] = useState([...INITIAL_CHAT]);
  const [visibleChatCount, setVisibleChatCount] = useState(INITIAL_VISIBLE_CHAT_COUNT);
  const chatMessagesRef = useRef(null);
  const [customGroceryItems, setCustomGroceryItems] = useState([]);
  const confirmedGroceryItemsRef = useRef([]);
  const [latestRecipeGroceryPlan, setLatestRecipeGroceryPlan] = useState(null);
  const [liveStateUser, setLiveStateUser] = useState("");
  const [householdBootstrap, setHouseholdBootstrap] = useState(null);
  const [onboardingMembers, setOnboardingMembers] = useState([""]);
  const [isOnboardingSaving, setIsOnboardingSaving] = useState(false);
  const [onboardingError, setOnboardingError] = useState("");
  const [authState, setAuthState] = useState({ loading: true, required: false, authenticated: false, email: "" });
  const [authError, setAuthError] = useState("");
  const [startupState, setStartupState] = useState({ attempts: 0, retrying: false, failed: false, message: "" });
  const startupRunRef = useRef(0);
  const [timeGreeting, setTimeGreeting] = useState("Welcome");
  const googleButtonRef = useRef(null);
  const [memberEditorOpen, setMemberEditorOpen] = useState(false);
  const [memberNameDrafts, setMemberNameDrafts] = useState({});
  const [memberEditorError, setMemberEditorError] = useState("");
  const [savingMemberId, setSavingMemberId] = useState("");

  // UI state variables
  const [chatInput, setChatInput] = useState("");
  const [notices, setNotices] = useState([]);
  const noticeIdRef = useRef(0);
  // Every outcome message lands in one notice queue the shell renders as a live
  // region, so failed saves are never silent. Tone is inferred from wording so
  // existing call sites keep their single-string signature.
  const triggerBannerAlert = useCallback((text, tone) => {
    const message = String(text || "").trim();
    if (!message) return;
    const inferredTone = tone || (/could not|couldn’t|failed|unable|not be|missing|error|needs attention|blocked|unavailable/i.test(message) ? "error" : "info");
    noticeIdRef.current += 1;
    const id = noticeIdRef.current;
    setNotices(current => [...current.slice(-3), { id, text: message, tone: inferredTone }]);
  }, []);
  const dismissNotice = useCallback((id) => {
    setNotices(current => current.filter(notice => notice.id !== id));
  }, []);
  const [isChatTyping, setIsChatTyping] = useState(false);
  const [smartDockExpanded, setSmartDockExpanded] = useState(false);
  const [pendingPhoto, setPendingPhoto] = useState(null);
  const [orderingProviders, setOrderingProviders] = useState([]);
  const [selectedOrderingProvider, setSelectedOrderingProvider] = useState(DEFAULT_ORDERING_PROVIDER);
  const [nutritionTargets, setNutritionTargets] = useState({
    daily_calorie_target: 2000,
    protein_target_g: 150,
    carbs_target_g: 200,
    fat_target_g: 67
  });
  const [nutritionDashboard, setNutritionDashboard] = useState({ days: [] });
  const [selectedNutritionDate, setSelectedNutritionDate] = useState("");
  const [nutritionTrendMetric, setNutritionTrendMetric] = useState("calories");
  const [expandedNutritionMeals, setExpandedNutritionMeals] = useState({ breakfast: true });
  const [nutritionEntryEditor, setNutritionEntryEditor] = useState(null);
  const [nutritionGoalEditor, setNutritionGoalEditor] = useState(null);
  const [isNutritionSaving, setIsNutritionSaving] = useState(false);
  const [providerCartReview, setProviderCartReview] = useState(null);
  const [providerLiveCart, setProviderLiveCart] = useState(null);
  const [providerConnectionStatus, setProviderConnectionStatus] = useState(null);
  const [providerSavedAddresses, setProviderSavedAddresses] = useState(null);
  const [isProviderAddressLoading, setIsProviderAddressLoading] = useState(false);
  const [providerAddressLoadError, setProviderAddressLoadError] = useState("");
  const [selectedProviderAddress, setSelectedProviderAddress] = useState("");
  const [selectedProviderPaymentMethod, setSelectedProviderPaymentMethod] = useState("");
  const [providerReviewAcknowledged, setProviderReviewAcknowledged] = useState(false);
  const [isUpdatingProviderReview, setIsUpdatingProviderReview] = useState(false);
  const [excludedProviderItemIds, setExcludedProviderItemIds] = useState([]);
  const [isProviderSyncing, setIsProviderSyncing] = useState(false);
  const [isProviderCartRefreshing, setIsProviderCartRefreshing] = useState(false);
  const [providerSyncStage, setProviderSyncStage] = useState("idle");
  const [groceryMutationCount, setGroceryMutationCount] = useState(0);
  const [isPlacingProviderOrder, setIsPlacingProviderOrder] = useState(false);
  const [isCheckingProviderPayment, setIsCheckingProviderPayment] = useState(false);
  const [isProviderOrderComplete, setIsProviderOrderComplete] = useState(false);
  const [providerPaymentCheckedAt, setProviderPaymentCheckedAt] = useState("");
  const [providerPaymentHandoff, setProviderPaymentHandoff] = useState(null);
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
  const pendingGroceryItemUpdatesRef = useRef(new Map());
  const providerSyncInFlightRef = useRef(false);
  const providerCartRefreshInFlightRef = useRef(false);
  const providerDraftRestoreInFlightRef = useRef(false);
  const providerSyncTimersRef = useRef([]);
  const providerSyncDialogRef = useRef(null);
  const selectedProvider = useMemo(() => (
    orderingProviders.find(provider => provider.id === selectedOrderingProvider) || {
      id: "",
      label: "ordering provider",
      brandLabel: "provider",
      enabled: false,
      state: "not_selected",
      message: "Select an ordering provider to continue.",
      capabilities: {},
      routes: null
    }
  ), [orderingProviders, selectedOrderingProvider]);
  const selectedProviderLabel = selectedProvider.label;
  const selectedProviderId = selectedProvider.id;
  const selectedProviderLiveCartRoute = selectedProvider.routes?.liveCart || "";
  const selectedProviderCheckoutDraftRoute = selectedProvider.routes?.checkoutDraft || "";
  const selectedProviderAddressesRoute = selectedProvider.routes?.addresses || "";
  const selectedProviderEnabled = Boolean(selectedProvider.enabled);
  const selectedProviderRequiresConnection = Boolean(selectedProvider.requires_connection);
  const selectedProviderRegistryState = selectedProvider.state || "unknown";
  const providerReviewLastValidatedAt = providerCartReview?.last_validated_at || "";
  const hasProviderCartDisplay = Boolean(providerLiveCart || providerCartReview);
  const applyProviderDraft = useCallback((review, { resetAcknowledgement = false } = {}) => {
    if (!review) {
      setProviderCartReview(null);
      setSelectedProviderPaymentMethod("");
      setProviderReviewAcknowledged(false);
      setProviderPaymentHandoff(null);
      return;
    }
    setProviderCartReview(review);
    setSelectedProviderAddress(review.selected_address_id || "");
    setSelectedProviderPaymentMethod(review.selected_payment_method_id || "");
    setProviderReviewAcknowledged(
      resetAcknowledgement ? false : Boolean(review.order_review_acknowledged)
    );
    setIsProviderOrderComplete(false);
  }, []);

  const invalidateProviderReview = useCallback(() => {
    setProviderCartReview(null);
    setSelectedProviderPaymentMethod("");
    setProviderReviewAcknowledged(false);
    setIsProviderOrderComplete(false);
    setProviderPaymentHandoff(null);
  }, []);

  const applyConfirmedGroceryCart = useCallback((items) => {
    const confirmedItems = Array.isArray(items) ? items : [];
    confirmedGroceryItemsRef.current = confirmedItems;
    setCustomGroceryItems(confirmedItems);
    invalidateProviderReview();
  }, [invalidateProviderReview]);

  const applyLiveState = useCallback((userName, data) => {
    if (data.pantry_stock) {
      setPantryStock(data.pantry_stock);
    }
    if (data.pantry) {
      setPantryRevision(Number(data.pantry.revision || 0));
      setPantryReviewedAt(data.pantry.reviewedAt || "");
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
      if (data.profile.household_size) {
        setHouseholdSize(data.profile.household_size);
      }
    }
    if (Array.isArray(data.household_members) && data.household_members.length > 0) {
      const members = data.household_members.map(member => ({
        id: member.id,
        value: member.name,
        label: member.name
      }));
      setHouseholdMembers(members);
      setUserProfiles(prev => members.reduce((profiles, member) => ({
        ...profiles,
        [member.value]: profiles[member.value] || { name: member.value, loggedMeals: [] }
      }), prev));
    }
    if (data.nutrition_targets) {
      setNutritionTargets(data.nutrition_targets);
    }
    if (data.meal_plan) {
      const nextMealPlan = data.meal_plan;
      const days = Array.isArray(nextMealPlan.days) ? nextMealPlan.days : [];
      const plannedDays = days.filter(hasPlannedMeals);
      setMealPlan(nextMealPlan);
      setSelectedPlanDate(current => {
        return plannedDays.some(day => day.plan_date === current)
          ? current
          : plannedDays.some(day => day.plan_date === nextMealPlan.today)
            ? nextMealPlan.today
            : plannedDays[0]?.plan_date || "";
      });
    }
    if (data.grocery_cart) {
      applyConfirmedGroceryCart(data.grocery_cart);
    }
    if (Object.prototype.hasOwnProperty.call(data, "latest_recipe_grocery_plan")) {
      setLatestRecipeGroceryPlan(data.latest_recipe_grocery_plan || null);
    }
  }, [applyConfirmedGroceryCart]);

  const fetchLiveState = async (userName, { includeMealPlan = true } = {}) => {
    const query = includeMealPlan ? "" : "?include_meal_plan=false";
    const res = await apiFetch(apiUrl(`/api/state/${userName}${query}`));
    await requireSuccessfulResponse(res);
    return res.json();
  };

  const loadNutritionDashboard = useCallback(async (userName, focusDate) => {
    const weekStart = getWeekStartForDate(focusDate);
    const weekEnd = shiftIsoDate(weekStart, 6);
    const res = await apiFetch(apiUrl(
      `/api/nutrition/${encodeURIComponent(userName)}?start_date=${weekStart}&end_date=${weekEnd}`
    ));
    await requireSuccessfulResponse(res);
    const data = await res.json();
    setNutritionDashboard(data);
    setNutritionTargets(data.targets);
    setSelectedNutritionDate(current => (
      data.days?.some(day => day.date === current) ? current : focusDate || data.today
    ));
    return data;
  }, []);

  const loadMealPlanWeek = useCallback(async (weekStart, focusDate = "") => {
    const query = weekStart ? `?week_start=${encodeURIComponent(weekStart)}` : "";
    const res = await apiFetch(apiUrl(`/api/meal-plan${query}`));
    await requireSuccessfulResponse(res);
    const data = await res.json();
    const days = Array.isArray(data.days) ? data.days : [];
    const plannedDays = days.filter(hasPlannedMeals);
    const nextDate = plannedDays.some(day => day.plan_date === focusDate)
      ? focusDate
      : plannedDays.some(day => day.plan_date === data.today)
        ? data.today
        : plannedDays[0]?.plan_date || "";
    setMealPlan(data);
    setSelectedPlanDate(nextDate);
    setExpandedMealKey(nextDate ? `${nextDate}-${getTimeBasedMealSlot()}` : "");
    return data;
  }, []);

  const syncProviderRegistry = useCallback(async () => {
    try {
      const res = await apiFetch(apiUrl("/api/grocery/providers"));
      await requireSuccessfulResponse(res);
      const data = await res.json();
      const providers = (Array.isArray(data.providers) ? data.providers : []).map(withProviderRoutes);
      setOrderingProviders(providers);
      setProviderConnectionStatus(null);
      const selectedByWorkflow = data.selected_provider || "";
      setSelectedOrderingProvider(current => {
        if (providers.some(provider => provider.id === current && provider.enabled)) return current;
        if (providers.some(provider => provider.id === selectedByWorkflow && provider.enabled)) return selectedByWorkflow;
        const connectedInstamart = providers.find(provider => provider.id === "swiggy_instamart" && provider.enabled && provider.state === "connected");
        const connectedZepto = providers.find(provider => provider.id === "zepto" && provider.enabled && provider.state === "configured");
        return connectedInstamart?.id || connectedZepto?.id || "";
      });
      return providers;
    } catch (e) {
      console.error("Failed to load grocery provider registry", e);
      setOrderingProviders([]);
      setProviderConnectionStatus({
        state: "failed",
        message: "Could not load ordering providers from Kitch."
      });
      return [];
    }
  }, []);

  const syncProviderAddresses = useCallback(async () => {
    if (!selectedProviderEnabled || !selectedProviderAddressesRoute) return null;
    if (selectedProviderRequiresConnection && selectedProviderRegistryState !== "connected") {
      setProviderSavedAddresses(null);
      setSelectedProviderAddress("");
      return null;
    }
    setIsProviderAddressLoading(true);
    setProviderAddressLoadError("");
    try {
      const res = await apiFetch(apiUrl(selectedProviderAddressesRoute));
      await requireSuccessfulResponse(res);
      const data = await res.json();
      const addresses = data.addresses || null;
      const options = collectObjectsWithAnyKey(addresses, ["address", "address_line", "addressLine", "id"]);
      const providerDefault = options.find(option => (
        option?.is_default === true
        || option?.isDefault === true
        || option?.default === true
        || option?.selected === true
      )) || options[0];
      const providerDefaultId = providerDefault
        ? optionValue(providerDefault, ["id", "address_id", "addressId"], "")
        : "";
      setProviderSavedAddresses(addresses);
      setSelectedProviderAddress(current => (
        options.some((option, idx) => optionValue(option, ["id", "address_id", "addressId"], `address-${idx}`) === current)
          ? current
          : providerDefaultId
      ));
      if (options.length === 0) {
        setProviderAddressLoadError(`${selectedProviderLabel} did not return any saved delivery addresses.`);
      }
      return addresses;
    } catch (e) {
      console.error(`Failed to load ${selectedProviderLabel} delivery addresses`, e);
      setProviderSavedAddresses(null);
      setSelectedProviderAddress("");
      setProviderAddressLoadError(e?.message || `Could not load ${selectedProviderLabel} delivery addresses.`);
      return null;
    } finally {
      setIsProviderAddressLoading(false);
    }
  }, [
    selectedProviderAddressesRoute,
    selectedProviderEnabled,
    selectedProviderLabel,
    selectedProviderRegistryState,
    selectedProviderRequiresConnection
  ]);

  const syncLiveState = async (userName) => {
    try {
      const data = await fetchLiveState(userName);
      applyLiveState(userName, data);
      setLiveStateUser(userName);
      return data;
    } catch (e) {
      console.error("Failed to sync live state with Kitch storage", e);
      return null;
    }
  };

  const applyBootstrappedHousehold = useCallback((data) => {
    const members = (data?.members || []).map(member => ({
      id: member.id,
      value: member.name,
      label: member.name
    }));
    if (members.length > 0) {
      setHouseholdMembers(members);
      setHouseholdSize(members.length);
      setActiveUser(members[0].value);
      setUserProfiles(members.reduce((profiles, member) => ({
        ...profiles,
        [member.value]: { name: member.value, loggedMeals: [] }
      }), {}));
    }
    setHouseholdBootstrap(data);
  }, []);

  const loadAuthSession = useCallback(async () => {
    // A hosted backend that has been idle cold-starts on this request, which
    // can take far longer than an ordinary call.
    const response = await apiFetch(apiUrl("/api/auth/session"), {
      credentials: "include",
      timeoutMs: SESSION_REQUEST_TIMEOUT_MS
    });
    await requireSuccessfulResponse(response);
    const session = await response.json();
    setAuthState({
      loading: false,
      required: Boolean(session.auth_required),
      authenticated: Boolean(session.authenticated),
      email: session.email || ""
    });
    if (session.authenticated && session.household) {
      applyBootstrappedHousehold({
        initialized: true,
        ...session.household
      });
    }
    return session;
  }, [applyBootstrappedHousehold]);

  // Keep retrying while the backend wakes: network failures, timeouts and 5xx
  // responses are transient during a cold start. Only after the wake window
  // closes does the splash offer a manual retry; it never drops the visitor on
  // the sign-in page with a misleading error.
  const startSession = useCallback(async () => {
    const runId = startupRunRef.current + 1;
    startupRunRef.current = runId;
    setStartupState({ attempts: 0, retrying: false, failed: false, message: "" });
    setAuthState(current => ({ ...current, loading: true }));
    const deadline = Date.now() + STARTUP_WAKE_WINDOW_MS;
    for (let attempt = 1; ; attempt += 1) {
      try {
        await loadAuthSession();
        return;
      } catch (error) {
        if (startupRunRef.current !== runId) return;
        const transient = error?.name === "AbortError"
          || !(error instanceof ApiResponseError)
          || error.status >= 500;
        if (!transient || Date.now() >= deadline) {
          setStartupState({
            attempts: attempt,
            retrying: false,
            failed: true,
            message: apiErrorMessage(error, "Kitch could not be reached.")
          });
          return;
        }
        setStartupState({ attempts: attempt, retrying: true, failed: false, message: "" });
        await new Promise(resolve => window.setTimeout(resolve, Math.min(8000, 1500 * attempt)));
        if (startupRunRef.current !== runId) return;
      }
    }
  }, [loadAuthSession]);

  useEffect(() => {
    const timer = window.setTimeout(() => { startSession(); }, 0);
    return () => window.clearTimeout(timer);
  }, [startSession]);

  useEffect(() => {
    const timer = window.setTimeout(() => setTimeGreeting(getTimeBasedGreeting()), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleGoogleCredential = useCallback(async ({ credential }) => {
    setAuthError("");
    try {
      const response = await apiFetch(apiUrl("/api/auth/google"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          credential,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"
        })
      });
      await requireSuccessfulResponse(response);
      const result = await response.json();
      setAuthState({
        loading: false,
        required: true,
        authenticated: true,
        email: result.email || ""
      });
      applyBootstrappedHousehold({
        initialized: true,
        ...(result.household || {})
      });
    } catch (error) {
      setAuthError(apiErrorMessage(error, "Google sign-in could not be completed."));
    }
  }, [applyBootstrappedHousehold]);

  const signOut = useCallback(async () => {
    try {
      const response = await apiFetch(apiUrl("/api/auth/logout"), {
        method: "POST",
        credentials: "include"
      });
      await requireSuccessfulResponse(response);
      window.google?.accounts?.id?.disableAutoSelect?.();
      setMemberEditorOpen(false);
      setHouseholdBootstrap(null);
      setHouseholdMembers([]);
      setAuthState({ loading: false, required: true, authenticated: false, email: "" });
    } catch (error) {
      setMemberEditorError(apiErrorMessage(error, "Kitch could not sign out."));
    }
  }, []);

  const renderGoogleButton = useCallback(() => {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID;
    if (!window.google?.accounts?.id || !googleButtonRef.current || !clientId) return;
    window.google.accounts.id.initialize({ client_id: clientId, callback: handleGoogleCredential });
    window.google.accounts.id.renderButton(googleButtonRef.current, {
      theme: "outline", size: "large", shape: "pill", text: "continue_with", width: 300
    });
  }, [handleGoogleCredential]);

  useEffect(() => {
    if (authState.required && !authState.authenticated) renderGoogleButton();
  }, [authState.authenticated, authState.required, renderGoogleButton]);

  const submitHouseholdOnboarding = async (event) => {
    event.preventDefault();
    const members = onboardingMembers.map(name => name.trim()).filter(Boolean);
    if (members.length === 0) {
      setOnboardingError("Add at least one household member.");
      return;
    }
    setIsOnboardingSaving(true);
    setOnboardingError("");
    try {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
      const response = await apiFetch(apiUrl("/api/household/bootstrap"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ members, timezone })
      });
      await requireSuccessfulResponse(response);
      applyBootstrappedHousehold(await response.json());
    } catch (error) {
      setOnboardingError(apiErrorMessage(error, "Kitch could not create the household."));
    } finally {
      setIsOnboardingSaving(false);
    }
  };

  useEffect(() => {
    if (authState.loading || (authState.required && !authState.authenticated)) return undefined;
    if (householdBootstrap?.initialized) return undefined;
    let ignore = false;
    apiFetch(apiUrl("/api/household/bootstrap"), { credentials: "include" })
      .then(requireSuccessfulResponse)
      .then(response => response.json())
      .then(data => {
        if (!ignore) applyBootstrappedHousehold(data);
      })
      .catch(error => {
        if (!ignore) {
          setOnboardingError(apiErrorMessage(error, "Kitch could not inspect household storage."));
          setHouseholdBootstrap({ initialized: false, unavailable: true });
        }
      });
    return () => { ignore = true; };
  }, [
    applyBootstrappedHousehold,
    authState.authenticated,
    authState.loading,
    authState.required,
    householdBootstrap?.initialized
  ]);

  const openMemberEditor = () => {
    setMemberNameDrafts(householdMembers.reduce((drafts, member) => ({ ...drafts, [member.id]: member.value }), {}));
    setMemberEditorError("");
    setMemberEditorOpen(true);
  };

  const saveMemberName = async (member) => {
    const nextName = String(memberNameDrafts[member.id] || "").trim();
    if (!nextName || nextName === member.value) return;
    setSavingMemberId(member.id);
    setMemberEditorError("");
    try {
      const response = await apiFetch(apiUrl(`/api/household/members/${encodeURIComponent(member.id)}`), {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: nextName })
      });
      await requireSuccessfulResponse(response);
      const result = await response.json();
      const oldName = member.value;
      const members = result.members.map(item => ({
        id: item.id, value: item.name, label: item.name
      }));
      setHouseholdMembers(members);
      setActiveUser(current => current === oldName ? nextName : current);
      setUserProfiles(current => {
        const next = { ...current, [nextName]: { ...(current[oldName] || {}), name: nextName } };
        if (nextName !== oldName) delete next[oldName];
        return next;
      });
    } catch (error) {
      setMemberEditorError(apiErrorMessage(error, "Kitch could not rename that member."));
    } finally {
      setSavingMemberId("");
    }
  };

  useEffect(() => {
    if (!householdBootstrap?.initialized) return undefined;
    let ignore = false;

    async function loadState() {
      try {
        await loadMealPlanWeek();
      } catch (error) {
        console.error("Failed to load the current meal-plan week", error);
      }
      if (ignore) return;
      try {
        const data = await fetchLiveState(activeUser, { includeMealPlan: false });
        if (!ignore) {
          applyLiveState(activeUser, data);
          setLiveStateUser(activeUser);
        }
      } catch (e) {
        console.error("Failed to sync live state with Kitch storage", e);
      }
    }

    loadState();
    return () => {
      ignore = true;
    };
  }, [activeUser, applyLiveState, householdBootstrap?.initialized, loadMealPlanWeek]);

  useEffect(() => {
    if (activeTab !== "groceries") return undefined;
    const timer = window.setTimeout(() => {
      syncProviderRegistry();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activeTab, syncProviderRegistry]);

  useEffect(() => {
    if (activeTab !== "analytics" || !mealPlan.today) return undefined;
    let ignore = false;
    const focusDate = selectedNutritionDate || mealPlan.today;
    const timer = window.setTimeout(() => {
      loadNutritionDashboard(activeUser, focusDate).catch(error => {
        if (!ignore) {
          console.error("Failed to load nutrition dashboard", error);
          triggerBannerAlert(apiErrorMessage(error, "Could not load nutrition history."), "error");
        }
      });
    }, 0);
    return () => {
      ignore = true;
      window.clearTimeout(timer);
    };
    // The selected day is navigated explicitly so it does not trigger duplicate requests.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, activeUser, mealPlan.today, loadNutritionDashboard]);

  useEffect(() => {
    if (activeTab !== "groceries" || !selectedProviderAddressesRoute) return undefined;
    const timer = window.setTimeout(() => syncProviderAddresses(), 0);
    return () => window.clearTimeout(timer);
  }, [activeTab, selectedProviderAddressesRoute, syncProviderAddresses]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connectedProvider = params.get("provider_connection");
    if (!connectedProvider || params.get("connection_status") !== "connected") return;
    window.history.replaceState({}, "", window.location.pathname);
    const timer = window.setTimeout(() => {
      setActiveTab("groceries");
      setSelectedOrderingProvider(connectedProvider);
      triggerBannerAlert("The household grocery-provider connection is ready.", "success");
      syncProviderRegistry();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [syncProviderRegistry, triggerBannerAlert]);

  useEffect(() => {
    if (!isProviderSyncing) return undefined;

    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    const focusFrame = window.requestAnimationFrame(() => {
      providerSyncDialogRef.current?.focus();
    });
    const keepFocusInDialog = (event) => {
      if (event.key === "Escape" || event.key === "Tab") {
        event.preventDefault();
        providerSyncDialogRef.current?.focus();
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
  }, [isProviderSyncing]);

  useEffect(() => {
    const syncMealFocus = () => {
      const nextMealSlot = getTimeBasedMealSlot();
      setCurrentMealSlot(previousMealSlot => {
        if (previousMealSlot !== nextMealSlot) {
          setExpandedMealKey(currentKey => (
            currentKey === `${selectedPlanDate}-${previousMealSlot}`
              ? `${selectedPlanDate}-${nextMealSlot}`
              : currentKey
          ));
        }

        return nextMealSlot;
      });
    };

    syncMealFocus();
    const interval = window.setInterval(syncMealFocus, 60 * 1000);
    return () => window.clearInterval(interval);
  }, [selectedPlanDate]);

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

  // 2. Computed values - Reactive Shopping Cart List
  const groceryList = useMemo(() => {
    return customGroceryItems;
  }, [customGroceryItems]);

  // Sync count statistics
  const totalCount = groceryList.length;
  const providerSelectedCount = groceryList.filter(item => cartPurchaseAmount(item) > 0 && !excludedProviderItemIds.includes(cartItemKey(item))).length;

  // 3. Application operations

  const beginGroceryMutation = () => {
    groceryMutationCountRef.current += 1;
    setGroceryMutationCount(groceryMutationCountRef.current);
  };

  const endGroceryMutation = () => {
    groceryMutationCountRef.current = Math.max(0, groceryMutationCountRef.current - 1);
    setGroceryMutationCount(groceryMutationCountRef.current);
  };

  const clearProviderSyncTimers = useCallback(() => {
    providerSyncTimersRef.current.forEach(timer => window.clearTimeout(timer));
    providerSyncTimersRef.current = [];
  }, []);

  const startProviderSyncProgress = useCallback(() => {
    clearProviderSyncTimers();
    setProviderSyncStage("preparing");
    providerSyncTimersRef.current = [
      window.setTimeout(() => setProviderSyncStage("transferring"), 700),
      window.setTimeout(() => setProviderSyncStage("finalizing"), 6000)
    ];
  }, [clearProviderSyncTimers]);

  const saveHouseholdProfile = async (size) => {
    const res = await apiFetch(apiUrl("/api/household/profile"), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        household_size: size
      })
    });
    await requireSuccessfulResponse(res);
    return res.json();
  };

  const updateHouseholdSize = async (size) => {
    const val = Math.max(1, parseInt(size) || 1);
    try {
      const data = await saveHouseholdProfile(val);
      setHouseholdSize(data.profile.household_size);
      triggerBannerAlert(`Updated household size to ${data.profile.household_size}.`);
    } catch (e) {
      console.error("Failed to update household size", e);
      triggerBannerAlert(apiErrorMessage(e, "Could not update the household size."));
    }
  };

  const switchActiveUser = (userName) => {
    setActiveUser(userName);
    triggerBannerAlert(`Now logging as ${userName}.`);
  };

  const toggleProviderItemSelection = (item) => {
    if (providerSyncInFlightRef.current || !item || cartPurchaseAmount(item) <= 0) return;
    const key = cartItemKey(item);
    if (!key) return;
    invalidateProviderReview();
    setExcludedProviderItemIds(prev => (
      prev.includes(key)
        ? prev.filter(id => id !== key)
        : [...prev, key]
    ));
  };

  const setProviderSelectionForItems = (items, selected) => {
    if (providerSyncInFlightRef.current) return;
    const keys = items
      .filter(item => cartPurchaseAmount(item) > 0)
      .map(cartItemKey)
      .filter(Boolean);
    if (!keys.length) return;
    invalidateProviderReview();
    setExcludedProviderItemIds(current => selected
      ? current.filter(key => !keys.includes(key))
      : [...new Set([...current, ...keys])]
    );
  };

  const updateGroceryCartItemDetails = async (item, updates) => {
    if (providerSyncInFlightRef.current || !item?.id) return;

    invalidateProviderReview();
    beginGroceryMutation();
    try {
      const res = await apiFetch(apiUrl(`/api/grocery/cart/items/${item.id}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates)
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      if (data.grocery_cart) {
        applyConfirmedGroceryCart(data.grocery_cart);
      }
      return true;
    } catch (e) {
      console.error("Failed to update grocery cart item", e);
      setCustomGroceryItems(confirmedGroceryItemsRef.current);
      triggerBannerAlert(apiErrorMessage(e, "Could not update the grocery item."));
      return false;
    } finally {
      endGroceryMutation();
    }
  };

  const flushQueuedGroceryItemUpdate = async (itemId) => {
    const entry = pendingGroceryItemUpdatesRef.current.get(itemId);
    if (!entry || entry.saving) return;

    entry.timer = null;
    entry.saving = true;
    const savedVersion = entry.version;
    const updates = { ...entry.updates };
    beginGroceryMutation();
    try {
      const res = await apiFetch(apiUrl(`/api/grocery/cart/items/${itemId}`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates)
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      const confirmedItems = Array.isArray(data.grocery_cart) ? data.grocery_cart : [];
      const currentEntry = pendingGroceryItemUpdatesRef.current.get(itemId);

      if (currentEntry?.version === savedVersion) {
        pendingGroceryItemUpdatesRef.current.delete(itemId);
        applyConfirmedGroceryCart(confirmedItems);
      } else {
        confirmedGroceryItemsRef.current = confirmedItems;
        setCustomGroceryItems(confirmedItems.map(current => {
          const pending = pendingGroceryItemUpdatesRef.current.get(current.id);
          return pending ? { ...current, ...pending.updates } : current;
        }));
      }
    } catch (error) {
      console.error("Failed to update grocery cart item", error);
      const currentEntry = pendingGroceryItemUpdatesRef.current.get(itemId);
      if (currentEntry?.version === savedVersion) {
        pendingGroceryItemUpdatesRef.current.delete(itemId);
        setCustomGroceryItems(confirmedGroceryItemsRef.current);
      }
      triggerBannerAlert(apiErrorMessage(error, "Could not update the grocery item."));
    } finally {
      endGroceryMutation();
      const currentEntry = pendingGroceryItemUpdatesRef.current.get(itemId);
      if (currentEntry) {
        currentEntry.saving = false;
        if (currentEntry.version !== savedVersion && !currentEntry.timer) {
          currentEntry.timer = window.setTimeout(() => flushQueuedGroceryItemUpdate(itemId), 0);
        }
      }
    }
  };

  const adjustGroceryCartItemAmount = (item, delta) => {
    if (providerSyncInFlightRef.current || !item?.id) return;

    const pending = pendingGroceryItemUpdatesRef.current.get(item.id) || {
      updates: {},
      version: 0,
      saving: false,
      timer: null
    };
    const currentAmount = Number(pending.updates.amount ?? item.amount) || 1;
    const nextAmount = Math.max(0.1, currentAmount + delta);
    pending.updates = { ...pending.updates, amount: nextAmount };
    pending.version += 1;
    if (pending.timer) window.clearTimeout(pending.timer);
    if (!pending.saving) {
      pending.timer = window.setTimeout(() => flushQueuedGroceryItemUpdate(item.id), 300);
    }
    pendingGroceryItemUpdatesRef.current.set(item.id, pending);

    invalidateProviderReview();
    setCustomGroceryItems(current => current.map(currentItem => (
      currentItem.id === item.id ? { ...currentItem, amount: nextAmount } : currentItem
    )));
  };

  const saveGroceryItemName = async (item) => {
    const nextName = groceryItemNameDraft.trim();
    if (!nextName) {
      triggerBannerAlert("Enter an item name before saving.");
      return;
    }
    if (nextName === item.name) {
      setEditingGroceryItemId(null);
      setGroceryItemNameDraft("");
      return;
    }
    const saved = await updateGroceryCartItemDetails(item, { name: nextName });
    if (saved) {
      setEditingGroceryItemId(null);
      setGroceryItemNameDraft("");
    }
  };

  const deleteGroceryCartItem = async (item) => {
    if (providerSyncInFlightRef.current || !item?.id) return;

    invalidateProviderReview();
    beginGroceryMutation();
    try {
      const res = await apiFetch(apiUrl(`/api/grocery/cart/items/${item.id}`), {
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
    if (providerSyncInFlightRef.current) return;

    invalidateProviderReview();
    beginGroceryMutation();
    try {
      const res = await apiFetch(apiUrl("/api/grocery/cart/planned"), {
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
    if (providerSyncInFlightRef.current || !name.trim()) return;

    invalidateProviderReview();
    const requestedItem = {
      name: name.trim(),
      amount: parseFloat(amount) || 1,
      unit: unit || "piece",
      category,
      source: "manual",
      checked: false,
      purchaseAmount: Number(amount) || 1,
      purchaseUnit: unit || "piece",
      pantryAllocation: {}
    };

    beginGroceryMutation();
    try {
      const res = await apiFetch(apiUrl("/api/grocery/cart/items"), {
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

  const syncNativeCartToProvider = async () => {
    if (providerSyncInFlightRef.current) return;
    if (!selectedProvider.enabled || !selectedProvider.routes) {
      triggerBannerAlert(`${selectedProvider.label} ordering is not available yet.`);
      return;
    }
    if (groceryMutationCountRef.current > 0) {
      triggerBannerAlert(`Please wait for the native cart to finish saving before moving items to ${selectedProvider.label}.`);
      return;
    }
    if (checkoutItems.length === 0) {
      triggerBannerAlert(`Select at least one native cart item for ${selectedProvider.label}.`);
      return;
    }
    if (!selectedProviderAddress) {
      triggerBannerAlert(`Select a ${selectedProvider.label} delivery address before moving items to the cart.`);
      return;
    }

    invalidateProviderReview();
    setProviderLiveCart(null);
    providerSyncInFlightRef.current = true;
    setIsProviderSyncing(true);
    startProviderSyncProgress();
    try {
      const res = await apiFetch(apiUrl(selectedProvider.routes.syncCart), {
        method: "POST",
        timeoutMs: PROVIDER_OPERATION_TIMEOUT_MS,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cart_item_ids: checkoutItems.map(item => item.id).filter(Boolean),
          selected_address_id: selectedProviderAddress
        })
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      const review = data.review || data;
      applyProviderDraft(review);
      clearProviderSyncTimers();
      setProviderSyncStage("complete");
      await new Promise(resolve => window.setTimeout(resolve, 450));
      triggerBannerAlert(data.status === "success"
        ? `${selectedProvider.label} cart sync completed for review.`
        : `${selectedProvider.label} cart sync needs attention.`);
    } catch (e) {
      console.error(`Failed to sync ${selectedProvider.label} cart`, e);
      clearProviderSyncTimers();
      setProviderSyncStage("failed");
      await new Promise(resolve => window.setTimeout(resolve, 650));
      triggerBannerAlert(apiErrorMessage(e, `Failed to sync the native cart to ${selectedProvider.label}.`));
    } finally {
      clearProviderSyncTimers();
      providerSyncInFlightRef.current = false;
      setIsProviderSyncing(false);
      setProviderSyncStage("idle");
      syncProviderRegistry();
    }
  };

  const refreshProviderCart = useCallback(async ({ announce = true } = {}) => {
    if (providerCartRefreshInFlightRef.current || !selectedProviderLiveCartRoute) return null;
    providerCartRefreshInFlightRef.current = true;
    setIsProviderCartRefreshing(true);
    try {
      const res = await apiFetch(apiUrl(selectedProviderLiveCartRoute), {
        timeoutMs: PROVIDER_OPERATION_TIMEOUT_MS
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      setProviderLiveCart(data);
      if (announce) {
        triggerBannerAlert(`${selectedProviderLabel} cart refreshed.`);
      }
      return data;
    } catch (e) {
      if (announce) {
        triggerBannerAlert(apiErrorMessage(e, `Could not refresh the ${selectedProviderLabel} cart.`));
      }
      return null;
    } finally {
      providerCartRefreshInFlightRef.current = false;
      setIsProviderCartRefreshing(false);
    }
  }, [
    selectedProviderLabel,
    selectedProviderLiveCartRoute,
    triggerBannerAlert
  ]);

  const restoreProviderCheckoutDraft = useCallback(async () => {
    if (
      providerDraftRestoreInFlightRef.current
      || !selectedProviderCheckoutDraftRoute
    ) return null;
    providerDraftRestoreInFlightRef.current = true;
    try {
      const res = await apiFetch(apiUrl(selectedProviderCheckoutDraftRoute));
      await requireSuccessfulResponse(res);
      const data = await res.json();
      let review = data.draft || null;
      if (!review || !Array.isArray(review.native_items) || review.native_items.length === 0) {
        return null;
      }

      if (review.order_review_acknowledged || (
        review.selected_payment_method_id && selectedProviderId !== "swiggy_instamart"
      )) {
        const resetPayload = { order_review_acknowledged: false };
        if (selectedProviderId !== "swiggy_instamart") {
          resetPayload.selected_payment_method_id = null;
        }
        const resetRes = await apiFetch(apiUrl(selectedProviderCheckoutDraftRoute), {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(resetPayload)
        });
        await requireSuccessfulResponse(resetRes);
        review = (await resetRes.json()).draft || review;
      }
      applyProviderDraft(review, { resetAcknowledgement: true });
      return review;
    } catch (e) {
      console.error(`Failed to restore ${selectedProviderLabel} checkout draft`, e);
      triggerBannerAlert(apiErrorMessage(e, `Could not restore the ${selectedProviderLabel} checkout review.`));
      return null;
    } finally {
      providerDraftRestoreInFlightRef.current = false;
    }
  }, [
    applyProviderDraft,
    selectedProviderCheckoutDraftRoute,
    selectedProviderId,
    selectedProviderLabel,
    triggerBannerAlert
  ]);

  useEffect(() => {
    if (activeTab !== "groceries" || liveStateUser !== activeUser) return undefined;
    const timer = window.setTimeout(() => restoreProviderCheckoutDraft(), 0);
    return () => window.clearTimeout(timer);
  }, [activeTab, activeUser, liveStateUser, restoreProviderCheckoutDraft]);

  useEffect(() => {
    if (
      activeTab !== "groceries"
      || !selectedProviderLiveCartRoute
      || !selectedProviderEnabled
      || (selectedProviderRequiresConnection && providerConnectionStatus?.state !== "connected")
    ) return undefined;
    const refreshIfDue = () => {
      const readAt = Date.parse(providerLiveCart?.read_at || providerReviewLastValidatedAt);
      if (
        document.visibilityState === "visible"
        && (!Number.isFinite(readAt) || Date.now() - readAt >= PROVIDER_REVALIDATE_AFTER_MS)
      ) {
        refreshProviderCart({ announce: false });
      }
    };
    const refreshTimer = window.setInterval(refreshIfDue, PROVIDER_REVALIDATE_AFTER_MS);
    window.addEventListener("focus", refreshIfDue);
    document.addEventListener("visibilitychange", refreshIfDue);
    refreshIfDue();
    return () => {
      window.clearInterval(refreshTimer);
      window.removeEventListener("focus", refreshIfDue);
      document.removeEventListener("visibilitychange", refreshIfDue);
    };
  }, [
    activeTab,
    providerLiveCart?.read_at,
    providerReviewLastValidatedAt,
    refreshProviderCart,
    selectedProviderEnabled,
    selectedProviderLiveCartRoute,
    selectedProviderRequiresConnection,
    providerConnectionStatus?.state
  ]);

  const updateProviderReview = async (updates) => {
    if (!providerCartReview?.review_id || !selectedProvider.routes) return null;
    setIsUpdatingProviderReview(true);
    try {
      const res = await apiFetch(apiUrl(selectedProvider.routes.checkoutDraft), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates)
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      if (data.draft) {
        applyProviderDraft(data.draft);
        return data.draft;
      }
    } catch (e) {
      console.error(`Failed to update ${selectedProvider.label} review`, e);
      triggerBannerAlert(apiErrorMessage(e, `Could not update ${selectedProvider.label} review selection.`));
    } finally {
      setIsUpdatingProviderReview(false);
    }
    return null;
  };

  const selectProviderSyncAddress = (value) => {
    if (providerSyncInFlightRef.current) return;
    setSelectedProviderAddress(value);
    invalidateProviderReview();
  };

  const selectOrderingProvider = (provider) => {
    if (!provider.enabled || providerSyncInFlightRef.current) return;
    if (provider.id === selectedOrderingProvider) return;
    setSelectedOrderingProvider(provider.id);
    setProviderConnectionStatus(null);
    setProviderSavedAddresses(null);
    setProviderAddressLoadError("");
    setSelectedProviderAddress("");
    setProviderLiveCart(null);
    invalidateProviderReview();
    apiFetch(apiUrl("/api/grocery/provider-selection"), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected_provider: provider.id })
    }).catch(error => console.error("Failed to remember ordering provider", error));
  };

  const startProviderConnection = async (provider) => {
    if (!provider?.routes?.connectionStart || providerSyncInFlightRef.current) return;
    try {
      const res = await apiFetch(apiUrl(provider.routes.connectionStart), { method: "POST" });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      if (!data.authorization_url) throw new Error("The provider did not return an authorization URL.");
      window.location.assign(data.authorization_url);
    } catch (e) {
      triggerBannerAlert(apiErrorMessage(e, `Could not connect ${provider.label}.`));
    }
  };

  const disconnectProvider = async (provider) => {
    if (!provider?.routes?.connection || providerSyncInFlightRef.current) return;
    try {
      const res = await apiFetch(apiUrl(provider.routes.connection), { method: "DELETE" });
      await requireSuccessfulResponse(res);
      invalidateProviderReview();
      setProviderLiveCart(null);
      setProviderSavedAddresses(null);
      setSelectedProviderAddress("");
      await syncProviderRegistry();
      triggerBannerAlert(`${provider.label} disconnected from this household.`);
    } catch (e) {
      triggerBannerAlert(apiErrorMessage(e, `Could not disconnect ${provider.label}.`));
    }
  };

  const placeProviderOrder = async () => {
    if (providerSyncInFlightRef.current) return;
    if (!providerCartReview?.review_id || !providerCartReview?.confirmation_token) {
      triggerBannerAlert(`Final ${selectedProvider.label} approval token is missing. Sync the cart again before placing the order.`);
      return;
    }
    if (!providerReviewAcknowledged) {
      triggerBannerAlert(`Review and acknowledge the exact ${selectedProvider.label} cart before confirming the order.`);
      return;
    }

    // UPI payments finish on Instamart's own page (a QR on a computer, the UPI
    // app on a phone). Open the tab now, inside the click, so the browser does
    // not block it, and point it at Swiggy's page once the order exists.
    const chosenPayment = providerPaymentOptions.find(option => (
      String(optionValue(option, ["id", "payment_method_id", "paymentMethodId", "method"], "")) === String(effectiveProviderPaymentMethod)
    ));
    let paymentWindow = null;
    if (["upi_qr", "upi_intent"].includes(chosenPayment?.flow)) {
      paymentWindow = window.open("", "kitch-instamart-payment");
      if (paymentWindow) {
        paymentWindow.opener = null;
        paymentWindow.document.title = "Opening Instamart payment…";
        paymentWindow.document.body.innerHTML = '<p style="font:16px system-ui;margin:40vh auto;text-align:center;color:#474f42">Placing your order with Instamart…<br>The payment page opens here in a moment.</p>';
      }
    }

    providerSyncInFlightRef.current = true;
    setIsProviderSyncing(true);
    startProviderSyncProgress();
    setIsPlacingProviderOrder(true);
    try {
      const latestReview = await updateProviderReview({
        selected_payment_method_id: effectiveProviderPaymentMethod || null,
        order_review_acknowledged: true
      }) || providerCartReview;
      const res = await apiFetch(apiUrl(selectedProvider.routes.placeOrder), {
        method: "POST",
        timeoutMs: PROVIDER_OPERATION_TIMEOUT_MS,
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
      setProviderCartReview(data.review || data);
      const handoff = data.result?.payment_state || null;
      setProviderPaymentHandoff(handoff && (
        handoff.upi_intent_url || handoff.bridge_url || handoff.is_qr_flow
      ) ? {
        ...handoff,
        remaining_poll_ms: Number(handoff.max_poll_time_ms || 120000)
      } : null);
      setIsProviderOrderComplete(data.status === "success");
      const paymentUrl = safeProviderPaymentUrl(handoff?.bridge_url || handoff?.upi_intent_url);
      if (paymentWindow && !paymentWindow.closed) {
        if (paymentUrl && /^https?:/.test(paymentUrl)) paymentWindow.location.replace(paymentUrl);
        else paymentWindow.close();
      }
      clearProviderSyncTimers();
      setProviderSyncStage("complete");
      // A UPI/QR order is created first and confirmed once paid, so
      // "payment_pending" is the expected next step, not a failure.
      if (data.status === "success") {
        triggerBannerAlert(data.result?.message || `${selectedProvider.label} order placed.`, "info");
      } else if (data.status === "payment_pending") {
        triggerBannerAlert(
          handoff?.is_qr_flow
            ? `${selectedProvider.label} created your order. Scan the QR on the payment page to confirm it.`
            : `${selectedProvider.label} created your order. Finish the payment to confirm it.`,
          "info"
        );
      } else {
        triggerBannerAlert(data.result?.message || `${selectedProvider.label} order could not be placed.`, "error");
      }
    } catch (e) {
      console.error(`Failed to place ${selectedProvider.label} order`, e);
      if (paymentWindow && !paymentWindow.closed) paymentWindow.close();
      const changedDraft = e instanceof ApiResponseError ? e.detail?.draft : null;
      if (changedDraft) {
        applyProviderDraft(changedDraft, { resetAcknowledgement: true });
      }
      clearProviderSyncTimers();
      setProviderSyncStage("failed");
      triggerBannerAlert(apiErrorMessage(e, `Failed to contact the backend ${selectedProvider.label} order endpoint.`));
    } finally {
      clearProviderSyncTimers();
      providerSyncInFlightRef.current = false;
      setIsProviderSyncing(false);
      setProviderSyncStage("idle");
      setIsPlacingProviderOrder(false);
    }
  };

  // Status checks run inline while the person is paying (often scanning a QR
  // on another screen), so they never take over the page with a dialog.
  const checkProviderPaymentStatus = useCallback(async ({ manual = false } = {}) => {
    if (!selectedProvider?.routes?.paymentStatus || providerSyncInFlightRef.current) return;
    providerSyncInFlightRef.current = true;
    setIsCheckingProviderPayment(true);
    try {
      const res = await apiFetch(apiUrl(selectedProvider.routes.paymentStatus), {
        method: "POST",
        timeoutMs: PROVIDER_OPERATION_TIMEOUT_MS
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      const review = data.review || data;
      applyProviderDraft(review);
      setProviderPaymentCheckedAt(new Date().toISOString());
      setIsProviderOrderComplete(review.status === "ordered");
      if (review.status === "ordered") {
        setProviderPaymentHandoff(null);
        triggerBannerAlert(`${selectedProvider.label} confirmed the payment and order.`, "success");
      } else if (review.status !== "payment_pending") {
        setProviderPaymentHandoff(null);
        triggerBannerAlert(`The ${selectedProvider.label} payment did not go through.`, "error");
      } else if (manual) {
        triggerBannerAlert(`The ${selectedProvider.label} payment is still ${review.payment_state?.status || "pending"}.`);
      }
    } catch (e) {
      if (manual) triggerBannerAlert(apiErrorMessage(e, `Could not check the ${selectedProvider.label} payment status.`));
    } finally {
      providerSyncInFlightRef.current = false;
      setIsCheckingProviderPayment(false);
    }
  }, [
    applyProviderDraft,
    selectedProvider,
    triggerBannerAlert
  ]);

  useEffect(() => {
    if (!providerPaymentHandoff || providerCartReview?.status !== "payment_pending") return undefined;
    const interval = Math.max(2000, Number(providerPaymentHandoff.polling_interval_ms || 5000));
    const remaining = Number(providerPaymentHandoff.remaining_poll_ms || 0);
    if (remaining < interval) return undefined;
    const timer = window.setTimeout(async () => {
      await checkProviderPaymentStatus();
      setProviderPaymentHandoff(current => current ? {
        ...current,
        remaining_poll_ms: Math.max(0, Number(current.remaining_poll_ms || 0) - interval)
      } : null);
    }, interval);
    return () => window.clearTimeout(timer);
  }, [
    checkProviderPaymentStatus,
    providerCartReview?.status,
    providerPaymentHandoff,
    isCheckingProviderPayment
  ]);

  const resetDailyLogs = async () => {
    const diaryDate = selectedNutritionDate || nutritionDashboard.today;
    setConfirmationDialog({
      title: "Clear this nutrition day?",
      message: `This removes every nutrition entry for ${activeUser} on ${formatPlanDate(diaryDate, { month: "long", day: "numeric", year: "numeric" })}.`,
      confirmLabel: "Clear day",
      onConfirm: async () => {
        const res = await apiFetch(apiUrl(`/api/diary/clear/${encodeURIComponent(activeUser)}`), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmed: true, date: diaryDate }),
        });
        await requireSuccessfulResponse(res);
        await loadNutritionDashboard(activeUser, diaryDate);
        await syncLiveState(activeUser);
        triggerBannerAlert(`Cleared nutrition entries for ${formatPlanDate(diaryDate, { month: "short", day: "numeric" })}.`);
      },
    });
  };

  const navigateNutritionDate = async (nextDate) => {
    if (!nextDate) return;
    setSelectedNutritionDate(nextDate);
    setNutritionEntryEditor(null);
    const currentStart = nutritionDashboard.start_date;
    const currentEnd = nutritionDashboard.end_date;
    if (!currentStart || nextDate < currentStart || nextDate > currentEnd) {
      try {
        await loadNutritionDashboard(activeUser, nextDate);
      } catch (error) {
        triggerBannerAlert(apiErrorMessage(error, "Could not load that nutrition week."));
      }
    }
  };

  const openNutritionEntryEditor = (mealType, entry = null) => {
    setNutritionEntryEditor(entry ? {
      id: entry.id,
      meal_name: entry.name,
      quantity: entry.quantity,
      unit: entry.unit,
      meal_type: entry.meal_type,
      calories: entry.calories,
      protein: entry.macros.protein,
      carbs: entry.macros.carbs,
      fat: entry.macros.fat,
      fiber: entry.macros.fiber,
      consumed_at: entry.consumed_at
    } : { ...EMPTY_NUTRITION_ENTRY, meal_type: mealType });
    setExpandedNutritionMeals(current => ({ ...current, [mealType]: true }));
  };

  const saveNutritionEntry = async () => {
    if (!nutritionEntryEditor?.meal_name?.trim()) {
      triggerBannerAlert("Add a food name before saving.");
      return;
    }
    setIsNutritionSaving(true);
    try {
      const meal = NUTRITION_MEALS.find(item => item.id === nutritionEntryEditor.meal_type);
      const consumedAt = nutritionEntryEditor.consumed_at || (
        `${selectedNutritionDate}T${meal?.defaultTime || "12:00"}:00`
      );
      const payload = { ...nutritionEntryEditor, consumed_at: consumedAt };
      const route = nutritionEntryEditor.id
        ? `/api/diary/${encodeURIComponent(activeUser)}/entries/${nutritionEntryEditor.id}`
        : `/api/diary/${encodeURIComponent(activeUser)}/entries`;
      const res = await apiFetch(apiUrl(route), {
        method: nutritionEntryEditor.id ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      await requireSuccessfulResponse(res);
      setNutritionEntryEditor(null);
      await loadNutritionDashboard(activeUser, selectedNutritionDate);
      await syncLiveState(activeUser);
      triggerBannerAlert(nutritionEntryEditor.id ? "Nutrition entry updated." : "Food added to the diary.");
    } catch (error) {
      triggerBannerAlert(apiErrorMessage(error, "The nutrition entry could not be saved."));
    } finally {
      setIsNutritionSaving(false);
    }
  };

  const deleteNutritionEntry = async (entryId) => {
    try {
      const res = await apiFetch(apiUrl(`/api/diary/${encodeURIComponent(activeUser)}/entries/${entryId}`), {
        method: "DELETE"
      });
      await requireSuccessfulResponse(res);
      await loadNutritionDashboard(activeUser, selectedNutritionDate);
      await syncLiveState(activeUser);
      triggerBannerAlert("Nutrition entry removed.");
    } catch (error) {
      triggerBannerAlert(apiErrorMessage(error, "The nutrition entry could not be removed."));
    }
  };

  const saveNutritionGoals = async () => {
    if (!nutritionGoalEditor) return;
    setIsNutritionSaving(true);
    try {
      const res = await apiFetch(apiUrl(`/api/nutrition/targets/${encodeURIComponent(activeUser)}`), {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nutritionGoalEditor)
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      setNutritionTargets(data.nutrition_targets);
      setNutritionDashboard(current => ({ ...current, targets: data.nutrition_targets }));
      setNutritionGoalEditor(null);
      triggerBannerAlert("Daily nutrition goals updated.");
    } catch (error) {
      triggerBannerAlert(apiErrorMessage(error, "Nutrition goals could not be updated."));
    } finally {
      setIsNutritionSaving(false);
    }
  };

  const patchPantry = async (changes) => {
    try {
      const res = await apiFetch(apiUrl("/api/pantry"), {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: pantryRevision, changes }),
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      setPantryStock(Array.isArray(data.pantry) ? data.pantry : []);
      setPantryRevision(Number(data.revision || pantryRevision));
      setPantryReviewedAt(data.reviewed_at || pantryReviewedAt);
      return true;
    } catch (error) {
      triggerBannerAlert(apiErrorMessage(error, "The pantry change could not be saved."));
      return false;
    }
  };

  const reconcileCartWithPantry = async () => {
    try {
      const res = await apiFetch(apiUrl("/api/grocery-cart/reconcile-pantry"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: pantryRevision }),
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      const confirmedItems = Array.isArray(data.grocery_cart) ? data.grocery_cart : [];
      confirmedGroceryItemsRef.current = confirmedItems;
      setCustomGroceryItems(confirmedItems);
      if (data.provider_review_invalidated) invalidateProviderReview();
      triggerBannerAlert(
        data.provider_review_invalidated
          ? "Native cart updated from the pantry. The previous provider review was cleared."
          : "Native cart checked against the pantry. No purchase quantities changed."
      );
    } catch (error) {
      triggerBannerAlert(apiErrorMessage(error, "The native cart could not be updated from the pantry."));
    }
  };

  const savePantryRow = async (item) => {
    const draft = pantryDrafts[item.id] || item;
    const saved = await patchPantry([{ action: "set", id: item.id, name: draft.name,
      amount: Number(draft.amount), unit: draft.unit || "piece" }]);
    if (saved) {
      setPantryDrafts(current => { const next = { ...current }; delete next[item.id]; return next; });
      setEditingPantryItemId(null);
    }
  };

  const markPantryEmpty = () => setConfirmationDialog({
    title: "Mark the pantry empty?",
    message: `This will remove all ${pantryStock.length} pantry item(s). The native cart will not change unless you explicitly update it from the pantry.`,
    confirmLabel: "Mark empty",
    onConfirm: async () => {
      const res = await apiFetch(apiUrl("/api/pantry"), {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: pantryRevision, items: [], confirmed: true }),
      });
      await requireSuccessfulResponse(res);
      const data = await res.json();
      setPantryStock(Array.isArray(data.pantry) ? data.pantry : []);
      setPantryRevision(Number(data.revision || pantryRevision));
      setPantryReviewedAt(data.reviewed_at || pantryReviewedAt);
      triggerBannerAlert("Pantry marked empty.");
    },
  });

  const stagePhotoForInput = (file, source) => {
    if (!file) return;

    setPendingPhoto({
      file,
      source
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
        planner_context: {
          visible_week_start: mealPlan.week_start || "",
          selected_date: selectedPlanDate || mealPlan.today || ""
        },
        pantry_stock: pantryStock,
        grocery_list: groceryList
      };

      const res = await apiFetch(apiUrl("/api/chat"), {
        method: "POST",
        timeoutMs: AGENT_REQUEST_TIMEOUT_MS,
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
          time: responseTime,
          action: response.action || null
        }
      ]);

      await syncLiveState(activeUser);

      if (response.action) {
        const act = response.action;
        if (act.type === "UPDATE_PLANNER") {
          const focusDate = act.focus_date || act.affected_dates?.[0];
          if (focusDate) {
            await loadMealPlanWeek(getWeekStartForDate(focusDate), focusDate);
          }
        } else if (act.type === "UPDATE_NUTRITION") {
          const focusDate = act.focus_date || act.affected_dates?.[0] || mealPlan.today;
          if (focusDate) {
            await loadNutritionDashboard(activeUser, focusDate);
          }
        } else if (act.type === "UPDATE_PANTRY") {
        } else if (act.type === "UPDATE_GROCERY_CART") {
        } else if (act.type === "UPDATE_PROVIDER_CART") {
          const actionProvider = act.provider || "swiggy_instamart";
          setSelectedOrderingProvider(actionProvider);
          setActiveTab("groceries");
          if (actionProvider === selectedOrderingProvider) {
            await restoreProviderCheckoutDraft();
          }
          triggerBannerAlert("Provider cart prepared. Review the confirmed products before checkout.");
        } else if (act.type === "CONFIRM_DESTRUCTIVE_ACTION") {
          setConfirmationDialog({
            title: act.impact?.title || "Confirm this change?",
            message: act.impact?.message || "This action changes shared household state.",
            confirmLabel: "Confirm",
            onConfirm: async () => {
              const confirmRes = await apiFetch(apiUrl(`/api/agent-actions/${act.action_id}/confirm`), { method: "POST" });
              await requireSuccessfulResponse(confirmRes);
              await syncLiveState(activeUser);
              triggerBannerAlert("Confirmed change completed.");
            },
            onCancel: async () => {
              await apiFetch(apiUrl(`/api/agent-actions/${act.action_id}/cancel`), { method: "POST" });
            },
          });
        }
      }
    } catch (e) {
      console.error("Real API chat processing error", e);
      const message = apiErrorMessage(
        e,
        `I was unable to reach the Kitch backend server on \`${apiUrl("")}\`. Please make sure the FastAPI server is running.`
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
      handleRealPhotoUpload(photo.file, text);
      return;
    }

    if (text) {
      setChatInput("");
      sendChatMessage(text);
    }
  };

  // 5. Real Vision Camera scanning & upload workflow
  const handleRealPhotoUpload = async (file, accompanyingText = "", classificationOverride = "") => {
    if (!file) return;

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const trimmedText = accompanyingText.trim();
    const scanLabel = "image";

    setSmartDockExpanded(true);
    if (!classificationOverride) {
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
    }

    // Show live scanning overlay
    setScanningOverlay({
      active: true,
      title: "Kitch Vision Scanner",
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
      formData.append("message", trimmedText);
      if (classificationOverride) formData.append("classification_override", classificationOverride);

      setScanningOverlay(prev => ({
        ...prev,
        steps: [...prev.steps, "🧠 Running ADK multimodal vision analysis..."]
      }));

      const res = await apiFetch(apiUrl("/api/upload-photo"), {
        method: "POST",
        timeoutMs: AGENT_REQUEST_TIMEOUT_MS,
        body: formData
      });

      await requireSuccessfulResponse(res);

      setScanningOverlay(prev => ({
        ...prev,
        steps: [...prev.steps, "✅ Success! Parsing OCR payload outcomes..."]
      }));

      const data = await res.json();
      if (data.status === "needs_clarification") {
        setScanningOverlay({ active: false, title: "", steps: [], fileName: "" });
        setPendingPhoto({ file, source: "clarification", accompanyingText: trimmedText });
        setConfirmationDialog({
          title: data.question || "How should Kitch treat this image?",
          message: "Nothing has been saved yet.",
          choices: [
            { label: "Treat as meal", action: () => handleRealPhotoUpload(file, trimmedText, "meal") },
            { label: "Treat as pantry", action: () => handleRealPhotoUpload(file, trimmedText, "pantry") },
          ],
        });
        return;
      }
      
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
          time: responseTime,
          action: data.classification === "pantry" ? { type: "UPDATE_PANTRY" } : data.classification === "meal" ? { type: "UPDATE_NUTRITION" } : null
        }
      ]);

      setPendingPhoto(null);
      triggerBannerAlert(data.classification === "pantry" ? "Pantry updated from image." : "Meal logged from image.");

    } catch (e) {
      console.error("Real photo upload error", e);
      setScanningOverlay({ active: false, title: "", steps: [], fileName: "" });
      const message = apiErrorMessage(
        e,
        `Failed to reach \`/api/upload-photo\` on \`${apiUrl("")}\`. Is your FastAPI backend running?`
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

  const draftMealSwapPrompt = (planDate, slot) => {
    setActiveTab("planner");
    setSelectedPlanDate(planDate);
    setExpandedMealKey(`${planDate}-${slot}`);
    setChatInput(`Change ${formatPlanDate(planDate, { weekday: "long", month: "long", day: "numeric", year: "numeric" })} ${slot} to `);
  };

  // Personal nutrition goals are stored in the nutrition domain, independently
  // of free-form dietary preferences in agent memory.
  const targetCalories = Number(nutritionTargets.daily_calorie_target);
  const targetProtein = Number(nutritionTargets.protein_target_g);
  const targetCarbs = Number(nutritionTargets.carbs_target_g);
  const targetFat = Number(nutritionTargets.fat_target_g);

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
  const protPerc = Math.min(100, Math.round((loggedProt / targetProtein) * 100));
  const carbPerc = Math.min(100, Math.round((loggedCarb / targetCarbs) * 100));
  const fatPerc = Math.min(100, Math.round((loggedFat / targetFat) * 100));

  const selectedNutritionDay = nutritionDashboard.days?.find(
    day => day.date === selectedNutritionDate
  ) || { entries: [], totals: { calories: 0, protein: 0, carbs: 0, fat: 0, fiber: 0 } };
  const nutritionTotals = selectedNutritionDay.totals;
  const nutritionCalPercentage = Math.min(
    100, Math.round((Number(nutritionTotals.calories || 0) / targetCalories) * 100)
  );
  const nutritionStrokeDashoffset = 471.2 - (471.2 * nutritionCalPercentage) / 100;
  const nutritionMacroRows = [
    { key: "protein", label: "Protein", value: Number(nutritionTotals.protein || 0), target: targetProtein, klass: "protein" },
    { key: "carbs", label: "Carbs", value: Number(nutritionTotals.carbs || 0), target: targetCarbs, klass: "carbs" },
    { key: "fat", label: "Fats", value: Number(nutritionTotals.fat || 0), target: targetFat, klass: "fat" }
  ].map(row => ({ ...row, percent: Math.min(100, Math.round((row.value / row.target) * 100)) }));
  const nutritionEntriesByMeal = NUTRITION_MEALS.reduce((groups, meal) => ({
    ...groups,
    [meal.id]: (selectedNutritionDay.entries || []).filter(entry => entry.meal_type === meal.id)
  }), {});
  const nutritionTrendTarget = {
    calories: targetCalories, protein: targetProtein, carbs: targetCarbs, fat: targetFat
  }[nutritionTrendMetric];
  const nutritionTrendMax = Math.max(
    nutritionTrendTarget,
    ...(nutritionDashboard.days || []).map(day => Number(day.totals?.[nutritionTrendMetric] || 0)),
    1
  );
  const nutritionTip = nutritionTotals.calories <= 0
    ? "Log a meal or scan a plate to start today’s nutrition picture."
    : nutritionMacroRows.find(row => row.percent < 60)
      ? `${nutritionMacroRows.find(row => row.percent < 60).label} is furthest from today’s goal so far.`
      : nutritionCalPercentage > 100
        ? "Today’s logged calories are above the current goal. Review portions if anything looks off."
        : "Your logged intake is progressing steadily toward today’s goals.";

  // Items checkout checklist
  const checkoutItems = groceryList
    .filter(item => cartPurchaseAmount(item) > 0 && !excludedProviderItemIds.includes(cartItemKey(item)))
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
  const activeRecipeTitle = getRecipeCardTitle(activeRecipeCard, "");
  const activeRecipeIngredients = normalizeList(
    activeRecipeCard?.ingredients ||
    activeRecipeCard?.ingredientList ||
    activeRecipeCard?.ingredient_list ||
    latestRecipeGroceryPlan?.ingredients
  ).filter(ingredient => getIngredientName(ingredient));
  const activeRecipeSteps = getRecipeSteps(activeRecipeCard);
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
  const recipeNeededCartItems = recipeCartItems.filter(item => cartPurchaseAmount(item) > 0);

  const groupedGroceryCart = groceryList.reduce((groups, item) => {
    const category = item.category || "General";
    if (!groups[category]) groups[category] = [];
    groups[category].push(item);
    return groups;
  }, {});
  const groceryCategoryCount = Object.keys(groupedGroceryCart).length;
  const stockedCount = groceryList.filter(item => cartPurchaseAmount(item) <= 0).length;
  const pendingBuyCount = checkoutItems.length;
  const eligibleBuyCount = groceryList.filter(item => cartPurchaseAmount(item) > 0).length;
  const providerReviewStatus = providerCartReview?.status;
  const providerMatchedItems = Array.isArray(providerCartReview?.matched_items)
    ? providerCartReview.matched_items
    : Array.isArray(providerCartReview?.result?.items) ? providerCartReview.result.items : [];
  const providerLiveCartItems = Array.isArray(providerLiveCart?.provider_cart?.items)
    ? providerLiveCart.provider_cart.items
    : [];
  // Items added straight to Instamart are part of the order, so the review
  // lists them beside the rows that came from the Kitch shopping list.
  const providerExtraItems = providerLiveCart
    ? []
    : (providerCartReview?.checkout_context?.extra_provider_items || []);
  const providerDisplayedItems = providerLiveCart
    ? providerLiveCartItems.map(item => ({ matched_product: item, cart_item: item }))
    : [
      ...providerMatchedItems,
      ...providerExtraItems.map(item => ({ matched_product: item, cart_item: item, extra: true }))
    ];
  const providerCartRows = providerDisplayedItems
    .map((match, index) => ({
      match,
      index,
      ...getProviderCartLineData(match)
    }))
    .sort((left, right) => (
      (right.subtotalMinor ?? -1) - (left.subtotalMinor ?? -1)
      || left.index - right.index
    ));
  const rawProviderUnavailableItems = providerLiveCart
    ? []
    : Array.isArray(providerCartReview?.unavailable_items)
      ? providerCartReview.unavailable_items
      : Array.isArray(providerCartReview?.result?.unavailable_items) ? providerCartReview.result.unavailable_items : [];
  // The agent's omission and the reconciliation failure can both report the
  // same native item (KI-004); list each missing item once, first reason wins.
  const providerUnavailableItems = rawProviderUnavailableItems.filter((item, index, all) => {
    const key = String(item?.native_item_id || item?.name || index).toLowerCase();
    return all.findIndex(other => String(other?.native_item_id || other?.name || "").toLowerCase() === key) === index;
  });
  const providerCartChanges = providerLiveCart || !Array.isArray(providerCartReview?.changes) ? [] : providerCartReview.changes;
  const providerReplacements = providerLiveCart || !Array.isArray(providerCartReview?.replacements) ? [] : providerCartReview.replacements;
  const providerCartReadAt = providerLiveCart?.read_at || providerCartReview?.last_validated_at;
  const providerLastChecked = providerCartReadAt
    ? new Intl.DateTimeFormat("en-IN", {
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit"
      }).format(new Date(providerCartReadAt))
    : "Not checked yet";
  const providerCartDetails = providerLiveCart?.provider_cart || providerCartReview?.provider_cart || providerCartReview?.result?.provider_cart || providerCartReview?.result || null;
  const providerStoreGroups = Array.isArray(providerCartDetails?.stores) ? providerCartDetails.stores : [];
  const providerMultiStore = Boolean(providerCartDetails?.multi_store || providerStoreGroups.length > 1);
  const providerCartSummary = providerLiveCart?.cart_summary || providerCartReview?.cart_summary || {
    currency: "INR",
    subtotal_minor: null,
    discount_minor: null,
    fees: [],
    total_minor: null,
    total_source: "unavailable",
    total_notice: ""
  };
  const providerCurrency = providerCartSummary.currency || "INR";
  const providerSubtotal = formatMinorCurrency(providerCartSummary.subtotal_minor, providerCurrency);
  const providerDiscount = formatMinorCurrency(providerCartSummary.discount_minor, providerCurrency);
  const providerFees = Array.isArray(providerCartSummary.fees)
    ? providerCartSummary.fees
      .map(fee => ({
        label: fee?.label || "Fee",
        value: formatMinorCurrency(fee?.amount_minor, providerCurrency)
      }))
      .filter(fee => fee.value)
    : [];
  const providerTotal = formatMinorCurrency(providerCartSummary.total_minor, providerCurrency);
  const providerTotalSource = providerCartSummary.total_source || (providerTotal ? "provider" : "unavailable");
  const providerTotalNotice = providerCartSummary.total_notice || (
    providerTotal
      ? `Final total returned by ${selectedProvider.label}.`
      : `${selectedProvider.label} did not return enough information for a safe total.`
  );
  const providerCheckoutContext = providerCartReview?.checkout_context || providerCartReview?.result?.checkout_context || {};
  const providerSavedAddressOptions = collectObjectsWithAnyKey(providerSavedAddresses, ["address", "address_line", "addressLine", "id"]);
  const selectedProviderAddressOption = providerSavedAddressOptions.find((option, idx) => (
    optionValue(option, ["id", "address_id", "addressId"], `address-${idx}`) === selectedProviderAddress
  ));
  const selectedProviderAddressDisplay = selectedProviderAddressOption
    ? formatProviderAddressParts(selectedProviderAddressOption, `Selected ${selectedProvider.label} address`)
    : null;
  const providerAddressDetailsReady = Boolean(selectedProviderAddressDisplay);
  const providerPaymentOptions = collectObjectsWithAnyKey(
    providerCartReview?.payment_options || providerCheckoutContext.payment_methods,
    ["payment", "method", "payment_method", "id"]
  );
  const instamartSolePaymentOption = (
    selectedProvider.id === "swiggy_instamart" && providerPaymentOptions.length === 1
  ) ? providerPaymentOptions[0] : null;
  const instamartSolePaymentId = instamartSolePaymentOption
    ? optionValue(
      instamartSolePaymentOption,
      ["id", "payment_method_id", "paymentMethodId", "method"],
      ""
    )
    : "";
  const instamartSolePaymentLabel = instamartSolePaymentOption
    ? formatProviderPaymentLabel(instamartSolePaymentOption, "Cash on delivery")
    : "";
  const effectiveProviderPaymentMethod = selectedProviderPaymentMethod || instamartSolePaymentId;
  const providerPaymentState = providerCartReview?.payment_state || {};
  const providerPaymentHandoffUrl = safeProviderPaymentUrl(
    providerPaymentHandoff?.bridge_url || providerPaymentHandoff?.upi_intent_url
  );
  const providerOrderMessage = providerCheckoutContext.provider_message || "";
  const providerOrderResults = Array.isArray(providerCartReview?.order_results)
    ? providerCartReview.order_results
    : [];
  const providerPaymentPending = providerCartReview?.status === "payment_pending";
  const providerOrderAmbiguous = providerCartReview?.status === "unknown" || providerCartReview?.ambiguous_order;
  const providerOrderBlockers = Array.isArray(providerCartReview?.order_blockers) ? providerCartReview.order_blockers : [];
  const nativeCartStageComplete = checkoutItems.length > 0;
  const providerStageComplete = Boolean(selectedProvider.id && selectedProvider.enabled);
  const providerConnectionState = providerConnectionStatus?.state || selectedProvider.state || "unknown";
  const providerConnectionReady = Boolean(
    selectedProvider.id
    && (selectedProvider.requires_connection
      ? providerConnectionState === "connected"
      : ["configured", "connected", "ready"].includes(providerConnectionState))
  );
  const addressStageComplete = providerConnectionReady && Boolean(selectedProviderAddress);
  const providerReviewConfirmed = ["success", "ready", "changed"].includes(providerReviewStatus)
    && providerMatchedItems.length > 0;
  const transferStageComplete = providerReviewConfirmed;
  const reviewStageComplete = transferStageComplete && providerReviewAcknowledged;
  const providerOrderCompleted = isProviderOrderComplete || providerCartReview?.status === "ordered";
  const canPlaceProviderOrder = providerCartReview?.can_place_order
    && Boolean(providerCartReview?.confirmation_token)
    && Boolean(providerCartReview?.snapshot_hash)
    && Boolean(selectedProviderAddress)
    && providerAddressDetailsReady
    && providerOrderBlockers.length === 0
    && Boolean(effectiveProviderPaymentMethod)
    && providerReviewAcknowledged
    && !isUpdatingProviderReview;
  const providerStatusLabel = providerCartReview?.store_context?.state === "store_context_ready"
    ? `${selectedProvider.label} store ready`
    : providerSavedAddressOptions.length > 0
      ? `${selectedProvider.label} connected`
      : ({
    configured: `${selectedProvider.label} configured`,
    connected: `${selectedProvider.label} connected`,
    browser_login_required: "Browser login required",
    not_connected: `Connect ${selectedProvider.label}`,
    reconnect_required: `Reconnect ${selectedProvider.label}`,
    gated: `${selectedProvider.label} access gated`,
    disabled: "Disabled",
    failed: `${selectedProvider.label} sign-in needs attention`,
    unknown: `Checking ${selectedProvider.label} sign-in`
  }[providerConnectionState] || providerConnectionState);
  const providerStatusDescription = providerCartReview?.store_context?.state === "store_context_ready"
    ? "Products were resolved for the selected delivery address."
    : providerSavedAddressOptions.length > 0
      ? selectedProviderAddress
        ? `Address selected. ${selectedProvider.label} will confirm the serviceable store before searching products.`
        : `Select a delivery address before moving items to ${selectedProvider.label}.`
      : ({
    configured: `Loading saved addresses to verify the ${selectedProvider.label} connection.`,
    connected: `Select a saved delivery address before moving items to ${selectedProvider.label}.`,
    browser_login_required: `Sign in to ${selectedProvider.label} in the browser to continue.`,
    not_connected: `Authorize the household provider account before reading saved addresses.`,
    reconnect_required: `The provider connection expired or was revoked. Reconnect before continuing.`,
    gated: selectedProvider.message || `${selectedProvider.label} production access is not enabled.`,
    disabled: `${selectedProvider.label} cart sync is not enabled right now.`,
    failed: `Reconnect ${selectedProvider.label} and try again.`,
    unknown: `Checking whether ${selectedProvider.label} is ready.`
  }[providerConnectionState] || "");
  const planDays = useMemo(() => (
    Array.isArray(mealPlan.days) ? mealPlan.days : []
  ), [mealPlan.days]);
  const plannedDays = useMemo(() => planDays.filter(hasPlannedMeals), [planDays]);
  const hasVisibleWeekPlan = plannedDays.length > 0;
  const hasAnyMealPlan = Boolean(mealPlan.next_planned_date);
  const selectedPlanDay = plannedDays.find(day => day.plan_date === selectedPlanDate)
    || plannedDays.find(day => day.plan_date === mealPlan.today)
    || plannedDays[0]
    || {};
  const plannerDateRangeLabel = mealPlan.week_start && mealPlan.week_end
    ? `${formatPlanDate(mealPlan.week_start, { month: "short", day: "numeric" })} - ${formatPlanDate(mealPlan.week_end, { month: "short", day: "numeric", year: "numeric" })}`
    : "Loading calendar week";

  const currentMealLabel = MEAL_SLOT_LABELS[currentMealSlot];
  const firstPlannedFocusMeal = mealPlan.next_meal ? {
    planDate: mealPlan.next_meal.plan_date,
    weekday: mealPlan.next_meal.weekday,
    slot: mealPlan.next_meal.meal_slot,
    title: mealPlan.next_meal.meal_name
  } : {
    planDate: "",
    weekday: "",
    slot: currentMealSlot,
    title: `Ask Kitch to plan the first household ${currentMealLabel.toLowerCase()}`
  };

  const pantryPreview = pantryStock.slice(0, 3);
  const selectedDayMealList = MEAL_SLOTS.filter(slot => hasMealTitle(selectedPlanDay?.[slot])).map(slot => ({
    slot,
    key: `${selectedPlanDay.plan_date || "unplanned"}-${slot}`,
    title: getMealTitle(selectedPlanDay?.[slot], "")
  }));
  const nextPlannedOutsideVisibleWeek = mealPlan.next_planned_date
    && !plannedDays.some(day => day.plan_date === mealPlan.next_planned_date)
    ? mealPlan.next_planned_date
    : "";
  const focusMealDateText = firstPlannedFocusMeal.planDate
    ? formatPlanDate(firstPlannedFocusMeal.planDate, { weekday: "long", month: "long", day: "numeric" })
    : "Upcoming dates";
  const focusMealTitle = firstPlannedFocusMeal.title;
  const focusMealSlotLabel = MEAL_SLOT_LABELS[firstPlannedFocusMeal.slot] || currentMealLabel;
  const heroGreeting = `${timeGreeting}, ${activeUser}!`;
  const focusMealContext = firstPlannedFocusMeal.planDate
    ? `${focusMealSlotLabel} for ${focusMealDateText}`
    : "No household meal plan yet";
  const nutritionSummary = loggedCal > 0
    ? `${calPercentage}% of daily target`
    : "No meals logged yet";
  const quickPrompts = [
    ...(activeTab === "planner" && !hasAnyMealPlan ? [] : ["Plan next week for the whole household"]),
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

  return {
    providerPaymentCheckedAt,
    startupState,
    startSession,
    notices,
    dismissNotice,
    noticeIdRef,
    activeTab,
    setActiveTab,
    selectedPlanDate,
    setSelectedPlanDate,
    currentMealSlot,
    setCurrentMealSlot,
    expandedMealKey,
    setExpandedMealKey,
    householdSize,
    setHouseholdSize,
    householdMembers,
    setHouseholdMembers,
    activeUser,
    setActiveUser,
    userProfiles,
    setUserProfiles,
    pantryStock,
    setPantryStock,
    pantryRevision,
    setPantryRevision,
    pantryReviewedAt,
    setPantryReviewedAt,
    groceryWorkspaceTab,
    setGroceryWorkspaceTab,
    collapsedGroceryCategories,
    setCollapsedGroceryCategories,
    pantryTableCollapsed,
    setPantryTableCollapsed,
    editingGroceryItemId,
    setEditingGroceryItemId,
    groceryItemNameDraft,
    setGroceryItemNameDraft,
    pantryDrafts,
    setPantryDrafts,
    editingPantryItemId,
    setEditingPantryItemId,
    pantryNewItem,
    setPantryNewItem,
    confirmationDialog,
    setConfirmationDialog,
    mealPlan,
    setMealPlan,
    chatHistory,
    setChatHistory,
    visibleChatCount,
    setVisibleChatCount,
    chatMessagesRef,
    customGroceryItems,
    setCustomGroceryItems,
    confirmedGroceryItemsRef,
    latestRecipeGroceryPlan,
    setLatestRecipeGroceryPlan,
    liveStateUser,
    setLiveStateUser,
    householdBootstrap,
    setHouseholdBootstrap,
    onboardingMembers,
    setOnboardingMembers,
    isOnboardingSaving,
    setIsOnboardingSaving,
    onboardingError,
    setOnboardingError,
    authState,
    setAuthState,
    authError,
    setAuthError,
    timeGreeting,
    setTimeGreeting,
    googleButtonRef,
    memberEditorOpen,
    setMemberEditorOpen,
    memberNameDrafts,
    setMemberNameDrafts,
    memberEditorError,
    setMemberEditorError,
    savingMemberId,
    setSavingMemberId,
    chatInput,
    setChatInput,
    isChatTyping,
    setIsChatTyping,
    smartDockExpanded,
    setSmartDockExpanded,
    pendingPhoto,
    setPendingPhoto,
    orderingProviders,
    setOrderingProviders,
    selectedOrderingProvider,
    setSelectedOrderingProvider,
    nutritionTargets,
    setNutritionTargets,
    nutritionDashboard,
    setNutritionDashboard,
    selectedNutritionDate,
    setSelectedNutritionDate,
    nutritionTrendMetric,
    setNutritionTrendMetric,
    expandedNutritionMeals,
    setExpandedNutritionMeals,
    nutritionEntryEditor,
    setNutritionEntryEditor,
    nutritionGoalEditor,
    setNutritionGoalEditor,
    isNutritionSaving,
    setIsNutritionSaving,
    providerCartReview,
    setProviderCartReview,
    providerLiveCart,
    setProviderLiveCart,
    providerConnectionStatus,
    setProviderConnectionStatus,
    providerSavedAddresses,
    setProviderSavedAddresses,
    isProviderAddressLoading,
    setIsProviderAddressLoading,
    providerAddressLoadError,
    setProviderAddressLoadError,
    selectedProviderAddress,
    setSelectedProviderAddress,
    selectedProviderPaymentMethod,
    setSelectedProviderPaymentMethod,
    providerReviewAcknowledged,
    setProviderReviewAcknowledged,
    isUpdatingProviderReview,
    setIsUpdatingProviderReview,
    excludedProviderItemIds,
    setExcludedProviderItemIds,
    isProviderSyncing,
    setIsProviderSyncing,
    isProviderCartRefreshing,
    setIsProviderCartRefreshing,
    providerSyncStage,
    setProviderSyncStage,
    groceryMutationCount,
    setGroceryMutationCount,
    isPlacingProviderOrder,
    setIsPlacingProviderOrder,
    isCheckingProviderPayment,
    setIsCheckingProviderPayment,
    isProviderOrderComplete,
    setIsProviderOrderComplete,
    providerPaymentHandoff,
    setProviderPaymentHandoff,
    scanningOverlay,
    setScanningOverlay,
    recipeSidebarTab,
    setRecipeSidebarTab,
    recipeBodyTab,
    setRecipeBodyTab,
    groceryCustomName,
    setGroceryCustomName,
    groceryCustomAmount,
    setGroceryCustomAmount,
    groceryCustomUnit,
    setGroceryCustomUnit,
    groceryCustomCat,
    setGroceryCustomCat,
    groceryMutationCountRef,
    pendingGroceryItemUpdatesRef,
    providerSyncInFlightRef,
    providerCartRefreshInFlightRef,
    providerDraftRestoreInFlightRef,
    providerSyncTimersRef,
    providerSyncDialogRef,
    selectedProvider,
    selectedProviderLabel,
    selectedProviderId,
    selectedProviderLiveCartRoute,
    selectedProviderCheckoutDraftRoute,
    selectedProviderAddressesRoute,
    selectedProviderEnabled,
    selectedProviderRequiresConnection,
    selectedProviderRegistryState,
    providerReviewLastValidatedAt,
    hasProviderCartDisplay,
    applyProviderDraft,
    invalidateProviderReview,
    applyConfirmedGroceryCart,
    applyLiveState,
    fetchLiveState,
    loadNutritionDashboard,
    loadMealPlanWeek,
    syncProviderRegistry,
    syncProviderAddresses,
    syncLiveState,
    applyBootstrappedHousehold,
    loadAuthSession,
    handleGoogleCredential,
    signOut,
    renderGoogleButton,
    submitHouseholdOnboarding,
    openMemberEditor,
    saveMemberName,
    groceryList,
    totalCount,
    providerSelectedCount,
    triggerBannerAlert,
    beginGroceryMutation,
    endGroceryMutation,
    clearProviderSyncTimers,
    startProviderSyncProgress,
    saveHouseholdProfile,
    updateHouseholdSize,
    switchActiveUser,
    toggleProviderItemSelection,
    setProviderSelectionForItems,
    updateGroceryCartItemDetails,
    flushQueuedGroceryItemUpdate,
    adjustGroceryCartItemAmount,
    saveGroceryItemName,
    deleteGroceryCartItem,
    clearPlannedGroceryRows,
    addCustomGroceryItem,
    syncNativeCartToProvider,
    refreshProviderCart,
    restoreProviderCheckoutDraft,
    updateProviderReview,
    selectProviderSyncAddress,
    selectOrderingProvider,
    startProviderConnection,
    disconnectProvider,
    placeProviderOrder,
    checkProviderPaymentStatus,
    resetDailyLogs,
    navigateNutritionDate,
    openNutritionEntryEditor,
    saveNutritionEntry,
    deleteNutritionEntry,
    saveNutritionGoals,
    patchPantry,
    reconcileCartWithPantry,
    savePantryRow,
    markPantryEmpty,
    stagePhotoForInput,
    clearPendingPhoto,
    sendChatMessage,
    handleChatSubmit,
    handleRealPhotoUpload,
    draftMealSwapPrompt,
    targetCalories,
    targetProtein,
    targetCarbs,
    targetFat,
    activeUserProfile,
    loggedMeals,
    loggedCal,
    loggedProt,
    loggedCarb,
    loggedFat,
    calPercentage,
    protPerc,
    carbPerc,
    fatPerc,
    selectedNutritionDay,
    nutritionTotals,
    nutritionCalPercentage,
    nutritionStrokeDashoffset,
    nutritionMacroRows,
    nutritionEntriesByMeal,
    nutritionTrendTarget,
    nutritionTrendMax,
    nutritionTip,
    checkoutItems,
    recipeCards,
    activeRecipeCard,
    activeRecipeTitle,
    activeRecipeIngredients,
    activeRecipeSteps,
    recipeServings,
    recipeCookTime,
    recipeCalories,
    recipeDescription,
    recipePantryNotes,
    recipeLinkedCartItems,
    recipeCartItems,
    recipeNeededCartItems,
    groupedGroceryCart,
    groceryCategoryCount,
    stockedCount,
    pendingBuyCount,
    eligibleBuyCount,
    providerReviewStatus,
    providerMatchedItems,
    providerLiveCartItems,
    providerDisplayedItems,
    providerCartRows,
    providerUnavailableItems,
    providerCartChanges,
    providerReplacements,
    providerCartReadAt,
    providerLastChecked,
    providerCartDetails,
    providerStoreGroups,
    providerMultiStore,
    providerCartSummary,
    providerCurrency,
    providerSubtotal,
    providerDiscount,
    providerFees,
    providerTotal,
    providerTotalSource,
    providerTotalNotice,
    providerCheckoutContext,
    providerSavedAddressOptions,
    selectedProviderAddressOption,
    selectedProviderAddressDisplay,
    providerAddressDetailsReady,
    providerPaymentOptions,
    instamartSolePaymentOption,
    instamartSolePaymentId,
    instamartSolePaymentLabel,
    effectiveProviderPaymentMethod,
    providerPaymentState,
    providerPaymentHandoffUrl,
    providerOrderMessage,
    providerOrderResults,
    providerPaymentPending,
    providerOrderAmbiguous,
    providerOrderBlockers,
    nativeCartStageComplete,
    providerStageComplete,
    providerConnectionState,
    providerConnectionReady,
    addressStageComplete,
    providerReviewConfirmed,
    transferStageComplete,
    reviewStageComplete,
    providerOrderCompleted,
    canPlaceProviderOrder,
    providerStatusLabel,
    providerStatusDescription,
    planDays,
    plannedDays,
    hasVisibleWeekPlan,
    hasAnyMealPlan,
    selectedPlanDay,
    plannerDateRangeLabel,
    currentMealLabel,
    firstPlannedFocusMeal,
    pantryPreview,
    selectedDayMealList,
    nextPlannedOutsideVisibleWeek,
    focusMealDateText,
    focusMealTitle,
    focusMealSlotLabel,
    heroGreeting,
    focusMealContext,
    nutritionSummary,
    quickPrompts,
    hasStartedConversation,
    visibleChatStartIndex,
    visibleChatMessages,
    hasOlderChatMessages,
    revealEarlierMessages,
    handleChatScroll,
  };
}
