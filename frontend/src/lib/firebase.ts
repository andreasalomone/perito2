import { initializeApp, getApps, FirebaseApp, FirebaseOptions } from "firebase/app";
import { getAuth, GoogleAuthProvider, Auth } from "firebase/auth";

let app: FirebaseApp | undefined;
let auth: Auth | undefined;

export const initFirebase = (config: FirebaseOptions) => {
    if (getApps().length === 0) {
        app = initializeApp(config);
    } else {
        app = getApps()[0];
    }
    auth = getAuth(app);
    return { app, auth };
};

// Helper to get auth instance, throws if not initialized
export const getFirebaseAuth = (): Auth => {
    if (!auth) {
        // Fallback: try to get from default app if it exists (e.g. if init happened elsewhere)
        if (getApps().length > 0) {
            return getAuth(getApps()[0]);
        }
        throw new Error("Firebase not initialized");
    }
    return auth;
};

export const googleProvider = new GoogleAuthProvider();