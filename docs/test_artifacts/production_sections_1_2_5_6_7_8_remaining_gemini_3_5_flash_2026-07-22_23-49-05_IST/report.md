# Kitch Production Test Subset Rerun

- Started: `2026-07-22T23:49:25+05:30`
- Finished: `2026-07-23T00:01:56+05:30`
- Timezone: `Asia/Kolkata`
- Source plan: `docs/production_test_results.md`, sections 1, 2, 5, 6, 7, and 8
- Runtime: Google ADK native Gemini (`gemini-3.5-flash`)
- Original report unchanged: `yes`
- Provider sync and real order placement: not exercised

## Outcome

**0 PASS, 12 FAIL, 1 INCONCLUSIVE, 0 ERROR**

| Scenario | Section | Status | Duration | Result |
| :--- | :--- | :---: | ---: | :--- |
| 1.3 | Meal Plan Generation | **FAIL** | 11.5s | Plan persistence or requested theme validation failed |
| 2.1 | Plan Modification | **FAIL** | 14.3s | Unexpected plan delta or requested replacement missing |
| 2.2 | Plan Modification | **FAIL** | 178.8s | Unexpected plan delta or requested replacement missing |
| 2.3 | Plan Modification | **INCONCLUSIVE** | 203.4s | Generated prerequisite plan contained no salmon occurrences to replace |
| 5.1 | Grocery List Creation | **FAIL** | 124.5s | Recipe artifact or native cart persistence failed |
| 5.2 | Grocery List Creation | **FAIL** | 89.6s | Recipe artifact or native cart persistence failed |
| 6.1 | Pantry-Aware Grocery Subtraction | **FAIL** | 14.1s | Pantry persistence or cart subtraction evidence missing |
| 6.2 | Pantry-Aware Grocery Subtraction | **FAIL** | 16.1s | Vision persistence or pantry-aware follow-up evidence was incomplete |
| 7.1 | Preference Persistence | **FAIL** | 16.0s | Preference acknowledgement or recall/application failed |
| 7.2 | Preference Persistence | **FAIL** | 31.4s | Preference acknowledgement or recall/application failed |
| 8.1 | Datetime Awareness | **FAIL** | 17.8s | Response did not explicitly resolve Thursday |
| 8.2 | Datetime Awareness | **FAIL** | 15.9s | Response did not explicitly resolve Friday |
| 8.3 | Datetime Awareness | **FAIL** | 16.1s | Reported calorie total did not match persisted diary |

## Detailed Evidence

### 1.3 — Meal Plan Generation — FAIL

**Prompt:** Change my preference to keto and make a full weekly keto meal plan.

**Result:** Plan persistence or requested theme validation failed

**HTTP status:** `500`  
**Duration:** `11.507s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "days_persisted": 7,
    "nonempty_meal_slots": 21,
    "theme_detected": true,
    "weekly_plan": {
      "Wednesday": {
        "breakfast": "Aloo Paratha with Fresh Curd & Pickle",
        "lunch": "Rajma Masala with Steamed Rice",
        "dinner": "Palak Paneer with Rotis & Salad"
      },
      "Sunday": {
        "breakfast": "Puri Bhaji with Sooji Halwa",
        "lunch": "Hyderabadi Chicken Biryani with Mirchi Ka Salan",
        "dinner": "Dal Makhani with Jeera Rice & Garlic Naan"
      },
      "Thursday": {
        "breakfast": "Upma with Mixed Vegetables & Cashews",
        "lunch": "Baingan Bharta with Whole Wheat Rotis",
        "dinner": "Butter Chicken with Butter Naan"
      },
      "Monday": {
        "breakfast": "Poha with Roasted Peanuts & Curry Leaves",
        "lunch": "Dal Tadka with Jeera Rice & Cucumber Raita",
        "dinner": "Paneer Tikka Masala with Garlic Naan"
      },
      "Friday": {
        "breakfast": "Idli Sambar with Tomato Chutney",
        "lunch": "Vegetable Biryani with Cucumber Mint Raita",
        "dinner": "Fish Curry with Steamed Rice & Cabbage Poriyal"
      },
      "Saturday": {
        "breakfast": "Moong Dal Cheela with Green Chutney",
        "lunch": "Pav Bhaji with Toasted Pav",
        "dinner": "Kadhai Paneer with Missi Roti & Kachumber Salad"
      },
      "Tuesday": {
        "breakfast": "Masala Dosa with Sambar & Coconut Chutney",
        "lunch": "Chana Masala with Whole Wheat Parathas",
        "dinner": "Chicken Curry with Steamed Basmati Rice"
      }
    },
    "assistant_reply": ""
  }
}
```

</details>

### 2.1 — Plan Modification — FAIL

**Prompt:** Actually, swap Thursday dinner with something vegan.

**Result:** Unexpected plan delta or requested replacement missing

