"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Sparkles, Trash2 } from "lucide-react";
import apiClient from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { EventDetail } from "@/types";

export default function EventDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const {
    data: event,
    isLoading,
    isError,
  } = useQuery<EventDetail>({
    queryKey: ["event", id],
    queryFn: async () => {
      const res = await apiClient.get(`/api/events/${id}`);
      return res.data;
    },
    enabled: !!id,
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.delete(`/api/events/${id}`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      router.replace("/events");
    },
    onError: (err: any) => {
      if (err?.response?.status === 401) return;
      setDeleteError("Could not delete this case study. Please try again.");
    },
  });

  const transactions = event?.transactions ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Case Study</h1>
        <Link
          href="/events"
          className="text-blue-600 hover:text-blue-700 font-medium"
        >
          ← Back to Case Studies
        </Link>
      </div>

      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          Loading case study...
        </div>
      ) : isError || !event ? (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          Failed to load this case study.
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary panel */}
          <div className="bg-white rounded-lg shadow p-8">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h2 className="text-2xl font-bold text-gray-900 break-words">
                  {event.name}
                </h2>
                {event.description && (
                  <p className="text-gray-600 mt-2">{event.description}</p>
                )}
              </div>
              <div className="shrink-0">
                {confirmingDelete ? (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => deleteMutation.mutate()}
                      disabled={deleteMutation.isPending}
                      className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
                    >
                      {deleteMutation.isPending ? "Deleting…" : "Confirm delete"}
                    </button>
                    <button
                      onClick={() => setConfirmingDelete(false)}
                      disabled={deleteMutation.isPending}
                      className="px-3 py-1.5 text-gray-700 hover:bg-gray-100 text-sm font-medium rounded-lg disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmingDelete(true)}
                    className="inline-flex items-center gap-1.5 text-sm font-medium text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete
                  </button>
                )}
              </div>
            </div>

            {deleteError && (
              <p className="mt-3 text-sm text-red-600">{deleteError}</p>
            )}

            <div className="flex flex-wrap gap-8 mt-6">
              <div>
                <p className="text-3xl font-bold text-gray-900">
                  {formatCurrency(event.total_amount ?? 0)}
                </p>
                <p className="text-xs text-gray-500 uppercase tracking-wide">
                  Total
                </p>
              </div>
              <div>
                <p className="text-3xl font-bold text-gray-900">
                  {transactions.length}
                </p>
                <p className="text-xs text-gray-500 uppercase tracking-wide">
                  Transactions
                </p>
              </div>
            </div>

            {event.summary && (
              <div className="mt-6 rounded-lg border border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-5 h-5 text-blue-600" />
                  <h3 className="text-sm font-bold text-gray-900">AI Summary</h3>
                </div>
                <p className="text-gray-800 leading-relaxed">{event.summary}</p>
              </div>
            )}
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
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">
                      Date
                    </th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">
                      Merchant
                    </th>
                    <th className="px-6 py-3 text-left text-sm font-medium text-gray-700">
                      Category
                    </th>
                    <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">
                      Amount
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {transactions.length === 0 ? (
                    <tr>
                      <td
                        colSpan={4}
                        className="px-6 py-8 text-center text-gray-500"
                      >
                        This case study has no transactions.
                      </td>
                    </tr>
                  ) : (
                    transactions.map((tx) => (
                      <tr key={tx.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-sm text-gray-900 whitespace-nowrap">
                          {formatDate(tx.date)}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900">
                          {tx.raw_merchant}
                          {tx.memo && (
                            <span className="block text-xs text-gray-400">
                              {tx.memo}
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          {tx.categories?.name ? (
                            <span className="bg-blue-50 text-blue-700 text-xs px-2 py-1 rounded-full">
                              {tx.categories.name}
                            </span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm font-medium text-gray-900 text-right whitespace-nowrap">
                          {formatCurrency(tx.amount)}
                        </td>
                      </tr>
                    ))
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
