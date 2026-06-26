import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/lib/api';
import { Transaction } from '@/types';

interface TransactionFilters {
  start_date?: string;
  end_date?: string;
  category_id?: string;
  page?: number;
  limit?: number;
}

export const useTransactions = (filters?: TransactionFilters) => {
  const queryClient = useQueryClient();

  const {
    data,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['transactions', filters],
    queryFn: async () => {
      const response = await apiClient.get('/api/transactions', { params: filters });
      return response.data;
    },
  });

  const updateCategoryMutation = useMutation({
    mutationFn: async ({ transactionId, categoryId, merchantCorrection }: {
      transactionId: string;
      categoryId: string;
      merchantCorrection?: boolean;
    }) => {
      const response = await apiClient.patch(
        `/api/transactions/${transactionId}/category`,
        {
          category_id: categoryId,
          merchant_correction: merchantCorrection,
        }
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });

  return {
    transactions: data?.data || [],
    total: data?.total || 0,
    isLoading,
    error,
    updateCategory: updateCategoryMutation.mutate,
    isUpdating: updateCategoryMutation.isPending,
  };
};
