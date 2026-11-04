import { BrowserRouter, Route, Routes } from "react-router"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import Command from "@/routes/Command"
import Crew from "@/routes/Crew"
import Demo from "@/routes/Demo"
import Eval from "@/routes/Eval"
import Launcher from "@/routes/Launcher"

export default function App() {
  return (
    <TooltipProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Launcher />} />
          <Route path="/command" element={<Command />} />
          <Route path="/crew/:unitId" element={<Crew />} />
          <Route path="/demo" element={<Demo />} />
          <Route path="/eval" element={<Eval />} />
          <Route path="*" element={<Launcher />} />
        </Routes>
      </BrowserRouter>
      <Toaster theme="dark" position="top-center" richColors />
    </TooltipProvider>
  )
}
