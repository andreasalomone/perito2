import { z } from "zod";

// --- Zod Schemas ---

export const DocumentSchema = z.object({
    id: z.string().uuid(),
    filename: z.string(),
    ai_status: z.enum(["PENDING", "PROCESSING", "SUCCESS", "ERROR"]),
    created_at: z.string().datetime()
});
export type Document = z.infer<typeof DocumentSchema>;

export const ReportVersionSchema = z.object({
    id: z.string().uuid(),
    version_number: z.number(),
    is_final: z.boolean(),
    created_at: z.string().datetime()
});
export type ReportVersion = z.infer<typeof ReportVersionSchema>;

// Base Case Schema
export const CaseBaseSchema = z.object({
    id: z.string().uuid(),
    organization_id: z.string().uuid(),
    reference_code: z.string(),
    client_name: z.string().optional().nullable(), // Handle Python None
    status: z.enum(["OPEN", "CLOSED", "ARCHIVED", "PROCESSING", "GENERATING", "ERROR"]),
    created_at: z.string().datetime(),
});

// 1. Summary (List View) - NO documents/versions
export const CaseSummarySchema = CaseBaseSchema;
export type CaseSummary = z.infer<typeof CaseSummarySchema>;

// 2. Detail (Workspace View) - HAS documents/versions
export const CaseDetailSchema = CaseBaseSchema.extend({
    documents: z.array(DocumentSchema),
    report_versions: z.array(ReportVersionSchema)
});
export type CaseDetail = z.infer<typeof CaseDetailSchema>;

// Lightweight status for polling
export const CaseStatusSchema = z.object({
    id: z.string().uuid(),
    status: z.enum(["OPEN", "CLOSED", "ARCHIVED", "PROCESSING", "GENERATING", "ERROR"]),
    documents: z.array(DocumentSchema),
    is_generating: z.boolean()
});
export type CaseStatus = z.infer<typeof CaseStatusSchema>;

export interface DBUser {
    id: string;
    email: string;
    organization_id: string;
    role: string;
}
