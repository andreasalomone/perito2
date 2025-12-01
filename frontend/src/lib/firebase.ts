import { initializeApp, getApps } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

// Helper to get env var from window (runtime) or process (build time/dev)
const getEnv = (key: string, fallback: string | undefined) => {
    if (typeof window !== 'undefined' && (window as any).__ENV && (window as any).__ENV[key]) {
        return (window as any).__ENV[key];
    }
    return fallback;
};

const firebaseConfig = {
    apiKey: getEnv("NEXT_PUBLIC_FIREBASE_API_KEY", process.env.NEXT_PUBLIC_FIREBASE_API_KEY),
    authDomain: getEnv("NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN", process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN),
    projectId: getEnv("NEXT_PUBLIC_FIREBASE_PROJECT_ID", process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID),
    storageBucket: getEnv("NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET", process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET),
    messagingSenderId: getEnv("NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID", process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID),
    appId: getEnv("NEXT_PUBLIC_FIREBASE_APP_ID", process.env.NEXT_PUBLIC_FIREBASE_APP_ID),
    measurementId: getEnv("NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID", process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID),
};



// Initialize Firebase only once
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();