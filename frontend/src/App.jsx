import { Route, Routes } from "react-router-dom";
import Shell from "./components/Shell";
import Home from "./pages/Home";
import PaperDetail from "./pages/PaperDetail";
import Search from "./pages/Search";
import GraphExplorer from "./pages/GraphExplorer";
import Library from "./pages/Library";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Verify from "./pages/Verify";
import Profile from "./pages/Profile";

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Home />} />
        <Route path="search" element={<Search />} />
        <Route path="library" element={<Library />} />
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="verify" element={<Verify />} />
        <Route path="profile" element={<Profile />} />
        <Route path="papers/:paperId" element={<PaperDetail />} />
        <Route path="papers/:paperId/graph" element={<GraphExplorer />} />
      </Route>
    </Routes>
  );
}
