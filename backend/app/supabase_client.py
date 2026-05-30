# Kitch: Supabase Production Client Wrapper

import os
from typing import Dict, List, Any
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# 1. Initialize Supabase Connection Client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials missing! Set SUPABASE_URL and SUPABASE_KEY in your .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Helper: Map user names to static test UUIDs
USER_ID_MAP = {
    "Dynamite": "00000000-0000-0000-0000-000000000000",
    "Housemate A": "11111111-1111-1111-1111-111111111111",
    "Housemate B": "22222222-2222-2222-2222-222222222222"
}

def get_user_id(user_name: str) -> str:
    """Returns the UUID for a user name, falling back to Dynamite."""
    return USER_ID_MAP.get(user_name, USER_ID_MAP["Dynamite"])

# 2. Profiles CRUD
def get_profile(user_name: str) -> Dict[str, Any]:
    """Fetches user profile information from Supabase."""
    profile_id = get_user_id(user_name)
    try:
        response = supabase.table("profiles").select("*").eq("id", profile_id).execute()
        if response.data:
            return response.data[0]
        return {}
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return {}

def update_profile(user_name: str, diet_preference: str, household_size: int, daily_calorie_target: int = 2000) -> Dict[str, Any]:
    """Updates user profile information in Supabase."""
    profile_id = get_user_id(user_name)
    data = {
        "full_name": user_name,
        "diet_preference": diet_preference,
        "household_size": household_size,
        "daily_calorie_target": daily_calorie_target
    }
    try:
        response = supabase.table("profiles").upsert({"id": profile_id, **data}).execute()
        return response.data[0] if response.data else {}
    except Exception as e:
        print(f"Error updating profile: {e}")
        return {}

# 3. Pantry & Fridge Stock CRUD
def get_pantry_stock(user_name: str) -> List[Dict[str, Any]]:
    """Fetches pantry stock levels for a specific profile from Supabase."""
    profile_id = get_user_id(user_name)
    try:
        response = supabase.table("pantry_stock").select("*").eq("profile_id", profile_id).execute()
        # Map DB keys to frontend state format
        mapped = []
        for row in response.data or []:
            mapped.append({
                "name": row["ingredient_name"],
                "amount": float(row["amount"]),
                "unit": row["unit"]
            })
        return mapped
    except Exception as e:
        print(f"Error fetching pantry stock: {e}")
        return []

def add_to_pantry(user_name: str, name: str, amount: float, unit: str = "piece") -> Dict[str, Any]:
    """Adds or updates a pantry ingredient stock in Supabase."""
    profile_id = get_user_id(user_name)
    name_clean = name.strip()
    try:
        # Check if item already exists case-insensitively
        pantry_items = get_pantry_stock(user_name)
        existing = next((i for i in pantry_items if i["name"].lower() == name_clean.lower()), None)
        
        if existing:
            # Update quantity
            new_amount = float(existing["amount"]) + float(amount)
            response = supabase.table("pantry_stock").update({
                "amount": new_amount,
                "unit": unit
            }).eq("profile_id", profile_id).eq("ingredient_name", existing["name"]).execute()
            return response.data[0] if response.data else {}
        else:
            # Insert new
            data = {
                "profile_id": profile_id,
                "ingredient_name": name_clean,
                "amount": amount,
                "unit": unit
            }
            response = supabase.table("pantry_stock").insert(data).execute()
            return response.data[0] if response.data else {}
    except Exception as e:
        print(f"Error adding to pantry: {e}")
        return {}

def remove_from_pantry(user_name: str, name: str) -> bool:
    """Removes a pantry item from Supabase."""
    profile_id = get_user_id(user_name)
    try:
        supabase.table("pantry_stock").delete().eq("profile_id", profile_id).eq("ingredient_name", name).execute()
        return True
    except Exception as e:
        print(f"Error removing from pantry: {e}")
        return False

# 4. Macro Intake Diary CRUD
def get_macro_diary(user_name: str) -> List[Dict[str, Any]]:
    """Fetches macro log records from Supabase."""
    profile_id = get_user_id(user_name)
    try:
        response = supabase.table("macro_diary").select("*").eq("profile_id", profile_id).execute()
        # Map database format to frontend state layout
        mapped = []
        for row in response.data or []:
            mapped.append({
                "name": row["meal_name"],
                "calories": row["calories"],
                "macros": {
                    "protein": row["protein_g"],
                    "carbs": row["carbs_g"],
                    "fat": row["fat_g"],
                    "fiber": row["fiber_g"]
                },
                "time": row["logged_at"] # In production, format timestamp nicely
            })
        return mapped
    except Exception as e:
        print(f"Error fetching macro diary: {e}")
        return []

def log_macros(
    user_name: str, 
    meal_name: str, 
    calories: int, 
    protein: int, 
    carbs: int, 
    fat: int, 
    fiber: int = 0
) -> Dict[str, Any]:
    """Logs a macro plate record in Supabase."""
    profile_id = get_user_id(user_name)
    data = {
        "profile_id": profile_id,
        "meal_name": meal_name,
        "calories": calories,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
        "fiber_g": fiber
    }
    try:
        response = supabase.table("macro_diary").insert(data).execute()
        return response.data[0] if response.data else {}
    except Exception as e:
        print(f"Error logging macros: {e}")
        return {}

def clear_macro_diary(user_name: str) -> bool:
    """Deletes all macro logs for the active user."""
    profile_id = get_user_id(user_name)
    try:
        supabase.table("macro_diary").delete().eq("profile_id", profile_id).execute()
        return True
    except Exception as e:
        print(f"Error clearing macro logs: {e}")
        return False
