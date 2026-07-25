"use client";

import { useChat } from "@/hooks/useChat";
import { useState } from "react";
import Link from "next/link";
import { Send, Search, Wand2 } from "lucide-react";

// Two capabilities, shown distinctly: the assistant both ANSWERS questions and
// PERFORMS changes on your data — the "tell it and it does it" (Palantir) idea.
const ASK_PROMPTS = [
  "How much did I spend on food last month?",
  "Which merchants did I spend the most at?",
  "Did I spend more this month than last month?",
];
const DO_PROMPTS = [
  "Put all my Amazon purchases under Shopping",
  "Create a category called Rent",
  "Categorize Swiggy as Food & Dining",
];

export default function ChatPage() {
  const { messages, isLoading, sendMessage } = useChat();
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      sendMessage(input);
      setInput("");
    }
  };

  const handleExampleClick = (prompt: string) => {
    if (!isLoading) {
      sendMessage(prompt);
    }
  };

  return (
    <div className="max-w-4xl mx-auto h-full flex flex-col">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-4xl font-bold text-gray-900">Ask About Your Finances</h1>
          <p className="text-gray-600 mt-2">
            Ask about your spending — or tell me to categorize merchants and create
            categories, and I&apos;ll do it.
          </p>
        </div>
        <Link
          href="/chat/traces"
          className="text-sm text-gray-500 hover:text-gray-700 font-medium whitespace-nowrap mt-2"
        >
          Traces →
        </Link>
      </div>

      {/* Messages */}
      <div className="flex-1 bg-white rounded-lg shadow p-6 mb-6 overflow-y-auto space-y-4">
        {messages.length === 0 ? (
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
              </div>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`px-4 py-2 rounded-lg ${
                  message.role === "user"
                    ? "max-w-xs lg:max-w-md bg-blue-600 text-white"
                    : "max-w-md lg:max-w-2xl bg-gray-100 text-gray-900"
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                <p
                  className={`text-xs mt-1 ${
                    message.role === "user"
                      ? "text-blue-100"
                      : "text-gray-500"
                  }`}
                >
                  {message.timestamp.toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))
        )}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-900 px-4 py-2 rounded-lg">
              <div className="flex space-x-2">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }}></div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center space-x-2">
          <input
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
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white p-2 rounded-lg transition"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </form>
    </div>
  );
}
