"use client";

import Icon from "./Icon.js";
import Art, { heroArtFor, HERO_FALLBACK } from "./Art.js";
import { MacroBars, CalorieRing } from "./NutritionBits.js";
import { SkeletonLine } from "./Skeleton.js";
import { formatPlanDate, getWeekStartForDate, shiftIsoDate, MEAL_SLOTS } from "../../app/householdConfig.js";
import { getMealTitle, hasMealTitle, formatRelativeCheckedTime, MEAL_SLOT_LABELS } from "../lib/helpers.js";

const SLOT_TIMES = { breakfast: "8:30 am", lunch: "1:00 pm", dinner: "8:30 pm" };
const TODAY_SLOT_LABEL = { breakfast: "This morning’s breakfast", lunch: "Today’s lunch", dinner: "Tonight’s dinner" };

const longDate = (iso) => formatPlanDate(iso, { weekday: "long", day: "numeric", month: "long" });
// A saved recipe "Aloo gobi" belongs to the planned meal "Aloo gobi with roti and dal fry".
const sameTitle = (recipe, meal) => {
  const a = String(recipe || "").trim().toLowerCase();
  const b = String(meal || "").trim().toLowerCase();
  return Boolean(a && b) && (a === b || b.startsWith(a) || a.startsWith(b));
};

function Hero({ k, ask, go }) {
  const focus = k.firstPlannedFocusMeal;
  const planned = Boolean(focus.planDate);
  const isToday = planned && focus.planDate === k.mealPlan.today;
  const when = planned
    ? (isToday ? `${TODAY_SLOT_LABEL[focus.slot]} · ${longDate(focus.planDate)}` : `${MEAL_SLOT_LABELS[focus.slot]} · ${longDate(focus.planDate)}`)
    : "No meals planned yet";
  const recipeReady = planned && sameTitle(k.activeRecipeTitle, focus.title);
  const greeting = k.timeGreeting === "Welcome" ? `Welcome, ${k.activeUser}` : `${k.timeGreeting}, ${k.activeUser}`;
  // Until the week has loaded, "no meals planned" would be a guess, not a fact.
  const loading = !planned && !k.mealPlan.week_start;

  return (
    <section className="hero" aria-labelledby="hero-title">
      <Art className="hero-art" src={heroArtFor(k.timeGreeting)} fallback={HERO_FALLBACK} alt="" />
      <div className="hero-copy">
        <h1 id="hero-title">{greeting}</h1>
        {loading ? (
          <div className="hero-focus" aria-busy="true">
            <p className="hero-when"><Icon name="calendar" size="sm" />Checking today’s plan…</p>
            <SkeletonLine className="on-dark" width="62%" height={30} />
            <SkeletonLine className="on-dark" width="30%" height={14} />
          </div>
        ) : (
        <div className="hero-focus">
          <p className="hero-when"><Icon name={planned ? focus.slot : "calendar"} size="sm" />{when}</p>
          {planned ? (
            <>
              <h2>{focus.title}</h2>
              <p className="hero-meta">For {k.householdSize} {k.householdSize === 1 ? "person" : "people"}{recipeReady ? " · recipe saved" : ""}</p>
              <div className="hero-actions">
                {recipeReady
                  ? <button type="button" className="btn hero-primary" onClick={() => go("recipes")}>Open recipe</button>
                  : <button type="button" className="btn hero-primary" onClick={() => ask(`Show me the recipe for ${focus.title} planned on ${focus.planDate}`)}>Get the recipe</button>}
                <button type="button" className="btn hero-ghost" onClick={() => ask(`Change ${longDate(focus.planDate)} ${focus.slot} to `)}>Swap meal</button>
                <button type="button" className="btn hero-ghost" onClick={() => ask(`Log ${focus.title} planned on ${focus.planDate} for ${k.activeUser}`)}>Log as eaten</button>
              </div>
            </>
          ) : (
            <>
              <h2>Let’s plan the week together</h2>
              <p className="hero-meta">Tell Kitch what the household likes; it plans dated breakfasts, lunches and dinners for {k.householdSize}.</p>
              <div className="hero-actions">
                <button type="button" className="btn hero-primary" onClick={() => ask("Plan next week for the whole household")}>Plan next week</button>
                <button type="button" className="btn hero-ghost" onClick={() => ask("Help me choose meals for this household")}>Help me choose</button>
              </div>
            </>
          )}
        </div>
        )}
      </div>
    </section>
  );
}

