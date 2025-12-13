import axios from "axios";
import { z } from "zod";
import {
    CaseSummarySchema,
    CaseDetailSchema,
    CaseStatusSchema,
    CaseSummary,
    CaseDetail,
    CaseStatus,
    ClientSchema,
    Client,
    ClientCreateSchema,
    ClientUpdateSchema,
    ClientDetailSchema,
    ClientListItemSchema,
    EnrichedClientDataSchema,
    ClientCreate,
    ClientUpdate,
    ClientDetail,
    ClientListItem,
    EnrichedClientData,
    // Document Analysis (Early Analysis Feature)
    DocumentAnalysisResponseSchema,
    DocumentAnalysisCreateResponseSchema,
    DocumentAnalysisResponse,
    DocumentAnalysisCreateResponse,
    // Preliminary Report (Early Analysis Feature)
    PreliminaryReportResponseSchema,
    PreliminaryReportCreateResponseSchema,
    PreliminaryReportResponse,
    PreliminaryReportCreateResponse,
} from "@/types";
import { OrganizationSchema, AllowedEmailSchema, Organization, AllowedEmail } from "@/types/admin";
import { GlobalStatsSchema, OrgStatsSchema, UserStatsSchema, GlobalStats, OrgStats, UserStats } from "@/types/stats";
import { UserProfileResponseSchema, UserProfileResponse } from "@/types/user";
import { getApiUrl } from "@/context/ConfigContext";

