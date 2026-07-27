"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ChevronRight, Wrench, Zap } from "lucide-react";
import apiClient from "@/lib/api";
import type { ChatTrace } from "@/types";

function SourceBadge({ source }: { source: ChatTrace["source"] }) {
  const map: Record<ChatTrace["source"], string> = {
    agent: "bg-indigo-50 text-indigo-700",
    deterministic: "bg-gray-100 text-gray-600",
    "error-fallback": "bg-red-50 text-red-700",
  };
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide ${map[source]}`}>
      {source}
    </span>
  );
}

function TraceCard({ t }: { t: ChatTrace }) {
  const [open, setOpen] = useState(false);
  const steps = t.steps ?? [];
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-gray-900">{t.question}</p>
          <p className="text-sm text-gray-600 mt-1">{t.answer}</p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <SourceBadge source={t.source} />
          {t.action_taken && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 uppercase tracking-wide">
              <Zap className="w-3 h-3" /> action
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
        <span>{new Date(t.created_at).toLocaleString("en-IN")}</span>
        {t.duration_ms != null && <span>{t.duration_ms} ms</span>}
        <span className="inline-flex items-center gap-1">
          <Wrench className="w-3 h-3" />
          {steps.length} tool call{steps.length === 1 ? "" : "s"}
        </span>
        {(steps.length > 0 || t.error) && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700"
          >
            <ChevronRight className={`w-3.5 h-3.5 transition ${open ? "rotate-90" : ""}`} />
            {open ? "hide" : "why?"}
          </button>
        )}
      </div>

      {t.source !== "agent" && (
        <p className="mt-2 text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-2 py-1.5">
          Answered <strong>without AI</strong> (deterministic engine)
          {t.error ? ` — ${t.error}` : ""}.
        </p>
      )}

      {open && steps.length > 0 && (
        <div className="mt-3 space-y-2 border-t border-gray-100 pt-3">
          {steps.map((s, i) => (
            <div key={i} className="text-xs">
              <p className="font-mono font-semibold text-gray-800">
                {s.tool}({JSON.stringify(s.args)})
              </p>
              <pre className="mt-1 bg-gray-50 rounded-lg p-2 overflow-x-auto text-gray-700">
                {JSON.stringify(s.result, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ChatTracesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["chat-traces"],
    queryFn: async () => {
      const res = await apiClient.get("/api/chat/traces");
      return (res.data?.data ?? []) as ChatTrace[];
    },
  });

  const traces = data ?? [];
  // If the most recent turn didn't use the AI agent, the chat is almost certainly
  // running keyless — the single most useful thing to surface.
  const runningWithoutAi = traces.length > 0 && traces[0].source !== "agent";

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 md:text-4xl">Chat traces</h1>
          <p className="text-gray-500 mt-1">
            Exactly what the assistant did for each question — the tools it called,
            the real data it got, and how the answer was produced.
          </p>
        </div>
        <Link href="/chat" className="text-blue-600 hover:text-blue-700 font-medium">
          ← Chat
        </Link>
      </div>

      {runningWithoutAi && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4 text-sm text-amber-800">
          <strong>Chat is answering without AI.</strong> The most recent turn fell back
          to the deterministic engine
          {traces[0].error ? ` (${traces[0].error})` : ""} — set{" "}
          <code className="font-mono bg-amber-100 px-1 rounded">GEMINI_API_KEYS</code> in
          the backend to enable the smart agent, then ask again.
        </div>
      )}

      {isLoading ? (
        <p className="text-gray-500">Loading…</p>
      ) : error ? (
        <p className="text-red-600">Failed to load traces.</p>
      ) : traces.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-10 text-center">
          <p className="text-gray-500">
            No chat turns yet. Ask something in the chat, then come back here to see
            exactly how it answered.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {traces.map((t) => (
            <TraceCard key={t.id} t={t} />
          ))}
        </div>
      )}
    </div>
  );
}
