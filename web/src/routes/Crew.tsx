import { Link, useParams } from "react-router"
import PhoneFrame from "@/components/crew/PhoneFrame"
import CrewView from "@/components/crew/CrewView"

export default function Crew() {
  const { unitId = "kim" } = useParams()
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-3 bg-neutral-800 p-4">
      <Link to="/" className="self-start text-xs text-neutral-400 hover:text-neutral-100">
        ← back
      </Link>
      <PhoneFrame>
        <CrewView unitId={unitId} />
      </PhoneFrame>
    </div>
  )
}
