"use client";

import { useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import apiClient from "@/lib/api";
import type { Job, JobStatus, JobTransactionsResponse } from "@/types";

const PAGE_SIZE = 25;

const STATUS_STYLES: Record<JobStatus, string> = {
  queued: "bg-gray-100 text-gray-700",
  processing: "bg-blue-50 text-blue-700",
  done: "bg-green-50 text-green-700",
  failed: "bg-red-50 text-red-700",
};

function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={`inline-block text-xs font-medium px-2.5 py-1 rounded-full uppercase tracking-wide ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}

function formatTimestamp(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function inr(value: number | null | undefined): string {
  return Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [page, setPage] = useState(0);

  const { data: job, isLoading, isError } = useQuery<Job>({
    queryKey: ["job", id],
    queryFn: async () => {
      const response = await apiClient.get(`/api/jobs/${id}`);
      return response.data;
    },
    enabled: !!id,
    // Poll every 2s while the job is still running, then stop once terminal —
    // mirrors the upload page so we never hammer the endpoint forever.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "done" || status === "failed") return false;
      return 2000;
    },
  });

  const { data: txns, isLoading: txnsLoading } = useQuery<JobTransactionsResponse>({
    queryKey: ["job-transactions", id, { limit: PAGE_SIZE, offset: page * PAGE_SIZE }],
    queryFn: async () => {
      const response = await apiClient.get(`/api/jobs/${id}/transactions`, {
        params: { limit: PAGE_SIZE, offset: page * PAGE_SIZE },
      });
      return response.data;
    },
    enabled: !!id,
    placeholderData: keepPreviousData,
  });

  const stats = job?.stats;
  const total = txns?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const items = txns?.items ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Import Job</h1>
        <Link href="/jobs" className="text-blue-600 hover:text-blue-700 font-medium">
          ← Back to Jobs
        </Link>
      </div>

      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          Loading job...
        </div>
      ) : isError || !job ? (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          Failed to load this job.
        </div>
      ) : (
        <div className="space-y-6">
          {/* Status / summary panel */}
          <div className="bg-white rounded-lg shadow p-8">
            <div className="flex items-center gap-3 mb-2">
              <StatusBadge status={job.status} />
              {stats?.parser && (
                <span className="text-xs text-gray-500 uppercase tracking-wide">
                  {stats.parser}
                </span>
              )}
              {(job.status === "queued" || job.status === "processing") && (
                <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              )}
            </div>
            <p className="text-lg font-medium text-gray-900">
              {job.message || "Statement import"}
            </p>
            <p className="text-sm text-gray-500 mt-1">
              Created {formatTimestamp(job.created_at)}
              {job.finished_at && ` · Finished ${formatTimestamp(job.finished_at)}`}
              {stats?.duration_ms != null && ` · ${(stats.duration_ms / 1000).toFixed(1)}s`}
            </p>

            {stats && (
              <div className="mt-6 border-t pt-6">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                  {[
                    { label: "Parsed", value: stats.parsed },
                    { label: "Imported", value: stats.inserted },
                    { label: "Duplicates", value: stats.duplicates_skipped },
                    { label: "Failed", value: stats.failed },
                  ].map((m) => (
                    <div key={m.label} className="bg-gray-50 rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-gray-900">{m.value ?? 0}</p>
                      <p className="text-xs text-gray-500 uppercase tracking-wide">{m.label}</p>
                    </div>
                  ))}
                </div>

                {(stats.debit_count > 0 || stats.credit_count > 0) && (
                  <div className="flex flex-wrap gap-4 text-sm text-gray-600 mb-4">
                    <span>
                      💸 Paid: ₹{inr(stats.debit_total)} ({stats.debit_count})
                    </span>
                    <span>
                      💰 Received: ₹{inr(stats.credit_total)} ({stats.credit_count})
                    </span>
                  </div>
                )}

                {stats.categories && Object.keys(stats.categories).length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(stats.categories).map(([name, count]) => (
                      <span
                        key={name}
                        className="bg-blue-50 text-blue-700 text-xs px-2 py-1 rounded-full"
                      >
                        {name}: {count}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {(job.error || (stats?.errors && stats.errors.length > 0)) && (
              <details className="mt-4 text-sm">
                <summary className="cursor-pointer text-red-600">
                  {stats?.errors && stats.errors.length > 0
                    ? `${stats.errors.length} row error(s)`
                    : "Error details"}
                </summary>
                {job.error && <p className="mt-2 text-gray-600">{job.error}</p>}
                {stats?.errors && stats.errors.length > 0 && (
                  <ul className="mt-2 list-disc list-inside text-gray-500 space-y-1">
                    {stats.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                )}
              </details>
            )}
          </div>

          {/* Imported transactions */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">Imported Transactions</h2>
              <span className="text-sm text-gray-500">{total} total</span>
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
                  {txnsLoading && items.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                        Loading transactions...
                      </td>
                    </tr>
                  ) : items.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                        No transactions imported by this job.
                      </td>
                    </tr>
                  ) : (
                    items.map((tx) => {
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

            {totalPages > 1 && (
              <div className="bg-gray-50 px-6 py-4 flex items-center justify-between border-t">
                <p className="text-sm text-gray-600">
                  Page {page + 1} of {totalPages}
                </p>
                <div className="space-x-2">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-100"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-100"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
