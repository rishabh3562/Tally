"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import apiClient from "@/lib/api";
import type { Job, JobStatus } from "@/types";

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

export default function JobsPage() {
  const { data: jobs, isLoading, isError } = useQuery<Job[]>({
    queryKey: ["jobs"],
    queryFn: async () => {
      const response = await apiClient.get("/api/jobs");
      return response.data;
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Import Jobs</h1>
        <Link
          href="/upload"
          className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition"
        >
          + Upload Statement
        </Link>
      </div>

      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          Loading jobs...
        </div>
      ) : isError ? (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          Failed to load import jobs. Please try again.
        </div>
      ) : !jobs || jobs.length === 0 ? (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-8 text-center">
          <p className="text-gray-600 mb-4">
            No import jobs yet. Upload a bank statement to get started.
          </p>
          <Link
            href="/upload"
            className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition"
          >
            Upload Statement
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <Link
              key={job.job_id}
              href={`/jobs/${job.job_id}`}
              className="block bg-white rounded-lg shadow p-5 hover:shadow-md transition"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <StatusBadge status={job.status} />
                    {job.stats?.parser && (
                      <span className="text-xs text-gray-500 uppercase tracking-wide">
                        {job.stats.parser}
                      </span>
                    )}
                  </div>
                  <p className="font-medium text-gray-900 truncate">
                    {job.message || job.error || "Statement import"}
                  </p>
                  <p className="text-sm text-gray-500 mt-1">
                    Created {formatTimestamp(job.created_at)}
                    {job.finished_at && ` · Finished ${formatTimestamp(job.finished_at)}`}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2 justify-end shrink-0">
                  {[
                    { label: "Parsed", value: job.stats?.parsed },
                    { label: "Imported", value: job.stats?.inserted },
                    { label: "Duplicates", value: job.stats?.duplicates_skipped },
                    { label: "Failed", value: job.stats?.failed },
                  ].map((chip) => (
                    <div
                      key={chip.label}
                      className="bg-gray-50 rounded-lg px-3 py-1.5 text-center min-w-[70px]"
                    >
                      <p className="text-base font-bold text-gray-900 leading-tight">
                        {chip.value ?? "—"}
                      </p>
                      <p className="text-[10px] text-gray-500 uppercase tracking-wide">
                        {chip.label}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
