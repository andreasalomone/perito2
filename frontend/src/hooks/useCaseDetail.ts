import useSWR from 'swr';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { CaseDetail, CaseStatus } from '@/types';
import { useState, useEffect } from 'react';

export function useCaseDetail(id: string | undefined) {
    const { user, getToken } = useAuth();
    const [shouldPoll, setShouldPoll] = useState(false);

    // 1. Main Data Fetch (Full Payload) - Only fetches on mount or manual mutate
    const {
        data: caseData,
        error: caseError,
        isLoading,
        mutate: mutateCase
    } = useSWR<CaseDetail>(
        user && id ? ['case', id] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.cases.get(token, id!);
        },
        {
            revalidateOnFocus: true, // Re-fetch full data when tab focused
            refreshInterval: 0       // DO NOT POLL HEAVY DATA
        }
    );

    // 2. Determine if we need to poll based on case state
    useEffect(() => {
        if (!caseData) return;
        const isBusy =
            caseData.status === "GENERATING" ||
            caseData.status === "PROCESSING" ||
            caseData.documents.some(d => ["PROCESSING", "PENDING"].includes(d.ai_status));

        setShouldPoll(isBusy);
    }, [caseData]);

    // 3. Lightweight Polling (Status Only)
    const { data: statusData } = useSWR<CaseStatus>(
        shouldPoll && user && id ? ['case-status', id] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.cases.getStatus(token, id!);
        },
        {
            refreshInterval: 3000, // Poll light endpoint every 3s
            onSuccess: (newStatus) => {
                // If status changed to a "finished" state, trigger full re-fetch
                if (newStatus.status === "OPEN" || newStatus.status === "ERROR") {
                    setShouldPoll(false);
                    mutateCase(); // Re-fetch full details (documents, versions)
                }
            }
        }
    );

    // Merge logic: If we have newer status data, overlay it on caseData for UI feedback
    const displayData = caseData && statusData
        ? { ...caseData, status: statusData.status, documents: statusData.documents }
        : caseData;

    return {
        caseData: displayData,
        isLoading,
        isError: caseError,
        mutate: mutateCase,
        isGenerating: shouldPoll,
        setIsGenerating: setShouldPoll // Allow manual trigger from UI
    };
}
