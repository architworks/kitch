"use client";

import { useEffect, useRef } from "react";
import Icon from "./Icon.js";
import Art from "./Art.js";
import { SkeletonLine } from "./Skeleton.js";
import {
  GROCERY_CATEGORY_DESCRIPTIONS,
  cartItemKey,
  cartPurchaseAmount,
  cartPantryAmount,
  formatCartQuantity,
  formatRelativeCheckedTime,
  formatMinorCurrency,
  formatProviderAddressParts,
  formatProviderPaymentLabel,
  optionValue
} from "../lib/helpers.js";

const CATEGORIES = ["Fresh Produce", "Proteins & Dairy", "Grains & Bakery", "Pantry & Spices", "General"];
const PROVIDER_LOGOS = {
  swiggy_instamart: "/instamart-logo.jpg",
  zepto: "/zepto-logo.jpg",
  blinkit: "/blinkit-logo.jpg"
};

const rupees = (minor) => formatMinorCurrency(minor, "INR") || "—";

// One readable line per change Instamart made after the review.
function describeChange(change) {
  switch (change?.type) {
    case "bill_changed": {
      const fees = [
        ...(change.added_fees || []).map(fee => `${fee.label} ${rupees(fee.amount_minor)} added`),
        ...(change.changed_fees || []).map(fee => `${fee.label} ${rupees(fee.previous_minor)} → ${rupees(fee.amount_minor)}`)
      ];
      const total = change.total_minor == null
        ? "the total is no longer available"
        : change.previous_total_minor != null
          ? `total ${rupees(change.previous_total_minor)} → ${rupees(change.total_minor)}`
          : `total is now ${rupees(change.total_minor)}`;
      return [...fees, total].join("; ");
    }
    case "product_changed":
      return `${change.native_item?.name || "An item"}: ${(change.fields || ["details"]).map(field => field.replace(/_minor$/, "").replace(/_/g, " ")).join(", ")} changed`;
    case "provider_item_removed":
      return `${change.native_item?.name || "An item"} is no longer in the cart`;
    case "membership_changed":
    case "unexpected_provider_items":
    case "added":
      return "The items in the cart changed";
    default:
      return "The cart changed";
  }
}

// Swiggy's brand guidelines require "Powered by Instamart" beside the cart,
// the checkout summary and order status.
function PoweredBy({ provider }) {
  if (provider?.id !== "swiggy_instamart") return null;
  return (
    <span className="powered-by">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/instamart-logo.jpg" alt="" width="24" height="24" />
      <span>Powered by Instamart</span>
    </span>
  );
}

function ProviderLogo({ provider, size = 36 }) {
  const src = PROVIDER_LOGOS[provider?.id];
  if (!src) return <span className="provider-logo fallback" style={{ width: size, height: size }} aria-hidden="true">{String(provider?.label || "?").slice(0, 1)}</span>;
  // eslint-disable-next-line @next/next/no-img-element
  return <img className="provider-logo" src={src} alt="" width={size} height={size} />;
}

function ListLoading({ label }) {
  return (
    <div className="list-loading" aria-busy="true">
      <span className="visually-hidden">{label}</span>
      {[0, 1, 2, 3].map(index => <SkeletonLine key={index} height={40} width={`${100 - index * 6}%`} />)}
    </div>
  );
}

/* ---------- Shopping list ---------- */

