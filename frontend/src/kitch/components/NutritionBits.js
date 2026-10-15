import { formatNutritionNumber } from "../lib/helpers.js";

const pct = (value, target) => {
  const v = Number(value) || 0;
  const t = Number(target) || 0;
  return t > 0 ? Math.min(100, Math.round((v / t) * 100)) : 0;
};

export function CalorieRing({ value, target, size = 108, stroke = 10 }) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const percent = pct(value, target);
  const over = Number(target) > 0 && Number(value) > Number(target);
  return (
    <div className="ring" style={{ width: size, height: size }} role="img" aria-label={`${formatNutritionNumber(value)} of ${target || "—"} kcal`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--line-soft)" strokeWidth={stroke} />
        <circle
          className="ring-fill"
          cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke={over ? "var(--turmeric)" : "var(--green)"}
          strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - (circumference * percent) / 100}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="ring-label">
        <b>{formatNutritionNumber(value)}</b>
        <small>of {target ? Number(target).toLocaleString("en-IN") : "—"} kcal</small>
      </div>
    </div>
  );
}

export function MacroBars({ rows }) {
  return (
    <dl className="macros">
      {rows.map(row => (
        <div key={row.key} className={`macro ${row.key}`}>
          <dt>{row.label}</dt>
          <dd><b>{formatNutritionNumber(row.value)}</b> / {row.target || "—"} g</dd>
          <span className="bar" aria-hidden="true"><i style={{ width: `${pct(row.value, row.target)}%` }} /></span>
        </div>
      ))}
    </dl>
  );
}
