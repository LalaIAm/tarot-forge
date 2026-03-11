import { BrowserRouter, Route, Routes } from "react-router-dom";
import DeckProgressPage from "./pages/DeckProgressPage";
import StartPage from "./pages/StartPage";
import StyleBiblePage from "./pages/StyleBiblePage";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<StartPage />} />
        <Route path="/style-bible" element={<StyleBiblePage />} />
        <Route path="/decks/:deckId" element={<DeckProgressPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
