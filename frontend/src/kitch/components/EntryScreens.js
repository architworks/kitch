"use client";

import { useEffect, useState } from "react";
import Script from "next/script";
import Icon from "./Icon.js";
import Art, { HERO_FALLBACK } from "./Art.js";
import { LEGAL_CONTACT_EMAIL } from "../legal.js";

function Mark({ size = 40 }) {
  // eslint-disable-next-line @next/next/no-img-element
  return <img src="/kitch-chef-hat.svg" alt="" width={size} height={size} />;
}

// The first screen after a quiet spell on Vercel: the backend may need most of
// a minute to wake. Copy follows real elapsed time and real retries; nothing
// pretends to be progress it isn't.
export function SplashScreen({ startup, onRetry }) {
  const [elapsed, setElapsed] = useState(0);
  const failed = Boolean(startup?.failed);

  useEffect(() => {
    if (failed) return undefined;
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [failed, startup?.attempts]);

  const waking = elapsed >= 3 || startup?.retrying;
  const title = failed ? "Kitch couldn’t wake up" : waking ? "Warming up the kitchen" : "Opening your kitchen";
  const body = failed
    ? "The kitchen server didn’t answer. Your plans, pantry and lists are safe; nothing changed."
    : startup?.retrying
      ? "The server isn’t answering yet. Kitch keeps trying on its own."
      : elapsed >= 20
        ? "Still lighting the stove. Thanks for waiting; it’s nearly there."
        : waking
          ? "Kitch has been resting, so the first visit after a quiet spell takes a little longer. Usually under a minute."
          : "";

  return (
    <main className={`warmup ${failed ? "failed" : ""} ${waking ? "waking" : ""}`} aria-busy={!failed}>
      <div className="brand on-dark warmup-brand"><Mark size={30} /><span>Kitch</span></div>
      <div className="warmup-center">
        <div className="warmup-stove" aria-hidden="true">
          <span className="warmup-glow" />
          {!failed && <span className="steam"><i /><i /><i /></span>}
          <Art className="warmup-kadai" src="/art/spot-recipe.png" alt="" />
        </div>
        <h1>{title}</h1>
        <p className="warmup-body" aria-live="polite">{body}</p>
        {failed ? (
          <div className="warmup-actions">
            <button type="button" className="btn hero-primary" onClick={onRetry}>Try again</button>
            {startup?.message && <p className="warmup-detail">{startup.message}</p>}
          </div>
        ) : waking && (
          <p className="warmup-time"><span className="warmup-dot" />Waking for {elapsed}s</p>
        )}
      </div>
    </main>
  );
}

// Footer links to the public legal pages and the privacy contact.
export function LegalLinks({ className = "" }) {
  return (
    <nav className={`legal-links ${className}`} aria-label="Legal">
      <a href="/privacy" target="_blank" rel="noopener">Privacy Policy</a>
      <a href="/terms" target="_blank" rel="noopener">Terms of Use</a>
      {LEGAL_CONTACT_EMAIL && <a href={`mailto:${LEGAL_CONTACT_EMAIL}`}>Contact</a>}
    </nav>
  );
}

// The standalone notice: what Kitch collects, why, who processes it, and the
// person's rights, followed by two explicit, unticked confirmations.
function ConsentNotice({ k, compact = false }) {
  const { legalConsent, setLegalConsent } = k;
  return (
    <div className={`consent ${compact ? "compact" : ""}`}>
      {!compact && (
        <ul className="consent-list">
          <li><strong>What Kitch keeps:</strong> your Google name and email, household member names, meal plans, recipes, pantry and shopping lists, and the messages you send.</li>
          <li><strong>Health-related data:</strong> each member’s nutrition logs and meal or fridge photos.</li>
          <li><strong>Grocery orders:</strong> carts and delivery addresses, only if you connect Swiggy Instamart. Kitch never sees payment details.</li>
          <li><strong>Why:</strong> only to plan, cook, shop and log for your household. No ads, no selling data.</li>
          <li><strong>Who processes it:</strong> Google (Sign-In and Gemini AI), Supabase and Vercel, and Swiggy for orders you approve.</li>
          <li><strong>Your control:</strong> delete everything any time from Household settings, or write in to see or correct your data.</li>
        </ul>
      )}
      <label className="consent-check">
        <input type="checkbox" checked={legalConsent.ageConfirmed} onChange={event => setLegalConsent({ ageConfirmed: event.target.checked })} />
        <span>I am 18 or older.</span>
      </label>
      <label className="consent-check">
        <input type="checkbox" checked={legalConsent.accepted} onChange={event => setLegalConsent({ accepted: event.target.checked })} />
        <span>I agree to the <a href="/terms" target="_blank" rel="noopener">Terms of Use</a> and consent to Kitch processing my household’s data, including health-related nutrition logs, as described in the <a href="/privacy" target="_blank" rel="noopener">Privacy Policy</a>.</span>
      </label>
    </div>
  );
}

// Shown once to a signed-in owner who has not accepted the current notice.
export function ConsentScreen({ k }) {
  const ready = k.legalConsent.ageConfirmed && k.legalConsent.accepted;
  return (
    <main className="onboarding">
      <form className="onboarding-card consent-card" onSubmit={event => { event.preventDefault(); k.acceptLegalConsent(); }}>
        <div className="brand"><Mark size={30} /><span>Kitch</span></div>
        <h1>Before you continue</h1>
        <p>Here is what Kitch does with your household’s data. Please read it and confirm.</p>
        <ConsentNotice k={k} />
        {k.consentError && <p className="form-error" role="alert">{k.consentError}</p>}
        <button type="submit" className="btn primary lg block" disabled={!ready || k.isConsentSaving}>
          {k.isConsentSaving ? "Saving…" : "Agree and continue"}
        </button>
        <button type="button" className="btn quiet sm consent-out" onClick={k.signOut}>Not now, sign out</button>
        <LegalLinks />
      </form>
    </main>
  );
}

const SIGN_IN_POINTS = [
  { icon: "calendar", text: "One dated meal plan the whole household shares" },
  { icon: "basket", text: "Pantry-aware groceries, sent to Instamart or Zepto for review" },
  { icon: "chart", text: "Personal nutrition logs for each member" }
];

export function SignInScreen({ k }) {
  const { googleButtonRef, renderGoogleButton, authError } = k;
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID;
  const ready = k.legalConsent.ageConfirmed && k.legalConsent.accepted;
  return (
    <main className="signin">
      <Art className="signin-art" src="/art/signin.png" fallback={HERO_FALLBACK} alt="" />
      <section className="signin-panel" aria-labelledby="signin-title">
        <div className="brand on-dark"><Mark size={34} /><span>Kitch</span></div>
        <h1 id="signin-title"><span>Your household kitchen,</span> <span>planned together</span></h1>
        <p className="signin-lede">Kitch plans meals, writes recipes from what you have, prepares grocery carts, and keeps each person’s nutrition log. Nothing is ordered until you approve it.</p>
        <ul className="signin-points">
          {SIGN_IN_POINTS.map(point => (
            <li key={point.text}><Icon name={point.icon} />{point.text}</li>
          ))}
        </ul>
        <div className="signin-card">
          <h2>Open your household</h2>
          <p>Sign in with the Google account that owns this household.</p>
          <ConsentNotice k={k} compact />
          <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onLoad={renderGoogleButton} />
          <div className={`google-gate ${ready ? "open" : ""}`}>
            <div ref={googleButtonRef} className="google-button" aria-hidden={!ready} />
            {!ready && <span className="google-gate-cover" aria-hidden="true" />}
          </div>
          {!ready && <p className="google-gate-hint">Tick both boxes to sign in.</p>}
          {!clientId && <p className="form-error">Google Sign-In is not configured for this deployment.</p>}
          {authError && <p className="form-error" role="alert">{authError}</p>}
          <p className="signin-owner"><Icon name="household" size="sm" />One Google account owns the household. Everyone else is a member you switch to inside Kitch, so they don’t need to sign in.</p>
        </div>
        <LegalLinks className="on-dark" />
      </section>
    </main>
  );
}

export function OnboardingScreen({ k }) {
  const { onboardingMembers, setOnboardingMembers } = k;
  return (
    <main className="onboarding">
      <form className="onboarding-card" onSubmit={k.submitHouseholdOnboarding}>
        <Art className="onboarding-spot" src="/art/spot-household.png" alt="" />
        <div className="brand"><Mark size={30} /><span>Kitch</span></div>
        <h1>Who shares this kitchen?</h1>
        <p>Add everyone who eats from the household plan. Meal plans, pantry and groceries are shared; each person keeps their own nutrition log. The first name is the default.</p>
        <ol className="onboarding-members">
          {onboardingMembers.map((name, index) => (
            <li key={index}>
              <label className="visually-hidden" htmlFor={`member-${index}`}>{index === 0 ? "Your name" : `Member ${index + 1}`}</label>
              <span className="avatar sm" aria-hidden="true">{(name.trim()[0] || String(index + 1)).toUpperCase()}</span>
              <input
                id={`member-${index}`}
                className="input"
                autoFocus={index === 0}
                autoComplete="off"
                value={name}
                placeholder={index === 0 ? "Your name" : `Member ${index + 1}`}
                onChange={event => setOnboardingMembers(current => current.map((item, itemIndex) => (
                  itemIndex === index ? event.target.value : item
                )))}
              />
              {index > 0 && (
                <button
                  type="button"
                  className="icon-btn bare sm"
                  aria-label={`Remove member ${index + 1}`}
                  onClick={() => setOnboardingMembers(current => current.filter((_, itemIndex) => itemIndex !== index))}
                >
                  <Icon name="close" size="sm" />
                </button>
              )}
            </li>
          ))}
        </ol>
        <button type="button" className="btn quiet sm add-member" onClick={() => setOnboardingMembers(current => [...current, ""])}>
          <Icon name="plus" size="sm" /> Add another person
        </button>
        {k.onboardingError && <p className="form-error" role="alert">{k.onboardingError}</p>}
        <button type="submit" className="btn primary lg block" disabled={k.isOnboardingSaving || k.householdBootstrap?.unavailable}>
          {k.isOnboardingSaving ? "Setting up your kitchen…" : "Start planning"}
        </button>
      </form>
    </main>
  );
}
