"use client";

import { useChat } from "@/hooks/useChat";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Send, Search, Wand2, ArrowUpRight } from "lucide-react";
import { drillLinksFromTrace } from "@/lib/traceLinks";
import Markdown from "@/components/chat/Markdown";
import {
  ActionBadge,
  SourceBadge,
  SourceNote,
  ToolCallCount,
  TraceSteps,
  WhyToggle,
} from "@/components/chat/TraceDetail";
import type { ChatTrace } from "@/types";

// Two capabilities, shown distinctly: the assistant both ANSWERS questions and
// PERFORMS changes on your data — the "tell it and it does it" (Palantir) idea.
const ASK_PROMPTS = [
  "How much did I spend on food last month?",
  "What do I buy most often?",
  "What jumped this month?",
  "What's my average monthly spend?",
  "Which merchants did I spend the most at?",
];
const DO_PROMPTS = [
  "Put all my Amazon purchases under Shopping",
  "Create a category called Rent",
  "Categorize Swiggy as Food & Dining",
];

/** "Why?" under an answer: the tools that produced it and the data they
 *  returned, inline. The same provenance the /chat/traces page shows — here it's
 *  attached to the answer you're reading, so a wrong number is traceable to the
 *  exact call that produced it without leaving the conversation. */
function AnswerProvenance({ trace }: { trace: ChatTrace }) {
  const [open, setOpen] = useState(false);
  const steps = trace.steps ?? [];
  const drills = drillLinksFromTrace(trace);
  return (
    <>
      <SourceBadge source={trace.source} />
      {trace.action_taken && <ActionBadge />}
      <ToolCallCount steps={steps} />
      {trace.duration_ms != null && <span>{trace.duration_ms} ms</span>}
      {(steps.length > 0 || trace.error) && (
        <WhyToggle open={open} onToggle={() => setOpen((o) => !o)} />
      )}
      <div className="w-full">
        {/* An answer is never a dead end: the figures came from rows, so offer
            the rows. The filter is the tool's own arguments, not a guess. */}
        {drills.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-2">
            {drills.map((d) => (
              <Link
                key={d.label}
                href={d.href}
                className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-white px-2.5 py-1 text-xs font-medium text-blue-700 transition hover:bg-blue-50"
              >
                {d.label}
                <ArrowUpRight className="h-3 w-3" />
              </Link>
            ))}
          </div>
        )}
        <SourceNote trace={trace} />
        {open && <TraceSteps steps={steps} />}
      </div>
    </>
  );
}

