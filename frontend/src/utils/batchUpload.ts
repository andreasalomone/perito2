/**
 * Utility for batch processing file uploads.
 * Handles concurrency, error isolation, and configuration injection.
 */

export interface UploadResult {
    successCount: number;
    failCount: number;
}

export interface FileUploadConfig {
    /** Function to get a fresh auth token */
    getToken: () => Promise<string>;
    /** Function to get a signed URL and GCS path for a file */
    getSignedUrl: (filename: string, contentType: string) => Promise<{ upload_url: string; gcs_path: string }>;
    /** Function to upload the file binary to GCS */
    uploadToGcs: (url: string, file: File, contentType: string) => Promise<void>;
    /** Function to register the document in the backend */
    registerDocument: (filename: string, gcsPath: string, mimeType: string) => Promise<void>;
    /** Optional callback for progress updates (current index, total files) */
    onProgress?: (current: number, total: number) => void;
}

/**
 * Uploads files in batches with controlled concurrency.
 * Failures in one file do not stop the others (Promise.allSettled).
 * 
 * @param files Array of File objects to upload
 * @param config Configuration object containing API callbacks
 * @param batchSize Number of concurrent uploads (default: 4)
 * @returns Summary of successes and failures
 */
export async function batchUploadFiles(
    files: File[],
    config: FileUploadConfig,
    batchSize: number = 4
): Promise<UploadResult> {
    let successCount = 0;
    let failCount = 0;

    // Helper to upload a single file
    const uploadSingleFile = async (file: File): Promise<void> => {
        // Refresh token per file to prevent expiration during long batches
        await config.getToken();

        // 1. Get Signed URL
        const { upload_url, gcs_path } = await config.getSignedUrl(file.name, file.type);

        // 2. Upload to GCS
        await config.uploadToGcs(upload_url, file, file.type);

        // 3. Register Document
        await config.registerDocument(file.name, gcs_path, file.type);
    };

    // Process in batches
    for (let i = 0; i < files.length; i += batchSize) {
        const batch = files.slice(i, i + batchSize);

        // Notify progress start of batch
        config.onProgress?.(i + 1, files.length);

        // Process batch concurrently, catching individual errors
        const results = await Promise.allSettled(
            batch.map(file => uploadSingleFile(file))
        );

        // Tally results
        for (let j = 0; j < results.length; j++) {
            if (results[j].status === 'fulfilled') {
                successCount++;
            } else {
                failCount++;
                console.error(`Failed to upload ${batch[j].name}:`, (results[j] as PromiseRejectedResult).reason);
            }
        }
    }

    return { successCount, failCount };
}
