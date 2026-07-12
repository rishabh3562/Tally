"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import apiClient from "@/lib/api";
import type { GroupDetail } from "@/types";

function inr(value: number | null | undefined): string {
  return Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function KindBadge({ kind }: { kind: GroupDetail["kind"] }) {
  const styles =
    kind === "auto"
      ? "bg-indigo-50 text-indigo-700"
      : "bg-gray-100 text-gray-700";
  return (
    <span
      className={`inline-block text-xs font-medium px-2.5 py-1 rounded-full uppercase tracking-wide ${styles}`}
    >
      {kind}
    </span>
  );
}

export default function GroupDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: group, isLoading, isError } = useQuery<GroupDetail>({
    queryKey: ["group", id],
    queryFn: async () => {
      const res = await apiClient.get(`/api/groups/${id}`);
      return res.data;
    },
    enabled: !!id,
  });

  const transactions = group?.transactions ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Group</h1>
        <Link href="/groups" className="text-blue-600 hover:text-blue-700 font-medium">
          ← Back to Groups
        </Link>
      </div>

      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          Loading group...
        </div>
      ) : isError || !group ? (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          Failed to load this group.
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary panel */}
          <div className="bg-white rounded-lg shadow p-8">
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-2xl font-bold text-gray-900">{group.name}</h2>
              <KindBadge kind={group.kind} />
            </div>
            <div className="flex flex-wrap gap-8 mt-4">
              <div>
                <p className="text-3xl font-bold text-gray-900">
                  ₹{inr(group.total)}
                </p>
                <p className="text-xs text-gray-500 uppercase tracking-wide">
                  Total
                </p>
              </div>
              <div>
                <p className="text-3xl font-bold text-gray-900">{group.count}</p>
                <p className="text-xs text-gray-500 uppercase tracking-wide">
                  Transactions
                </p>
              </div>
            </div>
          </div>

          {/* Member transactions */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b">
              <h2 className="text-lg font-bold text-gray-900">Transactions</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Date</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Merchant</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">Category</th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">UPI Txn ID</th>
                    <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {transactions.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                        This group has no transactions.
                      </td>
                    </tr>
                  ) : (
                    transactions.map((tx) => {
                      const isCredit = tx.direction === "credit";
                      return (
                        <tr key={tx.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 text-sm text-gray-900 whitespace-nowrap">
                            {new Date(tx.date).toLocaleDateString("en-IN")}
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-900">
                            {tx.raw_merchant}
                            {tx.memo && (
                              <span className="block text-xs text-gray-400">{tx.memo}</span>
                            )}
                          </td>
                          <td className="px-6 py-4 text-sm">
                            {tx.category ? (
                              <span className="bg-blue-50 text-blue-700 text-xs px-2 py-1 rounded-full">
                                {tx.category}
                              </span>
                            ) : (
                              <span className="text-gray-400">—</span>
                            )}
                          </td>
                          <td className="px-6 py-4 text-xs text-gray-500 font-mono">
                            {tx.upi_transaction_id || "—"}
                          </td>
                          <td
                            className={`px-6 py-4 text-sm font-medium text-right whitespace-nowrap ${
                              isCredit ? "text-green-600" : "text-gray-900"
                            }`}
                          >
                            {isCredit ? "+" : "−"}₹{inr(tx.amount)}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
