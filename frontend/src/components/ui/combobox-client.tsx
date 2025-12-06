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
import { Client } from "@/types"
import { useDebounce } from "@/hooks/useDebounce" // Assuming we have this or I need to create it

interface ClientComboboxProps {
    value?: string
    onChange: (value: string) => void
    disabled?: boolean
}

export function ClientCombobox({ value, onChange, disabled }: ClientComboboxProps) {
    const { getToken } = useAuth()
    const [open, setOpen] = React.useState(false)
    const [query, setQuery] = React.useState("")
    const [clients, setClients] = React.useState<Client[]>([])
    const [loading, setLoading] = React.useState(false)

    // Debounce query to prevent spamming API
    // If useDebounce doesn't exist, I'll implement a simple effect
    const [debouncedQuery, setDebouncedQuery] = React.useState(query)

    React.useEffect(() => {
        const timer = setTimeout(() => setDebouncedQuery(query), 300)
        return () => clearTimeout(timer)
    }, [query])

    React.useEffect(() => {
        let active = true

        const fetchClients = async () => {
            if (!open) return

            setLoading(true)
            try {
                const token = await getToken()
                if (token) {
                    // If query is empty, we search for "" to get initial list
                    const res = await api.clients.search(token, debouncedQuery)
                    if (active) setClients(res)
                }
            } catch (err) {
                console.error("Failed to fetch clients", err)
            } finally {
                if (active) setLoading(false)
            }
        }

        fetchClients()

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
                        ? (clients.find((client) => client.name === value)?.name || value)
                        : "Seleziona cliente..."}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
                <Command shouldFilter={false}>
                    <CommandInput
                        placeholder="Cerca cliente..."
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

                        {!loading && clients.length === 0 && !query && (
                            <CommandEmpty>Nessun cliente trovato.</CommandEmpty>
                        )}

                        {!loading && clients.length > 0 && (
                            <CommandGroup heading="Clienti Esistenti" forceMount>
                                {clients.map((client) => (
                                    <CommandItem
                                        key={client.id}
                                        value={client.name}
                                        onSelect={handleSelect}
                                        className="cursor-pointer"
                                    >
                                        <Check
                                            className={cn(
                                                "mr-2 h-4 w-4",
                                                value === client.name ? "opacity-100" : "opacity-0"
                                            )}
                                        />
                                        {client.name}
                                    </CommandItem>
                                ))}
                            </CommandGroup>
                        )}

                        {query && !clients.find(c => c.name.toLowerCase() === query.toLowerCase()) && (
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
