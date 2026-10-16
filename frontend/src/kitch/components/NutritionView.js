"use client";

import Icon from "./Icon.js";
import Art from "./Art.js";
import { LoadingCard } from "./Skeleton.js";
import { CalorieRing, MacroBars } from "./NutritionBits.js";
import { formatPlanDate, shiftIsoDate } from "../../app/householdConfig.js";
import { NUTRITION_MEALS, formatNutritionNumber, currentNutritionMealType } from "../lib/helpers.js";

const METRICS = [["calories", "Calories", "kcal"], ["protein", "Protein", "g"], ["carbs", "Carbs", "g"], ["fat", "Fats", "g"]];
const MEAL_ICON = { breakfast: "breakfast", lunch: "lunch", snack: "snack", dinner: "dinner" };
const GOALS = [["daily_calorie_target", "Calories", "kcal"], ["protein_target_g", "Protein", "g"], ["carbs_target_g", "Carbs", "g"], ["fat_target_g", "Fats", "g"]];

function EntryEditor({ k }) {
  const editor = k.nutritionEntryEditor;
  const set = (patch) => k.setNutritionEntryEditor(current => ({ ...current, ...patch }));
  return (
    <form className="entry-editor" onSubmit={event => { event.preventDefault(); k.saveNutritionEntry(); }}>
      <label className="field wide">Food<input className="input" autoFocus value={editor.meal_name} onChange={event => set({ meal_name: event.target.value })} placeholder="e.g. Dal tadka with rice" /></label>
      <label className="field">Meal
        <select className="select" value={editor.meal_type} onChange={event => set({ meal_type: event.target.value })}>
          {NUTRITION_MEALS.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
        </select>
      </label>
      <label className="field">Quantity<input className="input" type="number" min="0.01" step="0.01" value={editor.quantity} onChange={event => set({ quantity: event.target.value })} /></label>
      <label className="field">Unit<input className="input" value={editor.unit} onChange={event => set({ unit: event.target.value })} /></label>
      <label className="field">Calories<input className="input" type="number" min="0" value={editor.calories} onChange={event => set({ calories: event.target.value })} /></label>
      <label className="field">Protein (g)<input className="input" type="number" min="0" value={editor.protein} onChange={event => set({ protein: event.target.value })} /></label>
      <label className="field">Carbs (g)<input className="input" type="number" min="0" value={editor.carbs} onChange={event => set({ carbs: event.target.value })} /></label>
      <label className="field">Fats (g)<input className="input" type="number" min="0" value={editor.fat} onChange={event => set({ fat: event.target.value })} /></label>
      <div className="entry-editor-actions">
        <button type="button" className="btn quiet" onClick={() => k.setNutritionEntryEditor(null)}>Cancel</button>
        <button type="submit" className="btn primary" disabled={k.isNutritionSaving}>{editor.id ? "Save changes" : "Add to diary"}</button>
      </div>
    </form>
  );
}

function Trend({ k }) {
  const unit = METRICS.find(([key]) => key === k.nutritionTrendMetric)?.[2] || "";
  const days = k.nutritionDashboard.days || [];
  // Leave headroom above the tallest bar so the goal label never meets the header.
  const scaleMax = Math.max(1, k.nutritionTrendMax * 1.18);
  const goalPct = Math.max(4, (Number(k.nutritionTrendTarget) / scaleMax) * 100);
  return (
    <section className="card card-pad trend" aria-labelledby="trend-title">
      <div className="section-head">
        <h2 id="trend-title">This week</h2>
        <div className="push segmented small" role="group" aria-label="Metric">
          {METRICS.map(([key, label]) => (
            <button key={key} type="button" aria-pressed={k.nutritionTrendMetric === key} onClick={() => k.setNutritionTrendMetric(key)}>{label}</button>
          ))}
        </div>
      </div>
      <div className="trend-plot">
        <span className="goal-line" style={{ bottom: `${goalPct}%` }}><em>Goal {formatNutritionNumber(k.nutritionTrendTarget)} {unit}</em></span>
        <div className="trend-chart">
          {days.map(day => {
            const value = Number(day.totals?.[k.nutritionTrendMetric] || 0);
            const height = Math.min(100, (value / scaleMax) * 100);
            const selected = day.date === k.selectedNutritionDate;
            return (
              <button
                key={day.date}
                type="button"
                className={`trend-day ${selected ? "selected" : ""} ${value > Number(k.nutritionTrendTarget) ? "over" : ""}`}
                aria-pressed={selected}
                aria-label={`${day.weekday}: ${formatNutritionNumber(value)} ${unit}`}
                onClick={() => k.navigateNutritionDate(day.date)}
              >
                <span className="trend-bar"><i style={{ height: `${Math.max(value > 0 ? 3 : 0, height)}%` }} /></span>
              </button>
            );
          })}
        </div>
      </div>
      <div className="trend-labels" aria-hidden="true">
        {days.map(day => (
          <small key={day.date} className={day.date === k.selectedNutritionDate ? "selected" : ""}>{String(day.weekday || formatPlanDate(day.date, { weekday: "short" })).slice(0, 3)}</small>
        ))}
      </div>
    </section>
  );
}

export default function NutritionView({ k, ask }) {
  const day = k.selectedNutritionDate;
  const totals = k.nutritionTotals;
  const isToday = day && day === k.nutritionDashboard.today;

  return (
    <div className="page nutrition">
      <header className="page-header with-actions">
        <div>
          <h1 className="page-title">{k.activeUser}’s nutrition</h1>
          <p className="page-sub">Personal to {k.activeUser}. Switching members changes whose diary you see; shared meal plans stay the same.</p>
        </div>
        <div className="date-nav" role="group" aria-label="Diary date">
          <button type="button" className="icon-btn" aria-label="Previous day" disabled={!day} onClick={() => k.navigateNutritionDate(shiftIsoDate(day, -1))}><Icon name="left" /></button>
          <strong>{day ? (isToday ? "Today" : formatPlanDate(day, { weekday: "short", day: "numeric", month: "short" })) : "—"}</strong>
          <button type="button" className="icon-btn" aria-label="Next day" disabled={!day} onClick={() => k.navigateNutritionDate(shiftIsoDate(day, 1))}><Icon name="right" /></button>
          {!isToday && <button type="button" className="btn sm" disabled={!k.nutritionDashboard.today} onClick={() => k.navigateNutritionDate(k.nutritionDashboard.today)}>Back to today</button>}
        </div>
      </header>

      {!k.nutritionDashboard.start_date ? (
        <div className="nutrition-top">
          <LoadingCard label={`Loading ${k.activeUser}’s diary`} rows={3} />
          <LoadingCard label="Loading this week" rows={3} />
        </div>
      ) : (<>
      <div className="nutrition-top">
        <section className="card card-pad day-summary" aria-labelledby="day-summary-title">
          <h2 id="day-summary-title" className="visually-hidden">Day summary</h2>
          <CalorieRing value={totals.calories} target={k.targetCalories} size={148} stroke={12} />
          <MacroBars rows={k.nutritionMacroRows.map(row => ({ key: row.key, label: row.label, value: row.value, target: row.target }))} />
        </section>
        <Trend k={k} />
      </div>

      <div className="nutrition-grid">
        <section className="card card-pad diary" aria-labelledby="diary-title">
          <div className="section-head">
            <h2 id="diary-title">Food log</h2>
            <span className="muted">{formatPlanDate(day, { weekday: "long", day: "numeric", month: "long" })}</span>
            <div className="push">
              <button type="button" className="btn soft sm" onClick={() => k.openNutritionEntryEditor(currentNutritionMealType(k.nutritionDashboard.timezone))}><Icon name="plus" size="sm" />Add food</button>
              <button type="button" className="btn quiet sm" onClick={() => ask(`I ate `)}>Tell Kitch</button>
            </div>
          </div>

          <div className="meal-groups">
            {NUTRITION_MEALS.map(meal => {
              const entries = k.nutritionEntriesByMeal[meal.id] || [];
              const sum = entries.reduce((acc, entry) => ({
                calories: acc.calories + Number(entry.calories || 0),
                protein: acc.protein + Number(entry.macros?.protein || 0),
                carbs: acc.carbs + Number(entry.macros?.carbs || 0),
                fat: acc.fat + Number(entry.macros?.fat || 0)
              }), { calories: 0, protein: 0, carbs: 0, fat: 0 });
              const expanded = Boolean(k.expandedNutritionMeals[meal.id]);
              const editingHere = k.nutritionEntryEditor?.meal_type === meal.id;
              return (
                <section key={meal.id} className={`meal-group ${expanded ? "open" : ""}`}>
                  <button type="button" className="meal-group-head" aria-expanded={expanded} onClick={() => k.setExpandedNutritionMeals(current => ({ ...current, [meal.id]: !current[meal.id] }))}>
                    <span className={`slot-icon ${meal.id}`}><Icon name={MEAL_ICON[meal.id]} size="sm" /></span>
                    <strong>{meal.label}</strong>
                    <span className="muted">{entries.length ? `${entries.length} ${entries.length === 1 ? "item" : "items"}` : "Nothing logged"}</span>
                    <span className="meal-group-sum"><b>{formatNutritionNumber(sum.calories)}</b> kcal<span className="macro-mini">P {formatNutritionNumber(sum.protein)} · C {formatNutritionNumber(sum.carbs)} · F {formatNutritionNumber(sum.fat)}</span></span>
                    <Icon name={expanded ? "up" : "down"} size="sm" />
                  </button>
                  {expanded && (
                    <div className="meal-group-body">
                      {entries.length > 0 && (
                        <div className="entry-table" role="table" aria-label={`${meal.label} entries`}>
                          <div className="entry-row head" role="row">
                            <span role="columnheader">Food</span><span role="columnheader">Amount</span><span role="columnheader">kcal</span>
                            <span role="columnheader">Protein</span><span role="columnheader">Carbs</span><span role="columnheader">Fats</span>
                            <span role="columnheader"><span className="visually-hidden">Actions</span></span>
                          </div>
                          {entries.map(entry => (
                            <div key={entry.id} role="row" className="entry-row">
                              <strong role="cell">{entry.name}</strong>
                              <span role="cell">{formatNutritionNumber(entry.quantity)} {entry.unit}</span>
                              <span role="cell">{formatNutritionNumber(entry.calories)}</span>
                              <span role="cell">{formatNutritionNumber(entry.macros.protein)} g</span>
                              <span role="cell">{formatNutritionNumber(entry.macros.carbs)} g</span>
                              <span role="cell">{formatNutritionNumber(entry.macros.fat)} g</span>
                              <span role="cell" className="row-actions">
                                <button type="button" className="icon-btn bare sm" aria-label={`Edit ${entry.name}`} onClick={() => k.openNutritionEntryEditor(meal.id, entry)}><Icon name="edit" size="sm" /></button>
                                <button type="button" className="icon-btn bare sm danger" aria-label={`Delete ${entry.name}`} onClick={() => k.deleteNutritionEntry(entry.id)}><Icon name="trash" size="sm" /></button>
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      {editingHere && <EntryEditor k={k} />}
                      {!editingHere && (
                        <button type="button" className="btn quiet sm add-food" onClick={() => k.openNutritionEntryEditor(meal.id)}><Icon name="plus" size="sm" />Add to {meal.label.toLowerCase()}</button>
                      )}
                    </div>
                  )}
                </section>
              );
            })}
          </div>

          {(k.selectedNutritionDay.entries?.length || 0) > 0 && (
            <div className="danger-zone">
              <p>Clearing removes every entry {k.activeUser} logged on this day.</p>
              <button type="button" className="btn danger sm" onClick={k.resetDailyLogs}><Icon name="trash" size="sm" />Clear day</button>
            </div>
          )}
        </section>

        <aside className="nutrition-side">
          <section className="card card-pad goals" aria-labelledby="goals-title">
            <div className="section-head">
              <h2 id="goals-title">Daily goals</h2>
              {!k.nutritionGoalEditor && <div className="push"><button type="button" className="btn quiet sm" onClick={() => k.setNutritionGoalEditor({ ...k.nutritionTargets })}><Icon name="edit" size="sm" />Edit</button></div>}
            </div>
            {k.nutritionGoalEditor ? (
              <form className="goal-editor" onSubmit={event => { event.preventDefault(); k.saveNutritionGoals(); }}>
                {GOALS.map(([key, label, unit]) => (
                  <label key={key} className="goal-field">
                    <span>{label}</span>
                    <input className="input sm" type="number" min="1" value={k.nutritionGoalEditor[key]} onChange={event => k.setNutritionGoalEditor(current => ({ ...current, [key]: event.target.value }))} />
                    <em>{unit}</em>
                  </label>
                ))}
                <div className="entry-editor-actions">
                  <button type="button" className="btn quiet sm" onClick={() => k.setNutritionGoalEditor(null)}>Cancel</button>
                  <button type="submit" className="btn primary sm" disabled={k.isNutritionSaving}>Save goals</button>
                </div>
              </form>
            ) : (
              <dl className="goal-list">
                {GOALS.map(([key, label, unit]) => (
                  <div key={key}><dt>{label}</dt><dd>{k.nutritionTargets[key] ?? "—"} {unit}</dd></div>
                ))}
              </dl>
            )}
          </section>
          <section className="card tip">
            <Art className="tip-art" src="/art/spot-nutrition.png" alt="" />
            <div>
              <h2>Today’s note</h2>
              <p>{k.nutritionTip}</p>
            </div>
          </section>
        </aside>
      </div>
      </>)}
    </div>
  );
}
