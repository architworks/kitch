# Kitch Production Test Subset Rerun

- Started: `2026-07-22T23:39:32+05:30`
- Finished: `2026-07-22T23:41:59+05:30`
- Timezone: `Asia/Kolkata`
- Source plan: `docs/production_test_results.md`, sections 1, 2, 5, 6, 7, and 8
- Runtime: Google ADK native Gemini (`gemini-3.6-flash`)
- Original report unchanged: `yes`
- Provider sync and real order placement: not exercised

## Outcome

**3 PASS, 12 FAIL, 1 INCONCLUSIVE, 0 ERROR**

| Scenario | Section | Status | Duration | Result |
| :--- | :--- | :---: | ---: | :--- |
| 1.1 | Meal Plan Generation | **PASS** | 16.1s | 7 days/21 meals persisted with requested theme |
| 1.2 | Meal Plan Generation | **PASS** | 11.6s | 7 days/21 meals persisted with requested theme |
| 1.3 | Meal Plan Generation | **FAIL** | 7.7s | Plan persistence or requested theme validation failed |
| 2.1 | Plan Modification | **FAIL** | 3.1s | Unexpected plan delta or requested replacement missing |
| 2.2 | Plan Modification | **FAIL** | 3.1s | Unexpected plan delta or requested replacement missing |
| 2.3 | Plan Modification | **INCONCLUSIVE** | 3.1s | Generated prerequisite plan contained no salmon occurrences to replace |
| 5.1 | Grocery List Creation | **FAIL** | 6.6s | Recipe artifact or native cart persistence failed |
| 5.2 | Grocery List Creation | **FAIL** | 3.3s | Recipe artifact or native cart persistence failed |
| 6.1 | Pantry-Aware Grocery Subtraction | **FAIL** | 3.2s | Pantry persistence or cart subtraction evidence missing |
| 6.2 | Pantry-Aware Grocery Subtraction | **FAIL** | 2.6s | Vision persistence or pantry-aware follow-up evidence was incomplete |
| 7.1 | Preference Persistence | **FAIL** | 28.3s | Preference acknowledgement or recall/application failed |
| 7.2 | Preference Persistence | **FAIL** | 33.9s | Preference acknowledgement or recall/application failed |
| 7.3 | Preference Persistence | **PASS** | 12.1s | Preference acknowledged and recalled/applied |
| 8.1 | Datetime Awareness | **FAIL** | 3.5s | Response did not explicitly resolve Wednesday |
| 8.2 | Datetime Awareness | **FAIL** | 3.5s | Response did not explicitly resolve Thursday |
| 8.3 | Datetime Awareness | **FAIL** | 3.5s | Reported calorie total did not match persisted diary |

## Detailed Evidence

### 1.1 — Meal Plan Generation — PASS

**Prompt:** Plan my meals for next week. Keep it balanced and diverse.

**Result:** 7 days/21 meals persisted with requested theme

