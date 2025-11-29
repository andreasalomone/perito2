"use client";

import { AuthProvider, useAuth } from "@/context/AuthContext";
import ReportGenerator from "@/components/ReportGenerator";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Loader2, ShieldCheck, Sparkles } from "lucide-react";

function Dashboard() {
  const { user, login, loading } = useAuth();

  // State A: Loading
  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm font-medium text-muted-foreground animate-pulse">
            Caricando PeritoAI...
          </p>
        </div>
      </div>
    );
  }

  // State B: Not Logged In
  if (!user) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 relative overflow-hidden">
        {/* Abstract Background Decoration */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/5 rounded-full blur-3xl -z-10" />

        <div className="w-full max-w-md space-y-8 text-center">
          <div className="space-y-2">
            <div className="inline-flex items-center justify-center p-3 bg-primary/10 rounded-2xl mb-4">
              <Sparkles className="h-8 w-8 text-primary" />
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-foreground">
              PeritoAI
            </h1>
            <p className="text-lg text-muted-foreground">
              Per i periti del futuro.
            </p>
          </div>

          <Card className="border-border/50 shadow-xl bg-card/50 backdrop-blur-sm">
            <CardHeader>
              <CardTitle>Benvenuto</CardTitle>
              <CardDescription>Accedi per iniziare</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                onClick={() => login()}
                size="lg"
                className="w-full text-base font-semibold h-12"
              >
                Accedi con Google
              </Button>
            </CardContent>
          </Card>

          <p className="text-xs text-muted-foreground">
            Protetto da sicurezza di livello enterprise.
          </p>
        </div>
      </div>
    );
  }

  // State C: Logged In
  return (
    <div className="min-h-screen bg-muted/30">
      {/* Top Navigation Bar */}
      <nav className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/80 backdrop-blur-xl supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-primary text-primary-foreground p-1.5 rounded-lg">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <span className="text-lg font-bold tracking-tight">PeritoAI</span>
            <span className="bg-secondary text-secondary-foreground text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
              v2.0
            </span>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex flex-col items-end">
              <span className="text-sm font-medium leading-none">
                {user.displayName || "User"}
              </span>
              <span className="text-xs text-muted-foreground">
                {user.email}
              </span>
            </div>
            <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-xs">
              {user.email?.[0].toUpperCase()}
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="container py-10">
        <div className="mx-auto max-w-4xl space-y-8">
          <div className="flex flex-col gap-2">
            <h2 className="text-3xl font-bold tracking-tight">Genera Report</h2>
            <p className="text-muted-foreground">
              Carica i documenti e lascia che l&apos;IA crei un report professionale in pochi secondi.
            </p>
          </div>

          {/* Smart Upload Component */}
          <ReportGenerator />
        </div>
      </main>
    </div>
  );
}

export default function Home() {
  return (
    <AuthProvider>
      <Dashboard />
    </AuthProvider>
  );
}