import useSWR from 'swr';
import { useAuth } from '@/context/AuthContext';
import { useConfig } from '@/context/ConfigContext';
import axios from 'axios';

export interface AllowedEmail {
    id: string;
    email: string;
    role: string;
    organization_id: string;
    created_at: string;
}

export function useInvites(organizationId: string | null) {
    const { user, getToken } = useAuth();
    const { apiUrl } = useConfig();

    const { data, error, isLoading, mutate } = useSWR<AllowedEmail[]>(
        user && organizationId ? ['invites', organizationId] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            const response = await axios.get(
                `${apiUrl}/api/v1/admin/organizations/${organizationId}/invites`,
                { headers: { Authorization: `Bearer ${token}` } }
            );
            return response.data;
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
