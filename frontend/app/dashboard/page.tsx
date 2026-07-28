"use client";

import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer } from "recharts";
import Link from "next/link";
import { TrendingDown, Wallet, DollarSign, Banknote, Plus, ArrowRight, ListChecks } from "lucide-react";
import { useCategories } from "@/hooks/useCategories";
import CategoryDonut from "@/components/dashboard/CategoryDonut";
import { formatINR, formatINRCompact } from "@/lib/format";
import type { TriageResponse, MoversResponse, RecurringResponse } from "@/types";

// Skeleton shown while the (large, limit:1000) transactions query is in flight.
// Without it the page briefly renders its "No transactions yet" empty state to a
// user who has hundreds of transactions — the UI lying, then snapping to reality.
function DashboardSkeleton() {
  return (
    <div className="space-y-8 animate-pulse" aria-hidden="true">
      <div className="h-40 rounded-2xl bg-gray-100" />
      <div className="h-28 rounded-lg bg-gray-100" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-32 rounded-lg bg-gray-100" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-80 rounded-lg bg-gray-100" />
        <div className="h-80 rounded-lg bg-gray-100" />
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: transactionsData, isPending: txPending, isError: txError, refetch } = useQuery({
    queryKey: ["transactions", { limit: 1000 }],
    queryFn: async () => {
      const response = await apiClient.get("/api/transactions", { params: { limit: 1000 } });
      return response.data;
    },
  });

  const { data: accountsData, isPending: acctPending } = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => {
      const response = await apiClient.get("/api/accounts");
      return response.data || [];
    },
  });

  const { nameById, rootNameById, iconByName } = useCategories();

  const { data: triageData } = useQuery({
    queryKey: ["triage"],
    queryFn: async () => {
      const res = await apiClient.get("/api/transactions/triage");
      return res.data as TriageResponse;
    },
  });

  // At-a-glance insights, surfaced on the landing page (reuse the tested
  // endpoints). Best-effort — the strip just hides if these don't load.
  const { data: moversData } = useQuery<MoversResponse>({
    queryKey: ["movers"],
    queryFn: async () => (await apiClient.get("/api/insights/movers")).data,
    staleTime: 5 * 60_000,
  });
  const { data: recurringData } = useQuery<RecurringResponse>({
    queryKey: ["recurring"],
    queryFn: async () => (await apiClient.get("/api/insights/recurring")).data,
    staleTime: 5 * 60_000,
  });
  const topMover = (moversData?.movers ?? []).find((m) => m.delta > 0) ?? null;

  const transactions = transactionsData?.data || [];
  const accounts = accountsData || [];
  const triageCount = triageData?.merchants ?? 0;

  // Calculate category totals. The list endpoint returns category_id (not a
  // name), so resolve it through the categories map — otherwise every row falls
  // into one bucket and the pie is meaningless. Sub-categories roll up to their
  // top-level parent (Food › Pizza counts under Food) so the pie stays legible.
  //
  // Spend rows only, matching `totalSpent` below. Netting credits in here made
  // the breakdown disagree with the headline: a ₹500 payment with a ₹100 refund
  // counted as 400 in the donut and 500 in "You spent", and any category that
  // happened to net negative vanished from the chart entirely.
  const categoryTotals = transactions
    .filter((tx: any) => tx.amount > 0)
    .reduce((acc: Record<string, number>, tx: any) => {
      const category =
        rootNameById.get(tx.category_id) ||
        nameById.get(tx.category_id) ||
        "Uncategorized";
      acc[category] = (acc[category] || 0) + tx.amount;
      return acc;
    }, {});

  const categoryData = Object.entries(categoryTotals)
    .map(([name, value]) => ({ name, value: Number(value) }));

  // Monthly totals, spend and money-in kept apart. Summing raw amounts nets a
  // refund against the spending it reverses, so a month with a big return used to
  // draw a short bar and quietly under-report what was actually paid out.
  const monthlyTotals: Record<string, { spent: number; received: number }> = {};
  transactions.forEach((tx: any) => {
    const month = new Date(tx.date).toLocaleDateString("en-IN", {
      month: "short",
      year: "numeric",
    });
    const bucket = (monthlyTotals[month] ||= { spent: 0, received: 0 });
    if (tx.amount > 0) bucket.spent += tx.amount;
    else bucket.received += -tx.amount;
  });

  const monthlyData = Object.entries(monthlyTotals)
    .sort((a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime())
    .map(([month, v]) => ({
      month,
      spent: Number(v.spent),
      received: Number(v.received),
    }));
  const anyMoneyIn = monthlyData.some((m) => m.received > 0);
  const avgMonthlySpend =
    monthlyData.length > 0
      ? monthlyData.reduce((s, m) => s + m.spent, 0) / monthlyData.length
      : 0;

  // Spend and received are opposite signs; report them separately (summing all
  // amounts together nets them and mislabels the result as "spent").
  const totalSpent = transactions.reduce(
    (sum: number, tx: any) => sum + (tx.amount > 0 ? tx.amount : 0),
    0
  );
  const totalReceived = transactions.reduce(
    (sum: number, tx: any) => sum + (tx.amount < 0 ? -tx.amount : 0),
    0
  );
  const spendCount = transactions.filter((tx: any) => tx.amount > 0).length;
  const topCategory =
    categoryData.length > 0
      ? categoryData.reduce((a, b) => (a.value > b.value ? a : b))
      : null;
  const topShare =
    topCategory && totalSpent > 0
      ? Math.round((topCategory.value / totalSpent) * 100)
      : 0;
  const topIsUncategorized = topCategory?.name === "Uncategorized";

  const inr = formatINR;

  const DashboardHeader = () => (
    <div className="flex items-center justify-between">
      <h1 className="text-2xl font-bold text-gray-900 md:text-4xl">Dashboard</h1>
      <Link
        href="/upload"
        className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition"
      >
        + Upload Statement
      </Link>
    </div>
  );

  // A failed fetch must not masquerade as "you have nothing" — say what happened
  // and give a way out.
  if (txError) {
    return (
      <div className="space-y-8">
        <DashboardHeader />
        <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center">
          <p className="text-gray-900 font-medium">Couldn&apos;t load your dashboard.</p>
          <p className="text-sm text-gray-600 mt-1">
            The server didn&apos;t respond. Check that the backend is running, then try again.
          </p>
          <button
            onClick={() => refetch()}
            className="mt-4 inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Show the chrome immediately, skeleton the data — never the "you have nothing"
  // empty state while the real data is still loading.
  if (txPending) {
    return (
      <div className="space-y-8">
        <DashboardHeader />
        <DashboardSkeleton />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <DashboardHeader />

      {/* Money story — answers "where did my money go" in one line */}
      {transactions.length > 0 && (
        <section className="rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 text-white p-8 shadow-sm">
          <p className="text-blue-100 text-sm font-medium uppercase tracking-wide mb-2">
            Where your money went
          </p>
          <p className="text-3xl md:text-4xl font-bold leading-tight">
            You spent{" "}
            <span className="tabular-nums">{inr(totalSpent)}</span>{" "}
            <span className="text-blue-200 font-semibold text-2xl md:text-3xl">
              across {spendCount} payment{spendCount === 1 ? "" : "s"}
            </span>
            .
          </p>
          {topCategory && !topIsUncategorized && (
            <p className="mt-3 text-lg text-blue-50">
              Your biggest slice was{" "}
              <span className="font-semibold text-white">{topCategory.name}</span>{" "}
              at {inr(topCategory.value)}
              {topShare > 0 ? ` — ${topShare}% of everything` : ""}.
            </p>
          )}
          {topIsUncategorized && (
            <Link
              href="/triage"
              className="mt-4 inline-flex items-center gap-2 bg-white/15 hover:bg-white/25 backdrop-blur px-4 py-2 rounded-lg font-medium transition"
            >
              {inr(topCategory!.value)} is still uncategorized — label it to see the real story
              <ArrowRight className="w-4 h-4" />
            </Link>
          )}
          {totalReceived > 0 && (
            <p className="mt-3 text-sm text-blue-200">
              {inr(totalReceived)} came back in (refunds, transfers, repayments).
            </p>
          )}
        </section>
      )}

      {/* This month at a glance — surfaces the insights that otherwise live only
          on the Insights page, on the landing screen. */}
      {(topMover || (recurringData?.count ?? 0) > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {topMover && (
            <Link
              href="/insights"
              className="flex items-center gap-3 bg-white rounded-lg shadow-sm border border-gray-100 p-4 hover:shadow-md transition"
            >
              <TrendingDown className="w-8 h-8 text-red-500 shrink-0" />
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide">Biggest jump this month</p>
                <p className="font-semibold text-gray-900">
                  {topMover.category} <span className="text-red-600">+{inr(topMover.delta)}</span>
                </p>
              </div>
            </Link>
          )}
          {(recurringData?.count ?? 0) > 0 && (
            <Link
              href="/insights"
              className="flex items-center gap-3 bg-white rounded-lg shadow-sm border border-gray-100 p-4 hover:shadow-md transition"
            >
              <Banknote className="w-8 h-8 text-indigo-500 shrink-0" />
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide">Recurring / subscriptions</p>
                <p className="font-semibold text-gray-900">
                  {inr(recurringData!.monthly_total)}/mo{" "}
                  <span className="text-gray-500 font-normal">
                    across {recurringData!.count}
                  </span>
                </p>
              </div>
            </Link>
          )}
        </div>
      )}

      {/* Uncategorized nudge — the core value loop */}
      {triageCount > 0 && (
        <Link
          href="/triage"
          className="flex items-center justify-between gap-4 bg-amber-50 border border-amber-200 rounded-lg p-4 hover:bg-amber-100 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
        >
          <div className="flex items-center gap-3">
            <ListChecks className="w-6 h-6 text-amber-600 shrink-0" />
            <div>
              <p className="font-semibold text-gray-900">
                {triageCount} merchant{triageCount === 1 ? "" : "s"} still uncategorized
              </p>
              <p className="text-sm text-gray-600">
                Your breakdown isn&apos;t accurate until these are labelled — takes a couple of minutes.
              </p>
            </div>
          </div>
          <span className="text-amber-700 font-medium flex items-center gap-1 shrink-0">
            Categorize <ArrowRight className="w-4 h-4" />
          </span>
        </Link>
      )}

      {/* Accounts Overview */}
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Banknote className="w-6 h-6 text-blue-600" />
            <h2 className="text-lg font-bold text-gray-900">My Accounts</h2>
          </div>
          <Link href="/accounts" className="text-blue-600 hover:text-blue-700 text-sm font-medium flex items-center gap-1">
            Manage <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {acctPending ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 animate-pulse">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-20 rounded-lg bg-white/60" />
            ))}
          </div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-4">
            <p className="text-gray-600 mb-4">No accounts yet. Create one to get started!</p>
            <Link
              href="/accounts"
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition"
            >
              <Plus className="w-4 h-4" />
              Add Account
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {accounts.map((account) => (
              <div key={account.id} className="bg-white rounded-lg p-4 shadow-sm hover:shadow-md transition">
                <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Account</p>
                <p className="font-semibold text-gray-900">{account.name}</p>
                <p className="text-xs text-gray-600 mt-2">{account.type}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm font-medium">Total Spent</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {inr(totalSpent)}
              </p>
            </div>
            <DollarSign className="w-12 h-12 text-blue-500 opacity-20" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm font-medium">Transactions</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">{transactions.length}</p>
            </div>
            <Wallet className="w-12 h-12 text-green-500 opacity-20" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm font-medium">Top Category</p>
              {/* Drills into the transactions behind the figure. */}
              {topCategory ? (
                <Link
                  href={{
                    pathname: "/transactions",
                    query: { category: topCategory.name },
                  }}
                  className="group"
                >
                  <p className="mt-2 text-3xl font-bold text-gray-900 group-hover:text-blue-700">
                    {iconByName.get(topCategory.name)
                      ? `${iconByName.get(topCategory.name)} `
                      : ""}
                    {topCategory.name}
                  </p>
                  <p className="mt-1 text-sm text-gray-500">
                    {inr(topCategory.value)}
                  </p>
                </Link>
              ) : (
                <p className="mt-2 text-3xl font-bold text-gray-900">—</p>
              )}
            </div>
            <TrendingDown className="w-12 h-12 text-red-500 opacity-20" />
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {categoryData.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <div className="mb-4 flex items-baseline justify-between gap-3">
              <h2 className="text-lg font-bold text-gray-900">Spending by Category</h2>
              <Link
                href="/transactions"
                className="shrink-0 text-sm font-medium text-blue-600 hover:text-blue-700"
              >
                All →
              </Link>
            </div>
            <CategoryDonut data={categoryData} iconByName={iconByName} />
          </div>
        )}

        {monthlyData.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <div className="mb-4 flex items-baseline justify-between gap-3">
              <h2 className="text-lg font-bold text-gray-900">
                {anyMoneyIn ? "Monthly Spend vs Money In" : "Monthly Spending"}
              </h2>
              {avgMonthlySpend > 0 && monthlyData.length > 1 && (
                <p className="shrink-0 text-sm text-gray-500">
                  avg <span className="font-semibold text-gray-700">{inr(avgMonthlySpend)}</span>/mo
                </p>
              )}
            </div>
            <div className="h-[220px] w-full lg:h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthlyData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
                  <XAxis
                    dataKey="month"
                    tick={{ fontSize: 12, fill: "#6b7280" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e5e7eb" }}
                    interval="preserveStartEnd"
                    minTickGap={8}
                  />
                  {/* Compact ticks: a full "₹12,00,000" label is wider than the
                      bar it belongs to once the chart is phone-width. */}
                  <YAxis
                    tick={{ fontSize: 12, fill: "#6b7280" }}
                    tickLine={false}
                    axisLine={false}
                    width={52}
                    tickFormatter={(v) => formatINRCompact(v as number)}
                  />
                  <Tooltip
                    cursor={{ fill: "#f3f4f6" }}
                    contentStyle={{
                      borderRadius: 8,
                      border: "1px solid #e5e7eb",
                      fontSize: 13,
                      color: "#111827",
                    }}
                    labelStyle={{ color: "#111827", fontWeight: 600 }}
                    formatter={(value, name) => [
                      inr(value as number),
                      name === "spent" ? "Spent" : "Money in",
                    ]}
                  />
                  {anyMoneyIn && (
                    <Legend
                      iconType="circle"
                      iconSize={8}
                      formatter={(value) => (
                        <span className="text-xs text-gray-600">
                          {value === "spent" ? "Spent" : "Money in"}
                        </span>
                      )}
                    />
                  )}
                  {/* What a typical month costs, so a spike reads as a spike. */}
                  {avgMonthlySpend > 0 && monthlyData.length > 1 && (
                    <ReferenceLine
                      y={avgMonthlySpend}
                      stroke="#9ca3af"
                      strokeDasharray="4 4"
                    />
                  )}
                  <Bar dataKey="spent" fill="#3b82f6" radius={[4, 4, 0, 0]} maxBarSize={48} />
                  {anyMoneyIn && (
                    <Bar dataKey="received" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={48} />
                  )}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* Recent Transactions */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-gray-900">Recent Transactions</h2>
          <Link href="/transactions" className="text-blue-600 hover:text-blue-700 text-sm font-medium">
            View All →
          </Link>
        </div>
        <div className="space-y-2 divide-y">
          {transactions.slice(0, 5).map((tx: any) => (
            <div key={tx.id} className="py-3 flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">{tx.raw_merchant}</p>
                <p className="text-sm text-gray-500">
                  {new Date(tx.date).toLocaleDateString("en-IN")}
                </p>
              </div>
              <p className="font-semibold text-gray-900">
                {inr(tx.amount)}
              </p>
            </div>
          ))}
        </div>
      </div>

      {transactions.length === 0 && (
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-10 text-center">
          <div className="w-14 h-14 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-5">
            <Banknote className="w-7 h-7 text-blue-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Welcome to Tally</h2>
          <p className="text-gray-600 mt-2 max-w-md mx-auto">
            Upload a bank or UPI statement and Tally parses it automatically to show you exactly where your money goes.
          </p>
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 mt-6 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition"
          >
            <Plus className="w-4 h-4" />
            Upload Statement
          </Link>
        </div>
      )}
    </div>
  );
}
