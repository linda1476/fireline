// Browser TTS (non-Meta). speak() QUEUES (never cancels): on /demo two crew phones share one speechSynthesis queue,
// and a brief pushed to both units in the same tick must be heard twice. stop() clears the queue.
import type { Lang } from "./types"

function pickVoice(lang: Lang): SpeechSynthesisVoice | undefined {
  if (typeof window === "undefined" || !window.speechSynthesis) return undefined
  const want = lang === "ko" ? "ko" : "en"
  const voices = window.speechSynthesis.getVoices()
  const exact = voices.find((v) => v.lang.toLowerCase() === (lang === "ko" ? "ko-kr" : "en-us"))
  return exact ?? voices.find((v) => v.lang.toLowerCase().startsWith(want))
}

export function speak(text: string, lang: Lang = "ko", rate = 1.05): void {
  if (typeof window === "undefined" || !window.speechSynthesis || !text) return
  const synth = window.speechSynthesis
  const u = new SpeechSynthesisUtterance(text)
  u.lang = lang === "ko" ? "ko-KR" : "en-US"
  const v = pickVoice(lang)
  if (v) u.voice = v
  u.rate = rate
  synth.speak(u)
}

export function stop(): void {
  if (typeof window !== "undefined" && window.speechSynthesis) window.speechSynthesis.cancel()
}

export const TTS_LABEL = "TTS: browser (non-Meta)"
