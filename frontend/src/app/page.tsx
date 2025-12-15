"use client";

import { useAuth } from "@/context/AuthContext";
import { FirebaseError } from "firebase/app";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Loader2, ArrowLeft, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { ModeToggle } from "@/components/primitives";

type Mode = "check" | "login" | "signup" | "forgot" | "denied";

function LandingPage() {
  const { user, isProfileComplete, syncError, login, signupWithEmail, loginWithEmail, resetPassword, loading } = useAuth();
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<Mode>("check");

  useEffect(() => {
    // Only redirect if user is logged in and there's no sync error
    if (user && !syncError) {
      router.push(isProfileComplete ? "/dashboard" : "/onboarding");
    }
  }, [user, isProfileComplete, syncError, router]);

  const handleCheckEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      toast.error("Inserisci la tua email");
      return;
    }

    setIsLoading(true);
    try {
      const result = await api.auth.checkStatus(email);

      if (result.status === "registered") {
        setMode("login");
        toast.info("Bentornato! Inserisci la password.");
      } else if (result.status === "invited") {
        setMode("signup");
        toast.info("Crea il tuo account per continuare.");
      } else {
        setMode("denied");
      }
    } catch (error) {
      console.error("Check status failed:", error);
      toast.error("Errore durante la verifica. Riprova.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setIsLoading(true);
    try {
      await login();
    } catch (error) {
      console.error("Login failed", error);

      if (error instanceof FirebaseError) {
        const errorMessages: Record<string, string> = {
          'auth/popup-closed-by-user': 'Accesso annullato',
          'auth/cancelled-popup-request': 'Richiesta annullata',
        };
        toast.error(errorMessages[error.code] || 'Accesso Google fallito. Riprova.');
      } else {
        toast.error('Errore imprevisto. Riprova.');
      }

      setIsLoading(false);
    }
  };

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Compila tutti i campi");
      return;
    }

    setIsLoading(true);
    try {
      if (mode === "login") {
        await loginWithEmail(email, password);
      } else if (mode === "signup") {
        await signupWithEmail(email, password);
        toast.success("Account creato con successo!");
      }
    } catch (error) {
      console.error("Auth failed", error);

      if (error instanceof FirebaseError) {
        const errorMessages: Record<string, string> = {
          'auth/invalid-credential': 'Credenziali non valide.',
          'auth/user-not-found': 'Utente non trovato.',
          'auth/wrong-password': 'Password errata.',
          'auth/email-already-in-use': 'Email già registrata.',
          'auth/weak-password': 'Password troppo debole (min 6 caratteri).',
        };
        toast.error(errorMessages[error.code] || 'Operazione fallita.');
      } else {
        toast.error('Operazione fallita.');
      }

      setIsLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      toast.error("Inserisci la tua email");
      return;
    }

    setIsLoading(true);
    try {
      await resetPassword(email);
      toast.success("Email di recupero inviata!");
      setMode("login");
    } catch (error) {
      console.error("Reset failed", error);
      toast.error("Errore durante il recupero password.");
    } finally {
      setIsLoading(false);
    }
  };

  const resetToCheck = () => {
    setMode("check");
    setPassword("");
  };

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // --- DENIED VIEW ---
  if (mode === "denied") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 relative overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-destructive/5 rounded-full blur-3xl -z-10" />
        <div className="w-full max-w-md space-y-6 text-center">
          <div className="inline-flex items-center justify-center p-3 bg-destructive/10 rounded-2xl">
            <ShieldAlert className="h-8 w-8 text-destructive" />
          </div>
          <h1 className="text-2xl font-bold">Accesso Non Autorizzato</h1>
          <p className="text-muted-foreground">
            L&apos;email <strong>{email}</strong> non è nella lista degli utenti autorizzati.
            Contatta l&apos;amministratore per richiedere l&apos;accesso.
          </p>
          <Button variant="outline" onClick={resetToCheck}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Prova con un&apos;altra email
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 relative overflow-hidden">
      <div className="absolute top-4 right-4 z-50">
        <ModeToggle />
      </div>

      {/* Abstract Background Decoration */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/5 rounded-full blur-3xl -z-10" />

      <div className="w-full max-w-md space-y-8 text-center">
        <div className="space-y-2">
          <div className="inline-flex items-center justify-center p-3 bg-primary/10 rounded-2xl mb-4">
            <img src="/perito-logo-black.svg" alt="Perito Logo" className="h-8 w-8 dark:invert" />
          </div>
          <img src="/myperito-black.svg" alt="MyPerito" className="h-10 mx-auto dark:invert" />
          <p className="text-lg text-muted-foreground">
            Per i periti del futuro.
          </p>
        </div>

        <Card className="border-border/50 shadow-xl bg-card/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle>
              {mode === "check" && "Inizia"}
              {mode === "login" && "Bentornato"}
              {mode === "signup" && "Crea Account"}
              {mode === "forgot" && "Recupera Password"}
            </CardTitle>
            <CardDescription>
              {mode === "check" && "Inserisci la tua email per continuare"}
              {mode === "login" && "Inserisci la password per accedere"}
              {mode === "signup" && "Crea una password per il tuo account"}
              {mode === "forgot" && "Ti invieremo un link di recupero"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">

            {/* CHECK MODE */}
            {mode === "check" && (
              <form onSubmit={handleCheckEmail} className="space-y-4 text-left">
                <Input
                  type="email"
                  placeholder="La tua email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="bg-background/50"
                  autoFocus
                />
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Continua
                </Button>
              </form>
            )}

            {/* LOGIN / SIGNUP MODE */}
            {(mode === "login" || mode === "signup") && (
              <form onSubmit={handleEmailAuth} className="space-y-4 text-left">
                <div className="space-y-2">
                  <Input
                    type="email"
                    placeholder="Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="bg-background/50"
                    disabled
                  />
                  <Input
                    type="password"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="bg-background/50"
                    autoFocus
                  />
                </div>
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {mode === "login" ? "Accedi" : "Registrati"}
                </Button>
              </form>
            )}

            {/* FORGOT MODE */}
            {mode === "forgot" && (
              <form onSubmit={handleForgotPassword} className="space-y-4 text-left">
                <Input
                  type="email"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="bg-background/50"
                />
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Invia Link
                </Button>
              </form>
            )}

            {/* GOOGLE LOGIN - show in login, signup modes only */}
            {(mode === "login" || mode === "signup") && (
              <>
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-background px-2 text-muted-foreground">
                      Oppure
                    </span>
                  </div>
                </div>

                <Button
                  variant="outline"
                  onClick={handleGoogleLogin}
                  className="w-full"
                  disabled={isLoading}
                >
                  <svg className="mr-2 h-4 w-4" aria-hidden="true" focusable="false" data-prefix="fab" data-icon="google" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 488 512"><path fill="currentColor" d="M488 261.8C488 403.3 391.1 504 248 504 110.8 504 0 393.2 0 256S110.8 8 248 8c66.8 0 123 24.5 166.3 64.9l-67.5 64.9C258.5 52.6 94.3 116.6 94.3 256c0 86.5 69.1 156.6 153.7 156.6 98.2 0 135-70.4 140.8-106.9H248v-85.3h236.1c2.3 12.7 3.9 24.9 3.9 41.4z"></path></svg>
                  Accedi con Google
                </Button>
              </>
            )}

            {/* NAVIGATION LINKS */}
            <div className="text-sm text-center space-y-2 mt-4">
              {mode === "check" && (
                <p>
                  Hai già un account?{" "}
                  <button onClick={() => setMode("login")} className="text-primary hover:underline font-medium">
                    Accedi
                  </button>
                </p>
              )}

              {mode === "login" && (
                <>
                  <button onClick={() => setMode("forgot")} className="text-xs text-muted-foreground hover:underline">
                    Password dimenticata?
                  </button>
                  <p>
                    <button onClick={resetToCheck} className="text-primary hover:underline font-medium flex items-center justify-center w-full">
                      <ArrowLeft className="mr-1 h-3 w-3" />
                      Cambia email
                    </button>
                  </p>
                </>
              )}

              {mode === "signup" && (
                <button onClick={resetToCheck} className="text-primary hover:underline font-medium flex items-center justify-center w-full">
                  <ArrowLeft className="mr-1 h-3 w-3" />
                  Cambia email
                </button>
              )}

              {mode === "forgot" && (
                <button onClick={() => setMode("login")} className="text-primary hover:underline font-medium">
                  Torna al login
                </button>
              )}
            </div>

          </CardContent>
        </Card>

        <p className="text-xs text-muted-foreground">
          Protetto da sicurezza di livello enterprise.
        </p>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <LandingPage />
  );
}
