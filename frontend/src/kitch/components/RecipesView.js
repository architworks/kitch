"use client";

import Icon from "./Icon.js";
import Art from "./Art.js";
import { MEAL_SLOTS, formatPlanDate } from "../../app/householdConfig.js";
import { getIngredientName, getIngredientQuantity, getMealTitle, cartPurchaseAmount, formatCartQuantity, renderMarkdownContent } from "../lib/helpers.js";

const TABS = [
  ["recipe", "Method"],
  ["ingredients", "Ingredients"],
  ["nutrition", "Nutrition"],
  ["notes", "Tips & notes"]
];

function RecipeEmpty({ k, ask }) {
  const today = k.planDays.find(day => day.plan_date === k.mealPlan.today);
  const suggestions = today
    ? MEAL_SLOTS.map(slot => getMealTitle(today[slot], "")).filter(Boolean)
    : [];
  return (
    <section className="card recipe-empty">
      <div className="empty">
        <Art className="spot" src="/art/spot-recipe.png" alt="" />
        <h3>No recipe yet</h3>
        <p>Ask Kitch for a recipe and it will use what’s in your pantry, scale it for {k.householdSize}, and keep the ingredients ready for the shopping list.</p>
        <div className="actions">
          {suggestions.map(title => (
            <button key={title} type="button" className="btn soft" onClick={() => ask(`Show me the recipe for ${title} planned on ${k.mealPlan.today}`)}>Recipe for {title}</button>
          ))}
          <button type="button" className={`btn ${suggestions.length ? "" : "primary"}`} onClick={() => ask("Give me a recipe for ")}>Ask for a recipe</button>
        </div>
      </div>
    </section>
  );
}

