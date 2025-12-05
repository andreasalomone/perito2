import useSWR from 'swr';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { Organization } from '@/types/admin';

// Re-export for backwards compatibility
export type { Organization } from '@/types/admin';

export function useOrganizations() {
    const { user, getToken } = useAuth();

    const { data, error, isLoading, mutate } = useSWR<Organization[]>(
        user ? ['organizations'] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.admin.listOrganizations(token);
        },
        {
            revalidateOnFocus: true,
            shouldRetryOnError: false,
        }
    );

    return {
        organizations: data || [],
        isLoading,
        isError: error,
        mutate,
    };
}
