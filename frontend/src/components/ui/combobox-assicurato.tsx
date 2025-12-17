"use client"

import * as React from "react"
import { Check, ChevronsUpDown, Plus, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
    CommandSeparator,
} from "@/components/ui/command"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"
import { useAuth } from "@/context/AuthContext"
import { api } from "@/lib/api"

interface Assicurato {
    id: string
    name: string
}

interface AssicuratoComboboxProps {
    value?: string
    onChange: (value: string) => void
    disabled?: boolean
}

export function AssicuratoCombobox({ value, onChange, disabled }: AssicuratoComboboxProps) {
    const { getToken } = useAuth()
    const [open, setOpen] = React.useState(false)
    const [query, setQuery] = React.useState("")
    const [assicurati, setAssicurati] = React.useState<Assicurato[]>([])
    const [loading, setLoading] = React.useState(false)

    // Debounce query to prevent spamming API
    const [debouncedQuery, setDebouncedQuery] = React.useState(query)

    React.useEffect(() => {
        const timer = setTimeout(() => setDebouncedQuery(query), 300)
        return () => clearTimeout(timer)
    }, [query])

    React.useEffect(() => {
        let active = true

        const fetchAssicurati = async () => {
            if (!open) return

            setLoading(true)
            try {
                const token = await getToken()
                if (token) {
                    const res = await api.assicurati.list(token, { q: debouncedQuery, limit: 10 })
                    if (active) setAssicurati(res)
                }
            } catch (err) {
                console.error("Failed to fetch assicurati", err)
            } finally {
                if (active) setLoading(false)
            }
        }

        fetchAssicurati()

        return () => { active = false }
    }, [open, debouncedQuery, getToken])

    const handleSelect = (currentValue: string) => {
        onChange(currentValue)
        setOpen(false)
    }

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    className="w-full justify-between"
                    disabled={disabled}
                >
                    {value
                        ? (assicurati.find((a) => a.name === value)?.name || value)
                        : "Seleziona assicurato..."}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
                <Command shouldFilter={false}>
                    <CommandInput
                        placeholder="Cerca assicurato..."
                        value={query}
                        onValueChange={setQuery}
                    />
                    <CommandList>
                        {loading && (
                            <div className="py-6 text-center text-sm text-muted-foreground flex items-center justify-center">
                                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                Caricamento...
                            </div>
                        )}

                        {!loading && assicurati.length === 0 && !query && (
                            <CommandEmpty>Nessun assicurato trovato.</CommandEmpty>
                        )}

                        {!loading && assicurati.length > 0 && (
                            <CommandGroup heading="Assicurati Esistenti" forceMount>
                                {assicurati.map((assicurato) => (
                                    <CommandItem
                                        key={assicurato.id}
                                        value={assicurato.name}
                                        onSelect={handleSelect}
                                        className="cursor-pointer"
                                    >
                                        <Check
                                            className={cn(
                                                "mr-2 h-4 w-4",
                                                value === assicurato.name ? "opacity-100" : "opacity-0"
                                            )}
                                        />
                                        {assicurato.name}
                                    </CommandItem>
                                ))}
                            </CommandGroup>
                        )}

                        {query && !assicurati.find(a => a.name.toLowerCase() === query.toLowerCase()) && (
                            <>
                                <CommandSeparator />
                                <CommandGroup heading="Nuovo" forceMount>
                                    <CommandItem
                                        value={`crea-${query}`}
                                        onSelect={() => handleSelect(query)}
                                        className="text-blue-500 cursor-pointer"
                                    >
                                        <Plus className="mr-2 h-4 w-4" />
                                        Crea "{query}"
                                    </CommandItem>
                                </CommandGroup>
                            </>
                        )}
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    )
}
