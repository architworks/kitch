# Kitch: Product Vision & Requirements Document

> [!NOTE]
> **Kitch** is a next-generation, AI-driven culinary assistant, personal chef, and smart household grocery manager. By blending conversational intelligence, multimodal computer vision, and local workspace file memory, it takes the cognitive load out of nourishing yourself, your family, and your household.

---

## 1. Executive Summary & Vision

Modern life demands split-second decisions about what we eat, yet managing nutrition, dietary preferences, household scaling, and grocery shopping remains a highly fragmented and stressful chore. 

**Kitch** bridges this gap. It acts as an empathetic, intelligent agent that:
1. **Understands your household’s unique palate and health targets.**
2. **Generates balanced, dynamic weekly meal plans** that scale perfectly to your household size (optimized for a 3-person home).
3. **Subtracts ingredients you already own** (pantry/fridge stock) from the weekly grocery orders to eliminate redundant buying.
4. **Maintains a platform-agnostic, Intermediary Native Grocery List** in its local database, separating planned needs from delivery logistics.
5. **Logs nutrition with zero friction** on an *individualized* basis using simple photo uploads.
6. **Remembers your precise ingredient brand preferences** using decentralized, offline local workspace memory files (`brand_preferences.md`) which the agent updates conversationally and consults natively during checkouts.
7. **Integrates with modular grocery delivery tools (like Blinkit MCP)** via a flexible Adapter Pattern, letting users review and order their list from their provider of choice with active human-in-the-loop approvals.

```mermaid
graph TD
    User([User]) <--> ChatAgent[Kitch Conversational Agent]
    User <--> WebDash[Web Dashboard]
    ChatAgent <--> CoreAI[Kitch GenAI Core]
    WebDash <--> CoreAI
    
    CoreAI --> Planner[Dynamic Weekly Planner]
    CoreAI --> VisionEngine[Plate & Fridge Vision Scanner]
    CoreAI --> PantryStock[Shared Pantry Inventory]
    CoreAI --> NativeList[Intermediary Native Grocery List]
    CoreAI <-->|Natively Reads & Writes| BrandPref[Local Workspace Brand Memory File]
    
    NativeList -->|Modular Adapter Layer| DeliveryRouter{Delivery Provider Router}
    DeliveryRouter -->|Blinkit Adapter| BlinkitMCP[Blinkit MCP Cart]
    DeliveryRouter -->|Zepto Adapter| ZeptoMCP[Zepto MCP Cart]
    DeliveryRouter -->|Future Adapters| OtherAPI[Instacart / BigBasket API]
```

---

## 2. Core Pillars & User Experience

### 🥗 Pillar 1: Dynamic Weekly Meal Planning & Pantry Subtraction
*No more redundant buying or "What's for dinner?" arguments.*
*   **Tailored to the Household:** Scales recipes and ingredient counts automatically for a 3-person home.
*   **Pantry Subtraction Logic:** Rather than buying raw recipe volumes every week, the system cross-references your current **Pantry & Fridge Stock**. Required ordering volumes are calculated dynamically:
    $$Shopping = \max(0, Required - Stock)$$
    If you already have enough, the item is labeled as *Stocked* and omitted from the order cart.
*   **Visual Fridge Scanning:** Simply take a photo of your fridge interior shelves. The computer vision engine segments shelves, detects items (e.g. cabbage, eggs, milk), and automatically inserts them into your Pantry Inventory.

### 📊 Pillar 2: Platform-Agnostic Intermediary Grocery List
*Decoupling recipe requirements from delivery providers.*
*   **Intermediary Native List**: The database maintains a native, provider-agnostic shopping list. This list aggregates scaled ingredients, tracks ticked items, and adjusts for pantry stock.
*   **Modular Delivery Adapters**: Delivery integrations are treated as modular plugins (the *Provider Pattern*). 
*   **Blinkit, Zepto, and More**: Users can review their native list on the dashboard, choose their preferred grocery delivery merchant, and export the list. The backend adapter maps native ingredients (e.g. "cabbage 1 piece") to merchant catalog payloads dynamically.

