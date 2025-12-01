import { initializeApp, getApps } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

// Helper to get env var from window (runtime) or process (build time/dev)
const getEnv = (key: string) => {
    if (typeof window !== 'undefined' && (window as any).__ENV && (window as any).__ENV[key]) {
        return (window as any).__ENV[key];
    }
    return process.env[key];
};

const firebaseConfig = {
    apiKey: getEnv("NEXT_PUBLIC_FIREBASE_API_KEY"),
    authDomain: getEnv("NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN"),
    projectId: getEnv("NEXT_PUBLIC_FIREBASE_PROJECT_ID"),
    storageBucket: getEnv("NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET"),
    messagingSenderId: getEnv("NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID"),
    appId: getEnv("NEXT_PUBLIC_FIREBASE_APP_ID"),
    measurementId: getEnv("NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID"),
};

// Debug logging
if (typeof window !== 'undefined') {
    console.log("Firebase Config Debug:");
    console.log("API Key (first 5 chars):", firebaseConfig.apiKey ? firebaseConfig.apiKey.substring(0, 5) : "UNDEFINED");
    console.log("Auth Domain:", firebaseConfig.authDomain);
    console.log("Project ID:", firebaseConfig.projectId);
    console.log("Full Config Keys:", Object.keys(firebaseConfig));
}

// Initialize Firebase only once
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();