**HTTP status:** `500`  
**Duration:** `14.347s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "changed_slots": [],
    "assistant_reply": ""
  }
}
```

</details>

### 2.2 — Plan Modification — FAIL

**Prompt:** Change Monday breakfast to chia pudding

**Result:** Unexpected plan delta or requested replacement missing

**HTTP status:** `500`  
**Duration:** `178.849s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "changed_slots": [],
    "assistant_reply": ""
  }
}
```

</details>

### 2.3 — Plan Modification — INCONCLUSIVE

**Prompt:** I don't like salmon, replace it wherever it appears in my weekly meal plan.

**Result:** Generated prerequisite plan contained no salmon occurrences to replace

**HTTP status:** `500`  
**Duration:** `203.431s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "salmon_slots_before": [],
    "salmon_slots_after": [],
    "changed_slots": [],
    "assistant_reply": ""
  }
}
```

</details>

### 5.1 — Grocery List Creation — FAIL

**Prompt:** What groceries do I need for the week?

**Result:** Recipe artifact or native cart persistence failed

**HTTP status:** `500`  
**Duration:** `124.495s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "recipe_plan": null,
    "cart_item_count": 0,
    "cart_items": [],
    "assistant_reply": ""
  }
}
```

</details>

### 5.2 — Grocery List Creation — FAIL

**Prompt:** Make a shopping list

**Result:** Recipe artifact or native cart persistence failed

**HTTP status:** `500`  
**Duration:** `89.645s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "recipe_plan": null,
    "cart_item_count": 0,
    "cart_items": [],
    "assistant_reply": ""
  }
}
```

</details>

### 6.1 — Pantry-Aware Grocery Subtraction — FAIL

**Prompt:** I already have eggs and avocado, update the grocery list.

**Result:** Pantry persistence or cart subtraction evidence missing

**HTTP status:** `500`  
**Duration:** `14.113s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "pantry_items": [
      {
        "name": "leeks",
        "amount": 2.0,
        "unit": "stalks"
      },
      {
        "name": "broccoli",
        "amount": 1.0,
        "unit": "head"
      },
      {
        "name": "corn on the cob",
        "amount": 2.0,
        "unit": "ears"
      },
      {
        "name": "cucumber",
        "amount": 2.0,
        "unit": "piece"
      },
      {
        "name": "red bell peppers",
        "amount": 2.0,
        "unit": "pieces"
      },
      {
        "name": "tomatoes",
        "amount": 7.0,
        "unit": "piece"
      },
      {
        "name": "parsley",
        "amount": 1.0,
        "unit": "bunch"
      },
      {
        "name": "green onions",
        "amount": 1.0,
        "unit": "bunch"
      },
      {
        "name": "lemon",
        "amount": 1.0,
        "unit": "piece"
      },
      {
        "name": "radicchio",
        "amount": 1.0,
        "unit": "head"
      },
      {
        "name": "green apple",
        "amount": 1.0,
        "unit": "piece"
      },
      {
        "name": "romaine lettuce",
        "amount": 2.0,
        "unit": "heads"
      },
      {
        "name": "eggplant",
        "amount": 2.0,
        "unit": "pieces"
      },
      {
        "name": "strawberries",
        "amount": 1.0,
        "unit": "box"
      },
      {
        "name": "romanesco cauliflower",
        "amount": 1.0,
        "unit": "head"
      },
      {
        "name": "yellow bell pepper",
        "amount": 1.0,
        "unit": "piece"
      },
      {
        "name": "green bell pepper",
        "amount": 1.0,
        "unit": "piece"
      },
      {
        "name": "potatoes",
        "amount": 8.0,
        "unit": "pieces"
      },
      {
        "name": "bok choy",
        "amount": 1.0,
        "unit": "bunch"
      },
      {
        "name": "sugar snap peas",
        "amount": 1.0,
        "unit": "bag"
      },
      {
        "name": "artichokes",
        "amount": 2.0,
        "unit": "pieces"
      },
      {
        "name": "nectarines",
        "amount": 6.0,
        "unit": "pieces"
      },
      {
        "name": "pomegranate",
        "amount": 1.0,
        "unit": "piece"
      },
      {
        "name": "cauliflower",
        "amount": 1.0,
        "unit": "head"
      },
      {
        "name": "oranges",
        "amount": 3.0,
        "unit": "pieces"
      },
      {
        "name": "limes",
        "amount": 4.0,
        "unit": "pieces"
      },
      {
        "name": "mango",
        "amount": 1.0,
        "unit": "piece"
      },
      {
        "name": "green beans",
        "amount": 1.0,
        "unit": "bunch"
      },
      {
        "name": "brussels sprouts",
        "amount": 5.0,
        "unit": "pieces"
      },
      {
        "name": "kale",
        "amount": 1.0,
        "unit": "bunch"
      },
      {
        "name": "savoy cabbage",
        "amount": 1.0,
        "unit": "head"
      },
      {
        "name": "onion",
        "amount": 1.0,
        "unit": "piece"
      },
      {
        "name": "eggs",
        "amount": 6.0,
        "unit": "piece"
      },
      {
        "name": "milk",
        "amount": 1.0,
        "unit": "bottle"
      },
      {
        "name": "paneer/block cheese",
        "amount": 1.0,
        "unit": "block"
      }
    ],
    "stocked_cart_items": [],
    "assistant_reply": ""
  }
}
```

