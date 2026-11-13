import { Link, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { BoardPage } from "./pages/BoardPage";
import { GamePage } from "./pages/GamePage";
import { MatchmakingPage } from "./pages/MatchmakingPage";
import { HistoryPage } from "./pages/HistoryPage";
import { ImportPage } from "./pages/ImportPage";
import { ReplayPage } from "./pages/ReplayPage";

export function App() {
  return <Routes>
    <Route element={<Layout />}>
      <Route index element={<HomePage />} />
      <Route path="login" element={<LoginPage />} />
      <Route path="register" element={<RegisterPage />} />
      <Route path="practice" element={<BoardPage />} />
      <Route path="play" element={<MatchmakingPage />} />
      <Route path="history" element={<HistoryPage />} />
      <Route path="history/import" element={<ImportPage />} />
      <Route path="history/:source/:id" element={<ReplayPage />} />
      <Route path="games" element={<GamePage />} />
      <Route path="games/:id" element={<GamePage />} />
      <Route path="*" element={<div className="not-found page-width">
        <h1 tabIndex={-1}>That page isn't on the board.</h1>
        <p>Check the address or head back to Chess Room.</p>
        <Link className="button-primary" to="/">Back to the room</Link>
      </div>} />
    </Route>
  </Routes>;
}
