"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Sparkles, ChevronRight, CornerDownLeft, ArrowDownLeft } from "lucide-react";
import apiClient from "@/lib/api";
import { useCategories } from "@/hooks/useCategories";
import { formatCurrency, formatDate } from "@/lib/utils";
import CategoryPicker from "@/components/common/CategoryPicker";
import type {
  Category,
  TransactionListItem,
  TriageMerchant,
  TriageResponse,
} from "@/types";

// Assigning a single row inside a merchant's drill-in overrides ONLY that row
// (no merchant_correction) — the merchant default is set separately.
function DrillIn({
  merchant,
  categories,
}: {
  merchant: string;
  categories: Category[];
}) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["merchant-rows", merchant],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/transactions?merchant=${encodeURIComponent(merchant)}&limit=200`
      );
      return (res.data?.data ?? []) as TransactionListItem[];
    },
  });

  const override = useMutation({
    mutationFn: async ({ id, categoryId }: { id: string; categoryId: string }) => {
      await apiClient.patch(`/api/transactions/${id}/category`, {
        category_id: categoryId,
      });
    },
    onSuccess: () => {
      // Refresh the affected data; keep the drill-in panel open so the user can
      // keep correcting individual payments (the whole point of drill-in).
      queryClient.invalidateQueries({ queryKey: ["merchant-rows", merchant] });
      queryClient.invalidateQueries({ queryKey: ["triage"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  if (isLoading) {
    return <p className="text-sm text-gray-500 px-1 py-2">Loading rows…</p>;
  }
  const rows = data ?? [];

  return (
    <div className="mt-3 border-t border-gray-100 pt-3">
      <p className="text-xs font-medium text-gray-500 mb-2">
        Override individual payments ({rows.length})
      </p>
      <ul className="space-y-1.5">
        {rows.map((r) => {
          const received = r.amount < 0; // positive = spent, negative = received
          return (
            <li
              key={r.id}
              className="flex items-center justify-between gap-3 text-sm"
            >
              <span className="text-gray-500 w-24 shrink-0">
                {formatDate(r.date)}
              </span>
              <span
                className={`w-28 shrink-0 font-medium ${
                  received ? "text-green-600" : "text-gray-900"
                }`}
              >
                {formatCurrency(r.amount)}
              </span>
              <span className="flex-1 truncate text-gray-400">{r.memo}</span>
              <select
                defaultValue={r.category_id ?? ""}
                onChange={(e) =>
                  e.target.value &&
                  override.mutate({ id: r.id, categoryId: e.target.value })
                }
                className="text-sm text-gray-900 border border-gray-300 rounded-lg px-2 py-1 bg-white max-w-[10rem]"
                aria-label={`Category for payment on ${r.date}`}
              >
                <option value="" disabled>
                  Set…
                </option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.icon ? `${c.icon} ` : ""}
                    {c.name}
                  </option>
                ))}
              </select>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function MerchantCard({
  m,
  focused,
  categories,
  autoFocusPicker,
  onFocus,
  onAssign,
  onCreate,
  drilled,
  onToggleDrill,
}: {
  m: TriageMerchant;
  focused: boolean;
  categories: Category[]; // already excludes "Other"
  autoFocusPicker: boolean;
  onFocus: () => void;
  onAssign: (categoryId: string) => void;
  onCreate: (name: string) => Promise<Category | void>;
  drilled: boolean;
  onToggleDrill: () => void;
}) {
  const quick = categories.slice(0, 9); // number-key quick-pick 1–9
  const received = m.net < 0;

  return (
    <div
      onClick={onFocus}
      className={`rounded-xl border bg-white px-5 py-4 transition cursor-pointer ${
        focused
          ? "border-blue-400 ring-2 ring-blue-100 shadow-sm"
          : "border-gray-200 hover:border-gray-300"
      }`}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="font-semibold text-gray-900 truncate">
            {m.raw_merchant}
          </p>
          <p className="text-xs text-gray-500">
            {m.count} {m.count === 1 ? "payment" : "payments"}
            {m.sample_memo ? ` · ${m.sample_memo}` : ""}
          </p>
        </div>
        <div className="text-right shrink-0">
          <p
            className={`font-bold ${received ? "text-green-600" : "text-gray-900"}`}
          >
            {formatCurrency(m.total)}
          </p>
          {received ? (
            <span className="inline-flex items-center gap-1 text-xs text-green-600 mt-0.5">
              <ArrowDownLeft className="w-3 h-3" />
              received
            </span>
          ) : (
            m.suggestion && (
              <span className="inline-flex items-center gap-1 text-xs text-indigo-600 mt-0.5">
                <Sparkles className="w-3 h-3" />
                {m.suggestion.category}
              </span>
            )
          )}
        </div>
      </div>

      {focused && (
        <div className="mt-4 space-y-3" onClick={(e) => e.stopPropagation()}>
          {received && (
            <p className="text-xs text-green-700 bg-green-50 border border-green-100 rounded-lg px-3 py-2">
              This merchant is <strong>net money received</strong> — don&apos;t
              label it as spending (e.g. a repayment, refund, or transfer in).
            </p>
          )}

          {m.suggestion && (
            <button
              onClick={() => onAssign(m.suggestion!.category_id)}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
            >
              <CornerDownLeft className="w-4 h-4" />
              Accept “{m.suggestion.category}”
            </button>
          )}

          {/* Number-key quick-pick */}
          <div className="flex flex-wrap gap-1.5">
            {quick.map((c, i) => (
              <button
                key={c.id}
                onClick={() => onAssign(c.id)}
                className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-700 hover:border-blue-300 hover:bg-blue-50"
                title={`Press ${i + 1}`}
              >
                <kbd className="text-[10px] text-gray-400">{i + 1}</kbd>
                <span>{c.icon ?? "🏷️"}</span>
                <span>{c.name}</span>
              </button>
            ))}
          </div>

          {/* Searchable / create-new (press "/" to focus) */}
          <CategoryPicker
            categories={categories}
            onSelect={onAssign}
            onCreate={onCreate}
            autoFocus={autoFocusPicker}
          />

          <button
            onClick={onToggleDrill}
            className="inline-flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-700"
          >
            <ChevronRight
              className={`w-3.5 h-3.5 transition ${drilled ? "rotate-90" : ""}`}
            />
            {drilled ? "Hide" : "Split"} individual payments{" "}
            <kbd className="text-[10px] text-gray-400">s</kbd>
          </button>

          {drilled && <DrillIn merchant={m.raw_merchant} categories={categories} />}
        </div>
      )}
    </div>
  );
}

export default function TriagePage() {
  const queryClient = useQueryClient();
  const { categories, createCategory } = useCategories();

  // "Other" is the bucket we're emptying — never an assignable target (it would
  // poison learning_records and waste a quick-pick slot).
  const selectable = useMemo(
    () => categories.filter((c) => c.name !== "Other"),
    [categories]
  );

  const { data, isLoading, error } = useQuery({
    queryKey: ["triage"],
    queryFn: async () => {
      const res = await apiClient.get("/api/transactions/triage");
      return res.data as TriageResponse;
    },
  });

  const merchants = data?.data ?? [];
  const [focus, setFocus] = useState(0);
  const [drill, setDrill] = useState<string | null>(null);
  const [searching, setSearching] = useState(false); // "/" focuses the picker
  const [assignError, setAssignError] = useState(false);

  // Capture the starting total once so we can show progress as we clear it.
  const startRef = useRef<{ amount: number; count: number } | null>(null);
  const [cleared, setCleared] = useState({ amount: 0, count: 0 });
  useEffect(() => {
    if (data && startRef.current === null) {
      startRef.current = { amount: data.total_amount, count: data.merchants };
    }
  }, [data]);

  const assign = useMutation({
    mutationFn: async ({
      raw_merchant,
      category_id,
    }: {
      raw_merchant: string;
      category_id: string;
    }) => {
      await apiClient.post("/api/transactions/assign-merchant", {
        raw_merchant,
        category_id,
      });
    },
    onSuccess: (_res, vars) => {
      let removedTotal = 0;
      queryClient.setQueryData<TriageResponse>(["triage"], (old) => {
        if (!old) return old;
        const removed = old.data.find((x) => x.raw_merchant === vars.raw_merchant);
        removedTotal = removed?.total ?? 0;
        const remaining = old.data.filter(
          (x) => x.raw_merchant !== vars.raw_merchant
        );
        return {
          data: remaining,
          merchants: remaining.length,
          total_amount: Math.max(0, old.total_amount - removedTotal),
        };
      });
      setCleared((c) => ({ amount: c.amount + removedTotal, count: c.count + 1 }));
      setDrill(null);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
    onError: (err: unknown) => {
      // Auth failures are handled by the API layer; surface everything else.
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status !== 401) setAssignError(true);
    },
  });

  const doAssign = useCallback(
    (raw_merchant: string, category_id: string) => {
      if (!category_id) return;
      setSearching(false);
      setAssignError(false);
      assign.mutate({ raw_merchant, category_id });
    },
    [assign]
  );

  const onCreate = useCallback(
    async (name: string) => {
      return await createCategory.mutateAsync({ name });
    },
    [createCategory]
  );

  // Keyboard: ↑/↓ or j/k move focus; ⏎ accept suggestion; 1–9 quick-pick;
  // "/" focus search; s split. Skipped while typing in the picker input.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) return;
      if (merchants.length === 0) return;
      const cur = merchants[Math.min(focus, merchants.length - 1)];

      if (e.key === "ArrowDown" || e.key === "j") {
        e.preventDefault();
        setSearching(false);
        setFocus((f) => Math.min(f + 1, merchants.length - 1));
      } else if (e.key === "ArrowUp" || e.key === "k") {
        e.preventDefault();
        setSearching(false);
        setFocus((f) => Math.max(f - 1, 0));
      } else if (e.key === "/") {
        e.preventDefault();
        setSearching(true);
      } else if (e.key === "Enter") {
        if (cur?.suggestion) doAssign(cur.raw_merchant, cur.suggestion.category_id);
      } else if (e.key === "s") {
        if (cur) setDrill((d) => (d === cur.raw_merchant ? null : cur.raw_merchant));
      } else if (/^[1-9]$/.test(e.key)) {
        const cat = selectable[parseInt(e.key, 10) - 1];
        if (cur && cat) doAssign(cur.raw_merchant, cat.id);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [merchants, focus, selectable, doAssign]);

  // Keep focus in range as the list shrinks.
  useEffect(() => {
    if (focus > merchants.length - 1) setFocus(Math.max(0, merchants.length - 1));
  }, [merchants.length, focus]);

  const start = startRef.current;
  const pct =
    start && start.amount > 0
      ? Math.min(100, Math.round((cleared.amount / start.amount) * 100))
      : 0;
  const focusedIndex = Math.min(focus, Math.max(0, merchants.length - 1));

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-4xl font-bold text-gray-900">Triage</h1>
          <p className="text-gray-500 mt-1">
            Label the biggest merchants first — each one clears all its payments
            and is remembered.
          </p>
        </div>
        <Link
          href="/dashboard"
          className="text-blue-600 hover:text-blue-700 font-medium"
        >
          ← Dashboard
        </Link>
      </div>

      {/* Progress */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mb-5">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="text-gray-600">
            {merchants.length} merchants ·{" "}
            <span className="font-semibold text-gray-900">
              {formatCurrency(data?.total_amount ?? 0)}
            </span>{" "}
            to categorize
          </span>
          {cleared.count > 0 && (
            <span className="text-green-600 font-medium">
              Cleared {cleared.count} · {formatCurrency(cleared.amount)}
            </span>
          )}
        </div>
        <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
          <div
            className="h-full bg-green-500 transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {assignError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
          Could not save that category. Please try again.
        </div>
      )}

      <p className="text-xs text-gray-400 mb-4">
        <kbd>↑</kbd>/<kbd>↓</kbd> move · <kbd>1–9</kbd> quick-pick ·{" "}
        <kbd>⏎</kbd> accept suggestion · <kbd>/</kbd> search · <kbd>s</kbd> split
      </p>

      {isLoading ? (
        <p className="text-gray-500">Loading your uncategorized merchants…</p>
      ) : error ? (
        <p className="text-red-600">Failed to load triage. Please try again.</p>
      ) : merchants.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-10 text-center">
          <p className="text-2xl font-semibold text-gray-900 mb-1">
            🎉 All caught up
          </p>
          <p className="text-gray-500 mb-4">
            Nothing left to categorize. Your breakdown is now truthful.
          </p>
          <Link
            href="/insights"
            className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700"
          >
            See your insights →
          </Link>
        </div>
      ) : (
        <div className="space-y-2.5">
          {merchants.map((m, i) => (
            <MerchantCard
              key={m.raw_merchant}
              m={m}
              focused={i === focusedIndex}
              categories={selectable}
              autoFocusPicker={i === focusedIndex && searching}
              onFocus={() => setFocus(i)}
              onAssign={(catId) => doAssign(m.raw_merchant, catId)}
              onCreate={onCreate}
              drilled={drill === m.raw_merchant}
              onToggleDrill={() =>
                setDrill((d) => (d === m.raw_merchant ? null : m.raw_merchant))
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