### 📈 Pillar 3: Context-Isolated Household vs. Individual "Minds"
*Shared collaborative assets alongside private personal health tracking.*
*   **The Shared Household Mind (Pantry & Weekly Schedule):** Pantry inventories, weekly recipe calendars, and intermediary grocery lists are collaborative household assets. All housemates see, edit, and subtract from the *same* physical inventory.
*   **The Individual Minds (Macro Diaries & User Preferences):** Calorie progress dials, daily macronutrient logs (Protein, Carbs, Fats, Fiber), and health journals are isolated **independently** per household member. 
*   **Frictionless Personal Logs:** If Dynamite snaps a photo of their lunch, it logs macros only to Dynamite's target diary. Housemate A and Housemate B's personal diaries remain separate and private.

### 📸 Pillar 4: Snap & Log (Computer Vision OCR)
*Say goodbye to tedious manual logging.*
*   **Photo-Based Estimation:** Snap a picture of your plate after eating. The multimodal GenAI identifies ingredients, estimates portion sizes, and logs personal macro/micro values.
*   **Interactive Refinement:** The AI presents its best estimate ("Looks like 150g grilled chicken, 100g quinoa. Correct?") and lets you confirm or adjust with a simple tap.

### 📝 Pillar 5: Decentralized Brand Preferences & Local File Memory
*No redundant relational table overhead. The agent manages its own records.*
*   **Local Preferences Markdown:** Rather than storing brand preferences in strict database tables, Kitch records your specific brand settings (e.g., always ordering bread from Brand A, paneer from Brand B) in a local markdown file (`brand_preferences.md`).
*   **Active Conversational Updates:** If you casually tell Kitch during a chat: *"Oh, remember to always buy Country Delight milk from now on,"* the agent utilizes its file editing tools to update your preference markdown dynamically.
*   **Checkout Consulting:** When you export your cart to Blinkit, the agent reads the local markdown file to translate generic recipe ingredients (e.g. "paneer 200g") into your favored branded SKUs (e.g., "Amul Malai Paneer 200g") in the delivery checkout payloads.
*   **Resource-Light Memory:** This file memory is only consulted when necessary, preventing bloat in the main conversational LLM prompt context window on routine chit-chat.

### 💬 Pillar 6: Conversational Chat & Delivery Verification
*An agent that lives in your ecosystem and fills your actual shopping cart.*
*   **Blinkit/Zepto MCP Cart Provisioning:** Finalized grocery lists can be exported directly into your grocery app cart via MCP tool hooks.
*   **Human-in-the-loop Review:** Before any grocery order is submitted, the application presents a clear terminal review prompt displaying the exact list. The order is placed only after explicit human approval.
*   **Conversational Chat (Telegram/WhatsApp):** Interact with Kitch on-the-go:
    *   *“We have chicken and spinach in the fridge, what can we make for the 3 of us tonight?”*
    *   *“Remember that Dynamite always prefers strictly organic whole wheat bread.”*
    *   *“Export my shopping list to Blinkit.”*

---

## 3. Product Features & Functional Requirements

### Feature Set 1: User & Household Profiling
| Feature ID | Feature Name | Description | User Impact |
| :--- | :--- | :--- | :--- |
| **REQ-001** | Household Scaling | Configures household size (default: 3 people), dietary profiles (keto, vegan, balanced), and ingredient exclusions (allergies). | Scales all planned recipe grocery lists. |
| **REQ-002** | Multi-User Macro Logs | Isolates macro logs, target calorie dials, and meal journals independently for each household member. | Accurate individual health tracking. |

### Feature Set 2: Pantry & Fridge Inventory Subtracted Planner
| Feature ID | Feature Name | Description | User Impact |
| :--- | :--- | :--- | :--- |
| **REQ-003** | Auto-Planner | Creates a cohesive, balanced 7-day meal schedule scaling all ingredients by household size. | Eliminates decision fatigue. |
| **REQ-004** | Shared Pantry Stock | A living shared inventory representing available ingredients in the home, editable manually or via natural language chats. | Tracks what the household already owns. |
| **REQ-005** | Cart Subtraction Engine | Compares weekly recipe requirements against pantry stock, reducing ordering quantities mathematically. | Prevents food waste and saves money. |

