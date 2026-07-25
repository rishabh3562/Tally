import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api';
import { Category } from '@/types';

/**
 * Fetch the selectable (system) categories once and expose an id -> name map.
 * Categories change rarely, so this is cached aggressively.
 */
export const useCategories = () => {
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

  return { categories, nameById, isLoading, error };
};
