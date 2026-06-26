"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import Link from "next/link";
import { Calendar, DollarSign } from "lucide-react";

export default function EventsPage() {
  const { data: events } = useQuery({
    queryKey: ["events"],
    queryFn: async () => {
      const response = await apiClient.get("/api/events");
      return response.data;
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Events</h1>
        <Link
          href="/dashboard"
          className="text-blue-600 hover:text-blue-700 font-medium"
        >
          ← Back to Dashboard
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {events && events.length > 0 ? (
          events.map((event: any) => (
            <div key={event.id} className="bg-white rounded-lg shadow p-6 hover:shadow-lg transition">
              <div className="flex items-start justify-between mb-4">
                <h2 className="text-lg font-bold text-gray-900">{event.name}</h2>
                <Calendar className="w-5 h-5 text-gray-400" />
              </div>
              {event.summary && (
                <p className="text-sm text-gray-600 mb-4">{event.summary}</p>
              )}
              <div className="flex items-center space-x-2 text-blue-600 font-semibold">
                <DollarSign className="w-4 h-4" />
                <span>View Details</span>
              </div>
            </div>
          ))
        ) : (
          <div className="col-span-full bg-blue-50 border border-blue-200 rounded-lg p-8 text-center">
            <p className="text-gray-600">No events yet. Create one from your transactions!</p>
            <Link
              href="/transactions"
              className="inline-block mt-4 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition"
            >
              Go to Transactions
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
