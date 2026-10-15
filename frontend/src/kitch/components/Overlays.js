"use client";

import { useEffect, useRef } from "react";
import Icon from "./Icon.js";
import { apiErrorMessage } from "../lib/helpers.js";

function useDialogFocus(ref, onEscape) {
  useEffect(() => {
    const previous = document.activeElement;
    const frame = window.requestAnimationFrame(() => {
      const target = ref.current?.querySelector("[data-autofocus]") || ref.current;
      target?.focus();
    });
    const onKey = (event) => { if (event.key === "Escape" && onEscape) onEscape(); };
    document.addEventListener("keydown", onKey);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKey);
      if (previous instanceof HTMLElement) previous.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

export function ConfirmDialog({ k }) {
  const dialog = k.confirmationDialog;
  const ref = useRef(null);
  const cancel = async () => {
    const onCancel = dialog.onCancel;
    k.setConfirmationDialog(null);
    if (onCancel) await onCancel();
  };
  useDialogFocus(ref, cancel);
  const destructive = /clear|empty|remove|delete/i.test(dialog.confirmLabel || "");

  return (
    <div className="scrim" role="presentation">
      <section ref={ref} className="dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title" tabIndex={-1}>
        <h2 id="confirm-title">{dialog.title}</h2>
        <p>{dialog.message}</p>
        <div className="dialog-actions">
          <button type="button" className="btn quiet spacer" onClick={cancel}>Cancel</button>
          {dialog.choices ? dialog.choices.map((choice, index) => (
            <button
              key={choice.label}
              type="button"
              className={`btn ${index === 0 ? "primary" : ""}`}
              data-autofocus={index === 0 ? true : undefined}
              onClick={() => { k.setConfirmationDialog(null); choice.action(); }}
            >
              {choice.label}
            </button>
          )) : (
            <button
              type="button"
              data-autofocus
              className={`btn ${destructive ? "danger-solid" : "primary"}`}
              onClick={async () => {
                const action = dialog.onConfirm;
                k.setConfirmationDialog(null);
                try { await action(); } catch (error) { k.triggerBannerAlert(apiErrorMessage(error, "The confirmed change could not be completed."), "error"); }
              }}
            >
              {dialog.confirmLabel || "Confirm"}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}

export function MemberDialog({ k, go }) {
  const ref = useRef(null);
  const close = () => k.setMemberEditorOpen(false);
  useDialogFocus(ref, close);
  return (
    <div className="scrim" role="presentation" onMouseDown={close}>
      <section ref={ref} className="dialog settings-dialog" role="dialog" aria-modal="true" aria-labelledby="settings-title" tabIndex={-1} onMouseDown={event => event.stopPropagation()}>
        <h2 id="settings-title">Household settings</h2>
        <p>Renaming someone keeps their nutrition history and every linked record.</p>

        <h3 className="settings-sub">Members</h3>
        <ul className="settings-members">
          {k.householdMembers.map(member => {
            const draft = k.memberNameDrafts[member.id] ?? member.value;
            const unchanged = String(draft).trim() === member.value || !String(draft).trim();
            return (
              <li key={member.id}>
                <label htmlFor={`rename-${member.id}`}>{member.id === k.householdBootstrap?.owner_profile_id ? "Household owner" : "Member"}</label>
                <div>
                  <input
                    id={`rename-${member.id}`}
                    className="input"
                    value={draft}
                    onChange={event => k.setMemberNameDrafts(current => ({ ...current, [member.id]: event.target.value }))}
                    onKeyDown={event => { if (event.key === "Enter" && !unchanged) k.saveMemberName(member); }}
                  />
                  <button type="button" className="btn sm" disabled={k.savingMemberId === member.id || unchanged} onClick={() => k.saveMemberName(member)}>
                    {k.savingMemberId === member.id ? "Saving…" : "Save"}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>

        <h3 className="settings-sub">Cooking for</h3>
        <div className="stepper-row">
          <p>Recipes and grocery quantities are scaled to this many people.</p>
          <div className="stepper" role="group" aria-label="Household size">
            <button type="button" className="icon-btn sm" aria-label="Fewer people" disabled={k.householdSize <= 1} onClick={() => k.updateHouseholdSize(k.householdSize - 1)}><Icon name="minus" size="sm" /></button>
            <output aria-live="polite">{k.householdSize}</output>
            <button type="button" className="icon-btn sm" aria-label="More people" disabled={k.householdSize >= 12} onClick={() => k.updateHouseholdSize(k.householdSize + 1)}><Icon name="plus" size="sm" /></button>
          </div>
        </div>

        {k.memberEditorError && <p className="form-error" role="alert">{k.memberEditorError}</p>}
        <div className="dialog-actions">
          {k.authState.required && (
            <button type="button" className="btn danger spacer" onClick={k.signOut}><Icon name="logout" size="sm" />Sign out</button>
          )}
          <button type="button" className="btn quiet" onClick={() => { close(); go("about"); }}>About Kitch</button>
          <button type="button" className="btn primary" data-autofocus onClick={close}>Done</button>
        </div>
      </section>
    </div>
  );
}

const TRANSFER_STEPS = (label) => [
  ["preparing", "Preparing your list"],
  ["transferring", `Matching ${label} products`],
  ["finalizing", "Building the review"]
];

export function ProviderTransferDialog({ k }) {
  const { providerSyncDialogRef } = k;
  const label = k.selectedProvider.label;
  const stage = k.providerSyncStage;
  const title = stage === "complete"
    ? k.isCheckingProviderPayment ? `${label} payment status updated` : k.isPlacingProviderOrder ? `${label} checkout confirmed` : `Your ${label} cart is ready`
    : stage === "failed"
      ? k.isCheckingProviderPayment ? "Payment status could not be read" : "The transfer needs attention"
      : k.isCheckingProviderPayment ? `Checking your ${label} payment…`
        : k.isPlacingProviderOrder ? `Checking ${label} availability before ordering…`
          : k.providerCartReview ? `Refreshing your ${label} cart…` : `Sending your items to ${label}…`;
  const body = stage === "complete"
    ? "The reviewed products and anything unavailable are ready for you to check."
    : stage === "failed"
      ? "Kitch could not complete the handoff. Your shopping list was left unchanged."
      : k.isCheckingProviderPayment ? `Kitch is making one status check with ${label}; it will not resubmit the order.`
        : k.isPlacingProviderOrder ? `Kitch is confirming every approved product and quantity with ${label} before placing the order.`
          : `Editing is paused while ${label} picks your store, matches products and builds the review.`;
  const steps = TRANSFER_STEPS(label);
  const current = steps.findIndex(([key]) => key === stage);

  return (
    <div className="scrim" role="presentation">
      <section ref={providerSyncDialogRef} className={`dialog transfer ${stage}`} role="dialog" aria-modal="true" aria-labelledby="transfer-title" aria-describedby="transfer-body" tabIndex={-1}>
        <div className="transfer-mark" aria-hidden="true">
          <span className="tile sage"><Icon name="list" /></span>
          <span className="transfer-line"><i /></span>
          <span className="tile turmeric"><Icon name="store" /></span>
        </div>
        <h2 id="transfer-title">{title}</h2>
        <p id="transfer-body">{body}</p>
        <ol className="transfer-steps">
          {steps.map(([key, text], index) => {
            const done = stage === "complete" || current > index;
            const active = current === index;
            return (
              <li key={key} className={`${done ? "done" : ""} ${active ? "active" : ""}`}>
                <span>{done ? <Icon name="check" size="sm" /> : index + 1}</span>{text}
              </li>
            );
          })}
        </ol>
        <p className="transfer-note"><Icon name="lock" size="sm" />{k.checkoutItems.length} selected {k.checkoutItems.length === 1 ? "item is" : "items are"} locked while this runs. Keep this window open.</p>
      </section>
    </div>
  );
}

const SCAN_STEPS = ["Uploading your photo", "Checking whether it’s a meal or pantry", "Saving what Kitch found"];

export function PhotoScanDialog({ k }) {
  const progress = Math.min(SCAN_STEPS.length - 1, Math.max(0, k.scanningOverlay.steps.length - 2));
  return (
    <div className="scrim" role="presentation">
      <section className="dialog scan" role="dialog" aria-modal="true" aria-labelledby="scan-title" aria-busy="true">
        <span className="tile sage scan-tile" aria-hidden="true"><Icon name="camera" size="lg" /></span>
        <h2 id="scan-title">Reading your photo</h2>
        <p className="muted">{k.scanningOverlay.fileName}</p>
        <ol className="transfer-steps">
          {SCAN_STEPS.map((text, index) => (
            <li key={text} className={`${progress > index ? "done" : ""} ${progress === index ? "active" : ""}`}>
              <span>{progress > index ? <Icon name="check" size="sm" /> : index + 1}</span>{text}
            </li>
          ))}
        </ol>
        <p className="transfer-note">Nothing is saved until Kitch is sure what the photo shows.</p>
      </section>
    </div>
  );
}

export function Notices({ k }) {
  const { notices, dismissNotice } = k;
  useEffect(() => {
    const timers = notices
      .filter(notice => notice.tone !== "error")
      .map(notice => window.setTimeout(() => dismissNotice(notice.id), 5200));
    return () => timers.forEach(timer => window.clearTimeout(timer));
  }, [notices, dismissNotice]);

  return (
    <div className="notices" role="status" aria-live="polite">
      {notices.map(notice => (
        <div key={notice.id} className={`notice ${notice.tone}`} role={notice.tone === "error" ? "alert" : undefined}>
          <Icon name={notice.tone === "error" ? "alert" : "checkCircle"} size="sm" />
          <p>{notice.text}</p>
          <button type="button" className="icon-btn bare sm" aria-label="Dismiss" onClick={() => dismissNotice(notice.id)}><Icon name="close" size="sm" /></button>
        </div>
      ))}
    </div>
  );
}
