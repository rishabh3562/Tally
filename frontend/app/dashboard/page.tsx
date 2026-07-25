"use client";

import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import Link from "next/link";
import { TrendingDown, Wallet, DollarSign, Banknote, Plus, ArrowRight, ListChecks } from "lucide-react";
import { useCategories } from "@/hooks/useCategories";
import { formatINR } from "@/lib/format";
import type { TriageResponse } from "@/types";

const COLORS = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"];

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

  const { nameById, rootNameById } = useCategories();

  const { data: triageData } = useQuery({
    queryKey: ["triage"],
    queryFn: async () => {
      const res = await apiClient.get("/api/transactions/triage");
      return res.data as TriageResponse;
    },
  });

  const transactions = transactionsData?.data || [];
  const accounts = accountsData || [];
  const triageCount = triageData?.merchants ?? 0;

  // Calculate category totals. The list endpoint returns category_id (not a
  // name), so resolve it through the categories map — otherwise every row falls
  // into one bucket and the pie is meaningless. Sub-categories roll up to their
  // top-level parent (Food › Pizza counts under Food) so the pie stays legible.
  const categoryTotals = transactions.reduce((acc: Record<string, number>, tx: any) => {
    const category =
      rootNameById.get(tx.category_id) ||
      nameById.get(tx.category_id) ||
      "Uncategorized";
    acc[category] = (acc[category] || 0) + tx.amount;
    return acc;
  }, {});

  const categoryData = Object.entries(categoryTotals)
    .map(([name, value]) => ({ name, value: Number(value) }))
    .filter((c) => c.value > 0); // spend slices only (credits net to <= 0)

  // Calculate monthly totals
  const monthlyTotals: Record<string, number> = {};
  transactions.forEach((tx: any) => {
    const month = new Date(tx.date).toLocaleDateString("en-IN", {
      month: "short",
      year: "numeric",
    });
    monthlyTotals[month] = (monthlyTotals[month] || 0) + tx.amount;
  });

  const monthlyData = Object.entries(monthlyTotals)
    .sort((a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime())
    .map(([month, value]) => ({
      month,
      amount: Number(value),
    }));

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
      <h1 className="text-4xl font-bold text-gray-900">Dashboard</h1>
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

      {/* Uncategorized nudge — the core value loop */}
      {triageCount > 0 && (
        <Link
          href="/triage"
          className="flex items-center justify-between gap-4 bg-amber-50 border border-amber-200 rounded-lg p-4 hover:bg-amber-100 transition"
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
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {topCategory?.name || "—"}
              </p>
              {topCategory && (
                <p className="text-sm text-gray-500 mt-1">
                  {inr(topCategory.value)}
                </p>
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
            <h2 className="text-lg font-bold text-gray-900 mb-4">Spending by Category</h2>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={categoryData.slice(0, 6)}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) =>
                    `${name}: ${inr(value as number)}`
                  }
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {categoryData.slice(0, 6).map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {monthlyData.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Monthly Spending</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={monthlyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip
                  formatter={(value) =>
                    `${inr(value as number)}`
                  }
                />
                <Bar dataKey="amount" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
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
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-8 text-center">
          <p className="text-gray-600">No transactions yet. Upload a bank statement to get started.</p>
          <Link
            href="/upload"
            className="inline-block mt-4 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition"
          >
            Upload Statement
          </Link>
        </div>
      )}
    </div>
  );
}
