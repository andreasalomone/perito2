"use client";

import { AuthProvider, useAuth } from "@/context/AuthContext";
import ReportGenerator from "@/components/ReportGenerator";

// 1. Internal Component: Handles the UI based on Auth State
function Dashboard() {
  const { user, login, loading } = useAuth();

  // State A: Loading Firebase (Checking if user is logged in)
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="text-xl font-semibold text-gray-600 animate-pulse">
          Loading RobotPerizia...
        </div>
      </div>
    );
  }

  // State B: Not Logged In (Show Login Button)
  if (!user) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-md space-y-8 text-center">
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-gray-900">
              RobotPerizia
            </h1>
            <p className="mt-2 text-sm text-gray-600">
              AI-Powered Insurance Reporting
            </p>
          </div>
          <button
            onClick={() => login()}
            className="w-full rounded-lg bg-black px-6 py-4 text-lg font-semibold text-white shadow-md hover:bg-gray-800 transition-all focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
          >
            Sign in with Google
          </button>
        </div>
      </div>
    );
  }

  // State C: Logged In (Show Dashboard)
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top Navigation Bar */}
      <nav className="bg-white border-b border-gray-200 px-8 py-4">
        <div className="max-w-5xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold text-gray-900">RobotPerizia</span>
            <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-0.5 rounded">v2.0</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600 hidden sm:inline-block">
              {user.email}
            </span>
            {/* Optional: Add a Logout button here if you want later */}
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="max-w-5xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
        <div className="space-y-6">
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium leading-6 text-gray-900 mb-4">
              Create New Report
            </h2>
            {/* This is the Smart Upload Component we built in Step 4 */}
            <ReportGenerator />
          </div>
        </div>
      </main>
    </div>
  );
}

// 2. Main Page Component: Wraps everything in the Auth Provider
export default function Home() {
  return (
    <AuthProvider>
      <Dashboard />
    </AuthProvider>
  );
}