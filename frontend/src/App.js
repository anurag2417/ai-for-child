import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/components/AuthContext";
import ChatPage from "@/components/ChatPage";
import LoginPage from "@/components/LoginPage";
import AuthCallback from "@/components/AuthCallback";
import ParentDashboard from "@/components/ParentDashboard";
import ParentConversationDetail from "@/components/ParentConversationDetail";
import PasswordGate from "@/components/PasswordGate";

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="w-10 h-10 border-4 border-sky-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  return <PasswordGate>{children}</PasswordGate>;
}

function AppRouter() {
  const location = useLocation();

  // CRITICAL: Detect session_id during render, before ProtectedRoute runs
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/" element={<ChatPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route
        path="/parent"
        element={
          <ProtectedRoute>
            <ParentDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/parent/conversation/:id"
        element={
          <ProtectedRoute>
            <ParentConversationDetail />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
