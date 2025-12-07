"use client";

import { useAuth } from "@/context/AuthContext";
import { FirebaseError } from "firebase/app";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

function LandingPage() {
  const { user, isProfileComplete, syncError, login, signupWithEmail, loginWithEmail, resetPassword, loading } = useAuth();
  const router = useRouter();
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "signup" | "forgot">("login");

  useEffect(() => {
    // Only redirect if user is logged in and there's no sync error
    if (user && !syncError) {
      router.push(isProfileComplete ? "/dashboard" : "/onboarding");
    }
  }, [user, isProfileComplete, syncError, router]);

  const handleGoogleLogin = async () => {
    setIsLoggingIn(true);
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

      setIsLoggingIn(false);
    }
  };

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || (!password && mode !== "forgot")) {
      toast.error("Compila tutti i campi");
      return;
    }

    setIsLoggingIn(true);
    try {
      if (mode === "login") {
        await loginWithEmail(email, password);
      } else if (mode === "signup") {
        await signupWithEmail(email, password);
        toast.success("Account creato con successo!");
      } else if (mode === "forgot") {
        await resetPassword(email);
        toast.success("Email di recupero inviata!");
        setMode("login");
        setIsLoggingIn(false);
        return;
      }
    } catch (error) {
      console.error("Auth failed", error);

      if (error instanceof FirebaseError) {
        const errorMessages: Record<string, string> = {
          'auth/invalid-credential': 'Credenziali non valide.',
          'auth/user-not-found': 'Utente non trovato.',
          'auth/wrong-password': 'Password errata.',
          'auth/email-already-in-use': 'Email già registrata.',
          'auth/weak-password': 'Password troppo debole.',
        };
        toast.error(errorMessages[error.code] || 'Operazione fallita.');
      } else {
        toast.error('Operazione fallita.');
      }

      setIsLoggingIn(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

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
            <CardTitle>
              {mode === "login" && "Bentornato"}
              {mode === "signup" && "Crea Account"}
              {mode === "forgot" && "Recupera Password"}
            </CardTitle>
            <CardDescription>
              {mode === "login" && "Accedi per continuare"}
              {mode === "signup" && "Inserisci i tuoi dati per iniziare"}
              {mode === "forgot" && "Inserisci la tua email"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">

            <form onSubmit={handleEmailAuth} className="space-y-4 text-left">
              <div className="space-y-2">
                <Input
                  type="email"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="bg-background/50"
                />
                {mode !== "forgot" && (
                  <Input
                    type="password"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="bg-background/50"
                  />
                )}
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={isLoggingIn}
              >
                {isLoggingIn && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {mode === "login" && "Accedi"}
                {mode === "signup" && "Registrati"}
                {mode === "forgot" && "Invia Link"}
              </Button>
            </form>

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
              disabled={isLoggingIn}
            >
              <svg className="mr-2 h-4 w-4" aria-hidden="true" focusable="false" data-prefix="fab" data-icon="google" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 488 512"><path fill="currentColor" d="M488 261.8C488 403.3 391.1 504 248 504 110.8 504 0 393.2 0 256S110.8 8 248 8c66.8 0 123 24.5 166.3 64.9l-67.5 64.9C258.5 52.6 94.3 116.6 94.3 256c0 86.5 69.1 156.6 153.7 156.6 98.2 0 135-70.4 140.8-106.9H248v-85.3h236.1c2.3 12.7 3.9 24.9 3.9 41.4z"></path></svg>
              Accedi con Google
            </Button>

            <div className="text-sm text-center space-y-2 mt-4">
              {mode === "login" && (
                <>
                  <p>
                    Non hai un account?{" "}
                    <button onClick={() => setMode("signup")} className="text-primary hover:underline font-medium">
                      Registrati
                    </button>
                  </p>
                  <button onClick={() => setMode("forgot")} className="text-xs text-muted-foreground hover:underline">
                    Password dimenticata?
                  </button>
                </>
              )}

              {mode === "signup" && (
                <p>
                  Hai già un account?{" "}
                  <button onClick={() => setMode("login")} className="text-primary hover:underline font-medium">
                    Accedi
                  </button>
                </p>
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