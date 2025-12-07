"use client";
import { createContext, useContext, useEffect, useState, useRef } from "react";
import { onAuthStateChanged, User, signInWithPopup, signOut, Auth, createUserWithEmailAndPassword, signInWithEmailAndPassword, sendPasswordResetEmail } from "firebase/auth";
import { initFirebase, googleProvider, getFirebaseAuth } from "@/lib/firebase";
import { DBUser } from "@/types";
import axios from "axios";
import { useConfig } from "@/context/ConfigContext";

interface AuthContextType {
    user: User | null;
    dbUser: DBUser | null;
    loading: boolean;
    isProfileComplete: boolean;
    syncError: 'forbidden' | 'error' | null;
    login: () => Promise<void>;
    signupWithEmail: (email: string, password: string) => Promise<void>;
    loginWithEmail: (email: string, password: string) => Promise<void>;
    resetPassword: (email: string) => Promise<void>;
    logout: () => Promise<void>;
    getToken: () => Promise<string>;
}

const AuthContext = createContext<AuthContextType>({} as AuthContextType);

interface AuthProviderProps {
    children: React.ReactNode;
    firebaseConfig: Record<string, string | undefined>;
}

export function AuthProvider({ children, firebaseConfig }: AuthProviderProps) {
    const { apiUrl } = useConfig();
    const [user, setUser] = useState<User | null>(null);
    const [dbUser, setDbUser] = useState<DBUser | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isSynced, setIsSynced] = useState(false); // Track backend sync completion
    const [syncError, setSyncError] = useState<'forbidden' | 'error' | null>(null);
    const authRef = useRef<Auth | null>(null);
    const initialized = useRef(false);

    useEffect(() => {
        if (initialized.current) return;

        try {
            if (!firebaseConfig?.apiKey) {
                throw new Error("Missing Firebase API Key. Please check your environment variables or build configuration.");
            }
            const { auth } = initFirebase(firebaseConfig as any);
            authRef.current = auth;
            initialized.current = true;
        } catch (e) {
            console.error("Firebase init failed", e);
            setError(e instanceof Error ? e.message : "Failed to initialize Firebase");
            setLoading(false);
            return;
        }

        const auth = authRef.current;
        if (!auth) return;

        const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
            setUser(firebaseUser);

            if (firebaseUser) {
                // Set auth cookie for middleware
                document.cookie = "auth_session=1; path=/; max-age=86400; SameSite=Lax";

                setIsSynced(false);
                setSyncError(null);

                try {
                    const token = await firebaseUser.getIdToken();
                    const response = await axios.post(
                        `${apiUrl}/api/v1/auth/sync`,
                        {},
                        { headers: { 'Authorization': `Bearer ${token}` } }
                    );

                    const userData = response.data;
                    setDbUser(userData);

                    // Set profile completion cookie BEFORE marking synced
                    document.cookie = userData.is_profile_complete
                        ? "profile_complete=1; path=/; max-age=86400; SameSite=Lax"
                        : "profile_complete=0; path=/; max-age=86400; SameSite=Lax";

                    setIsSynced(true);
                } catch (error) {
                    console.error("Error syncing user:", error);
                    setDbUser(null);

                    // Differentiate 403 (forbidden) from other errors
                    if (axios.isAxiosError(error) && error.response?.status === 403) {
                        setSyncError('forbidden');
                        // Clear profile cookie - user is NOT allowed
                        document.cookie = "profile_complete=; path=/; max-age=0; SameSite=Lax";
                    } else {
                        setSyncError('error');
                    }

                    setIsSynced(true);  // FIX: Was false, caused infinite spinner!
                }
            } else {
                // Remove cookies on logout
                document.cookie = "auth_session=; path=/; max-age=0; SameSite=Lax";
                document.cookie = "profile_complete=; path=/; max-age=0; SameSite=Lax";
                setDbUser(null);
                setSyncError(null);
                setIsSynced(true); // Guest mode is technically "synced" (no user)
            }

            setLoading(false);
        });

        return () => unsubscribe();
    }, [firebaseConfig]);

    const login = async () => {
        if (authRef.current) {
            await signInWithPopup(authRef.current, googleProvider);
        }
    };

    const signupWithEmail = async (email: string, password: string) => {
        if (authRef.current) {
            await createUserWithEmailAndPassword(authRef.current, email, password);
        }
    };

    const loginWithEmail = async (email: string, password: string) => {
        if (authRef.current) {
            await signInWithEmailAndPassword(authRef.current, email, password);
        }
    };

    const resetPassword = async (email: string) => {
        if (authRef.current) {
            await sendPasswordResetEmail(authRef.current, email);
        }
    };

    const logout = async () => {
        if (authRef.current) {
            await signOut(authRef.current);
            document.cookie = "auth_session=; path=/; max-age=0; SameSite=Lax";
            document.cookie = "profile_complete=; path=/; max-age=0; SameSite=Lax";
            setDbUser(null);
            setSyncError(null);
        }
    };

    const getToken = async (): Promise<string> => {
        if (!user) throw new Error("Not authenticated");
        return user.getIdToken();
    };

    // PREVENT "ZOMBIE REQUESTS":
    // Do not render children until we know the Backend DB knows who we are.
    if (loading || (user && !isSynced)) {
        return <div className="flex items-center justify-center min-h-screen">
            <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className="text-gray-600">Synchronizing Profile...</p>
            </div>
        </div>;
    }

    if (error) {
        return <div className="flex items-center justify-center min-h-screen">
            <div className="text-center max-w-md mx-auto p-6 bg-red-50 rounded-lg">
                <h2 className="text-xl font-bold text-red-600 mb-2">Configuration Error</h2>
                <p className="text-red-800 mb-4">{error}</p>
                <div className="text-sm text-red-600 text-left bg-white p-4 rounded border border-red-200 overflow-auto">
                    <p className="font-semibold mb-1">Troubleshooting:</p>
                    <ul className="list-disc list-inside space-y-1">
                        <li>Check if <code>.env.local</code> exists</li>
                        <li>Verify <code>FIREBASE_API_KEY</code> is set</li>
                        <li>If using Cloud Run, check Secret Manager secrets</li>
                    </ul>
                </div>
            </div>
        </div>;
    }

    const isProfileComplete = dbUser?.is_profile_complete ?? false;

    return (
        <AuthContext.Provider value={{
            user, dbUser, loading, isProfileComplete, syncError,
            login, signupWithEmail, loginWithEmail, resetPassword, logout, getToken
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);