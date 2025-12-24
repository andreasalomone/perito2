/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

interface NotesDialogProps {
    isOpen: boolean;
    onClose: () => void;
    initialNotes: string;
    onSave: (notes: string) => void;
}

export function NotesDialog({ isOpen, onClose, initialNotes, onSave }: NotesDialogProps) {
    const [notes, setNotes] = useState(initialNotes);

    // Sync state when dialog opens or initialNotes changes
    // This is a valid use case - syncing props to local state for controlled form input
    // eslint-disable-next-line react-hooks/set-state-in-effect
    useEffect(() => {
        setNotes(initialNotes);
    }, [initialNotes, isOpen]);

    const handleSave = () => {
        onSave(notes);
        onClose();
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle>Istruzioni Aggiuntive</DialogTitle>
                    <DialogDescription>
                        Aggiungi note o istruzioni specifiche per la generazione del report.
                        L&apos;IA terrà conto di queste informazioni.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="notes">Note</Label>
                        <Textarea
                            id="notes"
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            placeholder="Es. Enfatizzare i danni alla carrozzeria..."
                            className="min-h-[150px] max-h-[200px] overflow-y-auto"
                        />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Annulla</Button>
                    <Button onClick={handleSave}>Salva</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
