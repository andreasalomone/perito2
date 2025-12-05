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
    Client
} from "@/types";
import { OrganizationSchema, AllowedEmailSchema, Organization, AllowedEmail } from "@/types/admin";
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

        getStatus: (token: string, id: string) =>
            fetchWithValidation<CaseStatus>(
                `${getBaseUrl()}/api/v1/cases/${id}/status`,
                token,
                CaseStatusSchema
            )
    },
    clients: {
        search: (token: string, query: string) =>
            fetchWithValidation<Client[]>(
                `${getBaseUrl()}/api/v1/clients/`,
                token,
                z.array(ClientSchema),
                { params: query ? { q: query } : {} }
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
            )
    }
};
