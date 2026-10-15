"use client";

import { useState } from "react";

// Illustration slot that degrades gracefully: commissioned art lives in
// /public/art and may not exist yet, so a missing file falls back to an
// existing illustration or disappears instead of showing a broken image.
export default function Art({ src, fallback = "", alt = "", className = "", ...rest }) {
  const [current, setCurrent] = useState(src);
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={current}
      alt={alt}
      className={className}
      decoding="async"
      onError={() => {
        if (fallback && current !== fallback) setCurrent(fallback);
        else setFailed(true);
      }}
      {...rest}
    />
  );
}

export const heroArtFor = (greeting) => {
  if (/morning/i.test(greeting)) return "/art/hero-morning.png";
  if (/afternoon/i.test(greeting)) return "/art/hero-afternoon.png";
  return "/art/hero-evening.png";
};

export const HERO_FALLBACK = "/countertop.png";
