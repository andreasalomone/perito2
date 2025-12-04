import useSWR from 'swr';
import { useAuth } from '@/context/AuthContext';
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export interface AllowedEmail {
    id: string;
    email: string;
    role: string;
    organization_id: string;
    created_at: string;
}

export function useInvites(organizationId: string | null) {
    const { user, getToken } = useAuth();

    const { data, error, isLoading, mutate } = useSWR<AllowedEmail[]>(
        user && organizationId ? ['invites', organizationId] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            const response = await axios.get(
                `${API_URL}/api/admin/organizations/${organizationId}/invites`,
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
