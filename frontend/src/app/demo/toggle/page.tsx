import { PremiumToggle } from "@/components/ui/bouncy-toggle"

export default function Page() {

    return (
        <div className="min-h-screen bg-background flex items-center justify-center p-8 w-full">
            <div className="flex flex-col gap-8">
                <div className="flex flex-col items-center gap-6">
                    <div className="text-center space-y-2">
                        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-medium">Premium Component</p>
                        <h1 className="text-2xl font-semibold text-foreground tracking-tight">Toggle Switch</h1>
                    </div>

                    <div className="p-8 rounded-2xl bg-muted/30 border border-border/50">
                        <PremiumToggle defaultChecked={true} onChange={(checked) => console.log("Main toggle:", checked)} />
                    </div>
                </div>

            </div>
        </div>
    )
}
