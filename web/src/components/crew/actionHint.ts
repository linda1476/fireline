import type { Brief } from "@/lib/types"

/** Derived action hint (CONTRACT "Briefs on the crew screen"). */
export function actionHint(tag: string | null | undefined, priority: Brief["priority"]): string {
  if (tag === "MAYDAY" || priority === "P0") return "확인 후 즉시 보고"
  if (tag === "DANGER") return "경로 확인"
  if (tag === "VICTIM_FOUND") return "구조 진행"
  return "참고"
}
