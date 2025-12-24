import { z } from "zod";

// Stats Type Schemas for API Contract Enforcement

export const CaseCountsByStatusSchema = z.object({
    OPEN: z.number(),
    CLOSED: z.number(),
    ERROR: z.number(),
    GENERATING: z.number(),
    PROCESSING: z.number(),
    ARCHIVED: z.number(),
});
export type CaseCountsByStatus = z.infer<typeof CaseCountsByStatusSchema>;

export const UserSummarySchema = z.object({
    id: z.string(), // Firebase UID - string, not UUID
    email: z.string().email(),
    first_name: z.string().nullable(),
    last_name: z.string().nullable(),
});
export type UserSummary = z.infer<typeof UserSummarySchema>;

export const GlobalStatsSchema = z.object({
    org_count: z.number(),
    user_count: z.number(),
    case_counts: CaseCountsByStatusSchema,
    document_count: z.number(),
    report_count: z.number(),
    gcs_bucket_size_gb: z.number().nullable(),
});
export type GlobalStats = z.infer<typeof GlobalStatsSchema>;

export const OrgStatsSchema = z.object({
    org_id: z.string(),
    org_name: z.string(),
    user_count: z.number(),
    case_counts: CaseCountsByStatusSchema,
    document_count: z.number(),
    users: z.array(UserSummarySchema),
});
export type OrgStats = z.infer<typeof OrgStatsSchema>;

export const UserCaseItemSchema = z.object({
    id: z.string(),
    reference_code: z.string().nullable(),
    created_at: z.string(),
    has_dati_generali: z.boolean(),
    has_doc_analysis: z.boolean(),
    has_prelim_report: z.boolean(),
    has_final_report: z.boolean(),
});
export type UserCaseItem = z.infer<typeof UserCaseItemSchema>;

export const UserStatsSchema = z.object({
    user_id: z.string(),
    user_email: z.string().email(),
    total_cases: z.number(),
    cases_today: z.number(),
    cases_last_7_days: z.number(),
    cases_by_status: CaseCountsByStatusSchema,
    cases: z.array(UserCaseItemSchema).default([]),
});
export type UserStats = z.infer<typeof UserStatsSchema>;
