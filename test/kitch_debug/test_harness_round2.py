#!/usr/bin/env python3
"""
Kitch Agent CLI Test Harness — Round 2
=======================================
Additional test scenarios: pantry-aware grocery, export, edge cases, 
multi-session memory, and proactive agent behavior.
"""

import asyncio
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part

RESULTS = []


def log_result(scenario_id: str, status: str, details: str):
    entry = {"id": scenario_id, "status": status, "details": details, "timestamp": datetime.now().isoformat()}
    RESULTS.append(entry)
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"  {icon} [{scenario_id}] {status}: {details}")


async def run_conversation(runner, user_id, session_id, messages, create_session=True):
    session_service = runner.session_service
    if create_session:
        try:
            await session_service.create_session(
                app_name="kitch_debug", user_id=user_id, session_id=session_id,
                state={"user:profile_name": "Archit", "user:dietary_profile": "balanced", "app:household_size": "3"}
            )
        except Exception:
            pass

    turn_results = []
    for i, message in enumerate(messages):
        print(f"\n  📨 Turn {i+1}: \"{message}\"")
        turn_data = {"input": message, "agent_responses": [], "tool_calls": [], "routing": [], "errors": []}
        user_content = Content(role="user", parts=[Part(text=message)])
        try:
            async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=user_content):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call
                            if fc.name == "transfer_to_agent":
                                target = fc.args.get("agent_name", "?") if fc.args else "?"
                                turn_data["routing"].append(target)
                                print(f"  🔀 Routed to: {target}")
                            else:
                                turn_data["tool_calls"].append(fc.name)
                                args_preview = json.dumps(fc.args, default=str)[:150] if fc.args else "()"
                                print(f"  🔧 Tool: {fc.name}({args_preview})")
                        if hasattr(part, 'function_response') and part.function_response:
                            result_preview = str(part.function_response.response)[:150]
                            print(f"  📦 Result: {result_preview}...")
                if event.is_final_response() and event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            turn_data["agent_responses"].append(part.text)
                            print(f"  💬 Response: {part.text[:250].replace(chr(10), ' ')}...")
                if hasattr(event, 'error_message') and event.error_message:
                    turn_data["errors"].append(event.error_message)
                    print(f"  ❌ Error: {event.error_message}")
        except Exception as e:
            turn_data["errors"].append(str(e))
            print(f"  ❌ Exception: {e}")
        turn_results.append(turn_data)
        await asyncio.sleep(0.5)
    return turn_results


