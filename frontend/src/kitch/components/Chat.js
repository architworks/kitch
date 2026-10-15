"use client";

import { useEffect, useRef, useState } from "react";
import Icon from "./Icon.js";
import { renderMarkdownContent } from "../lib/helpers.js";
import { formatPlanDate, getWeekStartForDate } from "../../app/householdConfig.js";

const describeAction = (action, k) => {
  if (!action?.type) return null;
  const dates = (action.affected_dates || []).filter(Boolean);
  const dateText = dates.length === 0
    ? ""
    : dates.length === 1
      ? formatPlanDate(dates[0], { weekday: "short", day: "numeric", month: "short" })
      : `${formatPlanDate(dates[0], { day: "numeric", month: "short" })} – ${formatPlanDate(dates[dates.length - 1], { day: "numeric", month: "short" })}`;
  switch (action.type) {
    case "UPDATE_PLANNER":
      return { icon: "calendar", text: `Meal plan updated${dateText ? ` · ${dateText}` : ""}`, cta: "View plan", target: "planner", focus: action.focus_date || dates[0] };
    case "UPDATE_NUTRITION":
      return { icon: "chart", text: `${k.activeUser}’s diary updated`, cta: "Open diary", target: "analytics" };
    case "UPDATE_PANTRY":
      return { icon: "pantry", text: "Pantry updated", cta: "Open pantry", target: "groceries", groceryTab: "pantry" };
    case "UPDATE_GROCERY_CART":
      return { icon: "basket", text: "Shopping list updated", cta: "Open list", target: "groceries", groceryTab: "cart" };
    case "UPDATE_PROVIDER_CART":
      return { icon: "store", text: "Provider cart prepared for your review", cta: "Review", target: "groceries", groceryTab: "cart" };
    case "CONFIRM_DESTRUCTIVE_ACTION":
      return { icon: "alert", text: "Waiting for your confirmation", cta: null };
    default:
      return null;
  }
};

function ChangeReceipt({ action, k, go }) {
  const info = describeAction(action, k);
  if (!info) return null;
  return (
    <div className="receipt">
      <Icon name={info.icon} size="sm" />
      <span>{info.text}</span>
      {info.cta && (
        <button
          type="button"
          onClick={() => {
            if (info.target === "planner" && info.focus) k.loadMealPlanWeek(getWeekStartForDate(info.focus), info.focus);
            go(info.target, info.groceryTab);
          }}
        >
          {info.cta}
        </button>
      )}
    </div>
  );
}

export function Composer({ k, inputRef, floating = false }) {
  const [focused, setFocused] = useState(false);
  const showPrompts = floating && focused && !k.hasStartedConversation && !k.chatInput.trim() && !k.pendingPhoto;

  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    // Grow with what the person typed, never with a wrapping placeholder.
    input.style.height = "auto";
    if (k.chatInput) input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
  }, [k.chatInput, inputRef]);

  return (
    <form
      className={`composer ${floating ? "floating" : "docked"}`}
      onSubmit={k.handleChatSubmit}
      onFocus={() => setFocused(true)}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false); }}
    >
      {showPrompts && (
        <div className="prompt-row" aria-label="Suggestions">
          {k.quickPrompts.map(prompt => (
            <button key={prompt} type="button" onMouseDown={event => event.preventDefault()} onClick={() => k.setChatInput(prompt)}>{prompt}</button>
          ))}
        </div>
      )}
      {k.pendingPhoto && (
        <div className="attachment">
          <Icon name={k.pendingPhoto.source === "camera" ? "camera" : "image"} size="sm" />
          <span><strong>{k.pendingPhoto.file.name}</strong> Kitch will check whether it’s a meal or pantry photo.</span>
          <button type="button" className="icon-btn bare sm" aria-label="Remove photo" onClick={k.clearPendingPhoto}><Icon name="close" size="sm" /></button>
        </div>
      )}
      <div className="composer-row">
        {floating && (
          <button type="button" className="icon-btn bare composer-history" aria-label="Open conversation" onClick={() => k.setSmartDockExpanded(true)}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/kitch-chef-hat.svg" alt="" width="24" height="24" />
            {k.hasStartedConversation && <i className="composer-dot" aria-hidden="true" />}
          </button>
        )}
        <label className="visually-hidden" htmlFor={floating ? "composer-floating" : "composer-docked"}>Message Kitch</label>
        <textarea
          id={floating ? "composer-floating" : "composer-docked"}
          ref={inputRef}
          rows={1}
          autoComplete="off"
          placeholder={k.pendingPhoto ? "Add a note about this photo…" : "Ask Kitch to plan, cook, shop or log a meal…"}
          value={k.chatInput}
          onChange={event => k.setChatInput(event.target.value)}
          onKeyDown={event => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
        />
        <label className="icon-btn bare" title="Attach a photo">
          <Icon name="image" />
          <span className="visually-hidden">Attach a photo from your gallery</span>
          <input type="file" accept="image/*" className="visually-hidden" onChange={event => { k.stagePhotoForInput(event.target.files[0], "gallery"); event.target.value = ""; }} />
        </label>
        <label className="icon-btn bare" title="Take a photo">
          <Icon name="camera" />
          <span className="visually-hidden">Take a photo with the camera</span>
          <input type="file" accept="image/*" capture="environment" className="visually-hidden" onChange={event => { k.stagePhotoForInput(event.target.files[0], "camera"); event.target.value = ""; }} />
        </label>
        <button type="submit" className="send" aria-label="Send" disabled={k.isChatTyping || (!k.chatInput.trim() && !k.pendingPhoto)}>
          <Icon name="send" />
        </button>
      </div>
    </form>
  );
}

