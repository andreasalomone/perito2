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

// Document with signed URL for preview/download
export const DocumentWithUrlSchema = z.object({
    id: z.string().uuid(),
    filename: z.string(),
    mime_type: z.string().optional().nullable(),
    status: z.enum(["PENDING", "PROCESSING", "SUCCESS", "ERROR", "SKIPPED"]),
    can_preview: z.boolean(),
    url: z.string().optional().nullable(),
});
export type DocumentWithUrl = z.infer<typeof DocumentWithUrlSchema>;

export const DocumentsListResponseSchema = z.object({
    documents: z.array(DocumentWithUrlSchema),
    total: z.number(),
    pending_extraction: z.number(),
});
export type DocumentsListResponse = z.infer<typeof DocumentsListResponseSchema>;

export const ReportVersionSchema = z.object({
    id: z.string().uuid(),
    version_number: z.number(),
    is_final: z.boolean(),
    source: z.string().optional().nullable(), // 'preliminary' | 'final' | 'human' | null
    created_at: z.string().datetime(),
    error_message: z.string().optional().nullable(),
    // Google Docs Live Draft support
    is_draft_active: z.boolean().default(false),
    edit_link: z.string().optional().nullable(),
    ai_raw_output: z.string().optional().nullable(),
});
export type ReportVersion = z.infer<typeof ReportVersionSchema>;

// Document Analysis Types (Early Analysis Feature)
// Document Analysis Types (Early Analysis Feature)
export const DocumentAnalysisSchema = z.object({
    id: z.string().uuid(),
    summary: z.string(),
    received_docs: z.array(z.string()),
    missing_docs: z.array(z.string()),
    document_hash: z.string(),
    is_stale: z.boolean(),
    created_at: z.string().datetime(),
});
export type DocumentAnalysis = z.infer<typeof DocumentAnalysisSchema>;

export const DocumentAnalysisResponseSchema = z.object({
    analysis: DocumentAnalysisSchema.nullable(),
    can_update: z.boolean(),
    pending_docs: z.number(),
});
export type DocumentAnalysisResponse = z.infer<typeof DocumentAnalysisResponseSchema>;

export const DocumentAnalysisCreateResponseSchema = z.object({
    analysis: DocumentAnalysisSchema,
    generated: z.boolean(),
});
export type DocumentAnalysisCreateResponse = z.infer<typeof DocumentAnalysisCreateResponseSchema>;

// Preliminary Report Types (Early Analysis Feature)
export const PreliminaryReportSchema = z.object({
    id: z.string().uuid(),
    content: z.string(),
    created_at: z.string().datetime(),
});
export type PreliminaryReport = z.infer<typeof PreliminaryReportSchema>;

export const PreliminaryReportResponseSchema = z.object({
    report: PreliminaryReportSchema.nullable(),
    can_generate: z.boolean(),
    pending_docs: z.number(),
});
export type PreliminaryReportResponse = z.infer<typeof PreliminaryReportResponseSchema>;

export const PreliminaryReportCreateResponseSchema = z.object({
    report: PreliminaryReportSchema,
    generated: z.boolean(),
});
export type PreliminaryReportCreateResponse = z.infer<typeof PreliminaryReportCreateResponseSchema>;

// Client Types
// Client Types
export const ClientSchema = z.object({
    id: z.string(),
    name: z.string(),
    logo_url: z.string().optional().nullable(),
});
export type Client = z.infer<typeof ClientSchema>;

export const ClientCreateSchema = z.object({
    name: z.string().max(255),
    vat_number: z.string().max(50).optional().nullable(),
    logo_url: z.string().max(1024).optional().nullable(),
    address_street: z.string().max(500).optional().nullable(),
    city: z.string().max(100).optional().nullable(),
    zip_code: z.string().max(20).optional().nullable(),
    province: z.string().max(10).optional().nullable(),
    country: z.string().max(100).optional().nullable().default("Italia"),
    website: z.string().max(500).optional().nullable(),
    referente: z.string().max(255).optional().nullable(),
    email: z.string().max(255).optional().nullable(),
    telefono: z.string().max(50).optional().nullable(),
});
export type ClientCreate = z.infer<typeof ClientCreateSchema>;

export const ClientUpdateSchema = ClientCreateSchema.partial();
export type ClientUpdate = z.infer<typeof ClientUpdateSchema>;

export const ClientDetailSchema = ClientCreateSchema.extend({
    id: z.string().uuid(),
    organization_id: z.string().uuid(),
    created_at: z.string().datetime(),
});
export type ClientDetail = z.infer<typeof ClientDetailSchema>;

export const ClientListItemSchema = z.object({
    id: z.string().uuid(),
    name: z.string(),
    logo_url: z.string().optional().nullable(),
    city: z.string().optional().nullable(),
    case_count: z.number().int().default(0),
});
export type ClientListItem = z.infer<typeof ClientListItemSchema>;

export const EnrichedClientDataSchema = z.object({
    full_legal_name: z.string(),
    vat_number: z.string().optional().nullable(),
    address_street: z.string().optional().nullable(),
    city: z.string().optional().nullable(),
    zip_code: z.string().optional().nullable(),
    province: z.string().optional().nullable(),
    country: z.string().optional().nullable(),
    website: z.string().optional().nullable(),
    logo_url: z.string().optional().nullable(),
});
export type EnrichedClientData = z.infer<typeof EnrichedClientDataSchema>;

export const CaseStatusEnum = z.enum(["OPEN", "CLOSED", "ARCHIVED", "PROCESSING", "GENERATING", "ERROR"]);
export type CaseStatusType = z.infer<typeof CaseStatusEnum>;

// Base Case Schema
export const CaseBaseSchema = z.object({
    id: z.string().uuid(),
    organization_id: z.string().uuid(),
    reference_code: z.string(),
    client_name: z.string().optional().nullable(), // Handle Python None
    client_id: z.string().uuid().optional().nullable(), // For linking to client page
    client_logo_url: z.string().optional().nullable(), // Helper from backend (ICE)
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
    assicurato_display: z.string().optional().nullable(), // Computed from assicurato_rel.name
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
    client_logo_url: z.string().optional().nullable(), // Helper from backend (ICE)
    creator_email: z.string().optional().nullable(),
    creator_name: z.string().optional().nullable(),
    assicurato: z.string().optional().nullable(),
    assicurato_display: z.string().optional().nullable(),
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

