"use client";
import { createContext, useContext, useEffect } from "react";

interface ConfigContextType {
    apiUrl: string;
}

const ConfigContext = createContext<ConfigContextType>({ apiUrl: "" });

interface ConfigProviderProps {
    children: React.ReactNode;
    apiUrl: string;
}

// For non-hook usage (e.g., in api.ts)
let globalApiUrl = "";
export const setGlobalApiUrl = (url: string) => {
    globalApiUrl = url;
};
export const getApiUrl = () => globalApiUrl;

export function ConfigProvider({ children, apiUrl }: ConfigProviderProps) {
    // Set global API URL for non-React contexts (like api.ts)
    useEffect(() => {
        setGlobalApiUrl(apiUrl);
    }, [apiUrl]);

    return (
        <ConfigContext.Provider value={{ apiUrl }}>
            {children}
        </ConfigContext.Provider>
    );
}

export const useConfig = () => useContext(ConfigContext);
