"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useKitch } from "./useKitch.js";
import Icon from "./components/Icon.js";
import { SplashScreen, SignInScreen, OnboardingScreen, ConsentScreen, HouseholdSetupScreen, LegalLinks } from "./components/EntryScreens.js";
import HouseholdView from "./components/HouseholdView.js";
import RecipesView from "./components/RecipesView.js";
import GroceriesView from "./components/GroceriesView.js";
import NutritionView from "./components/NutritionView.js";
import AboutView from "./components/AboutView.js";
import { Composer, ChatDrawer } from "./components/Chat.js";
import { ConfirmDialog, MemberDialog, ProviderTransferDialog, PhotoScanDialog, Notices } from "./components/Overlays.js";
import { subscribeSlowRequests, fetchServerStartup } from "./lib/helpers.js";

const NAV = [
  { key: "planner", label: "Household", short: "Home", icon: "household" },
  { key: "recipes", label: "Recipes", short: "Recipes", icon: "recipe" },
  { key: "groceries", label: "Groceries", short: "Groceries", icon: "basket" },
  { key: "analytics", label: "Nutrition", short: "Nutrition", icon: "chart" },
  { key: "about", label: "About Kitch", short: "About", icon: "info", desktopOnly: true }
];

// A server can restart mid-session (Vercel replaces idle instances). When an
// ordinary request has waited 3 s, ask the server how long it has been up; the
// pill appears only if it has just started (or is too busy starting to say).
// It never blocks the screen and leaves the moment the request finishes.
const FRESH_SERVER_S = 120;

function WarmupPill() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let pendingCheck = 0;
    return subscribeSlowRequests(count => {
      if (count === 0) {
        pendingCheck += 1;
        setVisible(false);
        return;
      }
      const check = ++pendingCheck;
      const tooBusyToAnswer = window.setTimeout(() => { if (check === pendingCheck) setVisible(true); }, 1500);
      fetchServerStartup()
        .then(status => {
          if (check !== pendingCheck) return;
          setVisible(status.uptime_s === null ? false : status.uptime_s < FRESH_SERVER_S || status.stage !== "ready");
        })
        .catch(() => { if (check === pendingCheck) setVisible(true); })
        .finally(() => window.clearTimeout(tooBusyToAnswer));
    });
  }, []);

  if (!visible) return null;
  return (
    <div className="warmup-pill" role="status">
      <span className="wait-dots amber" aria-hidden="true"><i /><i /><i /></span>
      <span>The kitchen dozed off · Unlocking it again<small>Your change is on its way; nothing is lost.</small></span>
    </div>
  );
}

const initialOf = (name) => String(name || "?").trim().slice(0, 1).toUpperCase() || "?";

