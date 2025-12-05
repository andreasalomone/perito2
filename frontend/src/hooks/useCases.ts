import useSWR from 'swr';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { CaseSummary } from '@/types';

export function useCases(params: {
    search?: string;
    client_id?: string;
    status?: string;
    scope?: string;
} = {}) {
    const { user, getToken } = useAuth();

    // Include params in SWR key to trigger re-fetch on change
    // Using JSON.stringify(params) is a quick way to stable-key object deps
    const key = user ? ['cases', user.uid, JSON.stringify(params)] : null;

    const { data, error, isLoading, mutate } = useSWR<CaseSummary[]>(
        key,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.cases.list(token, params);
        },
        {
            refreshInterval: 5000,
            revalidateOnFocus: true,
            shouldRetryOnError: false,
            keepPreviousData: true, // UX: Keep showing old data while filtering
        }
    );

    return {
        cases: data || [],
        isLoading,
        isError: error,
        mutate,
    };
}
