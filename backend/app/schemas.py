# Kitch: FastAPI Pydantic Schemas

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class PantryItem(BaseModel):
    name: str = Field(description="Name of ingredient/item")
    amount: float = Field(description="Quantity available")
    unit: str = Field(description="Unit of measurement (e.g. piece, g, cup)")

class MacroLog(BaseModel):
    recipe_name: str = Field(description="Name of parsed plate meal")
    calories: int = Field(description="Estimated energy in calories")
    protein_g: int = Field(description="Grams of protein")
    carbs_g: int = Field(description="Grams of carbohydrates")
    fat_g: int = Field(description="Grams of fats")
    fiber_g: int = Field(description="Grams of dietary fiber")

class FridgeScanResult(BaseModel):
    detected_items: List[PantryItem] = Field(description="List of items segment detected in the fridge")

class PlannerContext(BaseModel):
    visible_week_start: str
    selected_date: str

class ChatRequest(BaseModel):
    message: str
    active_user: str
    diet_preference: str
    household_size: int
    planner_context: PlannerContext
    pantry_stock: List[Dict[str, Any]]
    grocery_list: List[Dict[str, Any]]

class ChatResponse(BaseModel):
    text: str
    action: Optional[Dict[str, Any]] = None

class PantryAddRequest(BaseModel):
    name: str
    amount: float
    unit: str
