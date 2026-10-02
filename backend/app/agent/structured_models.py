"""Strict structured outputs used at non-mutating agent boundaries."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ObservedPantryItem(BaseModel):
    name: str = Field(min_length=1)
    amount: float = Field(ge=0)
    unit: str = Field(min_length=1)
    observation_mode: Literal["add", "set"] = "set"


class ObservedMeal(BaseModel):
    meal_name: str
    calories: int = Field(ge=0)
    protein_g: int = Field(ge=0)
    carbs_g: int = Field(ge=0)
    fat_g: int = Field(ge=0)
    fiber_g: int = Field(ge=0)


class PhotoAnalysis(BaseModel):
    classification: Literal["meal", "pantry", "ambiguous"]
    summary: str
    meal: ObservedMeal | None = None
    pantry_items: list[ObservedPantryItem] = Field(default_factory=list)
    ambiguity_question: str | None = None


class PantryAllocationSource(BaseModel):
    pantry_item_id: int | None = None
    pantry_item_name: str = Field(min_length=1)
    amount: float = Field(ge=0)
    unit: str = Field(min_length=1)


class PantryAllocationDetail(BaseModel):
    allocated_amount: float = Field(ge=0)
    allocated_unit: str = Field(min_length=1)
    sources: list[PantryAllocationSource] = Field(default_factory=list)
    reasoning: str = ""


class PantryCartAllocation(BaseModel):
    id: int
    purchase_amount: float = Field(ge=0)
    purchase_unit: str = Field(min_length=1)
    pantry_allocation: PantryAllocationDetail


class PantryReconciliation(BaseModel):
    allocations: list[PantryCartAllocation]
