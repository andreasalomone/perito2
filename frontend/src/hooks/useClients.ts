import useSWR from 'swr';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { ClientListItem } from '@/types';

export function useClients(params: {
    q?: string;
    limit?: number;
    skip?: number;
} = {}) {
    const { user, getToken } = useAuth();

    // Include params in SWR key to trigger re-fetch on change
    const key = user ? ['clients', user.uid, JSON.stringify(params)] : null;

    const { data, error, isLoading, mutate } = useSWR<ClientListItem[]>(
        key,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.clients.list(token, params);
        },
        {
            keepPreviousData: true, // UX: Keep showing old data while filtering
            revalidateOnFocus: false, // Don't spam fetches
        }
    );

    return {
        clients: data || [],
        isLoading,
        isError: error,
        mutate,
    };
}

export function useClient(id: string) {
    const { user, getToken } = useAuth();
    const key = user && id ? ['client', id] : null;

    const { data, error, isLoading, mutate } = useSWR(
        key,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.clients.get(token, id);
        }
    );

    return {
        client: data,
        isLoading,
        isError: error,
        mutate
    };
}
