export const HOUSEHOLD_MEMBERS = [
  { value: "Archit", label: "Archit (me)" },
  { value: "Anubhav", label: "Anubhav" },
  { value: "Naman", label: "Naman" }
];

export const DEFAULT_ACTIVE_USER = HOUSEHOLD_MEMBERS[0].value;
export const DEFAULT_HOUSEHOLD_SIZE = HOUSEHOLD_MEMBERS.length;

export const WEEK_DAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday"
];

export const MEAL_SLOTS = ["breakfast", "lunch", "dinner", "snack"];

export function createEmptyWeeklyPlan() {
  return WEEK_DAYS.reduce((plan, day) => {
    plan[day] = {
      breakfast: "",
      lunch: "",
      dinner: "",
      snack: ""
    };
    return plan;
  }, {});
}

export function createUserProfiles() {
  return HOUSEHOLD_MEMBERS.reduce((profiles, member) => {
    profiles[member.value] = { name: member.value, loggedMeals: [] };
    return profiles;
  }, {});
}
