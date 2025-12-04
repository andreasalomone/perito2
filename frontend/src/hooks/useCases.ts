import useSWR from 'swr';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { CaseSummary } from '@/types';

export function useCases() {
    const { user, getToken } = useAuth();

    const { data, error, isLoading, mutate } = useSWR<CaseSummary[]>(
        user ? ['cases', user.uid] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.cases.list(token);
        },
        {
            refreshInterval: 5000, // Poll every 5 seconds
            revalidateOnFocus: true,
            shouldRetryOnError: false,
        }
    );

    return {
        cases: data || [],
        isLoading,
        isError: error,
        mutate,
    };
}
