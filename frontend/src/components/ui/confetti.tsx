"use client";

import { useCallback, useRef, useEffect } from "react";
import confetti from "canvas-confetti";

// Celebration colors - encapsulated in this component
const CELEBRATION_COLORS = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ec4899'];

/**
 * useConfetti - Hook for triggering celebration confetti
 *
 * Returns a triggerConfetti function that fires confetti bursts from both sides.
 */
export function useConfetti() {
    const triggerConfetti = useCallback(() => {
        // First burst from left
        confetti({
            particleCount: 100,
            spread: 70,
            origin: { x: 0.2, y: 0.6 },
            colors: CELEBRATION_COLORS,
        });
        // Second burst from right (slightly delayed)
        setTimeout(() => {
            confetti({
                particleCount: 100,
                spread: 70,
                origin: { x: 0.8, y: 0.6 },
                colors: CELEBRATION_COLORS,
            });
        }, 150);
    }, []);

    return { triggerConfetti };
}

/**
 * useConfettiOnTransition - Hook that triggers confetti when a condition transitions
 *
 * @param isActive - Current active state
 * @param hasResult - Whether there's a result to celebrate
 */
export function useConfettiOnTransition(isActive: boolean, hasResult: boolean) {
    const { triggerConfetti } = useConfetti();
    const prevActive = useRef<boolean | null>(null);

    useEffect(() => {
        // Only fire when transitioning from active (true) to not active (false)
        // AND there's a result (successful completion)
        if (prevActive.current === true && isActive === false && hasResult) {
            triggerConfetti();
        }
        prevActive.current = isActive;
    }, [isActive, hasResult, triggerConfetti]);
}

/**
 * useConfettiOnStreamState - Hook that triggers confetti when stream state transitions to "done"
 *
 * @param state - Current stream state ("idle" | "thinking" | "streaming" | "done" | "error")
 */
export function useConfettiOnStreamState(state: string) {
    const { triggerConfetti } = useConfetti();
    const prevState = useRef<string | null>(null);

    useEffect(() => {
        const wasActive = prevState.current === "thinking" || prevState.current === "streaming";
        if (wasActive && state === "done") {
            triggerConfetti();
        }
        prevState.current = state;
    }, [state, triggerConfetti]);
}
