import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { FileText, Building2, Briefcase } from "lucide-react";
import { TemplateType } from "@/components/cases/VersionItem";

interface TemplateSelectionDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onSelect: (template: TemplateType) => void;
    title?: string;
    description?: string;
}

export function TemplateSelectionDialog({
    isOpen,
    onClose,
    onSelect,
    title = "Scarica Report",
    description = "Seleziona il modello di documento da generare."
}: TemplateSelectionDialogProps) {
    const handleSelect = (template: TemplateType) => {
        onSelect(template);
        onClose();
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                    <DialogDescription>
                        {description}
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <Button
                        variant="outline"
                        className="h-auto p-4 flex flex-col items-center gap-2 hover:bg-accent/50 hover:border-primary"
                        onClick={() => handleSelect('default')}
                    >
                        <FileText className="h-6 w-6" />
                        <div className="text-center">
                            <div className="font-semibold">Standard</div>
                            <div className="text-xs text-muted-foreground">Formato generico non brandizzato</div>
                        </div>
                    </Button>

                    <Button
                        variant="outline"
                        className="h-auto p-4 flex flex-col items-center gap-2 hover:bg-accent/50 hover:border-primary"
                        onClick={() => handleSelect('bn')}
                    >
                        <Building2 className="h-6 w-6" />
                        <div className="text-center">
                            <div className="font-semibold">BN Surveys</div>
                            <div className="text-xs text-muted-foreground">Template specifico per BN</div>
                        </div>
                    </Button>

                    <Button
                        variant="outline"
                        className="h-auto p-4 flex flex-col items-center gap-2 hover:bg-accent/50 hover:border-primary"
                        onClick={() => handleSelect('salomone')}
                    >
                        <Briefcase className="h-6 w-6" />
                        <div className="text-center">
                            <div className="font-semibold">Salomone e Associati</div>
                            <div className="text-xs text-muted-foreground">Template ufficiale Salomone</div>
                        </div>
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
