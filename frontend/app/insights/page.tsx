"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api";
import { Sparkles, TrendingDown, TrendingUp, Wallet, Hash, Wand2, Users } from "lucide-react";
import { useCategories } from "@/hooks/useCategories";
import { formatCurrency, formatDate } from "@/lib/utils";
import type {
  AIInsights,
  ContributionsResponse,
  InsightsSummary,
  MoversResponse,
  RecategorizeResponse,
  RecurringResponse,
} from "@/types";

import { formatAmount as inr } from "@/lib/format";

function monthLabel(month: string): string {
  // month is "YYYY-MM"
  const [y, m] = month.split("-");
  const date = new Date(Number(y), Number(m) - 1, 1);
  return date.toLocaleDateString("en-IN", { month: "short", year: "2-digit" });
}

export default function InsightsPage() {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [recatBanner, setRecatBanner] = useState<string | null>(null);
  const [recatError, setRecatError] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const { iconByName } = useCategories();

  const params: Record<string, string> = {};
  if (start) params.start = start;
  if (end) params.end = end;

  useEffect(() => {
    if (!recatBanner) return;
    const t = setTimeout(() => setRecatBanner(null), 8000);
    return () => clearTimeout(t);
  }, [recatBanner]);

  const recategorizeMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<RecategorizeResponse>("/api/recategorize");
      return res.data;
    },
    onSuccess: (data) => {
      setRecatError(null);
      if (data.status === "skipped") {
        setRecatBanner(
          data.reason || data.message || "Nothing to recategorize right now."
        );
        return;
      }
      setRecatBanner(
        data.message ||
          `AI categorized ${data.categorized_merchants ?? 0} merchants, updated ${
            data.updated_transactions ?? 0
          } transactions.`
      );
      // The categorised data lives in the summary + transactions queries. The AI
      // narrative (insights-ai) is intentionally expensive and cached, so we don't
      // force it to regenerate here.
      queryClient.invalidateQueries({ queryKey: ["insights-summary"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
    onError: (err: any) => {
      if (err?.response?.status === 401) return;
      setRecatError("Re-categorization failed. Please try again.");
    },
  });

  const {
    data: summary,
    isLoading,
    isError,
  } = useQuery<InsightsSummary>({
    queryKey: ["insights-summary", start || null, end || null],
    queryFn: async () => {
      const response = await apiClient.get("/api/insights/summary", { params });
      return response.data;
    },
  });

  const {
    data: ai,
    isLoading: aiLoading,
    isError: aiError,
  } = useQuery<AIInsights>({
    queryKey: ["insights-ai", start || null, end || null],
    queryFn: async () => {
      const response = await apiClient.get("/api/insights/ai", { params });
      return response.data;
    },
    // AI generation is slow — never poll it.
    refetchOnWindowFocus: false,
    staleTime: 5 * 60_000,
  });

  const { data: contributions, isSuccess: contributionsLoaded } =
    useQuery<ContributionsResponse>({
      queryKey: ["contributions"],
      queryFn: async () => {
        const response = await apiClient.get("/api/insights/contributions");
        return response.data;
      },
      refetchOnWindowFocus: false,
    });

  const contributionClusters = contributions?.data ?? [];

  const { data: recurring } = useQuery<RecurringResponse>({
    queryKey: ["recurring"],
    queryFn: async () => {
      const response = await apiClient.get("/api/insights/recurring");
      return response.data;
    },
    refetchOnWindowFocus: false,
    staleTime: 5 * 60_000,
  });
  const recurringItems = recurring?.data ?? [];

  const { data: movers } = useQuery<MoversResponse>({
    queryKey: ["movers"],
    queryFn: async () => {
      const response = await apiClient.get("/api/insights/movers");
      return response.data;
    },
    refetchOnWindowFocus: false,
    staleTime: 5 * 60_000,
  });
  // Only the genuine increases, biggest first, capped to keep the card scannable.
  const risers = (movers?.movers ?? []).filter((m) => m.delta > 0).slice(0, 5);

  // Promote a detected split-expense cluster into a tracked case-study event
  // (the #8 → #9 link). Includes the linked spend plus every repayment.
  const [savedCluster, setSavedCluster] = useState<string | null>(null);
  const saveCluster = useMutation({
    mutationFn: async (c: (typeof contributionClusters)[number]) => {
      const ids = [
        ...(c.source_debit ? [c.source_debit.id] : []),
        ...c.transaction_ids,
      ];
      const name = c.source_debit
        ? `Split: ${c.source_debit.merchant}`
        : `Split expense (${formatDate(c.date)})`;
      await apiClient.post("/api/events", {
        name,
        description: `${c.count} people repaid ${formatCurrency(
          c.total_received
        )}${c.net_cost !== null ? ` — net cost ${formatCurrency(c.net_cost)}` : ""}.`,
        transaction_ids: ids,
      });
      return name;
    },
    onSuccess: (name, c) => {
      setSavedCluster(`${c.date}`);
      queryClient.invalidateQueries({ queryKey: ["events"] });
      setTimeout(() => setSavedCluster(null), 3000);
    },
  });

  const maxCategory = Math.max(1, ...(summary?.top_categories ?? []).map((c) => c.total));
  const maxMonthly = Math.max(
    1,
    ...(summary?.monthly ?? []).flatMap((m) => [m.spent, m.received])
  );

  const tiles = [
    { label: "Total Spent", value: summary?.total_spent, icon: TrendingDown, color: "text-red-500" },
    { label: "Total Received", value: summary?.total_received, icon: TrendingUp, color: "text-green-500" },
    { label: "Net", value: summary?.net, icon: Wallet, color: "text-blue-500" },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-4xl font-bold text-gray-900">Insights</h1>
        <button
          onClick={() => recategorizeMutation.mutate()}
          disabled={recategorizeMutation.isPending}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition disabled:opacity-60"
        >
          {recategorizeMutation.isPending ? (
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <Wand2 className="w-4 h-4" />
          )}
          {recategorizeMutation.isPending
            ? "Re-categorizing…"
            : "Re-categorize with AI"}
        </button>
      </div>

      {recatBanner && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-lg">
          {recatBanner}
        </div>
      )}

      {recatError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {recatError}
        </div>
      )}

      {/* Date range filter */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-gray-900"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-gray-900"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={() => {
                setStart("");
                setEnd("");
              }}
              className="w-full px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-lg transition"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          Loading insights...
        </div>
      ) : isError || !summary ? (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          Failed to load insights. Please try again.
        </div>
      ) : (
        <>
          {/* Summary tiles */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {tiles.map((t) => {
              const Icon = t.icon;
              return (
                <div key={t.label} className="bg-white rounded-lg shadow p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-gray-500 text-sm font-medium">{t.label}</p>
                      <p className="text-3xl font-bold text-gray-900 mt-2">₹{inr(t.value)}</p>
                    </div>
                    <Icon className={`w-12 h-12 opacity-20 ${t.color}`} />
                  </div>
                </div>
              );
            })}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-500 text-sm font-medium">Transactions</p>
                  <p className="text-3xl font-bold text-gray-900 mt-2">{summary.txn_count}</p>
                </div>
                <Hash className="w-12 h-12 text-blue-500 opacity-20" />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top categories */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4">Top Categories</h2>
              {summary.top_categories.length === 0 ? (
                <p className="text-gray-500 text-sm">No spending data for this range.</p>
              ) : (
                <div className="space-y-3">
                  {summary.top_categories.map((c) => (
                    <div key={c.name}>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-gray-700">
                          {iconByName.get(c.name) ? `${iconByName.get(c.name)} ` : ""}
                          {c.name}{" "}
                          <span className="text-gray-400">({c.count})</span>
                        </span>
                        <span className="font-medium text-gray-900">₹{inr(c.total)}</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${(c.total / maxCategory) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Top merchants */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-bold text-gray-900 mb-4">Top Merchants</h2>
              {summary.top_merchants.length === 0 ? (
                <p className="text-gray-500 text-sm">No merchant data for this range.</p>
              ) : (
                <div className="divide-y">
                  {summary.top_merchants.map((m) => (
                    <div key={m.name} className="py-3 flex items-center justify-between">
                      <div className="min-w-0">
                        <p className="font-medium text-gray-900 truncate">{m.name}</p>
                        <p className="text-xs text-gray-500">{m.count} transactions</p>
                      </div>
                      <p className="font-semibold text-gray-900 shrink-0 ml-4">₹{inr(m.total)}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Monthly trend */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-900">Monthly Trend</h2>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm bg-red-400 inline-block" /> Spent
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm bg-green-400 inline-block" /> Received
                </span>
              </div>
            </div>
            {summary.monthly.length === 0 ? (
              <p className="text-gray-500 text-sm">No monthly data for this range.</p>
            ) : (
              <div className="overflow-x-auto">
                <div className="flex items-end gap-4 h-56 min-w-max pt-4">
                  {summary.monthly.map((m) => (
                    <div key={m.month} className="flex flex-col items-center gap-2">
                      <div className="flex items-end gap-1 h-44">
                        <div
                          className="w-6 bg-red-400 rounded-t hover:bg-red-500 transition-colors"
                          style={{ height: `${Math.max(2, (m.spent / maxMonthly) * 100)}%` }}
                          title={`Spent ₹${inr(m.spent)}`}
                        />
                        <div
                          className="w-6 bg-green-400 rounded-t hover:bg-green-500 transition-colors"
                          style={{ height: `${Math.max(2, (m.received / maxMonthly) * 100)}%` }}
                          title={`Received ₹${inr(m.received)}`}
                        />
                      </div>
                      <span className="text-xs text-gray-500">{monthLabel(m.month)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Month-over-month movers — what went up */}
      {risers.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-3 mb-1">
            <TrendingUp className="w-6 h-6 text-red-500" />
            <h2 className="text-lg font-bold text-gray-900">What went up</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            Biggest category increases
            {movers?.prev && movers?.latest
              ? ` from ${monthLabel(movers.prev)} to ${monthLabel(movers.latest)}`
              : ""}
            .
          </p>
          <div className="divide-y">
            {risers.map((m) => (
              <div key={m.category} className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-gray-900">{m.category}</p>
                  <p className="text-xs text-gray-500">
                    ₹{inr(m.from_amount)} → ₹{inr(m.to_amount)}
                  </p>
                </div>
                <span className="text-sm font-semibold text-red-600">+₹{inr(m.delta)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recurring payments / subscriptions */}
      {recurringItems.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-3 mb-1">
            <Wallet className="w-6 h-6 text-indigo-600" />
            <h2 className="text-lg font-bold text-gray-900">Recurring payments</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            Merchants charged on a regular monthly cadence — about{" "}
            <span className="font-medium text-gray-700">
              ₹{inr(recurring?.monthly_total ?? 0)}/mo
            </span>{" "}
            across {recurringItems.length} of them.
          </p>
          <div className="divide-y">
            {recurringItems.map((r) => (
              <div key={r.merchant} className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-gray-900">{r.merchant}</p>
                  <p className="text-xs text-gray-500">
                    {r.count} charges · every ~{r.cadence_days} days
                  </p>
                </div>
                <span className="text-sm font-semibold text-gray-900">
                  ₹{inr(r.monthly)}/mo
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Split expenses / contributions */}
      {contributionClusters.length > 0 ? (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-3 mb-1">
            <Users className="w-6 h-6 text-blue-600" />
            <h2 className="text-lg font-bold text-gray-900">
              Split expenses / contributions
            </h2>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            Clusters where friends sent money back to offset a big spend.
            {typeof contributions?.total_recovered === "number" && (
              <>
                {" "}
                <span className="font-medium text-gray-700">
                  {formatCurrency(contributions.total_recovered)}
                </span>{" "}
                recovered in total.
              </>
            )}
          </p>
          <div className="space-y-3">
            {contributionClusters.map((c, i) => (
              <div
                key={`${c.date}-${i}`}
                className="rounded-lg border border-gray-200 p-4"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      {c.count} {c.count === 1 ? "person" : "people"} sent ~
                      {formatCurrency(c.avg_amount)} back
                    </p>
                    <p className="text-xs text-gray-500">
                      {formatDate(c.date)} ·{" "}
                      {formatCurrency(c.total_received)} received
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {c.source_debit && c.net_cost !== null && (
                      <span className="text-sm font-semibold text-green-600 bg-green-50 px-3 py-1 rounded-full whitespace-nowrap">
                        net {formatCurrency(c.net_cost)}
                      </span>
                    )}
                    {savedCluster === c.date ? (
                      <span className="text-xs font-medium text-green-600 whitespace-nowrap">
                        ✓ Saved
                      </span>
                    ) : (
                      <button
                        onClick={() => saveCluster.mutate(c)}
                        disabled={saveCluster.isPending}
                        className="text-xs font-medium text-blue-600 hover:text-blue-700 whitespace-nowrap disabled:opacity-50"
                        title="Track this split as a case study"
                      >
                        Save as case study
                      </button>
                    )}
                  </div>
                </div>
                {c.source_debit && (
                  <div className="mt-3 pt-3 border-t border-gray-100 text-sm text-gray-700">
                    <span className="text-gray-500">Linked spend:</span>{" "}
                    <span className="font-medium text-gray-900">
                      {c.source_debit.merchant}
                    </span>{" "}
                    <span className="whitespace-nowrap">
                      {formatCurrency(c.source_debit.amount)} paid →{" "}
                      {formatCurrency(c.total_received)} back
                      {c.net_cost !== null && (
                        <> → net {formatCurrency(c.net_cost)}</>
                      )}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : contributionsLoaded ? (
        <p className="text-sm text-gray-400">No split expenses detected.</p>
      ) : null}

      {/* AI Insights */}
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <Sparkles className="w-6 h-6 text-blue-600" />
          <h2 className="text-lg font-bold text-gray-900">AI Insights</h2>
        </div>

        {aiLoading ? (
          <div className="flex items-center gap-3 text-gray-600">
            <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <span>Generating your financial narrative...</span>
          </div>
        ) : aiError || !ai ? (
          <p className="text-gray-600">
            AI insights are unavailable right now. Try again later.
          </p>
        ) : (
          <div>
            <p className="text-gray-800 leading-relaxed">{ai.summary}</p>
            {ai.highlights.length > 0 && (
              <ul className="mt-4 space-y-2">
                {ai.highlights.map((h, i) => (
                  <li key={i} className="flex items-start gap-2 text-gray-700">
                    <span className="text-blue-500 mt-1">•</span>
                    <span>{h}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-gray-400 mt-4">
              Generated {new Date(ai.generated_at).toLocaleString("en-IN")}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
