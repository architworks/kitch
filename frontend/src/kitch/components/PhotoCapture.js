"use client";

import { useSyncExternalStore } from "react";
import Icon from "./Icon.js";
import Art from "./Art.js";

// Phones and tablets open the camera straight away; desktops get a file
// picker, so the wording follows the device instead of promising a camera.
const COARSE = "(pointer: coarse)";
const subscribe = (onChange) => {
  const query = window.matchMedia?.(COARSE);
  query?.addEventListener?.("change", onChange);
  return () => query?.removeEventListener?.("change", onChange);
};
export const useCameraDevice = () => useSyncExternalStore(
  subscribe,
  () => Boolean(window.matchMedia?.(COARSE).matches),
  () => false
);

export const SNAP = {
  pantry: {
    art: "/art/spot-pantry.png",
    eyebrow: "Photo to pantry",
    snap: "Snap your fridge",
    upload: "Add a fridge photo",
    short: "Scan fridge",
    title: "Snap the fridge, skip the typing",
    body: "Point your camera at the fridge or a shelf. Kitch lists what it sees, and shopping lists leave out what you already have."
  },
  meal: {
    art: "/art/spot-nutrition.png",
    eyebrow: "Photo to diary",
    snap: "Snap your plate",
    upload: "Add a plate photo",
    short: "Snap plate",
    title: "Snap your plate",
    body: "Take a photo before you eat. Kitch estimates calories, protein, carbs and fats and logs it for you."
  }
};

// A label around a hidden file input, so one tap opens the camera or picker.
// `kind` routes the photo straight to the pantry or the diary; without it the
// photo is staged in the composer and Kitch works out what it shows.
export function SnapButton({ k, kind, camera = true, className = "btn primary", children, title }) {
  const busy = k.isChatTyping || Boolean(k.scanningOverlay?.active);
  return (
    <label className={`${className} snap-trigger ${busy ? "is-busy" : ""}`} title={title} aria-disabled={busy || undefined}>
      {children}
      <input
        type="file"
        accept="image/*"
        capture={camera ? "environment" : undefined}
        className="visually-hidden"
        disabled={busy}
        onChange={event => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (!file) return;
          if (kind) k.scanPhotoAs(file, kind);
          else k.stagePhotoForInput(file, camera ? "camera" : "gallery");
        }}
      />
    </label>
  );
}

// The primary call to action for a photo kind. On a phone it reads "Snap"
// and opens the camera; a second, quieter choice picks from the gallery.
export function SnapActions({ k, kind, size = "" }) {
  const onCamera = useCameraDevice();
  const copy = SNAP[kind];
  return (
    <div className="snap-actions">
      <SnapButton k={k} kind={kind} className={`btn primary ${size}`}>
        <Icon name="camera" size="sm" />{onCamera ? copy.snap : copy.upload}
      </SnapButton>
      {onCamera && (
        <SnapButton k={k} kind={kind} camera={false} className={`btn quiet ${size}`}>
          <Icon name="image" size="sm" />From photos
        </SnapButton>
      )}
    </div>
  );
}

// Illustrated invitation framed like a camera viewfinder.
// layout: "hero" (empty states), "strip" (above a list), "stack" or "compact" (side column).
export function SnapCard({ k, kind, layout = "stack", title, body, as: Tag = "section" }) {
  const copy = SNAP[kind];
  return (
    <Tag className={`snap-card snap-${kind} snap-${layout}`}>
      <div className="snap-frame" aria-hidden="true">
        <Art src={copy.art} alt="" />
        <i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" />
        <i className="scan-line" />
      </div>
      <div className="snap-copy">
        <span className="snap-eyebrow"><Icon name="camera" size="sm" />{copy.eyebrow}</span>
        <h3>{title || copy.title}</h3>
        <p>{body || copy.body}</p>
        <SnapActions k={k} kind={kind} size={layout === "strip" || layout === "compact" ? "sm" : ""} />
      </div>
    </Tag>
  );
}
