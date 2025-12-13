import useSWR, { mutate as globalMutate } from 'swr';
import { useAuth } from '@/context/AuthContext';
import { api } from '@/lib/api';
import { CaseDetail, CaseStatus } from '@/types';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { toast } from 'sonner';

// Workflow step type for the new case workflow
export type WorkflowStep = 1 | 2 | 3 | 4 | 'ERROR';

export function useCaseDetail(id: string | undefined) {
    const { user, getToken } = useAuth();
    const [shouldPoll, setShouldPoll] = useState(false);
    const [pollingStart, setPollingStart] = useState<number | null>(null);

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
            revalidateOnFocus: true,   // Re-fetch full data when tab focused
            refreshInterval: 0,        // DO NOT POLL HEAVY DATA
            keepPreviousData: true     // FIX: Prevent blank screen during refetch/mutation
        }
    );

    // 2. Determine if we need to poll based on case state
    useEffect(() => {
        if (!caseData) return;

        const isGeneratingReport =
            caseData.status === "GENERATING" ||
            caseData.status === "PROCESSING";

        const isProcessingDocs =
            caseData.documents.some(d => ["PROCESSING", "PENDING"].includes(d.ai_status));

        const isBusy = isGeneratingReport || isProcessingDocs;

        if (isBusy && !shouldPoll) {
            setPollingStart(Date.now());
        }
        setShouldPoll(isBusy);
    }, [caseData, shouldPoll]);

    // 3. Stop polling after 10 minutes (job likely stuck)
    useEffect(() => {
        if (!pollingStart || !shouldPoll) return;

        const elapsed = Date.now() - pollingStart;
        if (elapsed > 10 * 60 * 1000) {
            setShouldPoll(false);
            setPollingStart(null);
            toast.error("Generazione troppo lunga. Ricarica la pagina per verificare lo stato.");
        }
    }, [pollingStart, shouldPoll]);

    // 4. Pause polling when tab is hidden
    useEffect(() => {
        const handleVisibility = () => {
            if (document.hidden) {
                setShouldPoll(false);
            } else if (caseData?.status === "GENERATING" || caseData?.status === "PROCESSING") {
                setShouldPoll(true);
                mutateCase(); // Immediate refresh when returning
            }
        };

        document.addEventListener("visibilitychange", handleVisibility);
        return () => document.removeEventListener("visibilitychange", handleVisibility);
    }, [caseData?.status, mutateCase]);

    // 5. Adaptive polling interval (faster during generation)
    const pollInterval = caseData?.status === "GENERATING" ? 2000 : 5000;

    // 6. Lightweight Polling (Status Only)
    const { data: statusData } = useSWR<CaseStatus>(
        shouldPoll && user && id ? ['case-status', id] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.cases.getStatus(token, id!);
        },
        {
            refreshInterval: pollInterval, // Adaptive interval
            onSuccess: (newStatus) => {
                // If status changed to a "finished" state, trigger full re-fetch
                const statusChanged = caseData?.status !== newStatus.status;

                // Also check if document processing finished (if we were tracking that)
                const wasProcessingDocs = caseData?.documents.some(d => ["PROCESSING", "PENDING"].includes(d.ai_status));
                const isProcessingDocsNow = newStatus.documents.some((d: any) => ["PROCESSING", "PENDING"].includes(d.ai_status));
                const docsFinished = wasProcessingDocs && !isProcessingDocsNow;

                if ((statusChanged || docsFinished) && (newStatus.status === "OPEN" || newStatus.status === "ERROR")) {
                    setShouldPoll(false);
                    setPollingStart(null);

                    // FIX: Invalidate status cache to prevent race condition
                    globalMutate(['case-status', id], undefined, { revalidate: false });

                    mutateCase(); // Re-fetch full details (documents, versions)
                }
            }
        }
    );

    // Enhanced mutate wrapper that invalidates polling cache
    const safeRefresh = useCallback((data?: any, opts?: any) => {
        // Clear polling cache before full re-fetch (prevents race condition)
        globalMutate(['case-status', id], undefined, { revalidate: false });
        setPollingStart(null);
        return mutateCase(data, opts);
    }, [id, mutateCase]);

    // FIXED: Only merge if statusData exists and is not being invalidated
    const displayData = caseData && statusData
        ? { ...caseData, status: statusData.status, documents: statusData.documents }
        : caseData;

    const isGeneratingReport = caseData?.status === "GENERATING" || caseData?.status === "PROCESSING";
    const isProcessingDocs = caseData?.documents.some(d => ["PROCESSING", "PENDING"].includes(d.ai_status));

    // 7. Derive current workflow step from displayData (merged, most up-to-date)
    // NOTE: Closure panel is reached via manualStep only
    // CLOSED cases are redirected to /summary page, so they never show in the workflow
    const currentStep = useMemo((): WorkflowStep => {
        if (!displayData) return 1;

        // ERROR state takes priority - show error UI
        if (displayData.status === 'ERROR') {
            return 'ERROR';
        }

        // CLOSED cases should redirect to /summary, but return 3 as fallback
        // The page.tsx handles the actual redirect
        if (displayData.status === 'CLOSED' ||
            displayData.report_versions?.some(v => v.is_final)) {
            return 3; // Will redirect, but show Review if redirect fails
        }

        // Review: Draft exists but not finalized
        // NOTE: Exclude preliminary reports (source='preliminary') - they don't count as drafts
        const draftVersions = displayData.report_versions?.filter(
            v => !v.is_final && v.source !== 'preliminary'
        ) ?? [];
        if (draftVersions.length > 0) {
            return 3;
        }

        // Default: Ingestion panel (handles both idle and processing states)
        return 1;
    }, [displayData]);

    // Explicit return to avoid object literal syntax errors
    return {
        caseData: displayData,
        isLoading,
        isError: caseError,
        mutate: safeRefresh,
        isGeneratingReport: isGeneratingReport || (shouldPoll && !isProcessingDocs), // optimistic UI fallback
        isProcessingDocs: isProcessingDocs,
        isBusy: shouldPoll || isGeneratingReport || isProcessingDocs,
        setIsGenerating: setShouldPoll, // Allow manual trigger from UI
        currentStep, // NEW: Workflow step for case workflow redesign
    };
}
