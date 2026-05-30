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

export function createEmptyPlanningWeekDates() {
  return WEEK_DAYS.reduce((dates, day) => {
    dates[day] = { label: "", longLabel: "", iso: "" };
    return dates;
  }, {});
}

export function getUpcomingPlanningWeekDates(referenceDate = new Date()) {
  const start = new Date(referenceDate);
  start.setHours(0, 0, 0, 0);

  const currentDay = start.getDay();
  const daysUntilNextMonday = ((8 - currentDay) % 7) || 7;
  start.setDate(start.getDate() + daysUntilNextMonday);

  return WEEK_DAYS.reduce((dates, day, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);

    dates[day] = {
      iso: date.toISOString().slice(0, 10),
      label: date.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      longLabel: date.toLocaleDateString("en-US", {
        weekday: "long",
        month: "long",
        day: "numeric"
      })
    };

    return dates;
  }, {});
}

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
