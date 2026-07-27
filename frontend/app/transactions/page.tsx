"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { TableRowsSkeleton } from "@/components/common/Skeleton";
import { Sparkles } from "lucide-react";
import apiClient from "@/lib/api";
import { useTransactions } from "@/hooks/useTransactions";
import { useCategories } from "@/hooks/useCategories";
import { formatCurrency, formatDate } from "@/lib/utils";
import type {
  Category,
  CategorySuggestion,
  Event,
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

  // Rendered twice — in the Category column on desktop, and folded under the
  // merchant on mobile (where that column is hidden). Same component instance,
  // so both drive the one mutation; only one is ever displayed.
  const categoryControl = (
    <div className="flex items-center gap-2">
      <select
        value={tx.category_id ?? ""}
        onChange={(e) =>
          e.target.value && categoryMutation.mutate(e.target.value)
        }
        disabled={categoryMutation.isPending || categories.length === 0}
        className="max-w-[11rem] rounded-lg border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 disabled:opacity-50"
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
        <span className="whitespace-nowrap text-xs font-medium text-green-600">
          ✓ Remembered
        </span>
      )}
    </div>
  );

  return (
    <>
      <tr className="hover:bg-gray-50">
        <td className="px-3 py-4 align-top md:px-4 md:align-middle">
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggle(tx.id)}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            aria-label={`Select transaction ${tx.raw_merchant}`}
          />
        </td>
        <td className="hidden whitespace-nowrap px-6 py-4 text-sm text-gray-900 md:table-cell">
          {formatDate(tx.date)}
        </td>
        <td className="px-3 py-4 align-top text-sm text-gray-900 md:px-6 md:align-middle">
          <span className="break-words">{tx.raw_merchant}</span>
          {tx.memo && (
            <span className="block text-xs text-gray-400">{tx.memo}</span>
          )}
          {/* Mobile only: the columns we drop, folded into this cell. */}
          <span className="mt-0.5 block text-xs text-gray-500 md:hidden">
            {formatDate(tx.date)}
          </span>
          <div className="mt-2 md:hidden">{categoryControl}</div>
        </td>
        <td
          className={`whitespace-nowrap px-3 py-4 text-right align-top text-sm font-medium md:px-6 md:text-left md:align-middle ${
            isCredit ? "text-green-600" : "text-gray-900"
          }`}
        >
          {formatCurrency(tx.amount)}
        </td>
        <td className="hidden whitespace-nowrap px-6 py-4 md:table-cell">
          {categoryControl}
        </td>
        <td className="whitespace-nowrap px-3 py-4 text-right align-top md:px-6 md:align-middle">
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
            <span className="hidden sm:inline">
              {suggestMutation.isPending ? "Thinking…" : "Suggest"}
            </span>
            <span className="sr-only sm:hidden">
              Suggest a category for {tx.raw_merchant}
            </span>
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

