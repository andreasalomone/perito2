import useSWR from 'swr';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { CaseDetail } from '@/types';
import { useState, useEffect } from 'react';

export function useCaseDetail(id: string | undefined) {
    const { user, getToken } = useAuth();
    const [isGenerating, setIsGenerating] = useState(false);

    const { data, error, isLoading, mutate } = useSWR<CaseDetail>(
        user && id ? ['case', id] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.cases.get(token, id!);
        },
        {
            refreshInterval: (data) => {
                // Poll if locally generating OR backend says generating OR docs are processing
                const isProcessing = data?.documents.some(d => ["PROCESSING", "PENDING"].includes(d.ai_status));

                // Note: We don't have 'is_generating' on CaseDetail usually, but the previous code 
                // inferred it or fetched it from a separate status endpoint. 
                // The original code merged `statusData` which had `is_generating`.
                // Let's assume we rely on document status for now, or we need to update the type/API if `is_generating` is critical.
                // For now, we poll if documents are processing or if we explicitly started generation.

                if (isGenerating || isProcessing) return 3000;
                return 0;
            },
            revalidateOnFocus: true,
            shouldRetryOnError: false,
        }
    );

    // Reset local generating state when we see completion
    useEffect(() => {
        if (data && isGenerating) {
            const allDone = data.documents.every(d => ["COMPLETED", "ERROR"].includes(d.ai_status));
            if (allDone) {
                setIsGenerating(false);
            }
        }
    }, [data, isGenerating]);

    return {
        caseData: data,
        isLoading,
        isError: error,
        mutate,
        isGenerating,
        setIsGenerating
    };
}
