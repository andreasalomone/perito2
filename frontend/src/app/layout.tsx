import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PeritoAI | Perizie Powered by AI",
  description: "Automazione professionale per perizie assicurative.",
};

import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import { ConfigProvider } from "@/context/ConfigContext";
import { CommandMenu } from "@/components/CommandMenu";

// Force dynamic rendering to ensure environment variables are read at runtime
// This prevents Next.js from baking in 'undefined' env vars during build time
export const dynamic = "force-dynamic";

/**
 * Helper function to read environment variables at runtime.
 * Using a function prevents the Next.js bundler from inlining the values at build time.
 * This enables "build once, deploy anywhere" for Docker containers.
 */
function getEnvVar(key: string): string | undefined {
  return process.env[key];
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Server-side: Read runtime env vars using helper function
  // The function wrapper prevents build-time inlining in standalone mode
  const firebaseConfig = {
    apiKey: getEnvVar("FIREBASE_API_KEY"),
    authDomain: getEnvVar("FIREBASE_AUTH_DOMAIN"),
    projectId: getEnvVar("FIREBASE_PROJECT_ID"),
    storageBucket: getEnvVar("FIREBASE_STORAGE_BUCKET"),
    messagingSenderId: getEnvVar("FIREBASE_MESSAGING_SENDER_ID"),
    appId: getEnvVar("FIREBASE_APP_ID"),
    measurementId: getEnvVar("FIREBASE_MEASUREMENT_ID"),
  };

  // API URL for backend communication
  const apiUrl = getEnvVar("API_URL") || "";

  return (
    <html lang="it">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        <div
          className="fixed inset-0 z-50 pointer-events-none opacity-[0.03] mix-blend-overlay"
          style={{ backgroundImage: 'url("/noise.svg")' }}
        />
        <ConfigProvider apiUrl={apiUrl}>
          <AuthProvider firebaseConfig={firebaseConfig}>
            {children}
            <CommandMenu />
            <Toaster />
          </AuthProvider>
        </ConfigProvider>
      </body>
    </html>
  );
}