function ShoppingList({ k, ask, go }) {
  const busy = k.isProviderSyncing;
  const providerName = k.selectedProvider.id ? k.selectedProvider.label : "the ordering app";

  return (
    <div className="list-panel" id="cart-panel" role="tabpanel" aria-labelledby="cart-tab">
      <div className="list-meta">
        <p>
          <strong>{k.totalCount} {k.totalCount === 1 ? "item" : "items"}</strong>
          <span>{k.eligibleBuyCount} to buy</span>
          <span>{k.providerSelectedCount} selected for {providerName}</span>
        </p>
        <button type="button" className="btn quiet sm" disabled={busy || k.eligibleBuyCount === 0} onClick={() => k.setProviderSelectionForItems(k.groceryList, k.providerSelectedCount === 0)}>
          {k.providerSelectedCount === 0 ? "Select all" : "Deselect all"}
        </button>
      </div>

      {k.totalCount === 0 && k.liveStateUser !== k.activeUser ? (
        <ListLoading label="Loading the shopping list" />
      ) : k.totalCount === 0 ? (
        <div className="empty">
          <Art className="spot" src="/art/spot-groceries.png" alt="" />
          <h3>The shopping list is empty</h3>
          <p>Ask Kitch for groceries for a planned meal, or add something the household needs below.</p>
          <div className="actions">
            <button type="button" className="btn soft" onClick={() => ask("Add groceries for tomorrow’s meals to the native grocery cart")}>Groceries for tomorrow</button>
            <button type="button" className="btn" onClick={() => go("recipes")}>From the latest recipe</button>
          </div>
        </div>
      ) : (
        <div className="cart-groups">
          {Object.entries(k.groupedGroceryCart).map(([category, items]) => {
            const eligible = items.filter(item => cartPurchaseAmount(item) > 0);
            const selectedCount = eligible.filter(item => !k.excludedProviderItemIds.includes(cartItemKey(item))).length;
            const allSelected = eligible.length > 0 && selectedCount === eligible.length;
            const collapsed = Boolean(k.collapsedGroceryCategories[category]);
            return (
              <section key={category} className="cart-group">
                <header className="cart-group-head">
                  <button
                    type="button"
                    className="cart-group-toggle"
                    aria-expanded={!collapsed}
                    onClick={() => k.setCollapsedGroceryCategories(current => ({ ...current, [category]: !current[category] }))}
                  >
                    <Icon name={collapsed ? "right" : "down"} size="sm" />
                    <strong>{category}</strong>
                    <span className="muted">{items.length}</span>
                    <small className="muted">{GROCERY_CATEGORY_DESCRIPTIONS[category] || GROCERY_CATEGORY_DESCRIPTIONS.General}</small>
                  </button>
                  <label className="cart-group-select">
                    <span>{selectedCount} selected</span>
                    <input
                      type="checkbox"
                      className="check"
                      aria-label={`${allSelected ? "Deselect" : "Select"} all ${category}`}
                      checked={allSelected}
                      disabled={busy || eligible.length === 0}
                      onChange={() => k.setProviderSelectionForItems(items, !allSelected)}
                    />
                  </label>
                </header>
                {!collapsed && (
                  <div className="cart-table" role="table" aria-label={`${category} items`}>
                    <div className="cart-row head" role="row">
                      <span role="columnheader"><span className="visually-hidden">Send</span></span>
                      <span role="columnheader">Item</span>
                      <span role="columnheader">Needed</span>
                      <span role="columnheader">Have</span>
                      <span role="columnheader">To buy</span>
                      <span role="columnheader"><span className="visually-hidden">Actions</span></span>
                    </div>
                    {items.map((item, index) => {
                      const stocked = cartPurchaseAmount(item) <= 0;
                      const selected = !stocked && !k.excludedProviderItemIds.includes(cartItemKey(item));
                      const editing = k.editingGroceryItemId === item.id;
                      const have = cartPantryAmount(item) > 0
                        ? formatCartQuantity(cartPantryAmount(item), item.pantryAllocation?.allocated_unit || item.unit)
                        : "—";
                      const buy = stocked ? "In pantry" : formatCartQuantity(cartPurchaseAmount(item), item.purchaseUnit || item.unit);
                      return (
                        <div key={item.id || `${item.name}-${index}`} role="row" className={`cart-row ${stocked ? "stocked" : ""} ${!selected && !stocked ? "excluded" : ""}`}>
                          <span role="cell">
                            <input
                              type="checkbox"
                              className="check"
                              aria-label={`Send ${item.name} to ${providerName}`}
                              checked={selected}
                              disabled={stocked || busy}
                              onChange={() => k.toggleProviderItemSelection(item)}
                            />
                          </span>
                          <span role="cell" className="cart-name">
                            {editing ? (
                              <input
                                className="input sm"
                                aria-label={`Rename ${item.name}`}
                                value={k.groceryItemNameDraft}
                                disabled={busy}
                                autoFocus
                                onChange={event => k.setGroceryItemNameDraft(event.target.value)}
                                onKeyDown={event => {
                                  if (event.key === "Enter") k.saveGroceryItemName(item);
                                  if (event.key === "Escape") { k.setEditingGroceryItemId(null); k.setGroceryItemNameDraft(""); }
                                }}
                              />
                            ) : <strong title={item.name}>{item.name}</strong>}
                            <small>{item.source === "manual" ? "Added by you" : "From a recipe"}</small>
                          </span>
                          <span role="cell" className="qty">
                            <button type="button" className="icon-btn sm" aria-label={`Less ${item.name}`} disabled={busy} onClick={() => k.adjustGroceryCartItemAmount(item, -1)}><Icon name="minus" size="sm" /></button>
                            <input
                              className="input sm qty-amount"
                              aria-label={`Amount of ${item.name}`}
                              type="number" min="0.1" step="0.1"
                              value={item.amount}
                              disabled={busy}
                              onChange={event => {
                                k.invalidateProviderReview();
                                const next = parseFloat(event.target.value) || 1;
                                k.setCustomGroceryItems(previous => previous.map(current => current.id === item.id ? { ...current, amount: next } : current));
                              }}
                              onBlur={event => k.updateGroceryCartItemDetails(item, { amount: parseFloat(event.target.value) || 1 })}
                            />
                            <button type="button" className="icon-btn sm" aria-label={`More ${item.name}`} disabled={busy} onClick={() => k.adjustGroceryCartItemAmount(item, 1)}><Icon name="plus" size="sm" /></button>
                            <input
                              className="input sm qty-unit"
                              aria-label={`Unit for ${item.name}`}
                              value={item.unit || ""}
                              disabled={busy}
                              onChange={event => {
                                k.invalidateProviderReview();
                                k.setCustomGroceryItems(previous => previous.map(current => current.id === item.id ? { ...current, unit: event.target.value } : current));
                              }}
                              onBlur={event => k.updateGroceryCartItemDetails(item, { unit: event.target.value || "piece" })}
                            />
                          </span>
                          <span role="cell" className="have">{have}</span>
                          <span role="cell" className={`buy ${stocked ? "in" : ""}`}>{buy}</span>
                          <span role="cell" className="row-actions">
                            {editing ? (
                              <>
                                <button type="button" className="icon-btn sm" aria-label={`Save ${item.name}`} disabled={busy || !k.groceryItemNameDraft.trim()} onClick={() => k.saveGroceryItemName(item)}><Icon name="check" size="sm" /></button>
                                <button type="button" className="icon-btn bare sm" aria-label="Cancel rename" disabled={busy} onClick={() => { k.setEditingGroceryItemId(null); k.setGroceryItemNameDraft(""); }}><Icon name="close" size="sm" /></button>
                              </>
                            ) : (
                              <>
                                <button type="button" className="icon-btn bare sm" aria-label={`Rename ${item.name}`} disabled={busy} onClick={() => { k.setEditingGroceryItemId(item.id); k.setGroceryItemNameDraft(item.name); }}><Icon name="edit" size="sm" /></button>
                                <button type="button" className="icon-btn bare sm danger" aria-label={`Remove ${item.name}`} disabled={busy} onClick={() => k.deleteGroceryCartItem(item)}><Icon name="trash" size="sm" /></button>
                              </>
                            )}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      <form
        className="add-row"
        onSubmit={event => { event.preventDefault(); k.addCustomGroceryItem(k.groceryCustomName, k.groceryCustomCat, k.groceryCustomAmount, k.groceryCustomUnit); }}
      >
        <input className="input" aria-label="Item to add" placeholder="Add an item, e.g. Amul butter" disabled={busy} value={k.groceryCustomName} onChange={event => k.setGroceryCustomName(event.target.value)} />
        <input className="input add-amount" aria-label="Amount" type="number" min="0.1" step="0.1" disabled={busy} value={k.groceryCustomAmount} onChange={event => k.setGroceryCustomAmount(parseFloat(event.target.value) || 1)} />
        <input className="input add-unit" aria-label="Unit" disabled={busy} value={k.groceryCustomUnit} onChange={event => k.setGroceryCustomUnit(event.target.value)} />
        <select className="select add-cat" aria-label="Category" disabled={busy} value={k.groceryCustomCat} onChange={event => k.setGroceryCustomCat(event.target.value)}>
          {CATEGORIES.map(category => <option key={category} value={category}>{category}</option>)}
        </select>
        <button type="submit" className="btn primary" disabled={busy || !k.groceryCustomName.trim()}><Icon name="plus" size="sm" />Add</button>
      </form>
    </div>
  );
}

/* ---------- Pantry ---------- */

function PantryPanel({ k }) {
  const busy = k.isProviderSyncing;
  const clearDraft = (id) => k.setPantryDrafts(current => { const next = { ...current }; delete next[id]; return next; });
  return (
    <div className="list-panel" id="pantry-panel" role="tabpanel" aria-labelledby="pantry-tab">
      <div className="list-meta">
        <p>
          <strong>{k.pantryStock.length} {k.pantryStock.length === 1 ? "item" : "items"} at home</strong>
          <span>{k.pantryReviewedAt ? `Reviewed ${formatRelativeCheckedTime(k.pantryReviewedAt)}` : "Not reviewed yet"}</span>
        </p>
        <button type="button" className="btn soft sm" disabled={busy} onClick={k.reconcileCartWithPantry} title="Recalculate what to buy using the current pantry">
          <Icon name="refresh" size="sm" />Update list from pantry
        </button>
      </div>

      {k.pantryStock.length === 0 && k.liveStateUser !== k.activeUser ? (
        <ListLoading label="Loading the pantry" />
      ) : k.pantryStock.length === 0 ? (
        <div className="empty">
          <Art className="spot" src="/art/spot-pantry.png" alt="" />
          <h3>The pantry is empty</h3>
          <p>Add what you have below, or send Kitch a photo of your fridge or shelves and it will fill this in.</p>
        </div>
      ) : (
        <div className="pantry-table" role="table" aria-label="Pantry items">
          <div className="pantry-row head" role="row">
            <span role="columnheader">Item</span>
            <span role="columnheader">Quantity</span>
            <span role="columnheader">Updated</span>
            <span role="columnheader"><span className="visually-hidden">Actions</span></span>
          </div>
          {k.pantryStock.map(item => {
            const draft = k.pantryDrafts[item.id] || item;
            const editing = k.editingPantryItemId === item.id;
            const setDraft = (patch) => k.setPantryDrafts(current => ({ ...current, [item.id]: { ...draft, ...patch } }));
            return (
              <div key={item.id} role="row" className={`pantry-row ${editing ? "editing" : ""}`}>
                <span role="cell">
                  {editing
                    ? <input className="input sm" aria-label={`Name of ${item.name}`} value={draft.name} autoFocus onChange={event => setDraft({ name: event.target.value })} />
                    : <strong>{item.name}</strong>}
                </span>
                <span role="cell" className="qty">
                  {editing ? (
                    <>
                      <button type="button" className="icon-btn sm" aria-label={`Less ${item.name}`} onClick={() => setDraft({ amount: Math.max(0, (Number(draft.amount) || 0) - 1) })}><Icon name="minus" size="sm" /></button>
                      <input className="input sm qty-amount" aria-label={`Amount of ${item.name}`} type="number" min="0" step="0.1" value={draft.amount} onChange={event => setDraft({ amount: event.target.value })} />
                      <button type="button" className="icon-btn sm" aria-label={`More ${item.name}`} onClick={() => setDraft({ amount: (Number(draft.amount) || 0) + 1 })}><Icon name="plus" size="sm" /></button>
                      <input className="input sm qty-unit" aria-label={`Unit for ${item.name}`} value={draft.unit} onChange={event => setDraft({ unit: event.target.value })} />
                    </>
                  ) : <span className="qty-text">{formatCartQuantity(item.amount, item.unit)}</span>}
                </span>
                <span role="cell" className="muted">{item.updatedAt ? formatRelativeCheckedTime(item.updatedAt) : "—"}</span>
                <span role="cell" className="row-actions">
                  {editing ? (
                    <>
                      <button type="button" className="icon-btn sm" aria-label={`Save ${item.name}`} disabled={!String(draft.name || "").trim()} onClick={() => k.savePantryRow(item)}><Icon name="check" size="sm" /></button>
                      <button type="button" className="icon-btn bare sm" aria-label="Cancel" onClick={() => { k.setEditingPantryItemId(null); clearDraft(item.id); }}><Icon name="close" size="sm" /></button>
                    </>
                  ) : (
                    <>
                      <button type="button" className="icon-btn bare sm" aria-label={`Edit ${item.name}`} onClick={() => { k.setEditingPantryItemId(item.id); k.setPantryDrafts(current => ({ ...current, [item.id]: { ...item } })); }}><Icon name="edit" size="sm" /></button>
                      <button type="button" className="icon-btn bare sm danger" aria-label={`Remove ${item.name} from pantry`} onClick={() => k.patchPantry([{ action: "remove", id: item.id }])}><Icon name="trash" size="sm" /></button>
                    </>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <form
        className="add-row pantry-add"
        onSubmit={async event => {
          event.preventDefault();
          const saved = await k.patchPantry([{ action: "add", name: k.pantryNewItem.name, amount: Number(k.pantryNewItem.amount), unit: k.pantryNewItem.unit }]);
          if (saved) k.setPantryNewItem({ name: "", amount: 1, unit: "piece" });
        }}
      >
        <input className="input" aria-label="Pantry item to add" placeholder="Add something you have, e.g. Toor dal" value={k.pantryNewItem.name} onChange={event => k.setPantryNewItem(current => ({ ...current, name: event.target.value }))} />
        <input className="input add-amount" aria-label="Amount" type="number" min="0.1" step="0.1" value={k.pantryNewItem.amount} onChange={event => k.setPantryNewItem(current => ({ ...current, amount: event.target.value }))} />
        <input className="input add-unit" aria-label="Unit" value={k.pantryNewItem.unit} onChange={event => k.setPantryNewItem(current => ({ ...current, unit: event.target.value }))} />
        <button type="submit" className="btn primary" disabled={!k.pantryNewItem.name.trim()}><Icon name="plus" size="sm" />Add</button>
      </form>

      {k.pantryStock.length > 0 && (
        <div className="danger-zone">
          <p>Starting over? Clearing the pantry does not change the shopping list until you update it from the pantry.</p>
          <button type="button" className="btn danger sm" disabled={busy} onClick={k.markPantryEmpty}><Icon name="trash" size="sm" />Mark pantry empty</button>
        </div>
      )}
    </div>
  );
}

/* ---------- Checkout steps ---------- */

function Step({ n, done, locked, title, sub, children }) {
  return (
    <li className={`step ${done ? "done" : ""} ${locked ? "locked" : ""}`}>
      <span className="step-marker" aria-hidden="true">{done ? <Icon name="check" size="sm" /> : n}</span>
      <div className="step-body">
        <h3>{title}<span className="visually-hidden">{done ? " (complete)" : locked ? " (locked)" : ""}</span></h3>
        {sub && <p className="step-sub">{sub}</p>}
        {children}
      </div>
    </li>
  );
}

function Locked({ title, children }) {
  return (
    <div className="locked-note">
      <Icon name="lock" size="sm" />
      <div><strong>{title}</strong>{children}</div>
    </div>
  );
}

function Checkout({ k }) {
  const p = k.selectedProvider;
  const label = p.label;
  const busy = k.isProviderSyncing;

  return (
    <section className="card card-pad checkout" aria-labelledby="checkout-title">
      <div className="section-head">
        <h2 id="checkout-title">Order from an app</h2>
        <span className="muted">Kitch prepares the cart. Only you can place the order.</span>
      </div>
      <ol className="steps-list">
        <Step n={1} done={k.nativeCartStageComplete} title="Choose what to buy" sub={k.nativeCartStageComplete ? `${k.checkoutItems.length} ${k.checkoutItems.length === 1 ? "item" : "items"} selected from the shopping list.` : "Tick items in the shopping list above."} />

        <Step n={2} done={k.providerStageComplete} title="Pick an ordering app" sub="Your shopping list stays the same whichever app you use.">
          <div className="providers" role="radiogroup" aria-label="Ordering app">
            {k.orderingProviders.length === 0 && <p className="muted">{k.providerConnectionStatus?.message || "Loading ordering apps…"}</p>}
            {k.orderingProviders.map(provider => {
              const selected = provider.id === k.selectedOrderingProvider;
              const ready = provider.state === "connected" || provider.state === "configured";
              return (
                <button
                  key={provider.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  className={`provider ${selected ? "selected" : ""}`}
                  disabled={!provider.enabled || busy}
                  onClick={() => k.selectOrderingProvider(provider)}
                >
                  <ProviderLogo provider={provider} />
                  <span>
                    <strong>{provider.label}</strong>
                    <small>{provider.enabled ? (ready ? "Connected" : "Needs connecting") : (provider.badge || "Unavailable")}</small>
                  </span>
                  {selected && <Icon name="checkCircle" className="provider-check" />}
                </button>
              );
            })}
          </div>
          {p.requires_connection && (
            <div className="connection-line">
              {k.providerConnectionState === "connected" ? (
                <>
                  <span className="muted">{label} account connected for this household.</span>
                  <button type="button" className="btn quiet sm" disabled={busy} onClick={() => k.disconnectProvider(p)}>Disconnect</button>
                </>
              ) : (
                <button type="button" className="btn primary sm" disabled={busy || p.production_gated} onClick={() => k.startProviderConnection(p)}>
                  {k.providerConnectionState === "reconnect_required" ? `Reconnect ${label}` : `Connect ${label}`}
                </button>
              )}
            </div>
          )}
        </Step>

        <Step n={3} done={k.addressStageComplete} locked={!p.id || k.checkoutItems.length === 0 || !k.providerConnectionReady} title="Delivery address">
          {!p.id ? (
            <Locked title="Pick an ordering app first">Addresses come from the app you choose.</Locked>
          ) : k.checkoutItems.length === 0 ? (
            <Locked title="Select at least one item to buy">The address unlocks once something is selected.</Locked>
          ) : !k.providerConnectionReady ? (
            <Locked title={k.providerStatusLabel}>
              {k.providerStatusDescription}
              {p.requires_connection && !p.production_gated && (
                <button type="button" className="btn sm" onClick={() => k.startProviderConnection(p)}>
                  {k.providerConnectionState === "reconnect_required" ? "Reconnect" : "Connect"}
                </button>
              )}
            </Locked>
          ) : (
            <div className="address">
              <label className="field">
                <span>Deliver to</span>
                <select
                  className="select"
                  value={k.selectedProviderAddress}
                  disabled={busy || k.isProviderAddressLoading || k.providerSavedAddressOptions.length === 0}
                  onChange={event => k.selectProviderSyncAddress(event.target.value)}
                >
                  <option value="">{k.isProviderAddressLoading ? `Loading ${label} addresses…` : "Choose a saved address"}</option>
                  {k.providerSavedAddressOptions.map((option, index) => {
                    const value = optionValue(option, ["id", "address_id", "addressId"], `address-${index}`);
                    const address = formatProviderAddressParts(option, `Address ${index + 1}`);
                    return <option key={`${value}-${index}`} value={value}>{address.detail ? `${address.title} — ${address.detail}` : address.title}</option>;
                  })}
                </select>
              </label>
              <p className="muted small-note">{k.providerStatusDescription}</p>
              {k.providerAddressLoadError && <p className="form-error">{k.providerAddressLoadError}</p>}
            </div>
          )}
        </Step>

        <Step n={4} done={k.transferStageComplete} locked={!k.selectedProviderAddress} title={`Send items to ${p.id ? label : "the app"}`} sub="This replaces the app’s cart with your selection. It does not place an order.">
          <button
            type="button"
            className="btn primary"
            onClick={k.syncNativeCartToProvider}
            disabled={busy || k.groceryMutationCount > 0 || k.checkoutItems.length === 0 || !k.selectedProviderAddress}
          >
            <Icon name="send" size="sm" />
            {k.groceryMutationCount > 0 ? "Saving the list…" : busy ? `Sending to ${label}…` : !k.selectedProviderAddress ? "Choose an address first" : `Send ${k.checkoutItems.length} ${k.checkoutItems.length === 1 ? "item" : "items"} to ${label}`}
          </button>
        </Step>

        <Step n={5} done={k.reviewStageComplete} locked={!k.hasProviderCartDisplay} title={`Check the ${p.id ? label : "app"} cart`} sub="The exact products, quantities and prices the app returned.">
          {!k.hasProviderCartDisplay ? (
            <Locked title={`${p.id ? label : "The app"} cart hasn’t been loaded`}>
              Send items above, or read the cart that’s already there.
              {p.id && <button type="button" className="btn sm" onClick={() => k.refreshProviderCart({ announce: true })} disabled={k.isProviderCartRefreshing}>{k.isProviderCartRefreshing ? "Reading…" : `Read ${label} cart`}</button>}
            </Locked>
          ) : <ProviderReview k={k} />}
        </Step>

        <Step n={6} done={k.providerOrderCompleted} locked={!k.providerCartReview} title="Approve and order">
          {!k.providerCartReview ? (
            <Locked title="Needs a checked cart">Payment and ordering unlock once step 5 has a valid review.</Locked>
          ) : <Payment k={k} />}
        </Step>
      </ol>
    </section>
  );
}

function ProviderReview({ k }) {
  const label = k.selectedProvider.label;
  const tone = k.providerLiveCart ? "good" : k.providerReviewConfirmed ? (k.providerUnavailableItems.length > 0 ? "warn" : "good") : "bad";
  const message = k.providerLiveCart
    ? (k.providerDisplayedItems.length > 0 ? `This is the latest cart ${label} returned.` : `Your ${label} cart is empty.`)
    : k.providerReviewConfirmed
      ? (k.providerUnavailableItems.length > 0
        ? `${k.providerMatchedItems.length} ${k.providerMatchedItems.length === 1 ? "item is" : "items are"} in ${label}. ${k.providerUnavailableItems.length} ${k.providerUnavailableItems.length === 1 ? "item wasn’t" : "items weren’t"} found and won’t be ordered.`
        : `Every selected item was matched. Check products and quantities below.`)
      : (k.providerCartReview?.message || `${label} sync needs attention.`);

  return (
    <div className="review">
      <PoweredBy provider={k.selectedProvider} />
      <div className={`callout ${tone}`}>
        <Icon name={tone === "good" ? "checkCircle" : "alert"} />
        <div>{message}<span className="review-checked">Checked {k.providerLastChecked}</span></div>
        <button type="button" className="btn sm" onClick={() => k.refreshProviderCart({ announce: true })} disabled={k.isProviderCartRefreshing}>
          <Icon name="refresh" size="sm" />{k.isProviderCartRefreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {(k.providerReplacements.length > 0 || k.providerCartChanges.length > 0) && (
        <div className="callout warn" role="status">
          <Icon name="swap" />
          <div>
            <strong>{label} changed the order after you reviewed it</strong>
            <ul className="change-list">
              {k.providerReplacements.map((replacement, index) => (
                <li key={`replacement-${index}`}>
                  {replacement.native_item?.name || "Item"}: {replacement.previous_product?.name || replacement.previous_product?.title || "previous product"} → {replacement.replacement_product?.name || replacement.replacement_product?.title || "replacement"}
                </li>
              ))}
              {k.providerCartChanges.filter(change => change.type !== "replacement").map((change, index) => (
                <li key={`change-${index}`}>{describeChange(change)}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {k.providerCartRows.length === 0 ? (
        !k.providerLiveCart && <p className="muted">The {label} cart is empty.</p>
      ) : (
        <div className="product-table" role="table" aria-label={`${label} cart, highest subtotal first`}>
          <div className="product-row head" role="row">
            <span role="columnheader">Product</span>
            <span role="columnheader">Price</span>
            <span role="columnheader">Qty</span>
            <span role="columnheader">Pack</span>
            <span role="columnheader">Subtotal</span>
          </div>
          {k.providerCartRows.map(({ match, index, imageUrl, priceMinor, quantity, packSize, subtotalMinor }) => {
            const product = match.matched_product || {};
            const native = match.native_item || {};
            const name = match.cart_item?.name || product.name || product.title || product.product_name || `${label} item`;
            return (
              <div key={`${native.id || native.name || index}-match`} role="row" className="product-row">
                <span role="cell" className="product">
                  <span className="product-img">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    {imageUrl ? <img src={imageUrl} alt="" width="52" height="52" loading="lazy" /> : <span aria-hidden="true">{String(name).slice(0, 1).toUpperCase()}</span>}
                  </span>
                  <span>
                    <strong>{name}</strong>
                    <small>{match.extra ? `Added directly in ${label}` : native.name ? `For “${native.name}”` : `In your ${label} cart`}</small>
                    {k.selectedProvider.id === "swiggy_instamart" && match.matching && (
                      <small className="match-notes">
                        Asked for {match.matching.requested_quantity ?? native.amount ?? "—"} {match.matching.requested_unit || native.unit || ""}
                        {match.matching.fulfilled_quantity != null && ` · covers ${match.matching.fulfilled_quantity}`}
                        {Number(match.matching.excess_quantity || 0) > 0 && ` · ${match.matching.excess_quantity} extra`}
                        {" · "}{match.matching.preference_source === "explicit" ? "household preference" : match.matching.preference_source === "history" ? "Swiggy history" : "no preference"}
                        {match.matching.reason && <span className="match-reason">{match.matching.reason}</span>}
                      </small>
                    )}
                  </span>
                </span>
                <span role="cell">{formatMinorCurrency(priceMinor, k.providerCurrency) || "—"}</span>
                <span role="cell">{quantity}</span>
                <span role="cell" className="muted">{packSize || "—"}</span>
                <span role="cell" className="subtotal">{formatMinorCurrency(subtotalMinor, k.providerCurrency) || "—"}</span>
              </div>
            );
          })}
        </div>
      )}

      {k.providerUnavailableItems.length > 0 && (
        <div className="callout bad">
          <Icon name="alert" />
          <div>
            <strong>Won’t be ordered: not found on {label}</strong>
            <ul className="change-list">
              {k.providerUnavailableItems.map((item, index) => (
                <li key={`${item.native_item_id || item.id || item.name || "item"}-${index}`}><b>{item.name || "Unknown item"}</b> — {item.reason || `${label} returned no usable match.`}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

function Payment({ k }) {
  const label = k.selectedProvider.label;
  const status = k.providerPaymentState.status || "pending";
  return (
    <div className="payment">
      {(k.providerOrderAmbiguous || k.providerOrderCompleted) && (
        <div className={`callout ${k.providerOrderCompleted ? "good" : "warn"}`} role="status">
          <Icon name={k.providerOrderCompleted ? "checkCircle" : "alert"} />
          <div>
            <strong>{k.providerOrderCompleted ? "Order placed" : "Check this order in the Swiggy app"}</strong>
            {k.providerOrderCompleted
              ? (k.providerOrderMessage || `${label} confirmed this order.`)
              : `Kitch won’t resubmit this checkout. Confirm it in ${label} before doing anything else.`}
            {k.providerOrderResults.length > 0 && (
              <ul className="change-list">
                {k.providerOrderResults.map((result, index) => (
                  <li key={`${result?.order_id || "store"}-${index}`}>
                    <b>{result?.order_id ? `Order ${result.order_id}` : `Store ${index + 1}`}</b> · {result?.status || "Unknown status"}{result?.message ? ` — ${result.message}` : ""}
                  </li>
                ))}
              </ul>
            )}
            {k.selectedProvider.id === "swiggy_instamart" && k.providerOrderCompleted && (
              <p className="order-help">To change or cancel this order, call Swiggy customer care on <a href="tel:08067466729">080-67466729</a>.</p>
            )}
            <PoweredBy provider={k.selectedProvider} />
          </div>
        </div>
      )}

      <div className="pay-grid">
        <div className="pay-field">
          <span className="pay-label"><Icon name="pin" size="sm" />Delivery address</span>
          {k.selectedProviderAddressDisplay ? (
            <p><strong>{k.selectedProviderAddressDisplay.title}</strong>{k.selectedProviderAddressDisplay.detail && <span>{k.selectedProviderAddressDisplay.detail}</span>}</p>
          ) : k.selectedProviderAddress ? (
            <p><strong>Saved address</strong><span>Details are still loading from {label}.</span></p>
          ) : (
            <p><span>No confirmed address. Choose one in step 3 and send again.</span></p>
          )}
        </div>
        <div className="pay-field">
          <span className="pay-label"><Icon name="wallet" size="sm" />Payment</span>
          {k.instamartSolePaymentOption ? (
            <p><strong>{k.instamartSolePaymentLabel}</strong><span>The only method Swiggy Instamart offered for this cart.</span></p>
          ) : k.providerPaymentOptions.length > 0 ? (
            <PaymentPicker k={k} />
          ) : (
            <p><span>{label} didn’t return a supported payment method, so ordering stays blocked.</span></p>
          )}
        </div>
      </div>

      {k.providerMultiStore && (
        <div className="callout warn">
          <Icon name="store" />
          <div><strong>Delivered from {k.providerStoreGroups.length || "several"} stores</strong>Review every item and the full bill before approving.</div>
        </div>
      )}
      {!k.providerAddressDetailsReady && k.selectedProviderAddress && (
        <div className="callout" role="status"><Icon name="clock" /><div><strong>Loading the address</strong>Payment stays locked until the selected address can be shown for review.</div></div>
      )}
      {k.providerOrderBlockers.length > 0 && (
        <div className="callout bad">
          <Icon name="alert" />
          <div><strong>Order blocked</strong><ul className="change-list">{k.providerOrderBlockers.map((blocker, index) => <li key={`${blocker}-${index}`}>{blocker}</li>)}</ul></div>
        </div>
      )}

      <label className="approve">
        <input
          type="checkbox"
          className="check"
          checked={k.providerReviewAcknowledged}
          disabled={!k.providerAddressDetailsReady || k.isUpdatingProviderReview || k.isPlacingProviderOrder}
          onChange={event => {
            const checked = event.target.checked;
            k.setProviderReviewAcknowledged(checked);
            k.updateProviderReview({ order_review_acknowledged: checked });
          }}
        />
        <span>I’ve checked the exact {label} cart, total, delivery address, payment and the items that won’t be ordered{k.providerMultiStore ? ", and that it ships from several stores" : ""}.</span>
      </label>

      {k.providerPaymentPending ? <PaymentHandoff k={k} /> : (
      <div className="place-order">
        <button type="button" className="btn primary lg" onClick={k.placeProviderOrder} disabled={!k.canPlaceProviderOrder || k.isPlacingProviderOrder}>
          {k.isPlacingProviderOrder ? "Placing order…" : `Place order with ${label}${k.providerTotal ? ` · ${k.providerTotal}` : ""}`}
        </button>
        <p className="muted">This is the only button that can place a real order. Kitch’s chat never can.</p>
      </div>
      )}

      <details className="raw">
        <summary>Technical details from {label}</summary>
        <pre>{JSON.stringify(k.providerCartDetails, null, 2)}</pre>
      </details>
    </div>
  );
}

// Swiggy's payment rules: offer only returned methods; scan-QR and UPI apps
// both go through Instamart's own payment page (never our own QR); Swiggy
// Money debits the balance inline; Cash is placed immediately.
const PAYMENT_GROUPS = [
  { key: "qr", title: "Scan a QR code", hint: "Instamart shows a QR to scan with any UPI app on your phone. Best on a computer.", match: option => option.flow === "upi_qr" },
  { key: "intent", title: "Pay in a UPI app", hint: "Opens the app on this device. On a computer, scan a QR instead.", match: option => option.flow === "upi_intent" },
  { key: "wallet", title: "Swiggy Money", hint: "Paid from your balance. If it doesn’t cover the total, nothing is charged and no order is placed.", match: option => option.kind === "swiggy_money" },
  { key: "cash", title: "Cash on delivery", hint: "The order is placed right away; pay the delivery partner.", match: option => option.kind === "cod" }
];

function PaymentPicker({ k }) {
  const touch = typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)").matches;
  const order = touch ? ["intent", "qr", "wallet", "cash"] : ["qr", "wallet", "cash", "intent"];
  const groups = order
    .map(key => PAYMENT_GROUPS.find(group => group.key === key))
    .map(group => ({ ...group, options: k.providerPaymentOptions.filter(group.match) }))
    .filter(group => group.options.length > 0);
  const disabled = !k.providerAddressDetailsReady || k.isUpdatingProviderReview || k.isPlacingProviderOrder;
  const choose = (value) => {
    k.setSelectedProviderPaymentMethod(value);
    k.updateProviderReview({ selected_payment_method_id: value || null });
  };
  return (
    <div className="pay-options" role="radiogroup" aria-label="Payment method">
      {groups.map(group => (
        <div key={group.key} className="pay-group">
          <p className="pay-group-title">{group.title}<small>{group.hint}</small></p>
          <div className={`pay-group-options ${group.key === "intent" ? "apps" : ""}`}>
            {group.options.map((option, index) => {
              const value = optionValue(option, ["id", "payment_method_id", "paymentMethodId", "method"], `payment-${index}`);
              const selected = String(k.selectedProviderPaymentMethod) === String(value);
              return (
                <button
                  key={`${value}-${index}`}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  disabled={disabled}
                  className={`pay-option ${selected ? "selected" : ""}`}
                  onClick={() => choose(value)}
                >
                  {formatProviderPaymentLabel(option, String(value))}
                  {selected && <Icon name="check" size="sm" />}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function PaymentHandoff({ k }) {
  const label = k.selectedProvider.label;
  const panelRef = useRef(null);
  // Bring the payment step into view where the person is already looking.
  useEffect(() => {
    panelRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);
  const handoff = k.providerPaymentHandoff;
  const qr = Boolean(handoff?.is_qr_flow);
  const url = k.providerPaymentHandoffUrl;
  const checked = k.providerPaymentCheckedAt
    ? new Date(k.providerPaymentCheckedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" })
    : "";
  return (
    <div className="handoff" role="status" ref={panelRef}>
      <span className="tile turmeric handoff-tile" aria-hidden="true"><Icon name={qr ? "image" : "wallet"} size="lg" /></span>
      <div className="handoff-body">
        <strong>{qr ? "Scan the QR to pay" : "Finish paying in your UPI app"}</strong>
        <p>
          {url
            ? qr
              ? `${label}’s payment page opened in a new tab. Scan its QR code with any UPI app on your phone. If the tab didn’t open, use the button below.`
              : `${label}’s payment page opened in a new tab; on a phone it hands over to your UPI app. If it didn’t open, use the button below.`
            : `The payment link isn’t available on this screen any more. Finish or check the payment in the Swiggy app.`}
        </p>
        <div className="inline-actions">
          {url && (
            <a className="btn primary" href={url} target="_blank" rel="noopener noreferrer">
              {qr ? "Show payment QR" : "Open payment page"} <Icon name="external" size="sm" />
            </a>
          )}
          {k.selectedProvider.capabilities?.payment_status && (
            <button type="button" className="btn" onClick={() => k.checkProviderPaymentStatus({ manual: true })} disabled={k.isCheckingProviderPayment}>
              {k.isCheckingProviderPayment ? "Checking…" : "I’ve paid, check now"}
            </button>
          )}
        </div>
        <small className="handoff-note">
          {k.isCheckingProviderPayment ? "Checking with Instamart…" : checked ? `Last checked ${checked}.` : "Kitch checks the payment automatically."} Don’t place the order again while this is pending.
        </small>
      </div>
    </div>
  );
}

/* ---------- Sidebar ---------- */

function OrderSummary({ k }) {
  const p = k.selectedProvider;
  const label = p.id ? p.label : "App";
  const shown = k.hasProviderCartDisplay;
  const emptyCart = shown && k.providerDisplayedItems.length === 0;
  const summary = k.providerCartSummary || {};
  const billLines = Array.isArray(summary.bill_lines) ? summary.bill_lines : [];
  // Without Swiggy's itemised lines, never let the parts silently fall short
  // of the total: whatever is not itemised is shown as "Other charges".
  const knownParts = (Number(summary.subtotal_minor) || 0)
    + (summary.fees || []).reduce((sum, fee) => sum + (Number(fee.amount_minor) || 0), 0)
    - (Number(summary.discount_minor) || 0);
  // Swiggy's itemised lines can add up to less than its total to pay; show
  // the gap plainly rather than letting the bill look complete.
  const unitemised = summary.total_minor != null && billLines.length > 0
    ? Number(summary.total_minor) - billLines.reduce((sum, line) => sum + (Number(line.amount_minor) || 0), 0)
    : 0;
  const otherCharges = summary.total_minor != null && summary.subtotal_minor != null
    ? Number(summary.total_minor) - knownParts
    : 0;
  return (
    <section className="card card-pad summary" aria-labelledby="summary-title">
      <div className="summary-head">
        {p.id && <ProviderLogo provider={p} size={30} />}
        <h2 id="summary-title">Order summary</h2>
      </div>
      <PoweredBy provider={p} />
      <dl className="totals">
        <div><dt>Items to buy</dt><dd>{k.eligibleBuyCount}</dd></div>
        <div><dt>Selected to order</dt><dd>{k.pendingBuyCount}</dd></div>
        {billLines.length > 0 ? (
          <>
            {/* Swiggy's own bill, line by line, exactly as Swiggy labels it. */}
            {billLines.map((line, index) => (
              <div key={`${line.label}-${index}`} className={index === 0 ? "sep" : ""}><dt>{line.label}</dt><dd>{line.value}</dd></div>
            ))}
            {unitemised > 0 && (
              <div className="unitemised"><dt>Not itemised by Instamart</dt><dd>{formatMinorCurrency(unitemised, k.providerCurrency)}</dd></div>
            )}
          </>
        ) : (
          <>
            <div className="sep"><dt>Subtotal</dt><dd>{k.providerSubtotal || (emptyCart ? "—" : shown ? "Not returned" : "Not synced")}</dd></div>
            {k.providerFees.map(fee => <div key={`${fee.label}-${fee.value}`}><dt>{fee.label}</dt><dd>{fee.value}</dd></div>)}
            {k.providerDiscount && <div className="discount"><dt>Discount</dt><dd>−{k.providerDiscount}</dd></div>}
            {otherCharges > 0 && <div className="unitemised"><dt>Not itemised by Instamart</dt><dd>{formatMinorCurrency(otherCharges, k.providerCurrency)}</dd></div>}
          </>
        )}
        <div className="grand"><dt>{label} total</dt><dd>{k.providerTotal || (emptyCart ? "Empty" : shown ? "Unavailable" : "Not synced")}</dd></div>
      </dl>
      <p className="summary-note">
        {emptyCart
          ? `The ${label} cart has no items yet. Send your selection to see real prices.`
          : shown
          ? <><b>{k.providerTotalSource === "provider" ? "Total from the app." : k.providerTotalSource === "line_items" ? "Exact sum of line items." : "Total unavailable."}</b> {k.providerTotalNotice}</>
          : `Prices appear once ${label} returns the cart. Kitch never estimates them.`}
      </p>
    </section>
  );
}

function ListTools({ k }) {
  const busy = k.isProviderSyncing;
  const label = k.selectedProvider.id ? k.selectedProvider.label : "the app";
  return (
    <section className="card card-pad tools" aria-labelledby="tools-title">
      <h2 id="tools-title">List tools</h2>
      <button type="button" className="tool" disabled={busy} onClick={() => k.setCustomGroceryItems(previous => [...previous].sort((a, b) => (a.category || "").localeCompare(b.category || "")))}><Icon name="sort" size="sm" />Sort by category</button>
      <button type="button" className="tool" disabled={busy} onClick={() => { k.invalidateProviderReview(); k.setExcludedProviderItemIds([]); }}><Icon name="checkCircle" size="sm" />Select everything for {label}</button>
      <button type="button" className="tool" disabled={busy} onClick={() => { k.invalidateProviderReview(); k.setExcludedProviderItemIds(k.groceryList.filter(item => cartPurchaseAmount(item) > 0).map(cartItemKey).filter(Boolean)); }}><Icon name="close" size="sm" />Clear selection</button>
      <div className="tools-danger">
        <button type="button" className="tool danger" disabled={busy} onClick={k.clearPlannedGroceryRows}><Icon name="trash" size="sm" />Remove recipe items</button>
        <small className="muted">Keeps items you added yourself.</small>
      </div>
    </section>
  );
}

export default function GroceriesView({ k, ask, go }) {
  const tab = k.groceryWorkspaceTab === "pantry" ? "pantry" : "cart";
  return (
    <div className="page groceries">
      <header className="page-header with-actions">
        <div>
          <h1 className="page-title">Groceries</h1>
          <p className="page-sub">What the household has, what it needs, and the app cart you approve before anything is ordered.</p>
        </div>
        <button type="button" className="btn" disabled={k.isProviderSyncing} onClick={() => ask("Add groceries for tomorrow’s meals to the native grocery cart")}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/kitch-chef-hat.svg" alt="" width="18" height="18" />Ask Kitch
        </button>
      </header>

      <div className="groceries-grid">
        <div className="groceries-main">
          <section className="card lists">
            <div className="segmented big" role="tablist" aria-label="Shopping list or pantry">
              <button type="button" role="tab" id="cart-tab" aria-selected={tab === "cart"} aria-controls="cart-panel" onClick={() => k.setGroceryWorkspaceTab("cart")}>
                <Icon name="basket" size="sm" />Shopping list <em>{k.totalCount}</em>
              </button>
              <button type="button" role="tab" id="pantry-tab" aria-selected={tab === "pantry"} aria-controls="pantry-panel" onClick={() => k.setGroceryWorkspaceTab("pantry")}>
                <Icon name="pantry" size="sm" />Pantry <em>{k.pantryStock.length}</em>
              </button>
            </div>
            {tab === "cart" ? <ShoppingList k={k} ask={ask} go={go} /> : <PantryPanel k={k} />}
          </section>
          <Checkout k={k} />
        </div>
        <aside className="groceries-side">
          <OrderSummary k={k} />
          <ListTools k={k} />
        </aside>
      </div>
    </div>
  );
}
