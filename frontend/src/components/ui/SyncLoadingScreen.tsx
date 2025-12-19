"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LiquidGlassCard } from "@/components/kokonutui/liquid-glass-card";
import { Loader2 } from "lucide-react";

const MESSAGES = [
    "Sincronizzazione in corso...",
    "Preparazione dell'area di lavoro...",
    "Verifica delle credenziali...",
    "Quasi pronto...",
    "Ottimizzazione dell'esperienza..."
];

export function SyncLoadingScreen() {
    const [messageIndex, setMessageIndex] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setMessageIndex((prev) => (prev + 1) % MESSAGES.length);
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="relative flex items-center justify-center min-h-screen overflow-hidden bg-background">
            {/* Premium Background Elements */}
            <div className="absolute inset-0 z-0">
                <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-500/10 blur-[120px] rounded-full animate-pulse" />
                <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-indigo-500/10 blur-[120px] rounded-full animate-pulse [animation-delay:2s]" />
                <div className="noise-bg opacity-[0.02]" />
            </div>

            <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="relative z-10 w-full max-w-sm px-4"
            >
                <LiquidGlassCard glassSize="lg" className="border-border/50 bg-card/30 shadow-2xl backdrop-blur-md">
                    <div className="flex flex-col items-center py-6 text-center">
                        <div className="relative mb-8">
                            {/* Outer Glow */}
                            <motion.div
                                animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.6, 0.3] }}
                                transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
                                className="absolute inset-0 bg-blue-500/20 blur-xl rounded-full"
                            />

                            <div className="relative flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/5 border border-primary/10 shadow-inner">
                                <Loader2 className="w-8 h-8 text-primary animate-spin" strokeWidth={1.5} />
                            </div>
                        </div>

                        <div className="h-14 flex items-center justify-center">
                            <AnimatePresence mode="wait">
                                <motion.p
                                    key={messageIndex}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: -10 }}
                                    transition={{ duration: 0.5, ease: "easeInOut" }}
                                    className="text-lg font-medium text-foreground/80 tracking-tight"
                                >
                                    {MESSAGES[messageIndex]}
                                </motion.p>
                            </AnimatePresence>
                        </div>

                        <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: "100%" }}
                            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                            className="mt-8 h-[2px] w-full bg-muted overflow-hidden relative"
                        >
                            <motion.div
                                animate={{ x: ["-100%", "100%"] }}
                                transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
                                className="absolute inset-0 bg-gradient-to-r from-transparent via-primary to-transparent w-[50%]"
                            />
                        </motion.div>
                    </div>
                </LiquidGlassCard>
            </motion.div>
        </div>
    );
}

export default SyncLoadingScreen;
