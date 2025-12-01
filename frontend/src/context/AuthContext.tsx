"use client";
import { createContext, useContext, useEffect, useState, useRef } from "react";
import { onAuthStateChanged, User, signInWithPopup, signOut, Auth } from "firebase/auth";
import { initFirebase, googleProvider, getFirebaseAuth } from "@/lib/firebase";
import { DBUser } from "@/types";
import axios from "axios";

interface AuthContextType {
    user: User | null;
    dbUser: DBUser | null;
    loading: boolean;
    login: () => Promise<void>;
    logout: () => Promise<void>;
    getToken: () => Promise<string | undefined>;
}

const AuthContext = createContext<AuthContextType>({} as AuthContextType);

interface AuthProviderProps {
    children: React.ReactNode;
    firebaseConfig: Record<string, string | undefined>;
}

export function AuthProvider({ children, firebaseConfig }: AuthProviderProps) {
    const [user, setUser] = useState<User | null>(null);
    const [dbUser, setDbUser] = useState<DBUser | null>(null);
    const [loading, setLoading] = useState(true);
    const authRef = useRef<Auth | null>(null);

    // Initialize Firebase once
    if (!authRef.current) {
        try {
            const { auth } = initFirebase(firebaseConfig as any);
            authRef.current = auth;
        } catch (e) {
            console.error("Firebase init failed", e);
        }
    }

    useEffect(() => {
        const auth = authRef.current;
        if (!auth) return;

        const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
            setUser(firebaseUser);

            if (firebaseUser) {
                // Set cookie for middleware
                document.cookie = "auth_session=1; path=/; max-age=86400; SameSite=Lax";

                try {
                    const token = await firebaseUser.getIdToken();
                    const response = await axios.post(
                        `${process.env.NEXT_PUBLIC_API_URL}/api/auth/sync`,
                        {},
                        {
                            headers: {
                                'Authorization': `Bearer ${token}`
                            }
                        }
                    );

                    setDbUser(response.data);
                } catch (error) {
                    console.error("Error syncing user:", error);
                    setDbUser(null);
                }
            } else {
                // Remove cookie
                document.cookie = "auth_session=; path=/; max-age=0; SameSite=Lax";
                setDbUser(null);
            }

            setLoading(false);
        });
        return () => unsubscribe();
    }, []);

    const login = async () => {
        if (authRef.current) {
            await signInWithPopup(authRef.current, googleProvider);
        }
    };

    const logout = async () => {
        if (authRef.current) {
            await signOut(authRef.current);
            document.cookie = "auth_session=; path=/; max-age=0; SameSite=Lax";
            setDbUser(null);
        }
    };

    const getToken = async () => {
        return user?.getIdToken();
    };

    return (
        <AuthContext.Provider value={{ user, dbUser, loading, login, logout, getToken }}>
            {!loading && children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);