import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import CaseWorkspace from "./page";
import axios from "axios";
import { useAuth } from "@/context/AuthContext";
import { useParams } from "next/navigation";

// --- Mocks ---
jest.mock("axios");
jest.mock("@/context/AuthContext");
jest.mock("next/navigation", () => ({
    useParams: jest.fn(),
}));
jest.mock("sonner", () => ({
    toast: {
        success: jest.fn(),
        error: jest.fn(),
        loading: jest.fn(),
        dismiss: jest.fn(),
    },
}));

// Mock Data
const mockCase = {
    id: "123",
    reference_code: "REF-TEST",
    client_name: "Test Client",
    status: "OPEN",
    created_at: "2023-01-01T00:00:00Z", // Added missing field
    documents: [
        { id: "d1", filename: "doc1.pdf", ai_status: "SUCCESS", created_at: "2023-01-01T00:00:00Z" }, // Added missing field
        { id: "d2", filename: "doc2.pdf", ai_status: "PROCESSING", created_at: "2023-01-01T00:00:00Z" }  // Added missing field
    ],
    report_versions: [
        { id: "v1", version_number: 1, is_final: false, created_at: "2023-01-01T00:00:00Z" } // Added missing field
    ]
};

describe("CaseWorkspace Page", () => {
    beforeEach(() => {
        (useAuth as jest.Mock).mockReturnValue({
            getToken: jest.fn().mockResolvedValue("fake-token"),
        });
        (useParams as jest.Mock).mockReturnValue({ id: "123" });
        (axios.get as jest.Mock).mockResolvedValue({ data: mockCase });
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

    test("renders loading state initially", () => {
        // Mock a pending promise to keep it in loading state
        (axios.get as jest.Mock).mockImplementation(() => new Promise(() => { }));
        render(<CaseWorkspace />);
        // Check for skeleton or loading indicator (assuming skeleton has specific class or structure, 
        // but here we check if main content is NOT present yet)
        expect(screen.queryByText("REF-TEST")).not.toBeInTheDocument();
    });

    test("renders case details on success", async () => {
        render(<CaseWorkspace />);

        await waitFor(() => {
            expect(screen.getByText("REF-TEST")).toBeInTheDocument();
            expect(screen.getByText("Test Client")).toBeInTheDocument();
        });

        // Check documents
        expect(screen.getByText("doc1.pdf")).toBeInTheDocument();
        expect(screen.getByText("doc2.pdf")).toBeInTheDocument();

        // Check versions
        expect(screen.getByText("Versione 1")).toBeInTheDocument();
    });

    test("renders error state on API failure", async () => {
        (axios.get as jest.Mock).mockRejectedValue(new Error("Network Error"));
        render(<CaseWorkspace />);

        await waitFor(() => {
            expect(screen.getByText("Qualcosa è andato storto")).toBeInTheDocument();
        });
    });

    test("triggers generation on button click", async () => {
        render(<CaseWorkspace />);
        await waitFor(() => screen.getByText("Genera con IA"));

        const generateBtn = screen.getByText("Genera con IA");

        (axios.post as jest.Mock).mockResolvedValue({ data: { status: "started" } });

        fireEvent.click(generateBtn);

        await waitFor(() => {
            expect(axios.post).toHaveBeenCalledWith(
                expect.stringContaining("/api/cases/123/generate"),
                {},
                expect.objectContaining({ headers: { Authorization: "Bearer fake-token" } })
            );
        });
    });
});
