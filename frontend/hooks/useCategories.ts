import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api';
import { Category } from '@/types';

/**
 * Fetch the selectable categories (system + the user's own) once and expose an
 * id -> name map plus a "create custom category" mutation. Categories change
 * rarely, so reads are cached aggressively.
 */
export const useCategories = () => {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const response = await apiClient.get('/api/categories');
      return (response.data?.data ?? []) as Category[];
    },
    staleTime: 60 * 60 * 1000, // 1h — categories are effectively static
  });

  const categories = data ?? [];
  const nameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of categories) m.set(c.id, c.name);
    return m;
  }, [categories]);

  // Category NAME -> emoji icon, for prefixing category names in breakdowns.
  const iconByName = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of categories) if (c.icon) m.set(c.name, c.icon);
    return m;
  }, [categories]);

  // Resolve a category id to its TOP-LEVEL ancestor name, so sub-category spend
  // (Food › Pizza) rolls up into the parent slice on dashboards/insights instead
  // of fragmenting the breakdown. Guards against cycles.
  const rootNameById = useMemo(() => {
    const byId = new Map(categories.map((c) => [c.id, c]));
    const resolve = (id: string): string => {
      let cur = byId.get(id);
      const seen = new Set<string>();
      while (cur?.parent_id && byId.has(cur.parent_id) && !seen.has(cur.id)) {
        seen.add(cur.id);
        cur = byId.get(cur.parent_id);
      }
      return cur?.name ?? "";
    };
    const m = new Map<string, string>();
    for (const c of categories) m.set(c.id, resolve(c.id));
    return m;
  }, [categories]);

  // Create a user-scoped custom category (e.g. "Rent", "Loan given"). The
  // backend is idempotent by name, so calling with an existing name just
  // returns it. Resolves to the created/reused Category.
  const createCategory = useMutation({
    mutationFn: async ({ name, icon }: { name: string; icon?: string }) => {
      const res = await apiClient.post('/api/categories', { name, icon });
      return res.data.data as Category;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] });
    },
  });

  return { categories, nameById, iconByName, rootNameById, isLoading, error, createCategory };
};