**HTTP status:** `200`  
**Duration:** `16.087s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "text": "Here is your balanced and diverse meal plan for next week (**July 27, 2026 – August 2, 2026**):\n\n---\n\n### **Monday, July 27, 2026**\n* **Breakfast:** Berry & Nut Oatmeal with Honey\n* **Lunch:** Mediterranean Chickpea & Quinoa Salad\n* **Dinner:** Grilled Salmon with Asparagus and Brown Rice\n\n---\n\n### **Tuesday, July 28, 2026**\n* **Breakfast:** Avocado Toast with Poached Eggs\n* **Lunch:** Turkey and Veggie Wrap with Hummus\n* **Dinner:** Chicken & Broccoli Stir-Fry with Jasmine Rice\n\n---\n\n### **Wednesday, July 29, 2026**\n* **Breakfast:** Greek Yogurt Parfait with Granola & Fresh Berries\n* **Lunch:** Caprese Salad with Grilled Chicken\n* **Dinner:** Lean Beef Tacos with Black Beans and Corn Salsa\n\n---\n\n### **Thursday, July 30, 2026**\n* **Breakfast:** Spinach, Tomato & Mushroom Omelet\n* **Lunch:** Lentil Soup with Whole Wheat Sourdough Bread\n* **Dinner:** Baked Tofu Grain Bowl with Roasted Sweet Potatoes & Kale\n\n---\n\n### **Friday, July 31, 2026**\n* **Breakfast:** Whole Grain Pancakes with Fresh Fruit\n* **Lunch:** Asian Chicken Salad with Sesame Dressing\n* **Dinner:** Shrimp Scampi with Whole Wheat Spaghetti & Side Salad\n\n---\n\n### **Saturday, August 01, 2026**\n* **Breakfast:** Shakshuka with Warm Pita Bread\n* **Lunch:** Grilled Vegetable & Halloumi Panini\n* **Dinner:** Herb-Roasted Whole Chicken with Roasted Vegetables\n\n---\n\n### **Sunday, August 02, 2026**\n* **Breakfast:** Chia Seed Pudding with Mango and Coconut\n* **Lunch:** Minestrone Soup with Garlic Bread\n* **Dinner:** Pan-Seared Cod with Lemon Butter Sauce and Quinoa\n\n---\n\nThis plan has been saved to your schedule. Let me know if you'd like to swap any specific meal or if you want to generate detailed recipes and grocery lists for any of these dishes!",
    "action": {
      "type": "UPDATE_PLANNER"
    }
  },
  "evidence": {
    "days_persisted": 7,
    "nonempty_meal_slots": 21,
    "theme_detected": true,
    "weekly_plan": {
      "Sunday": {
        "breakfast": "Chia Seed Pudding with Mango and Coconut",
        "lunch": "Minestrone Soup with Garlic Bread",
        "dinner": "Pan-Seared Cod with Lemon Butter Sauce and Quinoa"
      },
      "Friday": {
        "breakfast": "Whole Grain Pancakes with Fresh Fruit",
        "lunch": "Asian Chicken Salad with Sesame Dressing",
        "dinner": "Shrimp Scampi with Whole Wheat Spaghetti & Side Salad"
      },
      "Tuesday": {
        "breakfast": "Avocado Toast with Poached Eggs",
        "lunch": "Turkey and Veggie Wrap with Hummus",
        "dinner": "Chicken & Broccoli Stir-Fry with Jasmine Rice"
      },
      "Wednesday": {
        "breakfast": "Greek Yogurt Parfait with Granola & Fresh Berries",
        "lunch": "Caprese Salad with Grilled Chicken",
        "dinner": "Lean Beef Tacos with Black Beans and Corn Salsa"
      },
      "Thursday": {
        "breakfast": "Spinach, Tomato & Mushroom Omelet",
        "lunch": "Lentil Soup with Whole Wheat Sourdough Bread",
        "dinner": "Baked Tofu Grain Bowl with Roasted Sweet Potatoes & Kale"
      },
      "Saturday": {
        "breakfast": "Shakshuka with Warm Pita Bread",
        "lunch": "Grilled Vegetable & Halloumi Panini",
        "dinner": "Herb-Roasted Whole Chicken with Roasted Vegetables"
      },
      "Monday": {
        "breakfast": "Berry & Nut Oatmeal with Honey",
        "lunch": "Mediterranean Chickpea & Quinoa Salad",
        "dinner": "Grilled Salmon with Asparagus and Brown Rice"
      }
    },
    "assistant_reply": "Here is your balanced and diverse meal plan for next week (**July 27, 2026 – August 2, 2026**):\n\n---\n\n### **Monday, July 27, 2026**\n* **Breakfast:** Berry & Nut Oatmeal with Honey\n* **Lunch:** Mediterranean Chickpea & Quinoa Salad\n* **Dinner:** Grilled Salmon with Asparagus and Brown Rice\n\n---\n\n### **Tuesday, July 28, 2026**\n* **Breakfast:** Avocado Toast with Poached Eggs\n* **Lunch:** Turkey and Veggie Wrap with Hummus\n* **Dinner:** Chicken & Broccoli Stir-Fry with Jasmine Rice\n\n---\n\n### **Wednesday, July 29, 2026**\n* **Breakfast:** Greek Yogurt Parfait with Granola & Fresh Berries\n* **Lunch:** Caprese Salad with Grilled Chicken\n* **Dinner:** Lean Beef Tacos with Black Beans and Corn Salsa\n\n---\n\n### **Thursday, July 30, 2026**\n* **Breakfast:** Spinach, Tomato & Mushroom Omelet\n* **Lunch:** Lentil Soup with Whole Wheat Sourdough Bread\n* **Dinner:** Baked Tofu Grain Bowl with Roasted Sweet Potatoes & Kale\n\n---\n\n### **Friday, July 31, 2026**\n* **Breakfast:** Whole Grain Pancakes with Fresh Fruit\n* **Lunch:** Asian Chicken Salad with Sesame Dressing\n* **Dinner:** Shrimp Scampi with Whole Wheat Spaghetti & Side Salad\n\n---\n\n### **Saturday, August 01, 2026**\n* **Breakfast:** Shakshuka with Warm Pita Bread\n* **Lunch:** Grilled Vegetable & Halloumi Panini\n* **Dinner:** Herb-Roasted Whole Chicken with Roasted Vegetables\n\n---\n\n### **Sunday, August 02, 2026**\n* **Breakfast:** Chia Seed Pudding with Mango and Coconut\n* **Lunch:** Minestrone Soup with Garlic Bread\n* **Dinner:** Pan-Seared Cod with Lemon Butter Sauce and Quinoa\n\n---\n\nThis plan has been saved to your schedule. Let me know if you'd like to swap any specific meal or if you want to generate detailed recipes and grocery lists for any of these dishes!"
  }
}
```

