#!/usr/bin/env python3
"""
Kitch Agent CLI Test Harness
=============================
Runs multi-turn conversation scenarios against the kitch_debug agent using
the ADK InMemoryRunner. Logs routing decisions, tool calls, and responses.

Usage:
    cd /path/to/diet_planner
    backend/venv/bin/python test/kitch_debug/test_harness.py
"""

import asyncio
import sys
import os
import json
import time
from datetime import datetime

# Add parent paths so we can import the agent module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import ADK components
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part


# --- Test Configuration ---

RESULTS = []
CURRENT_SCENARIO = ""


def log_result(scenario_id: str, status: str, details: str):
    """Log a test result."""
    entry = {
        "id": scenario_id,
        "status": status,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    RESULTS.append(entry)
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"  {icon} [{scenario_id}] {status}: {details}")


async def run_conversation(runner, user_id: str, session_id: str, messages: list[str]):
    """
    Run a multi-turn conversation and return structured results.
    
    Returns a list of turn results, each containing:
    - agent_responses: text from the agent
    - tool_calls: list of tool calls made
    - routing: which sub-agent was routed to
    """
    session_service = runner.session_service
    
    # Create session with initial state
    try:
        await session_service.create_session(
            app_name="kitch_debug",
            user_id=user_id,
            session_id=session_id,
            state={
                "user:profile_name": "Archit",
                "user:dietary_profile": "balanced",
                "app:household_size": "3"
            }
        )
    except Exception as e:
        print(f"  ℹ️  Session creation note: {e}")
    
    turn_results = []
    
    for i, message in enumerate(messages):
        print(f"\n  📨 Turn {i+1}: \"{message}\"")
        
        turn_data = {
            "input": message,
            "agent_responses": [],
            "tool_calls": [],
            "routing": [],
            "errors": []
        }
        
        user_content = Content(role="user", parts=[Part(text=message)])
        
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content
            ):
                # Capture routing (transfer_to_agent)
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call
                            if fc.name == "transfer_to_agent":
                                target = fc.args.get("agent_name", "unknown") if fc.args else "unknown"
                                turn_data["routing"].append(target)
                                print(f"  🔀 Routed to: {target}")
                            else:
                                tool_info = f"{fc.name}({json.dumps(fc.args, default=str)[:200]})" if fc.args else f"{fc.name}()"
                                turn_data["tool_calls"].append(fc.name)
                                print(f"  🔧 Tool: {tool_info}")
                        
                        if hasattr(part, 'function_response') and part.function_response:
                            fr = part.function_response
                            result_preview = str(fr.response)[:200] if fr.response else "None"
                            print(f"  📦 Result: {result_preview}...")
                
                # Capture final text response
                if event.is_final_response() and event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            turn_data["agent_responses"].append(part.text)
                            preview = part.text[:300].replace('\n', ' ')
                            print(f"  💬 Response: {preview}...")
                
                # Capture errors
                if hasattr(event, 'error_message') and event.error_message:
                    turn_data["errors"].append(event.error_message)
                    print(f"  ❌ Error: {event.error_message}")
                    
        except Exception as e:
            turn_data["errors"].append(str(e))
            print(f"  ❌ Exception: {e}")
        
        turn_results.append(turn_data)
        
        # Small delay between turns
        await asyncio.sleep(0.5)
    
    return turn_results


