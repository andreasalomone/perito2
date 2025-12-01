"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { onAuthStateChanged, User, signInWithPopup, signOut } from "firebase/auth";
import { auth, googleProvider } from "@/lib/firebase";
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

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [dbUser, setDbUser] = useState<DBUser | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
            setUser(firebaseUser);

            if (firebaseUser) {
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
                setDbUser(null);
            }

            setLoading(false);
        });
        return () => unsubscribe();
    }, []);

    const login = async () => {
        await signInWithPopup(auth, googleProvider);
    };

    const logout = async () => {
        await signOut(auth);
        setDbUser(null);
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