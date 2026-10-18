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

MAX_CHAT_MESSAGE_CHARS = 4000

class ChatRequest(BaseModel):
    # Long enough for any real kitchen request; stops pasted essays and
    # assignments from turning into large model calls.
    message: str = Field(max_length=MAX_CHAT_MESSAGE_CHARS)
    active_user: str
    planner_context: PlannerContext
    pantry_stock: List[Dict[str, Any]]
    grocery_list: List[Dict[str, Any]]

class ChatResponse(BaseModel):
    text: str
    action: Optional[Dict[str, Any]] = None
    # Grocery providers whose content this reply carries, so the UI can show
    # each one's required attribution beside it.
    provider_sources: List[str] = Field(default_factory=list)

class PantryAddRequest(BaseModel):
    name: str
    amount: float
    unit: str
