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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Server-side: Read runtime env vars (injected by Cloud Run at deploy time)
  // No NEXT_PUBLIC_ prefix needed because this is a Server Component
  const firebaseConfig = {
    apiKey: process.env.FIREBASE_API_KEY,
    authDomain: process.env.FIREBASE_AUTH_DOMAIN,
    projectId: process.env.FIREBASE_PROJECT_ID,
    storageBucket: process.env.FIREBASE_STORAGE_BUCKET,
    messagingSenderId: process.env.FIREBASE_MESSAGING_SENDER_ID,
    appId: process.env.FIREBASE_APP_ID,
    measurementId: process.env.FIREBASE_MEASUREMENT_ID,
  };

  // API URL for backend communication
  const apiUrl = process.env.API_URL || "";

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
