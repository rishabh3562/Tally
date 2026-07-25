"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Search, Plus } from "lucide-react";
import type { Category } from "@/types";

/**
 * Searchable category combobox with a "create new" affordance.
 *
 * Solves the "20 categories in a dropdown is high cognitive load" problem:
 * type to fuzzy-filter, ↑/↓ to move, ⏎ to pick, and if nothing matches your
 * text you can create a custom category inline. Generic and reusable (triage
 * screen, transactions table, …).
 */
export default function CategoryPicker({
  categories,
  onSelect,
  onCreate,
  placeholder = "Search or create a category…",
  autoFocus = false,
  disabled = false,
}: {
  categories: Category[];
  onSelect: (categoryId: string) => void;
  onCreate?: (name: string) => Promise<Category | void> | void;
  placeholder?: string;
  autoFocus?: boolean;
  disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  // Resolve a category's parent name so sub-categories read as "Food › Pizza".
  const nameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of categories) m.set(c.id, c.name);
    return m;
  }, [categories]);
  const pathLabel = (c: Category) =>
    c.parent_id && nameById.has(c.parent_id)
      ? `${nameById.get(c.parent_id)} › ${c.name}`
      : c.name;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return categories;
    return categories.filter((c) => pathLabel(c).toLowerCase().includes(q));
  }, [categories, query]);

  const exactExists = useMemo(
    () =>
      categories.some(
        (c) => c.name.toLowerCase() === query.trim().toLowerCase()
      ),
    [categories, query]
  );
  const canCreate = Boolean(onCreate) && query.trim().length > 0 && !exactExists;

  // Combined option count: filtered categories + optional "create" row.
  const optionCount = filtered.length + (canCreate ? 1 : 0);

  useEffect(() => {
    setHighlight(0);
  }, [query]);

  const choose = async (index: number) => {
    if (canCreate && index === filtered.length) {
      const created = await onCreate!(query.trim());
      if (created && "id" in created) onSelect(created.id);
      setQuery("");
      return;
    }
    const cat = filtered[index];
    if (cat) {
      onSelect(cat.id);
      setQuery("");
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(h + 1, optionCount - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(highlight);
    } else if (e.key === "Escape") {
      // Return control to the page-level keyboard shortcuts.
      e.preventDefault();
      inputRef.current?.blur();
    }
    // Stop page-level shortcuts (number keys, j/k, s) firing while typing.
    e.stopPropagation();
  };

  return (
    <div className="w-full max-w-sm">
      <div className="flex items-center gap-2 border border-gray-300 rounded-lg px-2 py-1.5 bg-white focus-within:ring-2 focus-within:ring-blue-500">
        <Search className="w-4 h-4 text-gray-400 shrink-0" />
        <input
          ref={inputRef}
          value={query}
          disabled={disabled}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          className="w-full text-sm text-gray-900 placeholder:text-gray-400 outline-none disabled:opacity-50"
          aria-label="Search or create a category"
        />
      </div>
      <ul className="mt-1 max-h-56 overflow-auto rounded-lg border border-gray-200 bg-white shadow-sm divide-y divide-gray-50">
        {filtered.map((c, i) => (
          <li key={c.id}>
            <button
              type="button"
              onMouseEnter={() => setHighlight(i)}
              onClick={() => choose(i)}
              className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 ${
                highlight === i
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              <span>{c.icon ?? "🏷️"}</span>
              <span className="truncate">
                {c.parent_id && nameById.has(c.parent_id) ? (
                  <>
                    <span className="text-gray-400">
                      {nameById.get(c.parent_id)} ›{" "}
                    </span>
                    {c.name}
                  </>
                ) : (
                  c.name
                )}
              </span>
            </button>
          </li>
        ))}
        {canCreate && (
          <li>
            <button
              type="button"
              onMouseEnter={() => setHighlight(filtered.length)}
              onClick={() => choose(filtered.length)}
              className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 ${
                highlight === filtered.length
                  ? "bg-green-50 text-green-700"
                  : "hover:bg-gray-50 text-gray-700"
              }`}
            >
              <Plus className="w-4 h-4" />
              Create “{query.trim()}”
            </button>
          </li>
        )}
        {optionCount === 0 && (
          <li className="px-3 py-2 text-sm text-gray-400">No categories</li>
        )}
      </ul>
    </div>
  );
}
