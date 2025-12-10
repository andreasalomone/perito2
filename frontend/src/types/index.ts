import { z } from "zod";

// --- Zod Schemas ---

export const DocumentSchema = z.object({
    id: z.string().uuid(),
    filename: z.string(),
    ai_status: z.enum(["PENDING", "PROCESSING", "SUCCESS", "ERROR", "SKIPPED"]),
    created_at: z.string().datetime(),
    error_message: z.string().optional().nullable()
});
export type Document = z.infer<typeof DocumentSchema>;

export const ReportVersionSchema = z.object({
    id: z.string().uuid(),
    version_number: z.number(),
    is_final: z.boolean(),
    created_at: z.string().datetime(),
    error_message: z.string().optional().nullable(),
    // Google Docs Live Draft support
    is_draft_active: z.boolean().default(false),
    edit_link: z.string().optional().nullable(),
});
export type ReportVersion = z.infer<typeof ReportVersionSchema>;

// Client Types
export const ClientSchema = z.object({
    id: z.string(),
    name: z.string(),
});
export type Client = z.infer<typeof ClientSchema>;

export const CaseStatusEnum = z.enum(["OPEN", "CLOSED", "ARCHIVED", "PROCESSING", "GENERATING", "ERROR"]);
export type CaseStatusType = z.infer<typeof CaseStatusEnum>;

// Base Case Schema
export const CaseBaseSchema = z.object({
    id: z.string().uuid(),
    organization_id: z.string().uuid(),
    reference_code: z.string(),
    client_name: z.string().optional().nullable(), // Handle Python None
    status: z.enum(["OPEN", "CLOSED", "ARCHIVED", "PROCESSING", "GENERATING", "ERROR"]),
    created_at: z.string().datetime(),
    error_message: z.string().optional().nullable(),

    // Business fields
    ns_rif: z.number().int().optional().nullable(),
    polizza: z.string().optional().nullable(),
    tipo_perizia: z.string().optional().nullable(),
    merce: z.string().optional().nullable(),
    descrizione_merce: z.string().optional().nullable(),
    riserva: z.number().optional().nullable(),
    importo_liquidato: z.number().optional().nullable(),
    perito: z.string().optional().nullable(),
    cliente: z.string().optional().nullable(),
    rif_cliente: z.string().optional().nullable(),
    gestore: z.string().optional().nullable(),
    assicurato: z.string().optional().nullable(),
    riferimento_assicurato: z.string().optional().nullable(),
    mittenti: z.string().optional().nullable(),
    broker: z.string().optional().nullable(),
    riferimento_broker: z.string().optional().nullable(),
    destinatari: z.string().optional().nullable(),
    mezzo_di_trasporto: z.string().optional().nullable(),
    descrizione_mezzo_di_trasporto: z.string().optional().nullable(),
    luogo_intervento: z.string().optional().nullable(),
    genere_lavorazione: z.string().optional().nullable(),
    data_sinistro: z.string().optional().nullable(), // YYYY-MM-DD
    data_incarico: z.string().optional().nullable(), // YYYY-MM-DD
    note: z.string().optional().nullable(),

    // AI
    ai_summary: z.string().optional().nullable(), // AI-generated markdown summary
});

// 1. Summary (List View) - NO documents/versions
export const CaseSummarySchema = z.object({
    id: z.string(),
    reference_code: z.string(),
    organization_id: z.string(),
    client_id: z.string().optional().nullable(),
    client: ClientSchema.optional().nullable(),
    status: CaseStatusEnum,
    created_at: z.string(),
    client_name: z.string().optional().nullable(), // Helper from backend
    creator_email: z.string().optional().nullable(), // New field
});
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
    first_name?: string | null;
    last_name?: string | null;
    is_profile_complete: boolean;
    organization_name: string;
    created_at: string;
    last_login?: string | null;
}

