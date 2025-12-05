import useSWR from 'swr';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { AllowedEmail } from '@/types/admin';

// Re-export for backwards compatibility
export type { AllowedEmail } from '@/types/admin';

export function useInvites(organizationId: string | null) {
    const { user, getToken } = useAuth();

    const { data, error, isLoading, mutate } = useSWR<AllowedEmail[]>(
        user && organizationId ? ['invites', organizationId] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.admin.listInvites(token, organizationId!);
        },
        {
            revalidateOnFocus: true,
            shouldRetryOnError: false,
        }
    );

    return {
        invites: data || [],
        isLoading,
        isError: error,
        mutate,
    };
}
