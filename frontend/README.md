# MyPerito Frontend

This is the frontend for the MyPerito application, built with **Next.js 16** and **React 19**, styled with **Tailwind CSS v4**. It is designed to be deployed on Google Cloud Run.

## 🚀 Getting Started

### Prerequisites

*   **Node.js 18+**
*   **npm**

### Setup

1.  **Install dependencies:**

    ```bash
    npm install
    ```

### Configuration

Create a `.env.local` file in the `frontend` directory with your local configuration. You can use `.env.local.example` (if available) or populate it with the necessary environment variables:

```env
# API Configuration
API_URL=http://localhost:8000

# Firebase Configuration
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=...
NEXT_PUBLIC_FIREBASE_PROJECT_ID=...
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=...
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=...
NEXT_PUBLIC_FIREBASE_APP_ID=...
```

### Running Locally

To start the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `src/app/page.tsx` (or relevant files in `src/`). The page auto-updates as you edit the file.

## 🛠️ Key Technologies

*   **Next.js 16:** React framework for production with App Router.
*   **React 19:** Latest React with improved performance and new features.
*   **Firebase Auth:** Secure user authentication.
*   **Tailwind CSS v4:** Utility-first CSS framework for styling.
*   **Radix UI:** Unstyled, accessible components for building high-quality design systems.
*   **Framer Motion:** Production-ready animations and transitions.
*   **Lucide React:** Beautiful & consistent icons.
*   **Axios:** Promise based HTTP client for the browser and node.js.
*   **SWR:** React Hooks for Data Fetching with cache revalidation.
*   **cmdk:** Command palette component for search/autocomplete.
*   **Zod:** TypeScript-first schema validation.
*   **Sonner:** Toast notifications.