function MemberMenu({ k, placement = "up", onManage }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => {
      if (event.type === "keydown" && event.key !== "Escape") return;
      if (event.type === "pointerdown" && rootRef.current?.contains(event.target)) return;
      setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  return (
    <div className={`member-menu ${placement}`} ref={rootRef}>
      <button
        type="button"
        className="member-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(value => !value)}
      >
        <span className="avatar">{initialOf(k.activeUser)}</span>
        <span className="member-trigger-text">
          <small>Logging as</small>
          <strong>{k.activeUser}</strong>
        </span>
        <Icon name={placement === "up" ? "up" : "down"} size="sm" className="member-chevron" />
      </button>
      {open && (
        <div className="member-popover" role="menu" aria-label="Household members">
          <p className="member-popover-note">Plans, pantry and groceries are shared. Nutrition logs follow the active member.</p>
          {k.householdMembers.map(member => (
            <button
              key={member.id || member.value}
              type="button"
              role="menuitemradio"
              aria-checked={member.value === k.activeUser}
              className="member-option"
              onClick={() => { k.switchActiveUser(member.value); setOpen(false); }}
            >
              <span className="avatar sm">{initialOf(member.value)}</span>
              {member.label}
              {member.value === k.activeUser && <Icon name="check" size="sm" className="member-check" />}
            </button>
          ))}
          <div className="member-popover-foot">
            <button type="button" role="menuitem" className="member-option" onClick={() => { setOpen(false); onManage(); }}>
              <Icon name="settings" size="sm" /> Household settings
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function KitchApp() {
  const k = useKitch();
  const composerRef = useRef(null);

  // Draft a request into the composer and hand focus to it, so every
  // shortcut stays a reviewable sentence rather than a hidden action.
  const ask = useCallback((prompt, { open = false } = {}) => {
    k.setChatInput(prompt);
    if (open) k.setSmartDockExpanded(true);
    window.requestAnimationFrame(() => {
      const input = composerRef.current;
      if (!input) return;
      input.focus();
      input.setSelectionRange?.(input.value.length, input.value.length);
    });
    // setChatInput / setSmartDockExpanded are stable state setters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const go = useCallback((tab, groceryTab) => {
    if (groceryTab) k.setGroceryWorkspaceTab(groceryTab);
    else if (tab === "groceries") k.setGroceryWorkspaceTab("cart");
    k.setActiveTab(tab);
    window.scrollTo({ top: 0 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { authState, householdBootstrap } = k;

  // The splash stays until the server reports every startup step done, so
  // nothing in the app is half-ready when it opens.
  if (authState.loading || !k.serverStartup.ready) {
    return <SplashScreen startup={k.startupState} onRetry={k.startSession} server={k.serverStartup} />;
  }
  if (authState.required && !authState.authenticated) return <SignInScreen k={k} />;
  if (authState.consentRequired) return <ConsentScreen k={k} />;
  if (authState.setupRequired) return <HouseholdSetupScreen k={k} />;
  if (householdBootstrap === null) return <SplashScreen server={k.serverStartup} />;
  if (!householdBootstrap.initialized) return <OnboardingScreen k={k} />;

  const view = {
    planner: <HouseholdView k={k} ask={ask} go={go} />,
    recipes: <RecipesView k={k} ask={ask} go={go} />,
    groceries: <GroceriesView k={k} ask={ask} go={go} />,
    analytics: <NutritionView k={k} ask={ask} go={go} />,
    about: <AboutView k={k} ask={ask} go={go} />
  }[k.activeTab] || <HouseholdView k={k} ask={ask} go={go} />;

  return (
    <div className={`app ${k.smartDockExpanded ? "drawer-open" : ""}`}>
      <a className="skip-link" href="#main">Skip to content</a>

      <aside className="rail" aria-label="Kitch">
        <div className="brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/kitch-chef-hat.svg" alt="" width="34" height="34" />
          <span>Kitch</span>
        </div>
        <nav className="rail-nav" aria-label="Sections">
          {NAV.map(item => (
            <button
              key={item.key}
              type="button"
              className="rail-link"
              aria-current={k.activeTab === item.key ? "page" : undefined}
              onClick={() => go(item.key)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.key === "groceries" && k.eligibleBuyCount > 0 && <em aria-label={`${k.eligibleBuyCount} to buy`}>{k.eligibleBuyCount}</em>}
            </button>
          ))}
        </nav>
        <LegalLinks className="rail-legal" />
        <MemberMenu k={k} placement="up" onManage={k.openMemberEditor} />
      </aside>

      <header className="topbar">
        <div className="brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/kitch-chef-hat.svg" alt="" width="28" height="28" />
          <span>Kitch</span>
        </div>
        <MemberMenu k={k} placement="down" onManage={k.openMemberEditor} />
      </header>

      <main id="main" className="workspace" tabIndex={-1}>
        {view}
      </main>

      <nav className="tabbar" aria-label="Sections">
        {NAV.filter(item => !item.desktopOnly).map(item => (
          <button
            key={item.key}
            type="button"
            aria-current={k.activeTab === item.key ? "page" : undefined}
            onClick={() => go(item.key)}
          >
            <Icon name={item.icon} />
            <span>{item.short}</span>
            {item.key === "groceries" && k.eligibleBuyCount > 0 && <em>{k.eligibleBuyCount}</em>}
          </button>
        ))}
      </nav>

      {!k.smartDockExpanded && <Composer k={k} inputRef={composerRef} floating />}
      <ChatDrawer k={k} go={go} inputRef={composerRef} />

      <Notices k={k} />
      <WarmupPill />
      {k.scanningOverlay.active && <PhotoScanDialog k={k} />}
      {k.isProviderSyncing && <ProviderTransferDialog k={k} />}
      {k.confirmationDialog && <ConfirmDialog k={k} />}
      {k.memberEditorOpen && <MemberDialog k={k} go={go} />}
    </div>
  );
}
