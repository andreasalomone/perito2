export interface Document {
    id: string;
    filename: string;
    ai_status: "pending" | "processing" | "completed" | "error";
    created_at: string;
}

export interface ReportVersion {
    id: string;
    version_number: number;
    is_final: boolean;
    // REMOVED: docx_storage_path (Security Risk)
    created_at: string;
}

export interface Case {
    id: string;
    reference_code: string;
    client_name?: string;
    status: "open" | "closed";
    created_at: string;
    documents: Document[];
    report_versions: ReportVersion[];
}

// Lightweight status for polling
export interface CaseStatus {
    id: string;
    status: "open" | "closed";
    documents: Document[];
    is_generating: boolean;
}

export interface DBUser {
    id: string;
    email: string;
    organization_id: string;
    role: string;
}
