import { Link, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";

export function App() {
  return <Routes>
    <Route element={<Layout />}>
      <Route index element={<HomePage />} />
      <Route path="login" element={<LoginPage />} />
      <Route path="register" element={<RegisterPage />} />
      <Route path="*" element={<div className="not-found page-width">
        <h1 tabIndex={-1}>That page isn't on the board.</h1>
        <p>Check the address or head back to Chess Room.</p>
        <Link className="button-primary" to="/">Back to the room</Link>
      </div>} />
    </Route>
  </Routes>;
}
