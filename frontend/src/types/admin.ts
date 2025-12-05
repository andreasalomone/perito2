import { z } from "zod";

// Admin Type Schemas for API Contract Enforcement

export const OrganizationSchema = z.object({
    id: z.string().uuid(),
    name: z.string(),
    created_at: z.string()
});
export type Organization = z.infer<typeof OrganizationSchema>;

export const AllowedEmailSchema = z.object({
    id: z.string().uuid(),
    email: z.string().email(),
    role: z.string(),
    organization_id: z.string().uuid(),
    created_at: z.string()
});
export type AllowedEmail = z.infer<typeof AllowedEmailSchema>;
