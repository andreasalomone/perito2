"use client";

import useSWR from "swr";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { DocumentAnalysisResponse, PreliminaryReportResponse } from "@/types";
import { getApiUrl } from "@/context/ConfigContext";
import { useState, useCallback, useRef, useEffect } from "react";
import { toast } from "sonner";

/**
 * Hook for managing Document Analysis feature.
 * Provides fetching, staleness detection, and generation trigger.
 *
 * @param caseId - The case ID to fetch analysis for
 * @param shouldPoll - Whether to poll for updates (default: false). Enable when documents are processing.
 */
export function useDocumentAnalysis(caseId: string | undefined, shouldPoll: boolean = false) {
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
            refreshInterval: shouldPoll ? 5000 : 0, // Only poll when processing
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
 *
 * @param caseId - The case ID to fetch report for
 * @param shouldPoll - Whether to poll for updates (default: false). Enable when documents are processing.
 */
export function usePreliminaryReport(caseId: string | undefined, shouldPoll: boolean = false) {
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
            refreshInterval: shouldPoll ? 5000 : 0, // Only poll when processing
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

export type StreamState = "idle" | "thinking" | "streaming" | "done" | "error";

interface StreamingResult {
    thoughts: string;
    content: string;
    state: StreamState;
    error: string | null;
}

/**
 * Hook for streaming Preliminary Report with visible AI reasoning.
 *
 * Uses the streaming endpoint to show "chain of thought" in real-time.
 *
 * @param caseId - The case ID to generate report for
 */
export function usePreliminaryReportStream(caseId: string | undefined) {
    const { getToken } = useAuth();
    const [result, setResult] = useState<StreamingResult>({
        thoughts: "",
        content: "",
        state: "idle",
        error: null,
    });

    // AbortController ref for cancelling on unmount
    const abortControllerRef = useRef<AbortController | null>(null);

    // Cleanup on unmount to prevent memory leaks
    useEffect(() => {
        return () => {
            abortControllerRef.current?.abort();
        };
    }, []);

    const reset = useCallback(() => {
        setResult({
            thoughts: "",
            content: "",
            state: "idle",
            error: null,
        });
    }, []);

    const generateStream = useCallback(async () => {
        if (!caseId) return;

        // Track if any error events were received during streaming
        let hasErrored = false;

        // Reset state
        setResult({
            thoughts: "",
            content: "",
            state: "thinking",
            error: null,
        });

        try {
            const token = await getToken();
            if (!token) throw new Error("No token available");

            // Cancel any existing stream
            abortControllerRef.current?.abort();
            abortControllerRef.current = new AbortController();

            const baseUrl = getApiUrl()?.replace(/\/$/, "") || "";
            const response = await fetch(
                `${baseUrl}/api/v1/cases/${caseId}/preliminary/stream`,
                {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${token}`,
                        "Content-Type": "application/json",
                    },
                    signal: abortControllerRef.current.signal,
                }
            );

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) {
                throw new Error("No response body");
            }

            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");

                // Keep incomplete line in buffer
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (!line.trim()) continue;

                    try {
                        const event = JSON.parse(line);

                        if (event.type === "thought") {
                            setResult(prev => ({
                                ...prev,
                                thoughts: prev.thoughts + event.text,
                                state: "thinking",
                            }));
                        } else if (event.type === "content") {
                            setResult(prev => ({
                                ...prev,
                                content: prev.content + event.text,
                                state: "streaming",
                            }));
                        } else if (event.type === "done") {
                            setResult(prev => ({
                                ...prev,
                                state: "done",
                            }));
                        } else if (event.type === "error") {
                            setResult(prev => ({
                                ...prev,
                                state: "error",
                                error: event.text,
                            }));
                            toast.error(event.text);
                            hasErrored = true;
                        }
                    } catch {
                        // Skip malformed JSON lines
                        console.warn("Failed to parse NDJSON line:", line);
                    }
                }
            }

            // Process any remaining buffer - check for both done AND error events
            if (buffer.trim()) {
                try {
                    const event = JSON.parse(buffer);
                    if (event.type === "done") {
                        setResult(prev => ({ ...prev, state: "done" }));
                    } else if (event.type === "error") {
                        setResult(prev => ({ ...prev, state: "error", error: event.text }));
                        toast.error(event.text);
                        hasErrored = true;
                    }
                } catch {
                    // Ignore
                }
            }

            // Only show success toast if no errors occurred during streaming
            if (!hasErrored) {
                toast.success("Report preliminare generato");
            }

        } catch (err: any) {
            // Ignore abort errors (user navigated away)
            if (err?.name === "AbortError") {
                return;
            }
            const message = err?.message || "Errore durante lo streaming";
            setResult(prev => ({
                ...prev,
                state: "error",
                error: message,
            }));
            toast.error(message);
        }
    }, [caseId, getToken]);

    return {
        ...result,
        generateStream,
        reset,
        isStreaming: result.state === "thinking" || result.state === "streaming",
    };
}

/**
 * Hook for streaming Final Report.
 * Targeting: /api/v1/cases/{caseId}/final-report/stream
 */
export function useFinalReportStream(caseId: string | undefined) {
    const { getToken } = useAuth();
    const [result, setResult] = useState<StreamingResult>({
        thoughts: "",
        content: "",
        state: "idle",
        error: null,
    });

    // AbortController ref for cancelling on unmount
    const abortControllerRef = useRef<AbortController | null>(null);

    // Cleanup on unmount to prevent memory leaks
    useEffect(() => {
        return () => {
            abortControllerRef.current?.abort();
        };
    }, []);

    const reset = useCallback(() => {
        setResult({
            thoughts: "",
            content: "",
            state: "idle",
            error: null,
        });
    }, []);

    const generateStream = useCallback(async (language: string, extraInstructions?: string) => {
        if (!caseId) return;

        // Track if any error events were received during streaming
        let hasErrored = false;

        // Reset state
        setResult({
            thoughts: "",
            content: "",
            state: "thinking", // Initial state
            error: null,
        });

        try {
            const token = await getToken();
            if (!token) throw new Error("No token available");

            // Cancel any existing stream
            abortControllerRef.current?.abort();
            abortControllerRef.current = new AbortController();

            const baseUrl = getApiUrl()?.replace(/\/$/, "") || "";
            const response = await fetch(
                `${baseUrl}/api/v1/cases/${caseId}/final-report/stream`,
                {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${token}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        language,
                        extra_instructions: extraInstructions
                    }),
                    signal: abortControllerRef.current.signal,
                }
            );

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) {
                throw new Error("No response body");
            }

            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (!line.trim()) continue;

                    try {
                        const event = JSON.parse(line);

                        if (event.type === "thought") {
                            setResult(prev => ({
                                ...prev,
                                thoughts: prev.thoughts + event.text,
                                state: "thinking",
                            }));
                        } else if (event.type === "content") {
                            setResult(prev => ({
                                ...prev,
                                content: prev.content + event.text,
                                state: "streaming",
                            }));
                        } else if (event.type === "done") {
                            setResult(prev => ({
                                ...prev,
                                state: "done",
                            }));
                        } else if (event.type === "error") {
                            setResult(prev => ({
                                ...prev,
                                state: "error",
                                error: event.text,
                            }));
                            toast.error(event.text);
                            hasErrored = true;
                        }
                    } catch {
                        // Skip
                    }
                }
            }

            // Flush buffer - check for both done AND error events
            if (buffer.trim()) {
                try {
                    const event = JSON.parse(buffer);
                    if (event.type === "done") {
                        setResult(prev => ({ ...prev, state: "done" }));
                    } else if (event.type === "error") {
                        setResult(prev => ({ ...prev, state: "error", error: event.text }));
                        toast.error(event.text);
                        hasErrored = true;
                    }
                } catch { }
            }

            // Only show success toast if no errors occurred during streaming
            if (!hasErrored) {
                toast.success("Report finale generato");
            }

        } catch (err: any) {
            // Ignore abort errors (user navigated away)
            if (err?.name === "AbortError") {
                return;
            }
            const message = err?.message || "Errore durante lo streaming";
            setResult(prev => ({
                ...prev,
                state: "error",
                error: message,
            }));
            toast.error(message);
        }
    }, [caseId, getToken]);

    return {
        ...result,
        generateStream,
        reset,
        isStreaming: result.state === "thinking" || result.state === "streaming",
    };
}


