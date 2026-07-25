"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import apiClient from "@/lib/api";
import { useTransactions } from "@/hooks/useTransactions";
import { useCategories } from "@/hooks/useCategories";
import { formatCurrency, formatDate } from "@/lib/utils";
import type {
  Category,
  CategorySuggestion,
  Group,
  TransactionListItem,
} from "@/types";

const itemsPerPage = 50;

function SourceBadge({ source }: { source: "ai" | "rule" }) {
  const styles =
    source === "ai"
      ? "bg-indigo-50 text-indigo-700"
      : "bg-gray-100 text-gray-600";
  return (
    <span
      className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide ${styles}`}
    >
      {source}
    </span>
  );
}

function TransactionRow({
  tx,
  selected,
  onToggle,
  categories,
}: {
  tx: TransactionListItem;
  selected: boolean;
  onToggle: (id: string) => void;
  categories: Category[];
}) {
  const queryClient = useQueryClient();
  const [showPanel, setShowPanel] = useState(false);
  const [suggestion, setSuggestion] = useState<CategorySuggestion | null>(null);
  const [applied, setApplied] = useState(false);
  const [savedHint, setSavedHint] = useState(false);

  const isCredit = tx.direction === "credit";

  const suggestMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<CategorySuggestion>(
        `/api/transactions/${tx.id}/suggest-category`
      );
      return res.data;
    },
    onSuccess: (data) => {
      setSuggestion(data);
      setApplied(false);
      setShowPanel(true);
    },
  });

  const applyMutation = useMutation({
    mutationFn: async (categoryId: string) => {
      // Apply only sets THIS transaction's category. We intentionally omit
      // merchant_correction: sending it true would upsert a learning_record that
      // retrains the merchant→category mapping for every txn from this merchant,
      // which the single-row "Apply" button does not imply.
      const res = await apiClient.patch(`/api/transactions/${tx.id}/category`, {
        category_id: categoryId,
      });
      return res.data;
    },
    onSuccess: () => {
      setApplied(true);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  // Manual category fix. Unlike the AI "Apply" button, this sends
  // merchant_correction: true so the backend upserts a learning_record —
  // every future import from this merchant will use this category ("sticks").
  const categoryMutation = useMutation({
    mutationFn: async (categoryId: string) => {
      const res = await apiClient.patch(`/api/transactions/${tx.id}/category`, {
        category_id: categoryId,
        merchant_correction: true,
      });
      return res.data;
    },
    onSuccess: () => {
      setSavedHint(true);
      setTimeout(() => setSavedHint(false), 2500);
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  const suggestFailed =
    suggestMutation.isError &&
    (suggestMutation.error as any)?.response?.status !== 401;
  const applyFailed =
    applyMutation.isError &&
    (applyMutation.error as any)?.response?.status !== 401;

  return (
    <>
      <tr className="hover:bg-gray-50">
        <td className="px-4 py-4">
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggle(tx.id)}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            aria-label={`Select transaction ${tx.raw_merchant}`}
          />
        </td>
        <td className="px-6 py-4 text-sm text-gray-900 whitespace-nowrap">
          {formatDate(tx.date)}
        </td>
        <td className="px-6 py-4 text-sm text-gray-900">
          {tx.raw_merchant}
          {tx.memo && (
            <span className="block text-xs text-gray-400">{tx.memo}</span>
          )}
        </td>
        <td
          className={`px-6 py-4 text-sm font-medium whitespace-nowrap ${
            isCredit ? "text-green-600" : "text-gray-900"
          }`}
        >
          {formatCurrency(tx.amount)}
        </td>
        <td className="px-6 py-4 whitespace-nowrap">
          <div className="flex items-center gap-2">
            <select
              value={tx.category_id ?? ""}
              onChange={(e) =>
                e.target.value && categoryMutation.mutate(e.target.value)
              }
              disabled={categoryMutation.isPending || categories.length === 0}
              className="text-sm text-gray-900 border border-gray-300 rounded-lg px-2 py-1 bg-white max-w-[11rem] disabled:opacity-50"
              aria-label={`Category for ${tx.raw_merchant}`}
            >
              <option value="" disabled>
                Uncategorized
              </option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.icon ? `${c.icon} ` : ""}
                  {c.name}
                </option>
              ))}
            </select>
            {savedHint && (
              <span className="text-xs font-medium text-green-600 whitespace-nowrap">
                ✓ Remembered
              </span>
            )}
          </div>
        </td>
        <td className="px-6 py-4 text-right whitespace-nowrap">
          <button
            onClick={() => {
              if (showPanel) {
                setShowPanel(false);
              } else if (suggestion) {
                setShowPanel(true);
              } else {
                suggestMutation.mutate();
              }
            }}
            disabled={suggestMutation.isPending}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 disabled:opacity-50"
          >
            {suggestMutation.isPending ? (
              <span className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {suggestMutation.isPending ? "Thinking…" : "Suggest"}
          </button>
        </td>
      </tr>

      {suggestFailed && (
        <tr>
          <td colSpan={6} className="px-6 pb-4">
            <p className="text-sm text-red-600">
              Could not fetch a suggestion. Please try again.
            </p>
          </td>
        </tr>
      )}

      {showPanel && suggestion && (
        <tr>
          <td colSpan={6} className="px-6 pb-4 bg-blue-50/40">
            <div className="rounded-lg border border-blue-200 bg-white p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-gray-900">
                      {suggestion.suggested_category}
                    </span>
                    <SourceBadge source={suggestion.source} />
                    <span className="text-xs text-gray-400">
                      {Math.round((suggestion.confidence ?? 0) * 100)}% confidence
                    </span>
                  </div>
                  {suggestion.reasoning && (
                    <p className="text-sm text-gray-600">{suggestion.reasoning}</p>
                  )}
                  {applyFailed && (
                    <p className="mt-2 text-sm text-red-600">
                      Failed to apply. Please try again.
                    </p>
                  )}
                </div>
                <div className="shrink-0">
                  {applied ? (
                    <span className="text-sm font-medium text-green-600">
                      ✓ Applied
                    </span>
                  ) : (
                    <button
                      onClick={() =>
                        suggestion.suggested_category_id &&
                        applyMutation.mutate(suggestion.suggested_category_id)
                      }
                      disabled={
                        !suggestion.suggested_category_id ||
                        applyMutation.isPending
                      }
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
                      title={
                        suggestion.suggested_category_id
                          ? undefined
                          : "No matching category to apply"
                      }
                    >
                      {applyMutation.isPending ? "Applying…" : "Apply"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function TransactionsPage() {
  const [page, setPage] = useState(1);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [banner, setBanner] = useState<string | null>(null);
  const [clubError, setClubError] = useState<string | null>(null);
  const [clubModalOpen, setClubModalOpen] = useState(false);
  const [clubName, setClubName] = useState("");

  const queryClient = useQueryClient();

  // Debounce the merchant search so we don't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const { transactions, total, isLoading, error } = useTransactions({
    page,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    merchant: debouncedSearch || undefined,
    category_id: categoryFilter || undefined,
  });
  const { categories } = useCategories();

  const rows = transactions as TransactionListItem[];
  const totalPages = Math.ceil(total / itemsPerPage);

  // Auto-dismiss the success banner.
  useEffect(() => {
    if (!banner) return;
    const t = setTimeout(() => setBanner(null), 5000);
    return () => clearTimeout(t);
  }, [banner]);

  // Selecting spans the current page only; drop selection when the view changes.
  useEffect(() => {
    setSelected(new Set());
  }, [page, startDate, endDate, debouncedSearch, categoryFilter]);

  const allOnPageSelected =
    rows.length > 0 && rows.every((tx) => selected.has(tx.id));

  const toggleOne = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected((prev) => {
      if (rows.every((tx) => prev.has(tx.id))) return new Set();
      return new Set(rows.map((tx) => tx.id));
    });
  };

  const clubMutation = useMutation({
    mutationFn: async ({ name, ids }: { name: string; ids: string[] }) => {
      const res = await apiClient.post<Group>("/api/groups", {
        name,
        transaction_ids: ids,
      });
      return res.data;
    },
    onSuccess: (group) => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      setSelected(new Set());
      setClubError(null);
      setClubModalOpen(false);
      setBanner(`Grouped ${group.count} transactions into “${group.name}”.`);
    },
    onError: (err: any) => {
      if (err?.response?.status === 401) return; // auth layer handles this
      setClubError("Could not create the group. Please try again.");
    },
  });

  const handleClub = () => {
    if (selected.size === 0) return;
    setClubName("");
    setClubError(null);
    setClubModalOpen(true);
  };

  const confirmClub = () => {
    const ids = Array.from(selected);
    if (ids.length === 0 || !clubName.trim()) return;
    setClubError(null);
    clubMutation.mutate({ name: clubName.trim(), ids });
  };

  const selectedCount = selected.size;

  const bannerNode = useMemo(() => {
    if (!banner) return null;
    return (
      <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-lg mb-4 flex items-center justify-between">
        <span>{banner}</span>
        <Link
          href="/groups"
          className="text-green-700 hover:text-green-800 font-medium text-sm"
        >
          View groups →
        </Link>
      </div>
    );
  }, [banner]);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Transactions</h1>
        <Link
          href="/dashboard"
          className="text-blue-600 hover:text-blue-700 font-medium"
        >
          ← Back to Dashboard
        </Link>
      </div>

      {bannerNode}

      {/* Name-a-group modal (replaces window.prompt) */}
      {clubModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !clubMutation.isPending && setClubModalOpen(false)}
        >
          <div
            className="bg-white rounded-xl shadow-xl w-full max-w-md p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-gray-900 mb-1">Name this group</h3>
            <p className="text-sm text-gray-500 mb-4">
              Clubbing {selectedCount} transaction{selectedCount === 1 ? "" : "s"} into
              one group.
            </p>
            <input
              autoFocus
              type="text"
              value={clubName}
              onChange={(e) => setClubName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") confirmClub();
                if (e.key === "Escape") setClubModalOpen(false);
              }}
              placeholder="e.g. Goa trip, October rent…"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-400 mb-4"
            />
            {clubError && <p className="text-sm text-red-600 mb-3">{clubError}</p>}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setClubModalOpen(false)}
                disabled={clubMutation.isPending}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmClub}
                disabled={!clubName.trim() || clubMutation.isPending}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg disabled:opacity-50"
              >
                {clubMutation.isPending ? "Clubbing…" : "Create group"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-6 mb-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search merchant
            </label>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="e.g. Amazon, Swiggy, a person's name…"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-400"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Category
            </label>
            <select
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-gray-900 bg-white"
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.icon ? `${c.icon} ` : ""}
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-gray-900"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-gray-900"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={() => {
                setStartDate("");
                setEndDate("");
                setSearch("");
                setCategoryFilter("");
                setPage(1);
              }}
              className="w-full px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-lg transition"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Selection / club action bar */}
      {selectedCount > 0 && (
        <div className="sticky top-0 z-10 bg-blue-600 text-white rounded-lg shadow px-5 py-3 mb-4 flex items-center justify-between">
          <span className="font-medium">
            {selectedCount} selected
          </span>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSelected(new Set())}
              className="text-sm text-blue-100 hover:text-white"
            >
              Clear
            </button>
            <button
              onClick={handleClub}
              disabled={clubMutation.isPending}
              className="bg-white text-blue-700 hover:bg-blue-50 font-medium text-sm px-4 py-1.5 rounded-lg transition disabled:opacity-60"
            >
              {clubMutation.isPending
                ? "Clubbing…"
                : `Club ${selectedCount} selected`}
            </button>
          </div>
        </div>
      )}

      {clubError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
          {clubError}
        </div>
      )}

      {/* Transactions Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 w-10">
                <input
                  type="checkbox"
                  checked={allOnPageSelected}
                  onChange={toggleAll}
                  disabled={rows.length === 0}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  aria-label="Select all on this page"
                />
              </th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">
                Date
              </th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">
                Merchant
              </th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">
                Amount
              </th>
              <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">
                Category
              </th>
              <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">
                AI
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                  Loading transactions...
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-red-600">
                  Failed to load transactions. Please try again.
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                  No transactions found
                </td>
              </tr>
            ) : (
              rows.map((tx) => (
                <TransactionRow
                  key={tx.id}
                  tx={tx}
                  selected={selected.has(tx.id)}
                  onToggle={toggleOne}
                  categories={categories}
                />
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="bg-gray-50 px-6 py-4 flex items-center justify-between border-t">
            <p className="text-sm text-gray-600">
              Page {page} of {totalPages}
            </p>
            <div className="space-x-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-100"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
                className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-100"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
