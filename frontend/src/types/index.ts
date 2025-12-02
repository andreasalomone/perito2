import { z } from "zod";

// --- Zod Schemas ---

export const DocumentSchema = z.object({
    id: z.string(),
    filename: z.string(),
    ai_status: z.enum(["pending", "processing", "completed", "error"]),
    created_at: z.string()
});
export type Document = z.infer<typeof DocumentSchema>;

export const ReportVersionSchema = z.object({
    id: z.string(),
    version_number: z.number(),
    is_final: z.boolean(),
    created_at: z.string()
});
export type ReportVersion = z.infer<typeof ReportVersionSchema>;

// Base Case Schema
export const CaseBaseSchema = z.object({
    id: z.string(),
    reference_code: z.string(),
    client_name: z.string().optional().nullable(), // Handle Python None
    status: z.enum(["open", "closed", "processing", "generating", "error"]),
    created_at: z.string(),
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
    id: z.string(),
    status: z.enum(["open", "closed", "processing", "generating", "error"]),
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