### Feature Set 3: Multimodal Vision Scanners
| Feature ID | Feature Name | Description | User Impact |
| :--- | :--- | :--- | :--- |
| **REQ-006** | Plate Macro OCR | Users upload post-meal plates. GenAI estimates portions and logs values to the *active member's* profile. | Zero-barrier macro tracking. |
| **REQ-007** | Fridge OCR Scan | Users upload fridge shelf layouts. GenAI detects ingredient volumes and appends them to the Shared Pantry Inventory. | Hands-free pantry stock logs. |

### Feature Set 4: Workspace File Memory & MCP Delivery
| Feature ID | Feature Name | Description | User Impact |
| :--- | :--- | :--- | :--- |
| **REQ-008** | Brand Preference Memory | Agent maintains and conversationally updates a local workspace file (`brand_preferences.md`) detailing specific item brands. | Customizes order fulfillment automatically. |
| **REQ-009** | Native Intermediary List | Maintains a unified, provider-agnostic required shopping list in the database. | Decouples groceries from merchants. |
| **REQ-010** | Modular Exporter (MCP) | Exposes pluggable delivery adapters (Blinkit, Zepto, etc.) to map native items to branded merchant cart payloads. | Prepares for multi-app expansion. |
| **REQ-011** | Human-in-the-loop Review | Displays an authorization dialog showing cart JSON inputs, prompting for explicit user approval before execution. | High security and error prevention. |

---

## 4. User Journey Scenarios

```mermaid
sequenceDiagram
    autonumber
    actor Dynamite as Dynamite (Telegram)
    participant Agent as Kitch Agent
    participant File as brand_preferences.md
    participant DB as Supabase DB
    participant Blinkit as Blinkit MCP Cart
    
    Note over Dynamite, File: Scenario A: Updating Brand Preferences
    Dynamite->>Agent: "Remember to always order bread of brand Bakers Dozen."
    Agent->>File: Write preference ("bread" -> "Bakers Dozen Whole Wheat")
    File-->>Agent: Preference saved successfully
    Agent->>Dynamite: "📝 Got it! I've updated your brand preferences file. I'll always map bread to Bakers Dozen."
    
    Note over Dynamite, DB: Scenario B: Shared Subtracted List Compilation
    Dynamite->>Agent: "Compile our grocery list."
    Agent->>DB: Pull planned ingredients, subtract shared pantry, write required items
    DB->>Agent: Shared native list compiled
    Agent->>Dynamite: "Household Shopping List compiled in your database."
    
    Note over Dynamite, Blinkit: Scenario C: Brand-Mapped Checkout
    Dynamite->>Agent: "Export our grocery list to Blinkit."
    Agent->>File: Read brand preferences
    File-->>Agent: Brand maps returned
    Agent->>Blinkit: Map native ingredients (e.g. 'bread') to branded items (e.g. 'Bakers Dozen Bread')
    Blinkit->>Dynamite: Prompt [Human Approval Dialog]
    Dynamite->>Blinkit: Click [APPROVE MCP CALL]
    Blinkit->>Agent: Sync Cart Successful!
    Agent->>Dynamite: "✨ Success! Blinkit cart loaded with your preferred branded products."
```

---

## 5. Success Metrics & Design Directives

### 💫 Design Directives
*   **Vibrant, Glassmorphic Dashboard**: Dark backgrounds combined with glowing sage greens, warm honey highlights, and multi-user profile quick toggles.
*   **Transparent MCP Terminal Logs**: Clearly formats JSON tool structures on checkouts, giving users confidence in agent actions.
*   **Empathetic Tone**: Proactively supports culinary routines, celebrating nutrient goals and helping coordinate family diets smoothly.
