import axios from "axios";
import { z } from "zod";
import {
    CaseSummarySchema,
    CaseDetailSchema,
    CaseStatusSchema,
    CaseSummary,
    CaseDetail,
    CaseStatus
} from "@/types";




// BUILD-TIME VALIDATION: Ensure HTTPS enforcement
const rawApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim() || "";

if (!rawApiUrl) {
    throw new Error('[CONFIG ERROR] NEXT_PUBLIC_API_URL is not defined');
}

if (!rawApiUrl.startsWith('https://') && process.env.NODE_ENV === 'production') {
    throw new Error('[SECURITY] NEXT_PUBLIC_API_URL must use HTTPS in production. Got: ' + rawApiUrl);
}

// Clean up URL
export const API_URL = rawApiUrl.replace(/\/$/, "");

export class ApiError extends Error {
    constructor(message: string, public status?: number) {
        super(message);
        this.name = "ApiError";
    }
}

async function fetchWithValidation<T>(
    url: string,
    token: string,
    schema: z.ZodType<T>,
    options: { method?: string; data?: any } = {}
): Promise<T> {
    try {
        const res = await axios({
            method: options.method || "GET",
            url,
            data: options.data,
            headers: { Authorization: `Bearer ${token}` }
        });

        const parsed = schema.safeParse(res.data);

        if (!parsed.success) {
            console.error("API Contract Breach:", parsed.error);
            // In production, you might want to log this to Sentry
            throw new ApiError("Invalid API Response: Contract Mismatch");
        }

        return parsed.data;
    } catch (error) {
        if (axios.isAxiosError(error)) {
            throw new ApiError(
                error.response?.data?.detail || "Network Error",
                error.response?.status
            );
        }
        throw error;
    }
}

export const api = {
    cases: {
        list: (token: string) =>
            fetchWithValidation<CaseSummary[]>(
                `${API_URL}/api/v1/cases/`,
                token,
                z.array(CaseSummarySchema)
            ),

        get: (token: string, id: string) =>
            fetchWithValidation<CaseDetail>(
                `${API_URL}/api/v1/cases/${id}`,
                token,
                CaseDetailSchema
            ),

        create: (token: string, data: { reference_code: string; client_name?: string }) =>
            fetchWithValidation<CaseDetail>(
                `${API_URL}/api/v1/cases/`,
                token,
                CaseDetailSchema,
                {
                    method: "POST",
                    data
                }
            ),

        getStatus: (token: string, id: string) =>
            fetchWithValidation<CaseStatus>(
                `${API_URL}/api/v1/cases/${id}/status`,
                token,
                CaseStatusSchema
            )
    }
};
