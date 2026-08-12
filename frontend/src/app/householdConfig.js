export const HOUSEHOLD_MEMBERS = [
  { value: "Archit", label: "Archit (me)" },
  { value: "Anubhav", label: "Anubhav" },
  { value: "Naman", label: "Naman" }
];

export const DEFAULT_ACTIVE_USER = HOUSEHOLD_MEMBERS[0].value;
export const DEFAULT_HOUSEHOLD_SIZE = HOUSEHOLD_MEMBERS.length;

export const MEAL_SLOTS = ["breakfast", "lunch", "dinner"];

export function shiftIsoDate(isoDate, days) {
  const date = new Date(`${isoDate}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function getWeekStartForDate(isoDate) {
  const date = new Date(`${isoDate}T12:00:00Z`);
  const mondayOffset = (date.getUTCDay() + 6) % 7;
  return shiftIsoDate(isoDate, -mondayOffset);
}

export function formatPlanDate(isoDate, options) {
  if (!isoDate) return "";
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    ...options
  }).format(new Date(`${isoDate}T12:00:00Z`));
}

export function createUserProfiles() {
  return HOUSEHOLD_MEMBERS.reduce((profiles, member) => {
    profiles[member.value] = { name: member.value, loggedMeals: [] };
    return profiles;
  }, {});
}