function WeekPlan({ k, ask, go }) {
  const { mealPlan } = k;
  const days = k.planDays;
  const today = mealPlan.today;
  const containsToday = days.some(day => day.plan_date === today);
  const activeDay = days.find(day => day.plan_date === k.selectedPlanDate)
    || days.find(day => day.plan_date === today)
    || days.find(day => MEAL_SLOTS.some(slot => hasMealTitle(day[slot])))
    || days[0];
  const weekTitle = containsToday
    ? "This week"
    : mealPlan.week_start ? `Week of ${formatPlanDate(mealPlan.week_start, { day: "numeric", month: "long" })}` : "This week";
  const range = mealPlan.week_start && mealPlan.week_end
    ? `${formatPlanDate(mealPlan.week_start, { day: "numeric", month: "short" })} – ${formatPlanDate(mealPlan.week_end, { day: "numeric", month: "short" })}`
    : "Loading…";
  const planPrompt = containsToday || !mealPlan.week_start
    ? "Plan next week for the whole household"
    : `Plan meals for ${mealPlan.week_start} through ${mealPlan.week_end}`;
  const weekIsEmpty = days.length > 0 && !k.hasVisibleWeekPlan;

  return (
    <section className="card card-pad week" aria-labelledby="week-title">
      <div className="section-head">
        <h2 id="week-title">{weekTitle}</h2>
        <span className="muted">{range}</span>
        <div className="push">
          <button type="button" className="icon-btn" aria-label="Previous week" disabled={!mealPlan.week_start} onClick={() => k.loadMealPlanWeek(shiftIsoDate(mealPlan.week_start, -7))}><Icon name="left" /></button>
          <button type="button" className="btn sm" disabled={!today || containsToday} onClick={() => k.loadMealPlanWeek(getWeekStartForDate(today), today)}>Today</button>
          <button type="button" className="icon-btn" aria-label="Next week" disabled={!mealPlan.week_start} onClick={() => k.loadMealPlanWeek(shiftIsoDate(mealPlan.week_start, 7))}><Icon name="right" /></button>
          <button type="button" className="btn soft sm" disabled={days.length === 0} onClick={() => ask(planPrompt)}>{containsToday ? "Plan next week" : "Plan this week"}</button>
        </div>
      </div>

      <div className="day-strip" role="tablist" aria-label="Days">
        {days.map(day => {
          const isToday = day.plan_date === today;
          const isPast = today && day.plan_date < today;
          const selected = activeDay?.plan_date === day.plan_date;
          const filled = MEAL_SLOTS.map(slot => hasMealTitle(day[slot]));
          return (
            <button
              key={day.plan_date}
              type="button"
              role="tab"
              aria-selected={selected}
              className={`day ${isToday ? "today" : ""} ${isPast ? "past" : ""} ${selected ? "selected" : ""}`}
              onClick={() => k.setSelectedPlanDate(day.plan_date)}
              aria-label={`${formatPlanDate(day.plan_date, { weekday: "long", day: "numeric", month: "long" })}: ${filled.filter(Boolean).length} of 3 meals planned`}
            >
              <small>{isToday ? "Today" : formatPlanDate(day.plan_date, { weekday: "short" })}</small>
              <b>{formatPlanDate(day.plan_date, { day: "numeric" })}</b>
              <span className="dots" aria-hidden="true">{filled.map((on, index) => <i key={index} className={on ? "on" : ""} />)}</span>
            </button>
          );
        })}
      </div>

      {days.length === 0 && (
        <div className="week-loading" aria-busy="true">
          <span className="visually-hidden">Loading the week</span>
          <div className="day-strip">{Array.from({ length: 7 }).map((_, index) => <SkeletonLine key={index} height={66} className="day-skeleton" />)}</div>
          {[0, 1, 2].map(index => <SkeletonLine key={index} height={18} width={`${70 - index * 12}%`} className="meal-skeleton" />)}
        </div>
      )}

      {weekIsEmpty && (
        <div className="callout week-callout">
          <Icon name="calendar" />
          <div>
            <strong>Nothing planned for {range}</strong>
            {k.hasAnyMealPlan ? "Plans for other dates are kept as they are." : "Ask Kitch for a plan, or plan a single day below."}
          </div>
          {k.nextPlannedOutsideVisibleWeek && (
            <button type="button" className="btn sm" onClick={() => k.loadMealPlanWeek(getWeekStartForDate(k.nextPlannedOutsideVisibleWeek), k.nextPlannedOutsideVisibleWeek)}>
              Go to {formatPlanDate(k.nextPlannedOutsideVisibleWeek, { weekday: "short", day: "numeric", month: "short" })}
            </button>
          )}
        </div>
      )}

      {activeDay && (
        <ul className="meals" aria-label={`Meals for ${longDate(activeDay.plan_date)}`}>
          {MEAL_SLOTS.map(slot => {
            const title = getMealTitle(activeDay[slot], "");
            const planned = Boolean(title.trim());
            const upNext = planned && activeDay.plan_date === today && slot === k.currentMealSlot;
            const recipeReady = planned && sameTitle(k.activeRecipeTitle, title);
            return (
              <li key={slot} className={`meal ${planned ? "" : "unplanned"}`}>
                <span className={`slot-icon ${slot}`}><Icon name={slot} /></span>
                <div className="meal-slot">
                  <strong>{MEAL_SLOT_LABELS[slot]}</strong>
                  <small>{SLOT_TIMES[slot]}</small>
                </div>
                <p className="meal-title">{planned ? title : "Not planned"}</p>
                {upNext && <span className="meal-status"><Icon name="clock" size="sm" />Up next</span>}
                <div className="meal-actions">
                  {planned ? (
                    <>
                      <button type="button" className="btn quiet sm" onClick={() => recipeReady ? go("recipes") : ask(`Show me the recipe for ${title} planned on ${activeDay.plan_date}`)}>Recipe</button>
                      <button type="button" className="btn quiet sm" onClick={() => ask(`Change ${longDate(activeDay.plan_date)} ${slot} to `)}>Swap</button>
                      <button type="button" className="btn quiet sm" onClick={() => ask(`Log ${title} planned on ${activeDay.plan_date} for ${k.activeUser}`)}>Log</button>
                    </>
                  ) : (
                    <button type="button" className="btn soft sm" onClick={() => ask(`Plan ${slot} for ${longDate(activeDay.plan_date)}`)}>Plan {slot}</button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function TodayNutrition({ k, go }) {
  if (k.liveStateUser !== k.activeUser) {
    return <section className="card card-pad personal loading-card" aria-busy="true"><span className="visually-hidden">Loading {k.activeUser}’s day</span><SkeletonLine width="46%" height={20} /><SkeletonLine height={108} width="108px" /><SkeletonLine width="80%" /></section>;
  }
  return (
    <section className="card card-pad personal" aria-labelledby="today-nutrition-title">
      <div className="section-head">
        <h2 id="today-nutrition-title">{k.activeUser} today</h2>
        <div className="push"><button type="button" className="btn quiet sm" onClick={() => go("analytics")}>Diary <Icon name="right" size="sm" /></button></div>
      </div>
      <div className="today-nutrition">
        <CalorieRing value={k.loggedCal} target={k.targetCalories} size={108} />
        <MacroBars rows={[
          { key: "protein", label: "Protein", value: k.loggedProt, target: k.targetProtein },
          { key: "carbs", label: "Carbs", value: k.loggedCarb, target: k.targetCarbs },
          { key: "fat", label: "Fats", value: k.loggedFat, target: k.targetFat }
        ]} />
      </div>
      {k.loggedCal <= 0 && <p className="muted small-note">Nothing logged yet. Tell Kitch what you ate, or send a photo of your plate.</p>}
    </section>
  );
}

function KitchenStatus({ k, go }) {
  if (k.liveStateUser !== k.activeUser) {
    return <section className="card card-pad loading-card" aria-busy="true"><span className="visually-hidden">Loading pantry and groceries</span><SkeletonLine width="52%" height={16} /><SkeletonLine width="70%" /><SkeletonLine width="48%" height={16} /><SkeletonLine width="64%" /></section>;
  }
  const pantryCount = k.pantryStock.length;
  const toBuy = k.eligibleBuyCount;
  const providerLabel = k.selectedProvider.id ? k.selectedProvider.label : "an ordering app";
  return (
    <section className="card kitchen" aria-label="Kitchen status">
      <button type="button" className="kitchen-row" onClick={() => go("groceries", "pantry")}>
        <span className="tile sage"><Icon name="pantry" /></span>
        <span className="kitchen-text">
          <strong>Pantry · {pantryCount} {pantryCount === 1 ? "item" : "items"}</strong>
          <small>{pantryCount === 0 ? "Empty. Add items or send a fridge photo." : k.pantryReviewedAt ? `Reviewed ${formatRelativeCheckedTime(k.pantryReviewedAt)}` : "Not reviewed yet"}</small>
        </span>
        <Icon name="right" className="kitchen-chev" />
      </button>
      <button type="button" className="kitchen-row" onClick={() => go("groceries", "cart")}>
        <span className="tile turmeric"><Icon name="basket" /></span>
        <span className="kitchen-text">
          <strong>Groceries · {toBuy} to buy</strong>
          <small className={k.providerCartReview ? "good" : ""}>
            {k.providerCartReview ? `${providerLabel} cart is ready to review` : toBuy > 0 ? `Not sent to ${providerLabel} yet` : "Nothing to buy right now"}
          </small>
        </span>
        <Icon name="right" className="kitchen-chev" />
      </button>
      {k.activeRecipeTitle && (
        <button type="button" className="kitchen-row" onClick={() => go("recipes")}>
          <span className="tile plum"><Icon name="recipe" /></span>
          <span className="kitchen-text">
            <strong>Latest recipe</strong>
            <small>{k.activeRecipeTitle}</small>
          </span>
          <Icon name="right" className="kitchen-chev" />
        </button>
      )}
    </section>
  );
}

export default function HouseholdView({ k, ask, go }) {
  return (
    <div className="page household">
      <Hero k={k} ask={ask} go={go} />
      <div className="household-grid">
        <WeekPlan k={k} ask={ask} go={go} />
        <div className="household-side">
          <TodayNutrition k={k} go={go} />
          <KitchenStatus k={k} go={go} />
        </div>
      </div>
    </div>
  );
}
