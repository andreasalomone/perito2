"use client";

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Loader2 } from "lucide-react";
import { useState } from "react";

interface ConfirmDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => Promise<void> | void;
    title: string;
    description: string;
    confirmText?: string;
    cancelText?: string;
    variant?: "danger" | "warning" | "default";
}

/**
 * Reusable confirmation dialog for destructive actions.
 * Replaces native `confirm()` with a styled, accessible modal.
 */
export function ConfirmDialog({
    isOpen,
    onClose,
    onConfirm,
    title,
    description,
    confirmText = "Conferma",
    cancelText = "Annulla",
    variant = "danger",
}: Readonly<ConfirmDialogProps>) {
    const [isLoading, setIsLoading] = useState(false);

    const handleConfirm = async () => {
        setIsLoading(true);
        try {
            await onConfirm();
            onClose();
        } catch {
            // Error handled by caller via toast
        } finally {
            setIsLoading(false);
        }
    };

    const getButtonVariant = () => {
        switch (variant) {
            case "danger":
                return "destructive";
            case "warning":
                return "default";
            default:
                return "default";
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent showCloseButton={false}>
                <DialogHeader>
                    <div className="flex items-center gap-3">
                        {variant === "danger" && (
                            <div className="p-2 bg-destructive/10 rounded-full">
                                <AlertTriangle className="h-5 w-5 text-destructive" />
                            </div>
                        )}
                        <DialogTitle className="text-base">{title}</DialogTitle>
                    </div>
                    <DialogDescription className="pt-2">
                        {description}
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={onClose}
                        disabled={isLoading}
                    >
                        {cancelText}
                    </Button>
                    <Button
                        variant={getButtonVariant()}
                        onClick={handleConfirm}
                        disabled={isLoading}
                    >
                        {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                        {confirmText}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
