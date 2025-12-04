import useSWR from 'swr';
import { useAuth } from '@/context/AuthContext';
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export interface Organization {
    id: string;
    name: string;
    created_at: string;
}

export function useOrganizations() {
    const { user, getToken } = useAuth();

    const { data, error, isLoading, mutate } = useSWR<Organization[]>(
        user ? ['organizations'] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            const response = await axios.get(
                `${API_URL}/api/admin/organizations`,
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
        organizations: data || [],
        isLoading,
        isError: error,
        mutate,
    };
}
