import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { PageSpinner } from "./components/ui";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { LibraryPage } from "./pages/LibraryPage";
import { BookDetailPage } from "./pages/BookDetailPage";
import { AddBookPage } from "./pages/AddBookPage";
import { MassAddPage } from "./pages/MassAddPage";
import { LocationsPage } from "./pages/LocationsPage";
import { PeoplePage } from "./pages/PeoplePage";
import { PersonDetailPage } from "./pages/PersonDetailPage";
import { LoansPage } from "./pages/LoansPage";
import { SettingsPage } from "./pages/SettingsPage";

export function App() {
  const { me, loading } = useAuth();

  if (loading) return <PageSpinner />;
  if (!me) return <LoginPage />;

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<LibraryPage />} />
        <Route path="/books/:id" element={<BookDetailPage />} />
        <Route path="/add" element={<AddBookPage />} />
        <Route path="/scan" element={<MassAddPage />} />
        <Route path="/locations" element={<LocationsPage />} />
        <Route path="/people" element={<PeoplePage />} />
        <Route path="/people/:id" element={<PersonDetailPage />} />
        <Route path="/loans" element={<LoansPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
