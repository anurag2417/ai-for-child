import { BrowserRouter, Routes, Route } from "react-router-dom";
import ChatPage from "@/components/ChatPage";
import ParentDashboard from "@/components/ParentDashboard";
import ParentConversationDetail from "@/components/ParentConversationDetail";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/parent" element={<ParentDashboard />} />
        <Route path="/parent/conversation/:id" element={<ParentConversationDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
