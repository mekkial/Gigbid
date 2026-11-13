import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { useAuth } from "./lib/auth";
import { Login } from "./app/login";
import { Onboarding } from "./app/onboarding";
import { Inbox } from "./app/inbox";
import { JobDetailPage } from "./app/job-detail";
import { Studio } from "./app/studio";
import { Pipeline } from "./app/pipeline";
import { Messages } from "./app/messages";
import { RunViewer, RunsList } from "./app/runs";
import { Analytics } from "./app/analytics";
import { SettingsPage } from "./app/settings";

export default function App() {
  const { token } = useAuth();
  if (!token) return <Routes><Route path="*" element={<Login />} /></Routes>;
  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/inbox" />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/inbox" />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/inbox" element={<Inbox />} />
        <Route path="/jobs/:id" element={<JobDetailPage />} />
        <Route path="/studio/:id" element={<Studio />} />
        <Route path="/pipeline" element={<Pipeline />} />
        <Route path="/messages" element={<Messages />} />
        <Route path="/runs" element={<RunsList />} />
        <Route path="/runs/:id" element={<RunViewer />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
