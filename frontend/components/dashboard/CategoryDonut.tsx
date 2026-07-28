"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { formatINR } from "@/lib/format";

/**
 * Spending by category as a donut plus a real legend.
 *
 * The old chart wrote "Category: ₹12,345" around the rim: on a phone the labels
 * collided and clipped, and on a laptop the pie shrank to make room for them. The
 * numbers live in the legend now — a list reads better than radial text at every
 * width, and it can carry a link per row.
 *
 * Responsive with CSS only (stacked under 1024px, side-by-side above). No width
 * measuring: this page prerenders, and reading `window` during render would fail
 * the build, not the browser.
 */

const COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b",
  "#8b5cf6", "#ec4899", "#14b8a6", "#f97316",
];
const OTHER_COLOR = "#94a3b8";

/** Slices beyond this roll into "Other" — 12 legible arcs is already generous. */
const MAX_SLICES = 6;

export type CategorySlice = { name: string; value: number };

type Props = {
  data: CategorySlice[];
  /** Category name → emoji, so the legend matches the rest of the app. */
  iconByName?: Map<string, string | undefined>;
};

export default function CategoryDonut({ data, iconByName }: Props) {
  const [activeName, setActiveName] = useState<string | null>(null);

  // Everything below is derived from ONE list, so the arcs, the legend
  // percentages and the centre total can't disagree with each other. In
  // particular the denominator is this list's own sum — not the page's
  // `totalSpent`, which counts categories that net negative and would leave the
  // percentages refusing to add up to 100.
  const { slices, total } = useMemo(() => {
    const sorted = [...data].sort((a, b) => b.value - a.value);
    const head = sorted.slice(0, MAX_SLICES);
    const tail = sorted.slice(MAX_SLICES);
    const rolled: CategorySlice[] =
      tail.length > 0
        ? [...head, { name: "Other", value: tail.reduce((s, c) => s + c.value, 0) }]
        : head;
    return { slices: rolled, total: rolled.reduce((s, c) => s + c.value, 0) };
  }, [data]);

  const othersCount = Math.max(data.length - MAX_SLICES, 0);
  const colorFor = (name: string, i: number) =>
    name === "Other" ? OTHER_COLOR : COLORS[i % COLORS.length];
  const share = (value: number) => (total > 0 ? (value / total) * 100 : 0);

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:gap-6">
      {/* Chart. The wrapper owns the height so the donut can grow on a laptop
          without the legend reflowing. */}
      <div className="relative h-[200px] w-full shrink-0 lg:h-[240px] lg:w-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius="62%"
              outerRadius="92%"
              paddingAngle={1.5}
              stroke="none"
              onMouseEnter={(_, index) => setActiveName(slices[index]?.name ?? null)}
              onMouseLeave={() => setActiveName(null)}
            >
              {slices.map((slice, i) => (
                <Cell
                  key={slice.name}
                  fill={colorFor(slice.name, i)}
                  // Dim the rest instead of drawing a tooltip: the legend already
                  // shows every figure, so hover only needs to say "this one".
                  opacity={activeName === null || activeName === slice.name ? 1 : 0.3}
                  className="transition-opacity"
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>

        {/* Centre readout — the hovered slice, or the total at rest. */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <p className="max-w-[70%] truncate text-xs font-medium uppercase tracking-wide text-gray-500">
            {activeName ?? "Total"}
          </p>
          <p className="text-xl font-bold tabular-nums text-gray-900 lg:text-2xl">
            {formatINR(
              activeName
                ? slices.find((s) => s.name === activeName)?.value ?? 0
                : total
            )}
          </p>
        </div>
      </div>

      {/* Legend. Each row is a way into the transactions behind the figure —
          except "Other", which isn't a real category to filter by. */}
      <ul className="min-w-0 flex-1 space-y-0.5">
        {slices.map((slice, i) => {
          const row = (
            <>
              <span
                aria-hidden="true"
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: colorFor(slice.name, i) }}
              />
              <span className="min-w-0 flex-1 truncate text-sm text-gray-700">
                {iconByName?.get(slice.name) ? `${iconByName.get(slice.name)} ` : ""}
                {slice.name}
                {slice.name === "Other" && othersCount > 0 && (
                  <span className="text-gray-400"> · {othersCount} more</span>
                )}
              </span>
              <span className="shrink-0 text-sm font-semibold tabular-nums text-gray-900">
                {formatINR(slice.value)}
              </span>
              <span className="w-10 shrink-0 text-right text-xs tabular-nums text-gray-500">
                {share(slice.value).toFixed(0)}%
              </span>
            </>
          );

          const className =
            "flex items-center gap-2.5 rounded-md px-2 py-1.5 transition hover:bg-gray-50";

          return (
            <li
              key={slice.name}
              onMouseEnter={() => setActiveName(slice.name)}
              onMouseLeave={() => setActiveName(null)}
            >
              {slice.name === "Other" ? (
                <div className={className}>{row}</div>
              ) : (
                <Link
                  href={{ pathname: "/transactions", query: { category: slice.name } }}
                  className={`${className} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500`}
                >
                  {row}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