export default function RecipesView({ k, ask, go }) {
  if (!k.activeRecipeCard) {
    return (
      <div className="page recipes">
        <header className="page-header">
          <h1 className="page-title">Recipes</h1>
          <p className="page-sub">The latest recipe Kitch wrote for your household, with its ingredients and shopping list.</p>
        </header>
        <RecipeEmpty k={k} ask={ask} />
      </div>
    );
  }

  const title = k.activeRecipeTitle;
  const ingredients = k.activeRecipeIngredients;
  const steps = k.activeRecipeSteps;
  const toBuy = k.recipeNeededCartItems.length;
  const createdAt = k.latestRecipeGroceryPlan?.createdAt || k.latestRecipeGroceryPlan?.created_at;

  return (
    <div className="page recipes">
      <section className="recipe-hero card">
        <div className="recipe-hero-copy">
          <p className="recipe-kind">{createdAt ? `Saved ${formatPlanDate(String(createdAt).slice(0, 10), { day: "numeric", month: "long" })}` : "Latest recipe"}</p>
          <h1 className="page-title">{title}</h1>
          {k.recipeDescription && <p className="recipe-desc">{k.recipeDescription}</p>}
          <ul className="recipe-stats">
            {k.recipeCookTime && <li><Icon name="clock" size="sm" />{k.recipeCookTime}</li>}
            <li><Icon name="people" size="sm" />Serves {k.recipeServings}</li>
            {k.recipeCalories && <li><Icon name="flame" size="sm" />{k.recipeCalories} kcal per serving</li>}
            <li><Icon name="list" size="sm" />{ingredients.length} ingredients</li>
          </ul>
          <div className="recipe-actions">
            <button type="button" className="btn primary" onClick={() => ask(`Log ${title} for ${k.activeUser}`)}>Log as eaten</button>
            <button type="button" className="btn" onClick={() => ask(`Swap ${title} with another suitable meal`)}><Icon name="swap" size="sm" />Swap meal</button>
            <button type="button" className="btn quiet" onClick={() => ask(`Share the recipe for ${title}`)}><Icon name="external" size="sm" />Share</button>
          </div>
        </div>
        <div className="recipe-hero-art" aria-hidden="true">
          <Art className="spot" src="/art/spot-recipe.png" alt="" />
        </div>
      </section>

      <div className="recipe-grid">
        <section className="card recipe-body">
          <div className="tabs" role="tablist" aria-label="Recipe details">
            {TABS.map(([key, label]) => (
              <button
                key={key}
                type="button"
                role="tab"
                id={`recipe-tab-${key}`}
                aria-selected={k.recipeBodyTab === key}
                aria-controls="recipe-panel"
                onClick={() => k.setRecipeBodyTab(key)}
              >
                {label}
              </button>
            ))}
          </div>
          <div id="recipe-panel" role="tabpanel" aria-labelledby={`recipe-tab-${k.recipeBodyTab}`} className="recipe-panel">
            {k.recipeBodyTab === "recipe" && (steps.length === 0
              ? <p className="muted">No cooking steps were saved for this recipe.</p>
              : (
                <ol className="steps">
                  {steps.map((step, index) => (
                    <li key={`${step.title}-${index}`}>
                      <span className="step-n" aria-hidden="true">{index + 1}</span>
                      <div>
                        {step.title && !/^Step \d+$/.test(step.title) && <h3>{step.title}</h3>}
                        {step.body && <p>{step.body.replace(/^\s*(?:step\s*)?\d+\s*[.):-]\s*/i, "")}</p>}
                      </div>
                    </li>
                  ))}
                </ol>
              ))}
            {k.recipeBodyTab === "ingredients" && (ingredients.length === 0
              ? <p className="muted">No structured ingredients were saved for this recipe.</p>
              : (
                <ul className="ingredient-grid">
                  {ingredients.map((ingredient, index) => (
                    <li key={`${getIngredientName(ingredient)}-${index}`}>
                      <span>{getIngredientName(ingredient)}</span>
                      <strong>{getIngredientQuantity(ingredient)}</strong>
                    </li>
                  ))}
                </ul>
              ))}
            {k.recipeBodyTab === "nutrition" && (
              <p className="muted">
                {k.recipeCalories
                  ? `${k.recipeCalories} kcal per serving was saved with this recipe. Log it after eating to add exact macros to your diary.`
                  : "Detailed nutrition wasn’t saved for this recipe. Log it after eating and Kitch will estimate the macros."}
              </p>
            )}
            {k.recipeBodyTab === "notes" && (
              k.recipePantryNotes.length === 0 && !k.latestRecipeGroceryPlan?.notes
                ? <p className="muted">No pantry notes or tips were saved with this recipe.</p>
                : (
                  <div className="prose notes">
                    {k.latestRecipeGroceryPlan?.notes && renderMarkdownContent(k.latestRecipeGroceryPlan.notes)}
                    {k.recipePantryNotes.map((note, index) => (
                      <p key={`note-${index}`}>{typeof note === "string" ? note : JSON.stringify(note)}</p>
                    ))}
                  </div>
                )
            )}
          </div>
        </section>

        <aside className="card recipe-side" aria-label="Ingredients and shopping">
          <div className="segmented" role="tablist" aria-label="Ingredients or shopping list">
            <button type="button" role="tab" aria-selected={k.recipeSidebarTab === "ingredients"} onClick={() => k.setRecipeSidebarTab("ingredients")}>Ingredients</button>
            <button type="button" role="tab" aria-selected={k.recipeSidebarTab === "grocery"} onClick={() => k.setRecipeSidebarTab("grocery")}>To buy <em>{toBuy}</em></button>
          </div>

          {k.recipeSidebarTab === "ingredients" ? (
            ingredients.length === 0
              ? <p className="muted side-note">Ask Kitch for a recipe or grocery plan to list ingredients.</p>
              : (
                <ul className="side-list">
                  {ingredients.map((ingredient, index) => (
                    <li key={`${getIngredientName(ingredient)}-side-${index}`}>
                      <span>{getIngredientName(ingredient)}</span>
                      <em>{getIngredientQuantity(ingredient)}</em>
                    </li>
                  ))}
                </ul>
              )
          ) : (
            k.recipeCartItems.length === 0
              ? <p className="muted side-note">This recipe hasn’t added anything to the shopping list yet.</p>
              : (
                <>
                  <p className="muted side-note">Items already covered by the pantry are shown as in stock.</p>
                  <ul className="side-list">
                    {k.recipeCartItems.map((item, index) => {
                      const stocked = cartPurchaseAmount(item) <= 0;
                      return (
                        <li key={item.id || `${item.name}-${index}`} className={stocked ? "stocked" : ""}>
                          <span>{stocked && <Icon name="check" size="sm" />}{item.name}</span>
                          <em>{stocked ? "In pantry" : formatCartQuantity(cartPurchaseAmount(item), item.purchaseUnit || item.unit)}</em>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )
          )}

          <button
            type="button"
            className="btn primary block side-cta"
            disabled={!title && k.recipeCartItems.length === 0}
            onClick={() => {
              if (k.recipeCartItems.length > 0) go("groceries", "cart");
              else k.sendChatMessage(`Add groceries for ${title} to the native grocery cart`);
            }}
          >
            {k.recipeCartItems.length > 0 ? <>Open shopping list <Icon name="right" size="sm" /></> : "Add ingredients to shopping list"}
          </button>
        </aside>
      </div>
    </div>
  );
}