function TransactionsView() {
  // Filters can arrive in the URL (?category=Shopping&q=amazon&start=&end=), so a
  // figure elsewhere in the app — an Insights row, a dashboard tile — can link
  // straight to the transactions behind it, and the view stays bookmarkable.
  const searchParams = useSearchParams();
  const urlCategory = searchParams.get("category");

  const [page, setPage] = useState(1);
  const [startDate, setStartDate] = useState(searchParams.get("start") ?? "");
  const [endDate, setEndDate] = useState(searchParams.get("end") ?? "");
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  // Seeded to match `search` so the very first fetch is already filtered.
  const [debouncedSearch, setDebouncedSearch] = useState(
    searchParams.get("q") ?? ""
  );
  const [categoryFilter, setCategoryFilter] = useState("");
  const [sort, setSort] = useState<"date" | "amount">("date");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [banner, setBanner] = useState<string | null>(null);
  const [bannerLink, setBannerLink] = useState<{ href: string; label: string }>({
    href: "/groups",
    label: "View groups →",
  });
  const [clubError, setClubError] = useState<string | null>(null);
  const [clubModalOpen, setClubModalOpen] = useState(false);
  const [clubName, setClubName] = useState("");
  const [eventError, setEventError] = useState<string | null>(null);
  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [eventName, setEventName] = useState("");
  const [eventDescription, setEventDescription] = useState("");

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
    sort,
    order,
  });
  const { categories } = useCategories();

  // The URL names a category ("?category=Shopping") because that's what a link
  // from elsewhere knows; the filter itself needs the id, which only exists once
  // categories have loaded. Apply once, then leave the user's own changes alone.
  const urlCategoryApplied = useRef(false);
  useEffect(() => {
    if (urlCategoryApplied.current || !urlCategory || categories.length === 0) return;
    const match = categories.find(
      (c) => c.name.toLowerCase() === urlCategory.toLowerCase()
    );
    if (match) setCategoryFilter(match.id);
    urlCategoryApplied.current = true;
  }, [urlCategory, categories]);

  const rows = transactions as TransactionListItem[];
  const totalPages = Math.ceil(total / itemsPerPage);
  const hasFilters = Boolean(startDate || endDate || search || categoryFilter);
  const toggleSort = (col: "date" | "amount") => {
    if (sort === col) {
      setOrder((o) => (o === "desc" ? "asc" : "desc"));
    } else {
      setSort(col);
      setOrder("desc");
    }
    setPage(1);
  };
  const sortArrow = (col: "date" | "amount") =>
    sort === col ? (order === "desc" ? " ↓" : " ↑") : "";
  const clearFilters = () => {
    setStartDate("");
    setEndDate("");
    setSearch("");
    setCategoryFilter("");
    setPage(1);
  };

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
      setBannerLink({ href: "/groups", label: "View groups →" });
      setBanner(`Grouped ${group.count} transactions into “${group.name}”.`);
    },
    onError: (err: any) => {
      if (err?.response?.status === 401) return; // auth layer handles this
      setClubError("Could not create the group. Please try again.");
    },
  });

  const eventMutation = useMutation({
    mutationFn: async ({
      name,
      description,
      ids,
    }: {
      name: string;
      description: string;
      ids: string[];
    }) => {
      const res = await apiClient.post<Event>("/api/events", {
        name,
        description: description || undefined,
        transaction_ids: ids,
      });
      return res.data;
    },
    onSuccess: (event) => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
      setSelected(new Set());
      setEventError(null);
      setEventModalOpen(false);
      setBannerLink({ href: "/events", label: "View case studies →" });
      setBanner(`Saved “${event.name}” as a case study.`);
    },
    onError: (err: any) => {
      if (err?.response?.status === 401) return; // auth layer handles this
      setEventError("Could not save the event. Please try again.");
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

  const handleSaveEvent = () => {
    if (selected.size === 0) return;
    setEventName("");
    setEventDescription("");
    setEventError(null);
    setEventModalOpen(true);
  };

  const confirmEvent = () => {
    const ids = Array.from(selected);
    if (ids.length === 0 || !eventName.trim()) return;
    setEventError(null);
    eventMutation.mutate({
      name: eventName.trim(),
      description: eventDescription.trim(),
      ids,
    });
  };

  const selectedCount = selected.size;

  const bannerNode = useMemo(() => {
    if (!banner) return null;
    return (
      <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-lg mb-4 flex items-center justify-between">
        <span>{banner}</span>
        <Link
          href={bannerLink.href}
          className="text-green-700 hover:text-green-800 font-medium text-sm"
        >
          {bannerLink.label}
        </Link>
      </div>
    );
  }, [banner, bannerLink]);

  const handleExport = async () => {
    const res = await apiClient.get("/api/transactions/export", { responseType: "blob" });
    const url = URL.createObjectURL(res.data as Blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tally-transactions.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-gray-900 md:text-4xl">Transactions</h1>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={handleExport}
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Export CSV
          </button>
          <Link
            href="/dashboard"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            ← Back to Dashboard
          </Link>
        </div>
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

      {/* Save-as-event (case study) modal */}
      {eventModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !eventMutation.isPending && setEventModalOpen(false)}
        >
          <div
            className="bg-white rounded-xl shadow-xl w-full max-w-md p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-gray-900 mb-1">
              Save as a case study
            </h3>
            <p className="text-sm text-gray-500 mb-4">
              Grouping {selectedCount} transaction{selectedCount === 1 ? "" : "s"}{" "}
              into a named event. Each transaction keeps its own category.
            </p>
            <input
              autoFocus
              type="text"
              value={eventName}
              onChange={(e) => setEventName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setEventModalOpen(false);
              }}
              placeholder="e.g. New phone, Sister's wedding…"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-400 mb-3"
            />
            <textarea
              value={eventDescription}
              onChange={(e) => setEventDescription(e.target.value)}
              placeholder="Optional — what was this event about?"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-400 mb-4 resize-none"
            />
            {eventError && (
              <p className="text-sm text-red-600 mb-3">{eventError}</p>
            )}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setEventModalOpen(false)}
                disabled={eventMutation.isPending}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmEvent}
                disabled={!eventName.trim() || eventMutation.isPending}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg disabled:opacity-50"
              >
                {eventMutation.isPending ? "Saving…" : "Save event"}
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
              onClick={clearFilters}
              className="w-full px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-lg transition"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Selection / club action bar */}
      {selectedCount > 0 && (
        <div className="sticky top-0 z-10 mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-lg bg-blue-600 px-4 py-3 text-white shadow sm:px-5">
          <span className="font-medium">
            {selectedCount} selected
          </span>
          <div className="flex flex-wrap items-center gap-3">
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
            <button
              onClick={handleSaveEvent}
              disabled={eventMutation.isPending}
              className="bg-blue-500 text-white hover:bg-blue-400 font-medium text-sm px-4 py-1.5 rounded-lg transition disabled:opacity-60"
            >
              {eventMutation.isPending ? "Saving…" : "Save as Event"}
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
      <div className="overflow-x-auto rounded-lg bg-white shadow">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="w-10 px-3 py-3 md:px-4">
                <input
                  type="checkbox"
                  checked={allOnPageSelected}
                  onChange={toggleAll}
                  disabled={rows.length === 0}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  aria-label="Select all on this page"
                />
              </th>
              <th className="hidden px-6 py-3 text-left text-sm font-medium text-gray-700 md:table-cell">
                <button
                  type="button"
                  onClick={() => toggleSort("date")}
                  className="font-medium text-gray-700 hover:text-gray-900"
                >
                  Date{sortArrow("date")}
                </button>
              </th>
              <th className="px-3 py-3 text-left text-sm font-medium text-gray-700 md:px-6">
                <span className="md:hidden">
                  <button
                    type="button"
                    onClick={() => toggleSort("date")}
                    className="font-medium text-gray-700 hover:text-gray-900"
                  >
                    Merchant · Date{sortArrow("date")}
                  </button>
                </span>
                <span className="hidden md:inline">Merchant</span>
              </th>
              <th className="px-3 py-3 text-right text-sm font-medium text-gray-700 md:px-6 md:text-left">
                <button
                  type="button"
                  onClick={() => toggleSort("amount")}
                  className="font-medium text-gray-700 hover:text-gray-900"
                >
                  Amount{sortArrow("amount")}
                </button>
              </th>
              <th className="hidden px-6 py-3 text-left text-sm font-medium text-gray-700 md:table-cell">
                Category
              </th>
              <th className="px-3 py-3 text-right text-sm font-medium text-gray-700 md:px-6">
                AI
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading ? (
              <TableRowsSkeleton rows={8} cols={6} />
            ) : error ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-red-600">
                  Failed to load transactions. Please try again.
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-10 text-center">
                  {hasFilters ? (
                    <>
                      <p className="text-gray-900 font-medium">No transactions match these filters.</p>
                      <button
                        onClick={clearFilters}
                        className="mt-3 text-blue-600 hover:text-blue-700 font-medium"
                      >
                        Clear filters
                      </button>
                    </>
                  ) : (
                    <>
                      <p className="text-gray-900 font-medium">No transactions yet</p>
                      <p className="mt-1 text-sm text-gray-600">
                        Upload a bank or UPI statement and Tally does the rest.
                      </p>
                      <Link
                        href="/upload"
                        className="mt-3 inline-block text-blue-600 hover:text-blue-700 font-medium"
                      >
                        Upload a statement to get started
                      </Link>
                    </>
                  )}
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

export default function TransactionsPage() {
  // useSearchParams needs a Suspense boundary for the page to prerender.
  return (
    <Suspense
      fallback={
        <div className="rounded-lg bg-white p-6 shadow">
          <p className="text-gray-500">Loading transactions…</p>
        </div>
      }
    >
      <TransactionsView />
    </Suspense>
  );
}
