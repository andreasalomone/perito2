"use client";

import useSWR from "swr";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { DocumentAnalysisResponse, PreliminaryReportResponse } from "@/types";
import { useState, useCallback } from "react";
import { toast } from "sonner";

/**
 * Hook for managing Document Analysis feature.
 * Provides fetching, staleness detection, and generation trigger.
 */
export function useDocumentAnalysis(caseId: string | undefined) {
    const { user, getToken } = useAuth();
    const [isGenerating, setIsGenerating] = useState(false);

    const {
        data,
        error,
        isLoading,
        mutate,
    } = useSWR<DocumentAnalysisResponse>(
        user && caseId ? ["document-analysis", caseId] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.cases.getDocumentAnalysis(token, caseId!);
        },
        {
            revalidateOnFocus: true,
            refreshInterval: 5000,
            keepPreviousData: true,
        }
    );

    const generate = useCallback(async (force: boolean = false) => {
        if (!caseId) return;

        setIsGenerating(true);
        try {
            const token = await getToken();
            if (!token) throw new Error("No token available");

            const result = await api.cases.createDocumentAnalysis(token, caseId, force);

            // Update cache with new analysis
            mutate({
                analysis: result.analysis,
                can_update: true,
                pending_docs: 0,
            });

            if (result.generated) {
                toast.success("Analisi documenti completata");
            }

            return result;
        } catch (err: any) {
            const message = err?.message || "Errore durante l'analisi";
            toast.error(message);
            throw err;
        } finally {
            setIsGenerating(false);
        }
    }, [caseId, getToken, mutate]);

    return {
        analysis: data?.analysis ?? null,
        isStale: data?.analysis?.is_stale ?? false,
        canAnalyze: data?.can_update ?? false,
        pendingDocs: data?.pending_docs ?? 0,
        isLoading,
        isError: !!error,
        isGenerating,
        generate,
        mutate,
    };
}

/**
 * Hook for managing Preliminary Report feature.
 * Provides fetching and generation trigger.
 */
export function usePreliminaryReport(caseId: string | undefined) {
    const { user, getToken } = useAuth();
    const [isGenerating, setIsGenerating] = useState(false);

    const {
        data,
        error,
        isLoading,
        mutate,
    } = useSWR<PreliminaryReportResponse>(
        user && caseId ? ["preliminary-report", caseId] : null,
        async () => {
            const token = await getToken();
            if (!token) throw new Error("No token available");
            return api.cases.getPreliminaryReport(token, caseId!);
        },
        {
            revalidateOnFocus: true,
            refreshInterval: 5000,
            keepPreviousData: true,
        }
    );

    const generate = useCallback(async (force: boolean = false) => {
        if (!caseId) return;

        setIsGenerating(true);
        try {
            const token = await getToken();
            if (!token) throw new Error("No token available");

            const result = await api.cases.createPreliminaryReport(token, caseId, force);

            // Update cache with new report
            mutate({
                report: result.report,
                can_generate: true,
                pending_docs: 0,
            });

            if (result.generated) {
                toast.success("Report preliminare generato");
            }

            return result;
        } catch (err: any) {
            const message = err?.message || "Errore durante la generazione";
            toast.error(message);
            throw err;
        } finally {
            setIsGenerating(false);
        }
    }, [caseId, getToken, mutate]);

    return {
        report: data?.report ?? null,
        canGenerate: data?.can_generate ?? false,
        pendingDocs: data?.pending_docs ?? 0,
        isLoading,
        isError: !!error,
        isGenerating,
        generate,
        mutate,
    };
}