async def run_round2():
    print("=" * 70)
    print("🧪 KITCH AGENT TEST HARNESS — ROUND 2")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    from agent import (kitch_coordinator, IN_MEMORY_SCHEDULE, IN_MEMORY_MACROS,
                       IN_MEMORY_PANTRY, IN_MEMORY_PREFERENCES, RECIPE_DATABASE)

    runner = InMemoryRunner(agent=kitch_coordinator, app_name="kitch_debug")

    # PRE-SEED: Create a meal plan first so grocery tests work
    print("\n🔧 Pre-seeding meal plan...")
    results = await run_conversation(runner, "archit", "r2_seed",
        ["Plan a balanced meal plan for next week with some Indian food mixed in."])
    schedule_count = len(IN_MEMORY_SCHEDULE)
    print(f"  📊 Seeded {schedule_count} meal slots.")

    # ========================================================================
    # SCENARIO 2.3: Replace all instances of an ingredient
    # ========================================================================
    print("\n" + "=" * 70)
    print("✏️  SCENARIO 2.3: Replace All Salmon Meals")
    print("=" * 70)

    schedule_before = len(IN_MEMORY_SCHEDULE)
    results = await run_conversation(runner, "archit", "r2_seed",
        ["I don't like salmon. Replace it wherever it appears in my meal plan."])

    schedule_after = len(IN_MEMORY_SCHEDULE)
    tools_used = results[0].get("tool_calls", []) if results else []

    if "get_weekly_schedule_tool" in tools_used:
        if "update_single_meal_in_schedule" in tools_used:
            # Check no salmon remains
            salmon_remaining = [s for s in IN_MEMORY_SCHEDULE if s["recipe_id"] == "d1"]
            if not salmon_remaining:
                log_result("2.3", "PASS",
                    f"All salmon meals replaced. Schedule preserved: {schedule_before} → {schedule_after} slots.")
            else:
                log_result("2.3", "PARTIAL",
                    f"{len(salmon_remaining)} salmon slot(s) still remain. Tools: {tools_used}")
        elif "save_weekly_plan_tool" in tools_used:
            log_result("2.3", "FAIL",
                f"Used save_weekly_plan_tool (wipes plan!) instead of update_single_meal_in_schedule.")
        else:
            log_result("2.3", "PARTIAL", f"Checked schedule but didn't update. Tools: {tools_used}")
    else:
        log_result("2.3", "FAIL", f"Didn't check the schedule first. Tools: {tools_used}")

    # ========================================================================
    # SCENARIO 6: Pantry-Aware Grocery Subtraction
    # ========================================================================
    print("\n" + "=" * 70)
    print("🥕 SCENARIO 6: Pantry-Aware Grocery Subtraction")
    print("=" * 70)

    # First tell the agent what we have
    results = await run_conversation(runner, "archit", "r2_pantry",
        ["I already have 2 kg of rice, a dozen eggs, and 500g chicken breast at home. "
         "Now make me a grocery list for the week."])

    if results:
        tools = results[0].get("tool_calls", [])
        resp = " ".join(results[0].get("agent_responses", [])).lower()

        has_pantry_update = "add_to_pantry_tool" in tools
        has_grocery = "calculate_intermediary_grocery_list" in tools

        if has_grocery:
            log_result("6.1", "PASS" if has_pantry_update else "PARTIAL",
                f"Grocery list generated. Pantry update: {'yes' if has_pantry_update else 'no'}. Tools: {tools}")
        elif "already" in resp or "stocked" in resp or "pantry" in resp:
            log_result("6.1", "PARTIAL", "Agent discussed pantry but may not have used the right tools.")
        else:
            log_result("6.1", "FAIL", f"Expected grocery calculation. Tools used: {tools}")

    # ========================================================================
    # SCENARIO 7.2: Category-Level Preference
    # ========================================================================
    print("\n" + "=" * 70)
    print("⚙️  SCENARIO 7.2: Category-Level Preference (Never Buy Cereals)")
    print("=" * 70)

    results = await run_conversation(runner, "archit", "r2_pref_cat",
        ["Never add cereals or packaged snacks to my grocery list. I only want fresh produce, dairy, and proteins."])

    if results:
        resp = " ".join(results[0].get("agent_responses", [])).lower()
        tools = results[0].get("tool_calls", [])
        routing = results[0].get("routing", [])

        if any(word in resp for word in ["noted", "remember", "preference", "saved", "won't", "no cereals"]):
            log_result("7.2", "PASS", f"Agent acknowledged category preference. Routing: {routing}")
        else:
            log_result("7.2", "PARTIAL", f"Response unclear about saving preference. Routing: {routing}")

    # ========================================================================
    # SCENARIO 8.2: Tomorrow morning resolution
    # ========================================================================
    print("\n" + "=" * 70)
    print("🕐 SCENARIO 8.2: What Am I Eating Tomorrow Morning?")
    print("=" * 70)

    results = await run_conversation(runner, "archit", "r2_datetime",
        ["What am I eating tomorrow morning?"])

    if results:
        resp = " ".join(results[0].get("agent_responses", [])).lower()
        tools = results[0].get("tool_calls", [])

        tomorrow_day = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        today_idx = datetime.now().weekday()
        tomorrow_name = tomorrow_day[(today_idx + 1) % 7]

        if "get_weekly_schedule_tool" in tools:
            if "breakfast" in resp or any(r["name"].lower() in resp for r in RECIPE_DATABASE.values()):
                log_result("8.2", "PASS", f"Correctly resolved 'tomorrow morning' to {tomorrow_name} breakfast.")
            else:
                log_result("8.2", "PARTIAL", f"Checked schedule but response unclear about tomorrow's breakfast.")
        else:
            log_result("8.2", "PARTIAL", f"Didn't use schedule tool. Tools: {tools}")

    # ========================================================================
    # SCENARIO 8.3: Daily Calorie Summary
    # ========================================================================
    print("\n" + "=" * 70)
    print("🕐 SCENARIO 8.3: Daily Calorie Summary")
    print("=" * 70)

    # Pre-log a meal
    from agent import log_macros_tool
    log_macros_tool("Archit", "Test breakfast", 350, 15, 40, 12, 4)

    results = await run_conversation(runner, "archit", "r2_calories",
        ["How many calories have I eaten today?"])

    if results:
        tools = results[0].get("tool_calls", [])
        resp = " ".join(results[0].get("agent_responses", [])).lower()

        if "get_macro_diary_tool" in tools:
            log_result("8.3", "PASS", "Agent queried macro diary for daily calorie check.")
        elif any(word in resp for word in ["calorie", "kcal", "eaten"]):
            log_result("8.3", "PARTIAL", "Discussed calories but may not have used diary tool.")
        else:
            log_result("8.3", "FAIL", f"No calorie discussion. Tools: {tools}")

    # ========================================================================
    # SCENARIO 9.3: Order groceries on Blinkit
    # ========================================================================
    print("\n" + "=" * 70)
    print("💬 SCENARIO 9.3: Order Groceries on Blinkit")
    print("=" * 70)

    results = await run_conversation(runner, "archit", "r2_blinkit",
        ["Order the groceries on Blinkit"])

    if results:
        tools = results[0].get("tool_calls", [])
        routing = results[0].get("routing", [])

        if "checkout_exporter" in routing:
            if "export_to_delivery" in tools:
                log_result("9.3", "PASS", "Routed to checkout_exporter and called export_to_delivery.")
            elif "calculate_intermediary_grocery_list" in tools:
                log_result("9.3", "PARTIAL", "Routed correctly, calculated list but may not have exported.")
            else:
                log_result("9.3", "PARTIAL", f"Routed correctly but tools: {tools}")
        else:
            log_result("9.3", "FAIL", f"Expected checkout_exporter routing. Got: {routing}")

    # ========================================================================
    # SCENARIO 9.4: Proactive - "My fridge is almost empty"
    # ========================================================================
    print("\n" + "=" * 70)
    print("💬 SCENARIO 9.4: Proactive — 'My fridge is almost empty'")
    print("=" * 70)

    results = await run_conversation(runner, "archit", "r2_proactive",
        ["My fridge is almost empty"])

    if results:
        resp = " ".join(results[0].get("agent_responses", [])).lower()
        routing = results[0].get("routing", [])

        # Agent should proactively offer to help — scan fridge, restock, or make a grocery list
        if any(word in resp for word in ["scan", "grocery", "restock", "shopping", "buy", "list", "order"]):
            log_result("9.4", "PASS", f"Agent proactively suggested next steps. Routing: {routing}")
        elif any(word in resp for word in ["help", "want", "need", "shall"]):
            log_result("9.4", "PARTIAL", "Agent asked what to do but wasn't proactive enough.")
        else:
            log_result("9.4", "FAIL", f"No proactive suggestion. Response: {resp[:200]}")

    # ========================================================================
    # SCENARIO 12.1: Scale for 10 people
    # ========================================================================
    print("\n" + "=" * 70)
    print("🚨 SCENARIO 12.1: Edge Case — Scale for 10 People")
    print("=" * 70)

    results = await run_conversation(runner, "archit", "r2_scale",
        ["I'm having 10 guests for dinner tonight. Scale the salmon recipe for 10 people."])

    if results:
        tools = results[0].get("tool_calls", [])
        resp = " ".join(results[0].get("agent_responses", [])).lower()

        if "scale_ingredients" in tools:
            log_result("12.1", "PASS", "Used scale_ingredients tool for 10 people.")
        elif "10" in resp and any(word in resp for word in ["salmon", "serving", "ingredient"]):
            log_result("12.1", "PARTIAL", "Discussed scaling for 10 but may not have used the tool.")
        else:
            log_result("12.1", "FAIL", f"Didn't scale. Tools: {tools}")

    # ========================================================================
    # SCENARIO 12.2: Rough calorie estimate
    # ========================================================================
    print("\n" + "=" * 70)
    print("🚨 SCENARIO 12.2: Edge Case — Rough Large Meal Estimate")
    print("=" * 70)

    macros_before = len(IN_MEMORY_MACROS.get("Archit", []))

    results = await run_conversation(runner, "archit", "r2_big_meal",
        ["I just had a massive cheat meal at a buffet, probably around 2500 calories. Just log it."])

    macros_after = len(IN_MEMORY_MACROS.get("Archit", []))

    if macros_after > macros_before:
        latest = IN_MEMORY_MACROS["Archit"][-1]
        log_result("12.2", "PASS", f"Logged cheat meal: {latest['calories']} kcal")
    elif results and "log_macros_tool" in results[0].get("tool_calls", []):
        log_result("12.2", "PARTIAL", "Tool called but entry not found in memory.")
    else:
        log_result("12.2", "FAIL", f"Cheat meal not logged. Tools: {results[0].get('tool_calls', []) if results else 'none'}")

    # ========================================================================
    # SCENARIO 3.3: Minimal calorie item (black coffee)
    # ========================================================================
    print("\n" + "=" * 70)
    print("📝 SCENARIO 3.3: Minimal Item — Black Coffee")
    print("=" * 70)

    macros_before = len(IN_MEMORY_MACROS.get("Archit", []))

    results = await run_conversation(runner, "archit", "r2_coffee",
        ["Just had a black coffee, nothing else"])

    macros_after = len(IN_MEMORY_MACROS.get("Archit", []))

    if macros_after > macros_before:
        latest = IN_MEMORY_MACROS["Archit"][-1]
        if latest["calories"] <= 20:
            log_result("3.3", "PASS", f"Black coffee logged correctly: {latest['calories']} kcal")
        else:
            log_result("3.3", "PARTIAL", f"Logged but calories seem high for black coffee: {latest['calories']} kcal")
    else:
        log_result("3.3", "FAIL", "Black coffee not logged.")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 70)
    print("📊 ROUND 2 TEST SUMMARY")
    print("=" * 70)

    pass_count = sum(1 for r in RESULTS if r["status"] == "PASS")
    fail_count = sum(1 for r in RESULTS if r["status"] == "FAIL")
    partial_count = sum(1 for r in RESULTS if r["status"] == "PARTIAL")

    print(f"\n  ✅ PASS:    {pass_count}")
    print(f"  ⚠️  PARTIAL: {partial_count}")
    print(f"  ❌ FAIL:    {fail_count}")
    print(f"  📝 TOTAL:   {len(RESULTS)}")

    results_path = os.path.join(os.path.dirname(__file__), "test_results_round2.json")
    with open(results_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\n  📄 Results written to: {results_path}")

    if fail_count > 0:
        print("\n  ❌ FAILED TESTS:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"     [{r['id']}] {r['details']}")

    if partial_count > 0:
        print("\n  ⚠️  PARTIAL TESTS:")
        for r in RESULTS:
            if r["status"] == "PARTIAL":
                print(f"     [{r['id']}] {r['details']}")

    print("\n" + "=" * 70)
    return RESULTS


if __name__ == "__main__":
    asyncio.run(run_round2())