// Dynamic API URL getter - reads from ConfigContext at runtime
const getBaseUrl = () => {
    const url = getApiUrl();
    if (!url) {
        console.warn('[CONFIG] API_URL not yet initialized');
        return '';
    }
    return url.replace(/\/$/, "");
};

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
    options: { method?: string; data?: any; params?: any } = {}
): Promise<T> {
    try {
        const res = await axios({
            method: options.method || "GET",
            url,
            data: options.data,
            params: options.params,
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
    auth: {
        checkStatus: async (email: string): Promise<{ status: 'registered' | 'invited' | 'denied' }> => {
            const res = await axios.post(`${getBaseUrl()}/api/v1/auth/check-status`, { email });
            return res.data;
        },
    },
    cases: {
        list: (token: string, params: {
            skip?: number;
            limit?: number;
            search?: string;
            client_id?: string;
            status?: string;
            scope?: string;
        } = {}) =>
            fetchWithValidation<CaseSummary[]>(
                `${getBaseUrl()}/api/v1/cases/`,
                token,
                z.array(CaseSummarySchema),
                { params }
            ),

        get: (token: string, id: string) =>
            fetchWithValidation<CaseDetail>(
                `${getBaseUrl()}/api/v1/cases/${id}`,
                token,
                CaseDetailSchema
            ),

        create: (token: string, data: { reference_code: string; client_name?: string }) =>
            fetchWithValidation<CaseDetail>(
                `${getBaseUrl()}/api/v1/cases/`,
                token,
                CaseDetailSchema,
                {
                    method: "POST",
                    data
                }
            ),

        update: (token: string, id: string, data: Partial<CaseDetail>) =>
            fetchWithValidation<CaseDetail>(
                `${getBaseUrl()}/api/v1/cases/${id}`,
                token,
                CaseDetailSchema,
                {
                    method: "PATCH",
                    data
                }
            ),

        getStatus: (token: string, id: string) =>
            fetchWithValidation<CaseStatus>(
                `${getBaseUrl()}/api/v1/cases/${id}/status`,
                token,
                CaseStatusSchema
            ),

        deleteCase: async (token: string, caseId: string): Promise<void> => {
            await axios.delete(`${getBaseUrl()}/api/v1/cases/${caseId}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
        },

        deleteDocument: async (token: string, caseId: string, docId: string): Promise<void> => {
            await axios.delete(`${getBaseUrl()}/api/v1/cases/${caseId}/documents/${docId}`, {
                headers: { Authorization: `Bearer ${token}` }
            });
        },

        // Document Analysis (Early Analysis Feature)
        getDocumentAnalysis: (token: string, caseId: string) =>
            fetchWithValidation<DocumentAnalysisResponse>(
                `${getBaseUrl()}/api/v1/cases/${caseId}/document-analysis`,
                token,
                DocumentAnalysisResponseSchema
            ),

        createDocumentAnalysis: (token: string, caseId: string, force: boolean = false) =>
            fetchWithValidation<DocumentAnalysisCreateResponse>(
                `${getBaseUrl()}/api/v1/cases/${caseId}/document-analysis`,
                token,
                DocumentAnalysisCreateResponseSchema,
                { method: "POST", data: { force } }
            ),

        // Preliminary Report (Early Analysis Feature)
        getPreliminaryReport: (token: string, caseId: string) =>
            fetchWithValidation<PreliminaryReportResponse>(
                `${getBaseUrl()}/api/v1/cases/${caseId}/preliminary`,
                token,
                PreliminaryReportResponseSchema
            ),

        createPreliminaryReport: (token: string, caseId: string, force: boolean = false) =>
            fetchWithValidation<PreliminaryReportCreateResponse>(
                `${getBaseUrl()}/api/v1/cases/${caseId}/preliminary`,
                token,
                PreliminaryReportCreateResponseSchema,
                { method: "POST", data: { force } }
            ),
    },
    clients: {
        list: (token: string, params: { q?: string; limit?: number; skip?: number } = {}) =>
            fetchWithValidation<ClientListItem[]>(
                `${getBaseUrl()}/api/v1/clients/`,
                token,
                z.array(ClientListItemSchema),
                { params }
            ),

        get: (token: string, id: string) =>
            fetchWithValidation<ClientDetail>(
                `${getBaseUrl()}/api/v1/clients/${id}`,
                token,
                ClientDetailSchema
            ),

        create: (token: string, data: ClientCreate) =>
            fetchWithValidation<ClientDetail>(
                `${getBaseUrl()}/api/v1/clients/`,
                token,
                ClientDetailSchema,
                { method: "POST", data }
            ),

        update: (token: string, id: string, data: ClientUpdate) =>
            fetchWithValidation<ClientDetail>(
                `${getBaseUrl()}/api/v1/clients/${id}`,
                token,
                ClientDetailSchema,
                { method: "PATCH", data }
            ),

        triggerEnrichment: (token: string, id: string) =>
            fetchWithValidation<{ message: string }>(
                `${getBaseUrl()}/api/v1/clients/${id}/enrich`,
                token,
                z.object({ message: z.string() }),
                { method: "POST" }
            ),

        enrichPreview: (token: string, name: string) =>
            fetchWithValidation<EnrichedClientData | null>(
                `${getBaseUrl()}/api/v1/clients/enrich`,
                token,
                EnrichedClientDataSchema.nullable(),
                { method: "POST", data: { query_name: name } }
            ),
    },
    users: {
        updateProfile: (token: string, data: { first_name: string; last_name: string }) =>
            fetchWithValidation<UserProfileResponse>(
                `${getBaseUrl()}/api/v1/users/me`,
                token,
                UserProfileResponseSchema,
                { method: "PATCH", data }
            )
    },
    admin: {
        listOrganizations: (token: string) =>
            fetchWithValidation<Organization[]>(
                `${getBaseUrl()}/api/v1/admin/organizations`,
                token,
                z.array(OrganizationSchema)
            ),

        createOrganization: (token: string, name: string) =>
            fetchWithValidation<Organization>(
                `${getBaseUrl()}/api/v1/admin/organizations`,
                token,
                OrganizationSchema,
                { method: "POST", data: { name } }
            ),

        listInvites: (token: string, orgId: string) =>
            fetchWithValidation<AllowedEmail[]>(
                `${getBaseUrl()}/api/v1/admin/organizations/${orgId}/invites`,
                token,
                z.array(AllowedEmailSchema)
            ),

        inviteUser: (token: string, orgId: string, email: string, role: string) =>
            fetchWithValidation<{ message: string }>(
                `${getBaseUrl()}/api/v1/admin/organizations/${orgId}/users/invite`,
                token,
                z.object({ message: z.string() }),
                { method: "POST", data: { email, role } }
            ),

        deleteInvite: (token: string, inviteId: string) =>
            fetchWithValidation<{ message: string }>(
                `${getBaseUrl()}/api/v1/admin/invites/${inviteId}`,
                token,
                z.object({ message: z.string() }),
                { method: "DELETE" }
            ),

        // Stats endpoints
        getGlobalStats: (token: string) =>
            fetchWithValidation<GlobalStats>(
                `${getBaseUrl()}/api/v1/admin/stats`,
                token,
                GlobalStatsSchema
            ),

        getOrgStats: (token: string, orgId: string) =>
            fetchWithValidation<OrgStats>(
                `${getBaseUrl()}/api/v1/admin/stats/${orgId}`,
                token,
                OrgStatsSchema
            ),

        getUserStats: (token: string, orgId: string, userId: string) =>
            fetchWithValidation<UserStats>(
                `${getBaseUrl()}/api/v1/admin/stats/${orgId}/users/${userId}`,
                token,
                UserStatsSchema
            )
    }
};