</details>

### 1.2 — Meal Plan Generation — PASS

**Prompt:** Actually, I'm feeling like eating Indian food this week. Plan a completely new weekly meal plan focusing on delicious Indian dishes.

**Result:** 7 days/21 meals persisted with requested theme

**HTTP status:** `200`  
**Duration:** `11.591s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "text": "Here is your new Indian meal plan for next week (**July 27, 2026 – August 2, 2026**):\n\n---\n\n### **Monday, July 27, 2026**\n* **Breakfast:** Poha with Roasted Peanuts & Curry Leaves\n* **Lunch:** Dal Tadka with Jeera Rice & Cucumber Raita\n* **Dinner:** Paneer Tikka Masala with Garlic Naan\n\n---\n\n### **Tuesday, July 28, 2026**\n* **Breakfast:** Masala Dosa with Sambar & Coconut Chutney\n* **Lunch:** Chana Masala with Whole Wheat Parathas\n* **Dinner:** Chicken Curry with Steamed Basmati Rice\n\n---\n\n### **Wednesday, July 29, 2026**\n* **Breakfast:** Aloo Paratha with Fresh Curd & Pickle\n* **Lunch:** Rajma Masala with Steamed Rice\n* **Dinner:** Palak Paneer with Rotis & Salad\n\n---\n\n### **Thursday, July 30, 2026**\n* **Breakfast:** Upma with Mixed Vegetables & Cashews\n* **Lunch:** Baingan Bharta with Whole Wheat Rotis\n* **Dinner:** Butter Chicken with Butter Naan\n\n---\n\n### **Friday, July 31, 2026**\n* **Breakfast:** Idli Sambar with Tomato Chutney\n* **Lunch:** Vegetable Biryani with Cucumber Mint Raita\n* **Dinner:** Fish Curry with Steamed Rice & Cabbage Poriyal\n\n---\n\n### **Saturday, August 01, 2026**\n* **Breakfast:** Moong Dal Cheela with Green Chutney\n* **Lunch:** Pav Bhaji with Toasted Pav\n* **Dinner:** Kadhai Paneer with Missi Roti & Kachumber Salad\n\n---\n\n### **Sunday, August 02, 2026**\n* **Breakfast:** Puri Bhaji with Sooji Halwa\n* **Lunch:** Hyderabadi Chicken Biryani with Mirchi Ka Salan\n* **Dinner:** Dal Makhani with Jeera Rice & Garlic Naan\n\n---\n\nYour schedule has been updated with this delicious Indian menu! Let me know if you need to swap any individual meals or want recipes and ingredient lists.",
    "action": {
      "type": "UPDATE_PLANNER"
    }
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
    "assistant_reply": "Here is your new Indian meal plan for next week (**July 27, 2026 – August 2, 2026**):\n\n---\n\n### **Monday, July 27, 2026**\n* **Breakfast:** Poha with Roasted Peanuts & Curry Leaves\n* **Lunch:** Dal Tadka with Jeera Rice & Cucumber Raita\n* **Dinner:** Paneer Tikka Masala with Garlic Naan\n\n---\n\n### **Tuesday, July 28, 2026**\n* **Breakfast:** Masala Dosa with Sambar & Coconut Chutney\n* **Lunch:** Chana Masala with Whole Wheat Parathas\n* **Dinner:** Chicken Curry with Steamed Basmati Rice\n\n---\n\n### **Wednesday, July 29, 2026**\n* **Breakfast:** Aloo Paratha with Fresh Curd & Pickle\n* **Lunch:** Rajma Masala with Steamed Rice\n* **Dinner:** Palak Paneer with Rotis & Salad\n\n---\n\n### **Thursday, July 30, 2026**\n* **Breakfast:** Upma with Mixed Vegetables & Cashews\n* **Lunch:** Baingan Bharta with Whole Wheat Rotis\n* **Dinner:** Butter Chicken with Butter Naan\n\n---\n\n### **Friday, July 31, 2026**\n* **Breakfast:** Idli Sambar with Tomato Chutney\n* **Lunch:** Vegetable Biryani with Cucumber Mint Raita\n* **Dinner:** Fish Curry with Steamed Rice & Cabbage Poriyal\n\n---\n\n### **Saturday, August 01, 2026**\n* **Breakfast:** Moong Dal Cheela with Green Chutney\n* **Lunch:** Pav Bhaji with Toasted Pav\n* **Dinner:** Kadhai Paneer with Missi Roti & Kachumber Salad\n\n---\n\n### **Sunday, August 02, 2026**\n* **Breakfast:** Puri Bhaji with Sooji Halwa\n* **Lunch:** Hyderabadi Chicken Biryani with Mirchi Ka Salan\n* **Dinner:** Dal Makhani with Jeera Rice & Garlic Naan\n\n---\n\nYour schedule has been updated with this delicious Indian menu! Let me know if you need to swap any individual meals or want recipes and ingredient lists."
  }
}
```