export function ChatDrawer({ k, go, inputRef }) {
  const messagesRef = useRef(null);
  const open = k.smartDockExpanded;

  useEffect(() => {
    if (!open) return undefined;
    const frame = window.requestAnimationFrame(() => {
      const el = messagesRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [open, k.chatHistory.length, k.isChatTyping]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => { if (event.key === "Escape" && !k.confirmationDialog) k.setSmartDockExpanded(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, k.confirmationDialog]);

  if (!open) return null;

  return (
    <>
      <div className="drawer-scrim" onClick={() => k.setSmartDockExpanded(false)} aria-hidden="true" />
      <aside className="drawer" aria-label="Conversation with Kitch">
        <header className="drawer-head">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/kitch-chef-hat.svg" alt="" width="30" height="30" />
          <div>
            <h2>Kitch</h2>
            <p>Plans and groceries are shared · logs go to {k.activeUser}</p>
          </div>
          <button type="button" className="icon-btn bare" aria-label="Close conversation" onClick={() => k.setSmartDockExpanded(false)}><Icon name="close" /></button>
        </header>

        <div className="messages" ref={messagesRef} onScroll={k.handleChatScroll} aria-live="polite">
          {k.hasOlderChatMessages && (
            <button type="button" className="btn quiet sm older" onClick={k.revealEarlierMessages}>Show earlier messages</button>
          )}
          {k.chatHistory.length === 0 && (
            <div className="drawer-empty">
              <p>Ask in your own words. Kitch can plan dated meals, write a recipe from what you have, update the pantry from a fridge photo, build the shopping list, or log what you ate.</p>
              <div className="drawer-prompts">
                {k.quickPrompts.map(prompt => (
                  <button key={prompt} type="button" onClick={() => { k.setChatInput(prompt); inputRef.current?.focus(); }}>{prompt}</button>
                ))}
              </div>
            </div>
          )}
          {k.visibleChatMessages.map((message, index) => (
            <div key={`${k.visibleChatStartIndex + index}-${message.sender}-${message.time}`} className={`msg ${message.sender}`}>
              <div className="bubble prose">{renderMarkdownContent(message.text)}</div>
              {message.sender === "agent" && message.action && <ChangeReceipt action={message.action} k={k} go={go} />}
              <time>{message.time}</time>
            </div>
          ))}
          {k.isChatTyping && (
            <div className="msg agent">
              <div className="bubble typing" aria-label="Kitch is working"><i /><i /><i /></div>
            </div>
          )}
        </div>

        <Composer k={k} inputRef={inputRef} />
      </aside>
    </>
  );
}
