// main.tsx
import ReactDOM from "react-dom/client";
import { HashRouter, Routes, Route } from "react-router-dom";

import App from "./App";
import { ProcessorInfoWindow } from "./pages/processor_info";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <HashRouter>
    <Routes>
      <Route path="/" element={<App />} />
      <Route path="/proccesor" element={<ProcessorInfoWindow />} />
    </Routes>
  </HashRouter>,
);
