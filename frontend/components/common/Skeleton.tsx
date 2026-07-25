// Shared loading placeholders so every list page shimmers the same way instead
// of flashing plain "Loading…" text (matches the dashboard skeleton). Purely
// decorative — hidden from the accessibility tree.

export function CardListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3 animate-pulse" aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="bg-white rounded-lg shadow p-6">
          <div className="h-4 w-1/3 bg-gray-100 rounded mb-3" />
          <div className="h-3 w-1/2 bg-gray-100 rounded" />
        </div>
      ))}
    </div>
  );
}

export function TableRowsSkeleton({ rows = 8, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i} className="animate-pulse" aria-hidden="true">
          {Array.from({ length: cols }).map((_, j) => (
            <td key={j} className="px-6 py-4">
              <div className="h-4 bg-gray-100 rounded" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
