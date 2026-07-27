"use client";

import { ChevronRight, Wrench, Zap } from "lucide-react";
import type { ChatTrace, ChatTraceStep } from "@/types";

const SOURCE_STYLES: Record<ChatTrace["source"], string> = {
  agent: "bg-indigo-50 text-indigo-700",
  instant: "bg-emerald-50 text-emerald-700",
  deterministic: "bg-gray-100 text-gray-600",
  "error-fallback": "bg-red-50 text-red-700",
  failed: "bg-red-100 text-red-800",
};

export function SourceBadge({ source }: { source: ChatTrace["source"] }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
        SOURCE_STYLES[source] ?? "bg-gray-100 text-gray-600"
      }`}
    >
      {source}
    </span>
  );
}

export function ActionBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
      <Zap className="h-3 w-3" /> action
    </span>
  );
}

/** Toggle for a provenance panel — "why?" / "hide". */
export function WhyToggle({
  open,
  onToggle,
  label = "why?",
}: {
  open: boolean;
  onToggle: () => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700"
    >
      <ChevronRight
        className={`h-3.5 w-3.5 transition ${open ? "rotate-90" : ""}`}
      />
      {open ? "hide" : label}
    </button>
  );
}

export function ToolCallCount({ steps }: { steps: ChatTraceStep[] }) {
  return (
    <span className="inline-flex items-center gap-1">
      <Wrench className="h-3 w-3" />
      {steps.length} tool call{steps.length === 1 ? "" : "s"}
    </span>
  );
}

/** The tool calls behind an answer: what ran, with what arguments, and the exact
 *  data it returned. Shared by the /chat/traces page and the inline "why?" panel
 *  under a chat answer, so provenance looks the same wherever it's shown. */
export function TraceSteps({ steps }: { steps: ChatTraceStep[] }) {
  if (steps.length === 0) return null;
  return (
    <div className="mt-3 space-y-2 border-t border-gray-100 pt-3">
      {steps.map((s, i) => (
        <div key={i} className="text-xs">
          <p className="break-all font-mono font-semibold text-gray-800">
            {s.tool}({JSON.stringify(s.args)})
          </p>
          <pre className="mt-1 overflow-x-auto rounded-lg bg-gray-50 p-2 text-gray-700">
            {JSON.stringify(s.result, null, 2)}
          </pre>
        </div>
      ))}
    </div>
  );
}

/** One-line explanation of HOW the answer was produced, in plain words. */
export function SourceNote({ trace }: { trace: ChatTrace }) {
  if (trace.source === "agent") return null;

  // "instant" is a deliberate shortcut, not a degraded answer — this question has
  // a dedicated handler that's faster and more precise than asking the model. Say
  // so in green; the amber note below is for when the model was actually missing.
  if (trace.source === "instant") {
    return (
      <p className="mt-2 rounded-lg border border-emerald-100 bg-emerald-50 px-2 py-1.5 text-xs text-emerald-800">
        Answered straight from your data — no AI needed for this one
        {trace.duration_ms != null ? ` (${trace.duration_ms} ms)` : ""}.
      </p>
    );
  }

  const text =
    trace.source === "failed"
      ? "This question could not be answered at all"
      : "Answered without AI (deterministic engine)";
  return (
    <p className="mt-2 rounded-lg border border-amber-100 bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
      {text}
      {trace.error ? ` — ${trace.error}` : ""}.
    </p>
  );
}
