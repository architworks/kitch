---
name: Kitch — The Warm Working Kitchen
description: A household kitchen companion that feels like a lit home kitchen, organised like a dependable tool.
colors:
  paper: "#f5f1e8"
  paper-deep: "#ede7da"
  card: "#fffdf8"
  line: "#e5ddcd"
  line-soft: "#eee7da"
  ink: "#1f2a1f"
  ink-2: "#474f42"
  mute: "#6b6d60"
  olive: "#3f4229"
  on-olive: "#fbf5e9"
  on-olive-2: "#d8d4c1"
  green: "#2f5536"
  green-hover: "#264a2d"
  green-2: "#3f6b45"
  sage: "#e3ead8"
  sage-2: "#cfdcc0"
  turmeric: "#d98b2b"
  turmeric-ink: "#9a5a10"
  turmeric-soft: "#fbefd9"
  plum: "#4d4b7d"
  plum-soft: "#e8e6f2"
  wood: "#b08560"
  tomato: "#b4402a"
  tomato-soft: "#fbe6df"
typography:
  display:
    fontFamily: "Bricolage Grotesque, ui-sans-serif, system-ui, sans-serif"
    fontSize: "46px"
    fontWeight: 700
    lineHeight: 1.02
    letterSpacing: "-0.035em"
  page-title:
    fontFamily: "Bricolage Grotesque, ui-sans-serif, system-ui, sans-serif"
    fontSize: "34px"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-0.03em"
  section-title:
    fontFamily: "Bricolage Grotesque, ui-sans-serif, system-ui, sans-serif"
    fontSize: "21px"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Figtree, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Figtree, ui-sans-serif, system-ui, sans-serif"
    fontSize: "13.5px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
rounded:
  sm: "10px"
  md: "14px"
  lg: "20px"
  xl: "26px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "20px"
  xl: "24px"
  section: "22px"
components:
  button-primary:
    backgroundColor: "{colors.green}"
    textColor: "{colors.on-olive}"
    rounded: "12px"
    height: "40px"
    padding: "0 16px"
  button-primary-hover:
    backgroundColor: "{colors.green-hover}"
  button-default:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "12px"
    height: "40px"
    padding: "0 16px"
  button-soft:
    backgroundColor: "{colors.sage}"
    textColor: "{colors.green}"
    rounded: "12px"
    height: "40px"
  button-on-olive:
    backgroundColor: "{colors.on-olive}"
    textColor: "{colors.olive}"
    rounded: "12px"
    height: "42px"
  card:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.lg}"
    padding: "22px 24px"
  input:
    backgroundColor: "#ffffff"
    textColor: "{colors.ink}"
    rounded: "11px"
    height: "40px"
    padding: "0 12px"
  nav-item-active:
    backgroundColor: "{colors.card}"
    textColor: "{colors.green}"
    rounded: "12px"
    height: "44px"
---

# Design System: Kitch — The Warm Working Kitchen

## Overview

Kitch should feel like walking into a lit home kitchen in the evening: warm, specific, a little personal, and organised enough that a household can trust it with plans and orders. The emotional moments use painterly kitchen illustrations on a deep olive wall, and the hero changes with the time of day (morning, afternoon, evening). The working surfaces (week timetable, shopping list, checkout, diary) are calm, dense and standard. Warmth never gets in the way of a task.

The interface separates **household** state from **personal** state. Plans, pantry, recipes and the shopping list are shared and sit on plain warm-white cards. Nutrition belongs to the active member and carries a faint turmeric wash at the top of its cards.

Conversation is the primary control. The composer floats at the bottom of the workspace and opens into a conversation drawer. On wide screens the drawer docks beside the work instead of covering it. Every agent reply that changed saved state ends with a **change receipt** naming what changed and linking to it.

## Colors

### Primary
- **Kitchen Green `#2f5536`**: primary actions, the current day, selected navigation, completed checkout steps.
- **Olive Wall `#3f4229`**: the hero and sign-in grounds that hold the illustrations. Text on it uses **Warm Light `#fbf5e9`**, with secondary text in `#d8d4c1`.

### Secondary
- **Turmeric `#d98b2b`**: attention without alarm, used for "Up next", grocery counts, carbs, and calorie overruns. Text set in turmeric uses **`#9a5a10`** for contrast.
- **Plum `#4d4b7d`**: dinner and recipe accents, sparingly.

### Tertiary
- **Wood `#b08560`**: fats in macro bars. **Tomato `#b4402a`**: destructive actions and errors only.

### Neutral
- **Paper `#f5f1e8`** ground, **Card `#fffdf8`** surfaces, **Line `#e5ddcd`** borders, **Ink `#1f2a1f`** text, **Soft Ink `#474f42`** secondary text, **Mute `#6b6d60`** tertiary text.

### Named Rules
- **Meal colours are fixed.** Breakfast is turmeric-soft, lunch is sage, dinner is plum-soft, snack is warm wood. The same slot always has the same colour, everywhere.
- **Personal gets warmth.** Cards that show one member's data carry the turmeric wash. Shared cards never do.
- **Red means loss.** Tomato appears only where data is removed, an item won't be ordered, or something failed.