</details>

### 1.3 — Meal Plan Generation — FAIL

**Prompt:** Change my preference to keto and make a full weekly keto meal plan.

**Result:** Plan persistence or requested theme validation failed

**HTTP status:** `500`  
**Duration:** `7.691s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 5, model: gemini-3.6-flash\\nPlease retry in 51.507620012s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'model': 'gemini-3.6-flash', 'location': 'global'}, 'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '51s'}]}}"
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
**Duration:** `3.056s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 5, model: gemini-3.6-flash\\nPlease retry in 48.44662555s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '48s'}]}}"
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
**Duration:** `3.100s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 5, model: gemini-3.6-flash\\nPlease retry in 45.351254422s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '45s'}]}}"
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
**Duration:** `3.077s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 5, model: gemini-3.6-flash\\nPlease retry in 42.271862408s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '42s'}]}}"
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
**Duration:** `6.580s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 5, model: gemini-3.6-flash\\nPlease retry in 35.853911459s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '35s'}]}}"
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
**Duration:** `3.324s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 5, model: gemini-3.6-flash\\nPlease retry in 32.54035743s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '32s'}]}}"
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
**Duration:** `3.161s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 5, model: gemini-3.6-flash\\nPlease retry in 29.19275742s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '29s'}]}}"
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
        "amount": 1.0,
        "unit": "piece"
      },
      {
        "name": "red bell peppers",
        "amount": 2.0,
        "unit": "pieces"
      },
      {
        "name": "tomatoes",
        "amount": 5.0,
        "unit": "pieces"
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
**Duration:** `2.581s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 5, model: gemini-3.6-flash\\nPlease retry in 26.745600991s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '26s'}]}}"
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

