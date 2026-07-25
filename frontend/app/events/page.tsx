"use client";

import { useQuery } from "@tanstack/react-query";
import { CardListSkeleton } from "@/components/common/Skeleton";
import apiClient from "@/lib/api";
import Link from "next/link";
import { BookMarked } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import type { Event } from "@/types";

export default function EventsPage() {
  const {
    data: events,
    isLoading,
    isError,
  } = useQuery<Event[]>({
    queryKey: ["events"],
    queryFn: async () => {
      const res = await apiClient.get("/api/events");
      return res.data;
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Case Studies</h1>
        <Link
          href="/dashboard"
          className="text-blue-600 hover:text-blue-700 font-medium"
        >
          ← Back to Dashboard
        </Link>
      </div>

      {isLoading ? (
        <CardListSkeleton />
      ) : isError ? (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          Failed to load case studies. Please try again.
        </div>
      ) : !events || events.length === 0 ? (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-8 text-center">
          <BookMarked className="w-8 h-8 text-blue-500 mx-auto mb-3" />
          <p className="text-gray-600 mb-1">No case studies yet.</p>
          <p className="text-gray-500 text-sm mb-4">
            Select transactions on the Transactions page and “Save as Event” to
            group a big life event together.
          </p>
          <Link
            href="/transactions"
            className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition"
          >
            Go to Transactions
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {events.map((event) => (
            <Link
              key={event.id}
              href={`/events/${event.id}`}
              className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition flex flex-col"
            >
              <div className="flex items-start justify-between gap-3 mb-2">
                <h2 className="text-lg font-bold text-gray-900 min-w-0 break-words">
                  {event.name}
                </h2>
                <BookMarked className="w-5 h-5 text-gray-400 shrink-0" />
              </div>
              {event.description && (
                <p className="text-sm text-gray-600 mb-3">{event.description}</p>
              )}
              <p className="text-2xl font-bold text-gray-900 mb-2">
                {formatCurrency(event.total_amount ?? 0)}
              </p>
              {event.summary && (
                <p className="text-sm text-gray-500 line-clamp-3">
                  {event.summary}
                </p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
