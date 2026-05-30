export const DIET_TYPES = {
  balanced: {
    name: "Balanced Diet",
    description: "Even distribution of proteins, complex carbs, and healthy fats.",
    targetMacros: { protein: 30, carbs: 40, fat: 30 },
    dailyCalorieTargetPerPerson: 2000
  },
  keto: {
    name: "Keto / Low-Carb",
    description: "High healthy fats, moderate protein, and very low carbohydrates.",
    targetMacros: { protein: 25, carbs: 5, fat: 70 },
    dailyCalorieTargetPerPerson: 1800
  },
  vegan: {
    name: "Vegan / Plant-Based",
    description: "100% plant-based recipes rich in clean fibers and plant proteins.",
    targetMacros: { protein: 20, carbs: 55, fat: 25 },
    dailyCalorieTargetPerPerson: 1900
  },
  "high-protein": {
    name: "High-Protein Active",
    description: "Designed for muscle retention, high satiety, and active lifestyles.",
    targetMacros: { protein: 40, carbs: 35, fat: 25 },
    dailyCalorieTargetPerPerson: 2300
  }
};
