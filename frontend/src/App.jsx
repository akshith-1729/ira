import { Route, Routes } from "react-router-dom";
import Shell from "./components/Shell";
import Home from "./pages/Home";
import PaperDetail from "./pages/PaperDetail";
import Search from "./pages/Search";
import GraphExplorer from "./pages/GraphExplorer";

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Home />} />
        <Route path="search" element={<Search />} />
        <Route path="papers/:paperId" element={<PaperDetail />} />
        <Route path="papers/:paperId/graph" element={<GraphExplorer />} />
      </Route>
    </Routes>
  );
}
