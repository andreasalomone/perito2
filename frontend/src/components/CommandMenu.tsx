"use client"

import * as React from "react"
import {
    CommandDialog,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
    CommandSeparator,
} from "@/components/ui/command"
import { useRouter } from "next/navigation"
import { FileText, Plus, LayoutDashboard, Settings } from "lucide-react"

export function CommandMenu() {
    const [open, setOpen] = React.useState(false)
    const router = useRouter()

    React.useEffect(() => {
        const down = (e: KeyboardEvent) => {
            if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault()
                setOpen((open) => !open)
            }
        }
        document.addEventListener("keydown", down)
        return () => document.removeEventListener("keydown", down)
    }, [])

    const runCommand = React.useCallback((command: () => unknown) => {
        setOpen(false)
        command()
    }, [])

    return (
        <CommandDialog open={open} onOpenChange={setOpen}>
            <CommandInput placeholder="Cerca comandi..." />
            <CommandList>
                <CommandEmpty>Nessun risultato.</CommandEmpty>
                <CommandGroup heading="Navigazione">
                    <CommandItem onSelect={() => runCommand(() => router.push("/dashboard"))}>
                        <LayoutDashboard className="mr-2 h-4 w-4" />
                        Dashboard
                    </CommandItem>
                    <CommandItem onSelect={() => runCommand(() => router.push("/dashboard/create"))}>
                        <Plus className="mr-2 h-4 w-4" />
                        Nuovo Fascicolo
                    </CommandItem>
                </CommandGroup>
                <CommandSeparator />
                <CommandGroup heading="Impostazioni">
                    <CommandItem onSelect={() => runCommand(() => console.log("Settings"))}>
                        <Settings className="mr-2 h-4 w-4" />
                        Impostazioni
                    </CommandItem>
                </CommandGroup>
            </CommandList>
        </CommandDialog>
    )
}
