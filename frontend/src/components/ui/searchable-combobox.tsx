"use client"

import * as React from "react"
import { CheckIcon, ChevronsUpDownIcon, PlusIcon, Loader2Icon } from "lucide-react"
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

interface SearchableComboboxProps<T> {
    value?: string
    onChange: (value: string) => void
    disabled?: boolean
    // Data fetching
    fetchFn: (query: string, limit: number) => Promise<T[]>
    getItemId: (item: T) => string
    getItemLabel: (item: T) => string
    // Customization
    placeholder?: string
    searchPlaceholder?: string
    emptyMessage?: string
    groupHeading?: string
    /** Allow creating new items by typing. Default: true */
    allowCreate?: boolean
}

export function SearchableCombobox<T>({
    value,
    onChange,
    disabled,
    fetchFn,
    getItemId,
    getItemLabel,
    placeholder = "Seleziona...",
    searchPlaceholder = "Cerca...",
    emptyMessage = "Nessun risultato trovato.",
    groupHeading = "Risultati",
    allowCreate = true,
}: SearchableComboboxProps<T>) {
    const [open, setOpen] = React.useState(false)
    const [query, setQuery] = React.useState("")
    const [items, setItems] = React.useState<T[]>([])
    const [loading, setLoading] = React.useState(false)

    // Debounce query to prevent spamming API
    const [debouncedQuery, setDebouncedQuery] = React.useState(query)

    React.useEffect(() => {
        const timer = setTimeout(() => setDebouncedQuery(query), 300)
        return () => clearTimeout(timer)
    }, [query])

    React.useEffect(() => {
        let active = true

        const fetchItems = async () => {
            if (!open) return

            setLoading(true)
            try {
                const res = await fetchFn(debouncedQuery, 10)
                if (active) setItems(res)
            } catch (err) {
                console.error("Failed to fetch items", err)
            } finally {
                if (active) setLoading(false)
            }
        }

        fetchItems()

        return () => { active = false }
    }, [open, debouncedQuery, fetchFn])

    const handleSelect = (currentValue: string) => {
        onChange(currentValue)
        setOpen(false)
    }

    // Find the display label for the current value
    const displayLabel = React.useMemo(() => {
        if (!value) return null
        const found = items.find((item) => getItemLabel(item) === value)
        return found ? getItemLabel(found) : value
    }, [value, items, getItemLabel])

    // Check if query matches an existing item (case-insensitive)
    const queryMatchesExisting = React.useMemo(() => {
        return items.some(item => getItemLabel(item).toLowerCase() === query.toLowerCase())
    }, [items, query, getItemLabel])

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    data-slot="searchable-combobox-trigger"
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    className={cn(
                        "w-full justify-between font-normal",
                        "[&_svg:not([class*='size-'])]:size-4",
                        !displayLabel && "text-muted-foreground"
                    )}
                    disabled={disabled}
                >
                    <span className="truncate">{displayLabel || placeholder}</span>
                    <ChevronsUpDownIcon className="text-muted-foreground ml-2 shrink-0 opacity-50" />
                </Button>
            </PopoverTrigger>
            <PopoverContent
                data-slot="searchable-combobox-content"
                className={cn(
                    "w-[--radix-popover-trigger-width] p-0",
                    "data-[state=open]:animate-in data-[state=closed]:animate-out",
                    "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
                    "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
                    "data-[side=bottom]:slide-in-from-top-2 data-[side=top]:slide-in-from-bottom-2"
                )}
            >
                <Command shouldFilter={false}>
                    <CommandInput
                        placeholder={searchPlaceholder}
                        value={query}
                        onValueChange={setQuery}
                    />
                    <CommandList className="max-h-72 overflow-y-auto overscroll-contain">
                        {loading && (
                            <div className="py-6 text-center text-sm text-muted-foreground flex items-center justify-center">
                                <Loader2Icon className="size-4 animate-spin mr-2" />
                                Caricamento...
                            </div>
                        )}

                        {!loading && items.length === 0 && !query && (
                            <CommandEmpty>{emptyMessage}</CommandEmpty>
                        )}

                        {!loading && items.length > 0 && (
                            <CommandGroup heading={groupHeading} forceMount>
                                {items.map((item) => (
                                    <CommandItem
                                        key={getItemId(item)}
                                        value={getItemLabel(item)}
                                        onSelect={handleSelect}
                                        className={cn(
                                            "cursor-pointer gap-2 pr-8 relative",
                                            "[&_svg:not([class*='size-'])]:size-4",
                                            "[&_svg]:pointer-events-none [&_svg]:shrink-0"
                                        )}
                                    >
                                        {getItemLabel(item)}
                                        <span className="pointer-events-none absolute right-2 flex size-4 items-center justify-center">
                                            <CheckIcon
                                                className={cn(
                                                    "size-4",
                                                    value === getItemLabel(item) ? "opacity-100" : "opacity-0"
                                                )}
                                            />
                                        </span>
                                    </CommandItem>
                                ))}
                            </CommandGroup>
                        )}

                        {allowCreate && query && !queryMatchesExisting && (
                            <>
                                <CommandSeparator />
                                <CommandGroup heading="Nuovo" forceMount>
                                    <CommandItem
                                        value={`crea-${query}`}
                                        onSelect={() => handleSelect(query)}
                                        className={cn(
                                            "text-primary cursor-pointer gap-2",
                                            "[&_svg:not([class*='size-'])]:size-4",
                                            "[&_svg]:pointer-events-none [&_svg]:shrink-0"
                                        )}
                                    >
                                        <PlusIcon />
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
