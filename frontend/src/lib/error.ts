import { toast } from "sonner";
import axios from "axios";

export const handleApiError = (error: unknown, defaultMessage: string) => {
    console.error(error);
    if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        if (status === 401) {
            toast.error("Sessione scaduta. Effettua nuovamente il login.");
            return;
        }
        if (status === 403) {
            toast.error("Non hai i permessi per questa azione.");
            return;
        }
        if (status === 404) {
            toast.error("Risorsa non trovata.");
            return;
        }
        if (status && status >= 500) {
            toast.error("Errore del server. Riprova più tardi.");
            return;
        }
    }
    toast.error(defaultMessage);
};