## Typography

Bricolage Grotesque is the display voice for the greeting, page titles and section titles. Figtree carries all UI text, data and controls. Both are self-hosted with `next/font`, and all numbers use tabular figures.

### Hierarchy
- Greeting / hero: 46px / 700 / −0.035em (30px on mobile).
- Page title: 34px / 700 / −0.03em (28px on mobile).
- Section title: 21px / 700 / −0.02em.
- Meal and item names: 15.5–16.5px / 650.
- Body: 15px / 400 / 1.5. Labels and metadata: 12.5–13.5px / 600.

### Named Rules
- **No eyebrows.** Headings speak for themselves; there are no tracked uppercase kickers.
- **Sentence case everywhere**, including buttons.

## Layout

- Desktop: a fixed 236px rail plus a workspace capped at 1240px. Main grids are `minmax(0, 1fr) + 320–340px` side columns.
- The workspace is a **size container**. Layout breakpoints respond to the workspace width, not the window, so a docked conversation reflows the page instead of crushing it.
- Below 1024px the rail becomes a top bar with the member switcher, and the sections move to a bottom tab bar. About Kitch moves into Household settings.
- The workspace reserves bottom space for the composer, so floating UI never hides the last content.

## Elevation & Depth

Surfaces are flat by default, defined by a 1px warm line. Only three things lift:
- **Raise** (`0 1px 0 line, 0 8px 18px -12px`): the active nav item, the selected segmented button, suggestion chips.
- **Float** (`0 18px 40px -18px`): the composer, popovers, dialogs and notices.
- **Drawer edge**: a soft left shadow on the conversation drawer.

## Shapes

10px for small controls, 12px for buttons, 14px for list groups and tiles, 20px for cards, 26px for heroes and dialogs. Day tiles use 14px, and the checkout step markers are circles.

## Components

### Buttons
Primary (Kitchen Green), default (card with a line), soft (sage, used for "Plan next week" and suggestions), quiet (text only, used for row actions) and danger (tomato outline). On olive grounds: Warm Light primary plus a translucent outline ghost. Every button scales to 0.97 when pressed.

### Cards / Containers
Warm-white cards with a 1px line and a 20px radius. Don't nest cards; groups inside a card use a 14px outlined list group with a paper-coloured header.

### Inputs / Fields
White fields with a 1px line and an 11px radius. Focus shows a green border plus a 3px green ring at 15% opacity. Selects use a drawn chevron. Checkboxes use the Kitchen Green accent.

### Navigation
The rail uses icon-plus-label links; the active link is a raised white pill in green. Counts (items to buy) are turmeric badges. The member switcher is a single popover at the bottom of the rail (in the top bar on mobile).

### Week timetable (signature)
Seven equal day tiles, each showing the weekday, the date numeral in the display face, and three dots for breakfast, lunch and dinner (filled when planned, ringed when empty). Today is filled green and past days are dimmed. A selected day with meals lists all three slots; its unplanned slots keep a small "Plan" action.

### Planner empty states
Empty never means three "Not planned" rows. When nothing is planned from today to the end of the visible week, one paper panel with the dining-table spot illustration invites planning the rest of the week (or the whole week, for a future week), with "Just today" as the quiet alternative; the header's "Plan next week" steps back. When a single upcoming day is empty, the panel uses the kadai illustration, offers "Plan <day>", and three single-meal picks in the fixed slot colours. A past empty day gets one muted line and no action. Every action drafts a request into the composer rather than sending it.

### Change receipt (signature)
A sage-outlined strip under an agent reply, made of an icon, a sentence ("Shopping list updated") and one link ("Open list"). It is driven only by the backend's returned action, never by the reply's prose.

### Warm-up screen (signature)
The cold-start screen sits on an olive ground with a warm radial stove glow. The kadai illustration has three blurred steam strands rising above it, and that steam is the only loading indicator. The copy follows real elapsed time and real retries: "Opening your kitchen" first, an explanation after 3 seconds, reassurance after 20 seconds, and an honest failure with "Try again". It never shows a fake progress bar or step list. Under reduced motion the steam holds still.

### Checkout steps
A numbered vertical stepper (1–6) with a connecting rail. Pending markers are sage; completed markers are filled green; locked steps are outlined and paper-coloured and show a lock note saying what unlocks them. "Place order" is the only large primary button on the page and sits after a dashed divider.

## Do's and Don'ts

### Do:
- Do use the kitchen illustrations at full bleed on the olive wall, with text on the empty left side.
- Do show "Not synced" instead of a price until a provider returns one.
- Do keep destructive actions in a separate danger zone, apart from routine controls.
- Do use the Icon component's single stroke family for every glyph.

### Don't:
- Don't use emoji or Unicode symbols as icons.
- Don't add eyebrow labels, decorative pills, glass effects or gradient text.
- Don't let any floating element cover content, at any width.
- Don't put personal nutrition data on a shared card without naming the member.
