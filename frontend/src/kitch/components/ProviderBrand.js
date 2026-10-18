"use client";

// Grocery-app branding. Kitch works with several grocery apps, so nothing
// here is specific to one: each provider's descriptor from the backend says
// what attribution it needs, and it is shown only beside that provider's
// own content.

export const PROVIDER_LOGOS = {
  swiggy_instamart: "/instamart-logo.jpg",
  zepto: "/zepto-logo.jpg",
  blinkit: "/blinkit-logo.jpg"
};

export function ProviderLogo({ provider, size = 36 }) {
  const src = PROVIDER_LOGOS[provider?.id];
  if (!src) return <span className="provider-logo fallback" style={{ width: size, height: size }} aria-hidden="true">{String(provider?.label || "?").slice(0, 1)}</span>;
  // eslint-disable-next-line @next/next/no-img-element
  return <img className="provider-logo" src={src} alt="" width={size} height={size} />;
}

// The provider's required attribution, e.g. Instamart's square logo with
// "Powered by Instamart". The phrase is the accessible name, so the logo is
// decorative. Providers that declare no attribution render nothing.
export function ProviderAttribution({ provider }) {
  const text = provider?.attribution?.text;
  if (!text) return null;
  const src = PROVIDER_LOGOS[provider.id];
  return (
    <span className="powered-by">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {src && <img src={src} alt="" width="24" height="24" />}
      <span>{text}</span>
    </span>
  );
}
