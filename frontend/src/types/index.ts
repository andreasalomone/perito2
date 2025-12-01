export interface Document {
    id: string;
    filename: string;
    gcs_path: string;
    ai_status: "pending" | "processing" | "completed" | "error";
    created_at: string;
}

export interface ReportVersion {
    id: string;
    version_number: number;
    is_final: boolean;
    docx_storage_path: string | null;
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
