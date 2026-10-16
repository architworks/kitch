// Placeholders shown until confirmed data arrives. A cold Supabase round trip
// can take seconds, and an empty state ("No meals planned yet", "0 items")
// shown during that time states something false.
export function SkeletonLine({ width = "100%", height = 12, className = "" }) {
  return <span className={`skeleton ${className}`.trim()} style={{ width, height }} aria-hidden="true" />;
}

export function LoadingCard({ label, rows = 3, className = "" }) {
  return (
    <section className={`card card-pad loading-card ${className}`.trim()} aria-busy="true">
      <span className="visually-hidden">{label}</span>
      <SkeletonLine width="38%" height={20} />
      {Array.from({ length: rows }).map((_, index) => (
        <SkeletonLine key={index} width={`${92 - index * 14}%`} />
      ))}
    </section>
  );
}
