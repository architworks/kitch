import asyncio
from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part
from agent import kitch_coordinator, IN_MEMORY_SCHEDULE, RECIPE_DATABASE

async def test_salmon():
    runner = InMemoryRunner(agent=kitch_coordinator, app_name="kitch_debug")
    
    # 1. Seed
    await runner.session_service.create_session(
        app_name="kitch_debug", user_id="archit", session_id="test_s",
        state={"user:profile_name": "Archit", "user:dietary_profile": "balanced", "app:household_size": "3"}
    )
    user_content = Content(role="user", parts=[Part(text="Plan a balanced meal plan for next week with some Indian food mixed in.")])
    async for event in runner.run_async(user_id="archit", session_id="test_s", new_message=user_content):
        pass
    
    print("--- SEEDED SCHEDULE ---")
    for s in IN_MEMORY_SCHEDULE:
        recipe = RECIPE_DATABASE.get(s["recipe_id"])
        print(f"{s['day_of_week'].capitalize()} {s['meal_type']}: {recipe['name']} ({s['recipe_id']})")
        
    print("\n--- REPLACING SALMON ---")
    user_content2 = Content(role="user", parts=[Part(text="I don't like salmon. Replace it wherever it appears in my meal plan.")])
    async for event in runner.run_async(user_id="archit", session_id="test_s", new_message=user_content2):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    fc = part.function_call
                    print(f"Tool Call: {fc.name}({fc.args})")
                    
    print("\n--- FINAL SCHEDULE ---")
    for s in IN_MEMORY_SCHEDULE:
        recipe = RECIPE_DATABASE.get(s["recipe_id"])
        print(f"{s['day_of_week'].capitalize()} {s['meal_type']}: {recipe['name']} ({s['recipe_id']})")
        
    salmon_rem = [s for s in IN_MEMORY_SCHEDULE if s["recipe_id"] == "d1"]
    print(f"\nRemaining salmon count: {len(salmon_rem)}")

asyncio.run(test_salmon())