async def run_all_tests():
    """Run all test scenarios."""
    print("=" * 70)
    print("🧪 KITCH AGENT TEST HARNESS")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Import agent module - this triggers the agent.py code
    from agent import kitch_coordinator, IN_MEMORY_SCHEDULE, IN_MEMORY_MACROS, IN_MEMORY_PANTRY, RECIPE_DATABASE
    
    runner = InMemoryRunner(
        agent=kitch_coordinator,
        app_name="kitch_debug"
    )
    
    # ========================================================================
    # SCENARIO 1: Meal Plan Generation
    # ========================================================================
    print("\n" + "=" * 70)
    print("📋 SCENARIO 1: Meal Plan Generation")
    print("=" * 70)
    
    results = await run_conversation(
        runner, "archit", "s1_meal_plan",
        ["Plan my meals for next week. Keep it balanced and include some Indian food."]
    )
    
    if results and results[0]["tool_calls"]:
        if "save_weekly_plan_tool" in results[0]["tool_calls"]:
            log_result("1.1", "PASS", f"Plan saved. Schedule has {len(IN_MEMORY_SCHEDULE)} slots.")
        elif "get_recipes" in results[0]["tool_calls"]:
            log_result("1.1", "PARTIAL", f"Recipes fetched but plan may not be saved. Schedule: {len(IN_MEMORY_SCHEDULE)} slots.")
        else:
            log_result("1.1", "FAIL", f"Expected save_weekly_plan_tool. Got: {results[0]['tool_calls']}")
    elif results and results[0]["agent_responses"]:
        # Check if response mentions meals/days
        response_text = " ".join(results[0]["agent_responses"]).lower()
        has_days = any(d in response_text for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])
        if has_days:
            log_result("1.1", "PARTIAL", "Agent described a plan but may not have saved it to memory.")
        else:
            log_result("1.1", "FAIL", "No meal plan in response.")
    else:
        log_result("1.1", "FAIL", "No response or tool calls.")
    
    # Record schedule state for later tests
    schedule_after_plan = len(IN_MEMORY_SCHEDULE)
    print(f"\n  📊 Schedule state: {schedule_after_plan} slots")
    for slot in IN_MEMORY_SCHEDULE[:5]:
        recipe = RECIPE_DATABASE.get(slot.get("recipe_id", ""), {})
        print(f"     {slot['day_of_week'].capitalize()} {slot['meal_type']}: {recipe.get('name', slot['recipe_id'])}")
    if schedule_after_plan > 5:
        print(f"     ... and {schedule_after_plan - 5} more")
    
    # ========================================================================
    # SCENARIO 2: Plan Modification (Preserve Existing)
    # ========================================================================
    print("\n" + "=" * 70)
    print("✏️  SCENARIO 2: Plan Modification (Must Preserve Existing Plan)")
    print("=" * 70)
    
    # Only run if we have a plan
    if schedule_after_plan > 0:
        results = await run_conversation(
            runner, "archit", "s1_meal_plan",  # Same session for continuity
            ["Actually, change Monday dinner to Paneer Butter Masala"]
        )
        
        schedule_after_modify = len(IN_MEMORY_SCHEDULE)
        
        if schedule_after_modify >= schedule_after_plan - 1:
            # Check that save_weekly_plan_tool was NOT called (it wipes the plan)
            if results and "save_weekly_plan_tool" in results[0].get("tool_calls", []):
                log_result("2.1", "FAIL", 
                    f"Used save_weekly_plan_tool instead of update_single_meal_in_schedule! "
                    f"Plan went from {schedule_after_plan} to {schedule_after_modify} slots.")
            elif results and "update_single_meal_in_schedule" in results[0].get("tool_calls", []):
                log_result("2.1", "PASS", 
                    f"Used update_single_meal_in_schedule correctly. "
                    f"Plan preserved: {schedule_after_plan} → {schedule_after_modify} slots.")
            else:
                log_result("2.1", "PARTIAL", 
                    f"Plan seems preserved ({schedule_after_modify} slots) but unexpected tool calls: "
                    f"{results[0].get('tool_calls', [])}")
        else:
            log_result("2.1", "FAIL", 
                f"Plan was truncated! Went from {schedule_after_plan} to {schedule_after_modify} slots.")
    else:
        log_result("2.1", "SKIP", "No plan exists to modify.")
    
    # ========================================================================
    # SCENARIO 3: Macro Logging via Text
    # ========================================================================
    print("\n" + "=" * 70)
    print("📝 SCENARIO 3: Macro Logging via Text Message")
    print("=" * 70)
    
    macros_before = len(IN_MEMORY_MACROS.get("Archit", []))
    
    results = await run_conversation(
        runner, "archit", "s3_macros",
        ["I ate 2 rotis and dal for lunch today"]
    )
    
    macros_after = len(IN_MEMORY_MACROS.get("Archit", []))
    
    if macros_after > macros_before:
        latest = IN_MEMORY_MACROS["Archit"][-1]
        log_result("3.1", "PASS", 
            f"Meal logged: '{latest['name']}' — {latest['calories']} kcal, "
            f"P:{latest['macros']['protein']}g C:{latest['macros']['carbs']}g F:{latest['macros']['fat']}g")
    elif results and results[0]["tool_calls"]:
        if "log_macros_tool" in results[0]["tool_calls"]:
            log_result("3.1", "PARTIAL", "log_macros_tool was called but entry not found in memory.")
        else:
            log_result("3.1", "FAIL", f"Wrong tools called: {results[0]['tool_calls']}")
    else:
        log_result("3.1", "FAIL", "No macro entry logged and no tool calls made.")
    
    # Test 3.2: Smoothie
    results = await run_conversation(
        runner, "archit", "s3_macros",
        ["Had a smoothie — banana, peanut butter, oats, milk"]
    )
    
    macros_after_2 = len(IN_MEMORY_MACROS.get("Archit", []))
    if macros_after_2 > macros_after:
        latest = IN_MEMORY_MACROS["Archit"][-1]
        log_result("3.2", "PASS", f"Smoothie logged: '{latest['name']}' — {latest['calories']} kcal")
    else:
        log_result("3.2", "FAIL", "Smoothie not logged.")
    
    # ========================================================================
    # SCENARIO 5: Grocery List Creation
    # ========================================================================
    print("\n" + "=" * 70)
    print("🛒 SCENARIO 5: Grocery List Creation")
    print("=" * 70)
    
    results = await run_conversation(
        runner, "archit", "s5_grocery",
        ["What groceries do I need for the week?"]
    )
    
    if results and results[0]["tool_calls"]:
        if "calculate_intermediary_grocery_list" in results[0]["tool_calls"]:
            log_result("5.1", "PASS", "Grocery list calculated using the intermediary tool.")
        else:
            log_result("5.1", "PARTIAL", f"Tool calls made but not the expected one: {results[0]['tool_calls']}")
    elif results and results[0]["agent_responses"]:
        response_text = " ".join(results[0]["agent_responses"]).lower()
        if any(word in response_text for word in ["grocery", "buy", "shopping", "ingredient"]):
            log_result("5.1", "PARTIAL", "Agent discussed groceries but may not have used the calculation tool.")
        else:
            log_result("5.1", "FAIL", "Response doesn't discuss groceries.")
    else:
        log_result("5.1", "FAIL", "No response.")
    
    # ========================================================================
    # SCENARIO 7: Brand Preference
    # ========================================================================
    print("\n" + "=" * 70)
    print("⚙️  SCENARIO 7: Preference Persistence")
    print("=" * 70)
    
    from agent import IN_MEMORY_PREFERENCES
    prefs_before = len(IN_MEMORY_PREFERENCES)
    
    results = await run_conversation(
        runner, "archit", "s7_prefs",
        ["For bread, always get Baker's Dozen whole wheat"]
    )
    
    prefs_after = len(IN_MEMORY_PREFERENCES)
    
    if prefs_after > prefs_before:
        log_result("7.1", "PASS", f"Brand preference saved: {IN_MEMORY_PREFERENCES}")
    elif results and "set_brand_preference" in results[0].get("tool_calls", []):
        log_result("7.1", "PARTIAL", "set_brand_preference called but preference not found in memory.")
    else:
        log_result("7.1", "FAIL", f"No preference saved. Tool calls: {results[0].get('tool_calls', [])}")
    
    # ========================================================================
    # SCENARIO 8: Datetime Awareness
    # ========================================================================
    print("\n" + "=" * 70)
    print("🕐 SCENARIO 8: Datetime Awareness")
    print("=" * 70)
    
    results = await run_conversation(
        runner, "archit", "s8_datetime",
        ["What's for dinner tonight?"]
    )
    
    if results and results[0]["agent_responses"]:
        response_text = " ".join(results[0]["agent_responses"]).lower()
        today = datetime.now().strftime("%A").lower()
        
        # Check if the response mentions today's day or a specific recipe
        has_awareness = (
            today in response_text or
            "tonight" in response_text or
            "dinner" in response_text or
            any(r["name"].lower() in response_text for r in RECIPE_DATABASE.values())
        )
        
        if has_awareness:
            if "get_weekly_schedule_tool" in results[0].get("tool_calls", []):
                log_result("8.1", "PASS", f"Agent checked schedule and responded with today's ({today}) dinner.")
            else:
                log_result("8.1", "PARTIAL", f"Agent aware of context but didn't query schedule tool.")
        else:
            log_result("8.1", "FAIL", "Agent doesn't seem to know what day it is.")
    else:
        log_result("8.1", "FAIL", "No response.")
    
    # ========================================================================
    # SCENARIO 9: Natural Conversation Routing
    # ========================================================================
    print("\n" + "=" * 70)
    print("💬 SCENARIO 9: Natural Conversation Routing")
    print("=" * 70)
    
    # 9.1: Casual greeting should NOT route
    results = await run_conversation(
        runner, "archit", "s9_natural",
        ["Hey, what's up?"]
    )
    
    if results and results[0]["routing"]:
        log_result("9.1", "FAIL", f"Casual greeting was routed to: {results[0]['routing']} (should stay at coordinator)")
    elif results and results[0]["agent_responses"]:
        log_result("9.1", "PASS", "Coordinator handled greeting without routing.")
    else:
        log_result("9.1", "FAIL", "No response to greeting.")
    
    # 9.2: "I'm hungry" should route to chef_planner
    results = await run_conversation(
        runner, "archit", "s9_natural_2",
        ["I'm hungry, what should I eat?"]
    )
    
    if results and results[0]["routing"]:
        if "chef_planner" in results[0]["routing"]:
            log_result("9.2", "PASS", "Correctly routed 'I'm hungry' to chef_planner.")
        else:
            log_result("9.2", "PARTIAL", f"Routed to {results[0]['routing']} (expected chef_planner)")
    elif results and results[0]["agent_responses"]:
        response_text = " ".join(results[0]["agent_responses"]).lower()
        if any(word in response_text for word in ["eat", "meal", "recipe", "suggest", "dinner", "lunch"]):
            log_result("9.2", "PARTIAL", "Agent gave food advice but routing not detected.")
        else:
            log_result("9.2", "FAIL", "No food-related response.")
    else:
        log_result("9.2", "FAIL", "No response.")
    
    # ========================================================================
    # SCENARIO 10: Multi-Turn Continuity
    # ========================================================================
    print("\n" + "=" * 70)
    print("🔄 SCENARIO 10: Multi-Turn Continuity")
    print("=" * 70)
    
    results = await run_conversation(
        runner, "archit", "s10_multiturn",
        [
            "I ate pasta for lunch — about a big bowl of penne with tomato sauce",
            "How many calories have I eaten today so far?"
        ]
    )
    
    if len(results) >= 2:
        turn2_text = " ".join(results[1].get("agent_responses", [])).lower()
        turn2_tools = results[1].get("tool_calls", [])
        
        if "get_macro_diary_tool" in turn2_tools:
            log_result("10.2", "PASS", "Agent queried macro diary to check daily calories.")
        elif any(word in turn2_text for word in ["calorie", "kcal", "eaten", "total"]):
            log_result("10.2", "PARTIAL", "Agent discussed calories but may not have used diary tool.")
        else:
            log_result("10.2", "FAIL", "Turn 2 didn't reference the previous meal.")
    else:
        log_result("10.2", "FAIL", "Multi-turn conversation incomplete.")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    pass_count = sum(1 for r in RESULTS if r["status"] == "PASS")
    fail_count = sum(1 for r in RESULTS if r["status"] == "FAIL")
    partial_count = sum(1 for r in RESULTS if r["status"] == "PARTIAL")
    skip_count = sum(1 for r in RESULTS if r["status"] == "SKIP")
    
    print(f"\n  ✅ PASS:    {pass_count}")
    print(f"  ⚠️  PARTIAL: {partial_count}")
    print(f"  ❌ FAIL:    {fail_count}")
    print(f"  ⏭️  SKIP:    {skip_count}")
    print(f"  📝 TOTAL:   {len(RESULTS)}")
    
    # Write results to file
    results_path = os.path.join(os.path.dirname(__file__), "test_results.json")
    with open(results_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\n  📄 Results written to: {results_path}")
    
    # Print failures for easy debugging
    if fail_count > 0:
        print("\n  ❌ FAILED TESTS:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"     [{r['id']}] {r['details']}")
    
    print("\n" + "=" * 70)
    
    return RESULTS


if __name__ == "__main__":
    asyncio.run(run_all_tests())
