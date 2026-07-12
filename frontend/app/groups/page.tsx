"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Sparkles, Layers } from "lucide-react";
import apiClient from "@/lib/api";
import type { AutoClubResponse, Group } from "@/types";

function inr(value: number | null | undefined): string {
  return Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function KindBadge({ kind }: { kind: Group["kind"] }) {
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

export default function GroupsPage() {
  const queryClient = useQueryClient();
  const [banner, setBanner] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: groups,
    isLoading,
    isError,
  } = useQuery<Group[]>({
    queryKey: ["groups"],
    queryFn: async () => {
      const res = await apiClient.get("/api/groups");
      return res.data;
    },
  });

  useEffect(() => {
    if (!banner) return;
    const t = setTimeout(() => setBanner(null), 6000);
    return () => clearTimeout(t);
  }, [banner]);

  const autoClubMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<AutoClubResponse>("/api/groups/auto");
      return res.data;
    },
    onSuccess: (data) => {
      setActionError(null);
      setBanner(data.message);
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
    onError: (err: any) => {
      if (err?.response?.status === 401) return;
      setActionError("Auto-club failed. Please try again.");
    },
  });

  const ungroupMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await apiClient.delete(`/api/groups/${id}`);
      return res.data;
    },
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
    onError: (err: any) => {
      if (err?.response?.status === 401) return;
      setActionError("Could not ungroup. Please try again.");
    },
  });

  const handleUngroup = (id: string, name: string) => {
    if (
      !window.confirm(
        `Ungroup and delete “${name}”? The transactions will be released back to the list.`
      )
    )
      return;
    ungroupMutation.mutate(id);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Groups</h1>
        <button
          onClick={() => autoClubMutation.mutate()}
          disabled={autoClubMutation.isPending}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition disabled:opacity-60"
        >
          {autoClubMutation.isPending ? (
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          {autoClubMutation.isPending ? "Auto-clubbing…" : "Auto-club"}
        </button>
      </div>

      {banner && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-lg mb-4">
          {banner}
        </div>
      )}

      {actionError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
          {actionError}
        </div>
      )}

      {isLoading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          Loading groups...
        </div>
      ) : isError ? (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          Failed to load groups. Please try again.
        </div>
      ) : !groups || groups.length === 0 ? (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-8 text-center">
          <Layers className="w-8 h-8 text-blue-500 mx-auto mb-3" />
          <p className="text-gray-600 mb-1">No groups yet.</p>
          <p className="text-gray-500 text-sm">
            Select transactions to club them, or let AI group them automatically.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {groups.map((group) => (
            <div
              key={group.id}
              className="bg-white rounded-lg shadow p-5 hover:shadow-md transition flex items-center justify-between gap-4"
            >
              <Link href={`/groups/${group.id}`} className="min-w-0 flex-1">
                <div className="flex items-center gap-3 mb-1">
                  <span className="font-medium text-gray-900 truncate">
                    {group.name}
                  </span>
                  <KindBadge kind={group.kind} />
                </div>
                <p className="text-sm text-gray-500">
                  {group.count} transaction{group.count === 1 ? "" : "s"} · ₹
                  {inr(group.total)}
                </p>
              </Link>
              <button
                onClick={() => handleUngroup(group.id, group.name)}
                disabled={
                  ungroupMutation.isPending &&
                  ungroupMutation.variables === group.id
                }
                className="shrink-0 text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50"
              >
                {ungroupMutation.isPending &&
                ungroupMutation.variables === group.id
                  ? "Ungrouping…"
                  : "Ungroup"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