**HTTP status:** `200`  
**Duration:** `28.344s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "text": "",
    "action": {
      "type": "UPDATE_PANTRY"
    }
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
**Duration:** `33.930s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 5, model: gemini-3.6-flash\\nPlease retry in 26.313763196s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '5'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '26s'}]}}"
  },
  "evidence": {
    "assistant_reply": "",
    "verification_probe_http_status": 500,
    "verification_probe": {
      "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash\\nPlease retry in 23.641659218s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '23s'}]}}"
    }
  }
}
```

</details>

### 7.3 — Preference Persistence — PASS

**Prompt:** I prefer Amul butter over any other brand

**Result:** Preference acknowledged and recalled/applied

**HTTP status:** `200`  
**Duration:** `12.116s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "text": "You asked never to add **cereals** or **cookies** to your grocery list (focusing instead on dairy, fruits, veggies, and specified household staples).\n\nI have also updated your household food preferences to save that you **prefer Amul butter over any other brand**.",
    "action": null
  },
  "evidence": {
    "assistant_reply": "You asked never to add **cereals** or **cookies** to your grocery list (focusing instead on dairy, fruits, veggies, and specified household staples).\n\nI have also updated your household food preferences to save that you **prefer Amul butter over any other brand**.",
    "verification_probe_http_status": 200,
    "verification_probe": {
      "status": "success",
      "result": "Prepared 1 legacy Zepto preview items with ADK native brand memory active. This preview tool does not modify provider carts. For live Zepto cart sync, use sync_native_cart_to_zepto_tool. Mapped items: [{'name': 'Prefer Amul butter over any other brand', 'qty': 500, 'unit': 'g'}]"
    }
  }
}
```

</details>

### 8.1 — Datetime Awareness — FAIL

**Prompt:** What's for dinner tonight?

**Result:** Response did not explicitly resolve Wednesday

**HTTP status:** `500`  
**Duration:** `3.537s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash\\nPlease retry in 8.802244424s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '8s'}]}}"
  },
  "evidence": {
    "expected_day": "Wednesday",
    "assistant_reply": ""
  }
}
```

</details>

### 8.2 — Datetime Awareness — FAIL

**Prompt:** What am I eating tomorrow morning?

**Result:** Response did not explicitly resolve Thursday

**HTTP status:** `500`  
**Duration:** `3.480s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash\\nPlease retry in 5.222560189s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '5s'}]}}"
  },
  "evidence": {
    "expected_day": "Thursday",
    "assistant_reply": ""
  }
}
```

</details>

### 8.3 — Datetime Awareness — FAIL

**Prompt:** How many calories have I eaten today so far?

**Result:** Reported calorie total did not match persisted diary

**HTTP status:** `500`  
**Duration:** `3.528s`

<details>
<summary>Captured evidence</summary>

```json
{
  "response": {
    "detail": "\nOn how to mitigate this issue, please refer to:\n\nhttps://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted\n\n\n429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.6-flash\\nPlease retry in 1.726373978s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.6-flash'}, 'quotaValue': '20'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '1s'}]}}"
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
