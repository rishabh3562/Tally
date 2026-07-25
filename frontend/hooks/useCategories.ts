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

  return { categories, nameById, isLoading, error, createCategory };
};
