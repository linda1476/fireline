// Browser TTS (non-Meta). speak() cancels whatever is playing first.
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
  synth.cancel()
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
