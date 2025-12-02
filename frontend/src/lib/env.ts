export function getEnv(key: string): string | undefined {
    if (typeof window !== "undefined" && (window as any).__ENV__) {
        return (window as any).__ENV__[key];
    }
    return process.env[key];
}
