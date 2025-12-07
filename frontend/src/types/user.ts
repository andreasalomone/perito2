import { z } from "zod";

export const UserProfileResponseSchema = z.object({
    id: z.string(),
    email: z.string().email(),
    organization_id: z.string(),
    role: z.string(),
    first_name: z.string().nullable().optional(),
    last_name: z.string().nullable().optional(),
    is_profile_complete: z.boolean(),
});

export type UserProfileResponse = z.infer<typeof UserProfileResponseSchema>;
