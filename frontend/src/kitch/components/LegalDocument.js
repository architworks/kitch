import Link from "next/link";
import { LEGAL_CONTACT_EMAIL, LEGAL_EFFECTIVE_DATE } from "../legal.js";

// Public, sign-in-free page shell for the Privacy Policy and Terms of Use.
export default function LegalDocument({ title, intro, children }) {
  return (
    <main className="legal-page">
      <header className="legal-head">
        <Link href="/" className="brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/kitch-chef-hat.svg" alt="" width="30" height="30" />
          <span>Kitch</span>
        </Link>
        <nav aria-label="Legal">
          <Link href="/privacy">Privacy Policy</Link>
          <Link href="/terms">Terms of Use</Link>
        </nav>
      </header>
      <article className="legal-body">
        <h1>{title}</h1>
        <p className="legal-meta">Effective {LEGAL_EFFECTIVE_DATE}</p>
        <p className="legal-intro">{intro}</p>
        {children}
      </article>
    </main>
  );
}

export function ContactLine() {
  return LEGAL_CONTACT_EMAIL
    ? <a href={`mailto:${LEGAL_CONTACT_EMAIL}`}>{LEGAL_CONTACT_EMAIL}</a>
    : <strong>[contact email to be added]</strong>;
}
