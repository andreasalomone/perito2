"use client";

import { WorkflowStep } from "@/hooks/useCaseDetail";
import { cn } from "@/lib/utils";
import { Upload, Sparkles, Eye, CheckCircle, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";

interface StepDefinition {
    id: number;
    label: string;
    description: string;
    icon: React.ComponentType<{ className?: string }>;
}

const STEPS: StepDefinition[] = [
    {
        id: 1,
        label: "Acquisizione",
        description: "Carica i documenti del caso",
        icon: Upload,
    },
    {
        id: 2,
        label: "Elaborazione",
        description: "Analisi AI in corso",
        icon: Sparkles,
    },
    {
        id: 3,
        label: "Revisione",
        description: "Rivedi e scarica la bozza",
        icon: Eye,
    },
    {
        id: 4,
        label: "Chiusura",
        description: "Carica il documento finale",
        icon: CheckCircle,
    },
];

interface WorkflowStepperProps {
    currentStep: WorkflowStep;
    onStepClick?: (step: number) => void;
    className?: string;
}

/**
 * Visual workflow stepper showing the 4 case workflow steps.
 * Supports:
 * - Active/completed/pending states
 * - ERROR state overlay
 * - Backward navigation (clicking Step 1 from Step 3)
 */
export function WorkflowStepper({
    currentStep,
    onStepClick,
    className,
}: WorkflowStepperProps) {
    const isError = currentStep === "ERROR";
    const numericStep = isError ? 1 : currentStep;

    const getStepStatus = (stepId: number): "completed" | "active" | "pending" | "error" => {
        if (isError) return "error";
        if (stepId < numericStep) return "completed";
        if (stepId === numericStep) return "active";
        return "pending";
    };

    const canNavigateToStep = (stepId: number): boolean => {
        if (isError) return false;
        // Can go back to Step 1 from Step 3 (to modify documents)
        if (stepId === 1 && numericStep === 3) return true;
        return false;
    };

    return (
        <nav className={cn("flex flex-col gap-1", className)} aria-label="Workflow progress">
            {/* Error banner if in error state */}
            {isError && (
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex items-center gap-2 p-3 mb-3 text-sm text-red-700 bg-red-50 dark:bg-red-950/30 dark:text-red-400 rounded-lg border border-red-200 dark:border-red-800"
                >
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />
                    <span>Errore durante l&apos;elaborazione</span>
                </motion.div>
            )}

            {/* Steps */}
            {STEPS.map((step, index) => {
                const status = getStepStatus(step.id);
                const Icon = step.icon;
                const isClickable = canNavigateToStep(step.id);
                const isLast = index === STEPS.length - 1;

                return (
                    <div key={step.id} className="relative">
                        {/* Step item */}
                        <motion.button
                            type="button"
                            disabled={!isClickable}
                            onClick={() => isClickable && onStepClick?.(step.id)}
                            className={cn(
                                "w-full flex items-start gap-3 p-3 rounded-lg text-left transition-colors",
                                "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
                                {
                                    // Completed
                                    "bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800":
                                        status === "completed",
                                    // Active
                                    "bg-primary/10 border-2 border-primary shadow-sm":
                                        status === "active",
                                    // Pending
                                    "bg-muted/50 border border-transparent opacity-60":
                                        status === "pending",
                                    // Error
                                    "bg-red-50/50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 opacity-70":
                                        status === "error",
                                    // Clickable
                                    "cursor-pointer hover:bg-green-100 dark:hover:bg-green-900/30":
                                        isClickable,
                                    "cursor-default": !isClickable,
                                }
                            )}
                            whileHover={isClickable ? { scale: 1.02 } : {}}
                            whileTap={isClickable ? { scale: 0.98 } : {}}
                        >
                            {/* Icon */}
                            <div
                                className={cn(
                                    "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
                                    {
                                        "bg-green-500 text-white": status === "completed",
                                        "bg-primary text-primary-foreground": status === "active",
                                        "bg-muted text-muted-foreground": status === "pending",
                                        "bg-red-500 text-white": status === "error",
                                    }
                                )}
                            >
                                {status === "completed" ? (
                                    <CheckCircle className="h-4 w-4" />
                                ) : status === "error" ? (
                                    <AlertCircle className="h-4 w-4" />
                                ) : (
                                    <Icon className="h-4 w-4" />
                                )}
                            </div>

                            {/* Text */}
                            <div className="flex-1 min-w-0">
                                <div
                                    className={cn("font-medium text-sm", {
                                        "text-green-700 dark:text-green-400": status === "completed",
                                        "text-primary": status === "active",
                                        "text-muted-foreground": status === "pending",
                                        "text-red-700 dark:text-red-400": status === "error",
                                    })}
                                >
                                    {step.label}
                                </div>
                                <div className="text-xs text-muted-foreground truncate">
                                    {step.description}
                                </div>
                                {isClickable && (
                                    <div className="text-xs text-primary mt-1 font-medium">
                                        Modifica documenti →
                                    </div>
                                )}
                            </div>
                        </motion.button>

                        {/* Connector line */}
                        {!isLast && (
                            <div
                                className={cn(
                                    "absolute left-[1.375rem] top-[3.25rem] w-0.5 h-4",
                                    status === "completed" || status === "active"
                                        ? "bg-green-300 dark:bg-green-700"
                                        : "bg-muted"
                                )}
                            />
                        )}
                    </div>
                );
            })}
        </nav>
    );
}
