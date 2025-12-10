import { cookies } from "next/headers";
import { SidebarProvider } from "@/hooks/use-sidebar";
import { DashboardLayoutClient } from "@/components/dashboard/DashboardLayoutClient";

export default async function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const cookieStore = await cookies();
    const defaultOpen = cookieStore.get("sidebar:state")?.value !== "false";

    return (
        <SidebarProvider defaultOpen={defaultOpen}>
            <DashboardLayoutClient>{children}</DashboardLayoutClient>
        </SidebarProvider>
    );
}

