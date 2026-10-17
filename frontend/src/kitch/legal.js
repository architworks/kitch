// Must match backend/app/legal.py. Bump both together whenever the Privacy
// Policy or Terms of Use change materially: every owner is asked again.
export const LEGAL_TERMS_VERSION = "2026-10-18";
export const LEGAL_EFFECTIVE_DATE = "18 October 2026";

// The public address people use for privacy questions and data requests.
export const LEGAL_CONTACT_EMAIL = process.env.NEXT_PUBLIC_KITCH_CONTACT_EMAIL || "architmishrapro@gmail.com";
