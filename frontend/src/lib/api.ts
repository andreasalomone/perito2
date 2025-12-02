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


const API_URL = (process.env.NEXT_PUBLIC_API_URL || "").replace(/^http:\/\//, "https://");

export class ApiError extends Error {
    constructor(message: string, public status?: number) {
        super(message);
        this.name = "ApiError";
    }
}

async function fetchWithValidation<T>(
    url: string,
    token: string,
    schema: z.ZodType<T>
): Promise<T> {
    try {
        const res = await axios.get(url, {
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
                `${API_URL}/api/cases/`,
                token,
                z.array(CaseSummarySchema)
            ),

        get: (token: string, id: string) =>
            fetchWithValidation<CaseDetail>(
                `${API_URL}/api/cases/${id}`,
                token,
                CaseDetailSchema
            ),

        getStatus: (token: string, id: string) =>
            fetchWithValidation<CaseStatus>(
                `${API_URL}/api/cases/${id}/status`,
                token,
                CaseStatusSchema
            )
    }
};
