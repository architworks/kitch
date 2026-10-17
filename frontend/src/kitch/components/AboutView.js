"use client";

import Icon from "./Icon.js";
import Art, { HERO_FALLBACK } from "./Art.js";
import { SnapCard } from "./PhotoCapture.js";
import { LegalLinks } from "./EntryScreens.js";

const FLOW = [
  { icon: "calendar", title: "Plan", body: "Dated breakfasts, lunches and dinners for everyone at home." },
  { icon: "recipe", title: "Cook", body: "Recipes written from what’s already in your pantry." },
  { icon: "basket", title: "List", body: "Missing ingredients land on one shared shopping list." },
  { icon: "store", title: "Prepare", body: "Kitch fills an Instamart or Zepto cart for you to check." },
  { icon: "checkCircle", title: "Approve", body: "You review the real cart and place the order yourself." }
];

const ASKS = [
  "Plan next week, high protein, no mushrooms",
  "We have paneer, capsicum and peas. What’s for dinner?",
  "I had two rotis and dal for lunch",
  "Always buy Amul butter"
];

export default function AboutView({ k, ask, go }) {
  return (
    <div className="page about">
      <section className="about-hero">
        <Art className="about-hero-art" src="/art/hero-afternoon.png" fallback={HERO_FALLBACK} alt="" />
        <div className="about-hero-copy">
          <h1>A kitchen companion for the whole household</h1>
          <p>Kitch plans what you’ll eat, learns what’s in the kitchen from a photo of your fridge, turns recipes into a shopping list, and logs each person’s meals from a photo of their plate.</p>
          <div className="hero-actions">
            <button type="button" className="btn hero-primary" onClick={() => go("planner")}>Open the household plan</button>
            <button type="button" className="btn hero-ghost" onClick={() => ask("Plan next week for the whole household")}>Ask Kitch to plan</button>
          </div>
        </div>
      </section>

      <section className="about-split">
        <article className="card card-pad">
          <span className="tile sage"><Icon name="household" /></span>
          <h2>Shared by everyone</h2>
          <p>One meal plan, one pantry, one shopping list. When someone changes dinner, the whole household sees it.</p>
        </article>
        <article className="card card-pad">
          <span className="tile turmeric"><Icon name="chart" /></span>
          <h2>Personal where it matters</h2>
          <p>Nutrition logs and goals belong to whoever is logging. {k.householdMembers.length > 1 ? `${k.householdMembers.map(member => member.label).join(", ")} each keep their own.` : "Each member keeps their own."}</p>
        </article>
      </section>

      <section className="card card-pad about-flow" aria-labelledby="flow-title">
        <h2 id="flow-title">From plan to doorstep</h2>
        <ol>
          {FLOW.map((step, index) => (
            <li key={step.title}>
              <span className="flow-n" aria-hidden="true">{index + 1}</span>
              <Icon name={step.icon} />
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="about-snap" aria-labelledby="snap-title">
        <div className="about-snap-head">
          <h2 id="snap-title">Point your camera at it</h2>
          <p>No typing out a fridge full of groceries, no guessing calories. One photo is enough, and nothing is saved until Kitch is sure what it shows.</p>
        </div>
        <div className="about-snap-grid">
          <SnapCard k={k} kind="pantry" as="article" body="Photograph the fridge or a shelf. Kitch adds what it spots to the shared pantry, and future grocery orders skip what you already have." />
          <SnapCard k={k} kind="meal" as="article" body="Photograph what you’re about to eat. Kitch estimates calories, protein, carbs and fats and logs it to your own diary." />
        </div>
      </section>

      <section className="about-split">
        <article className="card card-pad about-asks">
          <h2>Just ask</h2>
          <p>Type like you’d talk at home, or send a photo of your plate or fridge.</p>
          <ul>
            {ASKS.map(text => (
              <li key={text}><button type="button" onClick={() => ask(text)}>“{text}”</button></li>
            ))}
          </ul>
        </article>
        <article className="card card-pad about-control">
          <span className="tile plum"><Icon name="shield" /></span>
          <h2>You approve every order</h2>
          <ul className="check-list">
            <li><Icon name="check" size="sm" />Kitch prepares the shopping list and the app cart.</li>
            <li><Icon name="check" size="sm" />You see real products, prices and anything unavailable.</li>
            <li><Icon name="check" size="sm" />Only the Place order button can buy. Chat never can.</li>
          </ul>
        </article>
      </section>

      <footer className="about-legal">
        <p>Kitch is an independent personal project, not affiliated with Google, Swiggy, Zepto or Blinkit. Nutrition figures are estimates, not medical advice.</p>
        <LegalLinks />
      </footer>
    </div>
  );
}
