"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import Link from "next/link";
import { TrendingDown, Wallet, DollarSign } from "lucide-react";

const COLORS = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"];

export default function DashboardPage() {
  const { data: transactionsData } = useQuery({
    queryKey: ["transactions", { limit: 1000 }],
    queryFn: async () => {
      const response = await apiClient.get("/api/transactions", { params: { limit: 1000 } });
      return response.data;
    },
  });

  const transactions = transactionsData?.data || [];

  // Calculate category totals
  const categoryTotals = transactions.reduce((acc: Record<string, number>, tx: any) => {
    const category = tx.category || "Other";
    acc[category] = (acc[category] || 0) + tx.amount;
    return acc;
  }, {});

  const categoryData = Object.entries(categoryTotals).map(([name, value]) => ({
    name,
    value: Number(value),
  }));

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

  const totalSpent = transactions.reduce((sum: number, tx: any) => sum + tx.amount, 0);
  const averageTransaction = transactions.length > 0 ? totalSpent / transactions.length : 0;
  const topCategory = categoryData.length > 0 ? categoryData.reduce((a, b) => (a.value > b.value ? a : b)) : null;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-4xl font-bold text-gray-900">Dashboard</h1>
        <Link
          href="/upload"
          className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition"
        >
          + Upload Statement
        </Link>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm font-medium">Total Spent</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                ₹{totalSpent.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
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
                  ₹{topCategory.value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
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
                    `${name}: ₹${(value as number).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
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
                    `₹${(value as number).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
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
                ₹{tx.amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
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