export default function ChatPage() {
  const { messages, isLoading, status, historyLoading, sendMessage, clearConversation } =
    useChat();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Keep the newest message and the typing indicator in view as the conversation
  // grows, and start with the cursor in the box so you can just type.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      sendMessage(input);
      setInput("");
      inputRef.current?.focus();
    }
  };

  const handleExampleClick = (prompt: string) => {
    if (!isLoading) {
      sendMessage(prompt);
    }
  };

  return (
    <div className="max-w-4xl mx-auto h-full flex flex-col">
      <div className="mb-6 flex items-start justify-between gap-4 md:mb-8">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-gray-900 md:text-4xl">Ask About Your Finances</h1>
          {/* Desktop only. On a phone this sentence wrapped to three lines and
              pushed the conversation below the fold, to say what the Ask/Do cards
              underneath already demonstrate with real examples. */}
          <p className="mt-2 hidden text-gray-600 md:block">
            Ask about your spending — or tell me to categorize merchants and create
            categories, and I&apos;ll do it.
          </p>
        </div>
        <div className="flex items-center gap-4 mt-2 whitespace-nowrap">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={() => {
                if (window.confirm("Clear this conversation? Your chat history will be deleted.")) {
                  clearConversation();
                }
              }}
              disabled={isLoading}
              className="text-sm text-gray-500 hover:text-gray-700 font-medium disabled:opacity-50"
            >
              New chat
            </button>
          )}
          <Link
            href="/chat/traces"
            className="text-sm text-gray-500 hover:text-gray-700 font-medium"
          >
            Traces →
          </Link>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 bg-white rounded-lg shadow p-6 mb-6 overflow-y-auto space-y-4">
        {historyLoading ? (
          <div className="h-full flex items-center justify-center">
            <div className="w-full max-w-2xl grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse" aria-hidden="true">
              <div className="h-40 rounded-xl bg-gray-100" />
              <div className="h-40 rounded-xl bg-gray-100" />
            </div>
          </div>
        ) : messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="w-full max-w-2xl grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Ask — questions answered from your real data */}
              <div className="rounded-xl border border-gray-200 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <Search className="w-4 h-4 text-blue-600" />
                  <h2 className="text-sm font-semibold text-gray-900">Ask</h2>
                  <span className="text-xs text-gray-400">answered from your data</span>
                </div>
                <div className="flex flex-col gap-2">
                  {ASK_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => handleExampleClick(prompt)}
                      disabled={isLoading}
                      className="text-left text-sm text-blue-700 bg-blue-50 hover:bg-blue-100 disabled:opacity-50 px-3 py-2 rounded-lg transition"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>

              {/* Do — the assistant changes your data on command */}
              <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <Wand2 className="w-4 h-4 text-indigo-600" />
                  <h2 className="text-sm font-semibold text-gray-900">Do</h2>
                  <span className="text-xs text-gray-400">I&apos;ll make the change</span>
                </div>
                <div className="flex flex-col gap-2">
                  {DO_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => handleExampleClick(prompt)}
                      disabled={isLoading}
                      className="text-left text-sm text-indigo-700 bg-white hover:bg-indigo-100 border border-indigo-100 disabled:opacity-50 px-3 py-2 rounded-lg transition"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
                <p className="mt-3 text-xs text-gray-500 leading-relaxed">
                  I can also rename a category, set its emoji (&ldquo;set the icon for Rent
                  to 🏠&rdquo;), merge two, or delete an empty one — just tell me.
                </p>
              </div>
            </div>
          </div>
        ) : (
          messages.map((message, i) => (
            <div
              key={message.id}
              className={`animate-rise flex ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`min-w-0 rounded-lg px-4 py-2 ${
                  message.role === "user"
                    ? "max-w-[85%] bg-blue-600 text-white lg:max-w-md"
                    : "max-w-[92%] bg-gray-100 text-gray-900 lg:max-w-2xl"
                }`}
              >
                {/* Assistant answers are markdown (tables, bold figures, lists).
                    What you type is not — rendering it would mangle a merchant
                    name with an underscore or asterisk in it.

                    Not while it streams, though: the answer arrives a token at a
                    time, and half a table is a paragraph of loose pipes that
                    reflows on every chunk. Plain text as it types, markdown the
                    moment it lands. break-words matters either way — answers list
                    raw merchant names like SATHISHREDDYVADICHERLA, which pre-wrap
                    alone won't break. */}
                {message.role === "assistant" &&
                !(isLoading && i === messages.length - 1) ? (
                  <Markdown>{message.content}</Markdown>
                ) : (
                  <p className="text-sm break-words whitespace-pre-wrap">
                    {message.content}
                  </p>
                )}
                <div
                  className={`mt-1 flex flex-wrap items-center gap-3 text-xs ${
                    message.role === "user" ? "text-blue-100" : "text-gray-500"
                  }`}
                >
                  <span>{message.timestamp.toLocaleTimeString()}</span>
                  {message.trace && <AnswerProvenance trace={message.trace} />}
                </div>
              </div>
            </div>
          ))
        )}
        {isLoading && (
          <div className="animate-rise flex justify-start">
            <div className="flex items-center gap-3 rounded-lg bg-gray-100 px-4 py-2 text-gray-900">
              <div className="flex space-x-1.5">
                <div className="h-2 w-2 animate-bounce rounded-full bg-gray-500" />
                <div className="h-2 w-2 animate-bounce rounded-full bg-gray-500" style={{ animationDelay: "0.2s" }} />
                <div className="h-2 w-2 animate-bounce rounded-full bg-gray-500" style={{ animationDelay: "0.4s" }} />
              </div>
              {/* The model can take tens of seconds on the free tier; saying what
                  it's doing is the difference between "thinking" and "broken". */}
              {status && (
                <span aria-live="polite" className="text-sm text-gray-600">
                  {status}
                </span>
              )}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center space-x-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your finances..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-900 placeholder:text-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            aria-label="Send message"
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white p-2 rounded-lg transition"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </form>
    </div>
  );
}