</details>

### 6.2 — Pantry-Aware Grocery Subtraction — FAIL

**Prompt:** Log my fridge scan and tell me what else I still need to buy

**Result:** Vision persistence or pantry-aware follow-up evidence was incomplete

**HTTP status:** `500`  
**Duration:** `16.054s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "known_fixture_items": [
      "eggs",
      "tomatoes",
      "cucumber",
      "milk",
      "paneer"
    ],
    "detected_expected_types": [],
    "new_pantry_items": [],
    "stocked_cart_items": [],
    "recipe_plan": null,
    "assistant_reply": ""
  }
}
```

</details>

### 7.1 — Preference Persistence — FAIL

**Prompt:** For bread, always get Baker's Dozen whole wheat

**Result:** Preference acknowledgement or recall/application failed

**HTTP status:** `500`  
**Duration:** `16.023s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "assistant_reply": "",
    "verification_probe_http_status": 200,
    "verification_probe": {
      "status": "success",
      "result": "Prepared 1 legacy Zepto preview items with ADK native brand memory active. This preview tool does not modify provider carts. For live Zepto cart sync, use sync_native_cart_to_zepto_tool. Mapped items: [{'name': 'bread', 'qty': 1, 'unit': 'loaf'}]"
    }
  }
}
```

</details>

### 7.2 — Preference Persistence — FAIL

**Prompt:** Never add cereals or cookies to my grocery list — only dairy, fruits, and veggies.

**Result:** Preference acknowledgement or recall/application failed

**HTTP status:** `500`  
**Duration:** `31.400s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "assistant_reply": "",
    "verification_probe_http_status": 500,
    "verification_probe": {
      "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
    }
  }
}
```

</details>

### 8.1 — Datetime Awareness — FAIL

**Prompt:** What's for dinner tonight?

**Result:** Response did not explicitly resolve Thursday

**HTTP status:** `500`  
**Duration:** `17.806s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "expected_day": "Thursday",
    "assistant_reply": ""
  }
}
```

</details>

### 8.2 — Datetime Awareness — FAIL

**Prompt:** What am I eating tomorrow morning?

**Result:** Response did not explicitly resolve Friday

**HTTP status:** `500`  
**Duration:** `15.929s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "expected_day": "Friday",
    "assistant_reply": ""
  }
}
```

</details>

### 8.3 — Datetime Awareness — FAIL

**Prompt:** How many calories have I eaten today so far?

**Result:** Reported calorie total did not match persisted diary

**HTTP status:** `500`  
**Duration:** `16.149s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
  },
  "evidence": {
    "diary_entries": [
      {
        "name": "2 egg omelette",
        "calories": 220,
        "macros": {
          "protein": 13,
          "carbs": 2,
          "fat": 17,
          "fiber": 0
        },
        "time": "2026-05-31T06:32:11.35226+00:00"
      },
      {
        "name": "Vegetable poha with peanuts",
        "calories": 430,
        "macros": {
          "protein": 10,
          "carbs": 68,
          "fat": 14,
          "fiber": 7
        },
        "time": "2026-05-31T06:34:24.703413+00:00"
      },
      {
        "name": "Paneer Manchurian (approx. 150g paneer)",
        "calories": 680,
        "macros": {
          "protein": 29,
          "carbs": 30,
          "fat": 45,
          "fiber": 2
        },
        "time": "2026-05-31T14:52:44.000167+00:00"
      },
      {
        "name": "Crispy Gnocchi Croquettes in Marinara Sauce",
        "calories": 190,
        "macros": {
          "protein": 3,
          "carbs": 23,
          "fat": 10,
          "fiber": 2
        },
        "time": "2026-05-31T15:40:01.509973+00:00"
      }
    ],
    "expected_calorie_total": 1520.0,
    "numbers_in_reply": [],
    "assistant_reply": ""
  }
}
```

</details>

## Test Fixture

`fridge_scan_fixture.png` was generated specifically for scenario 6.2. It visibly contains six eggs, two tomatoes, one cucumber, one milk bottle, and one paneer block.

## Integrity

- Before SHA-256: `386780c01907e764234f09bf63a738213edd33dd32ddc6d253c2af7d9c051066`
- After SHA-256: `386780c01907e764234f09bf63a738213edd33dd32ddc6d253c2af7d9c051066`

The historical `docs/production_test_results.md` file was read as the test plan and was not modified by this run.
