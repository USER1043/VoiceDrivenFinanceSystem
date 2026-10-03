// Microphone capture, browser speech recognition and read-aloud. Browser-only helpers.

// ---------- Recording for server speech-to-text ----------

const MIME_TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
export const MAX_RECORDING_MS = 15_000

export interface Recording {
  stop: () => Promise<{ blob: Blob; filename: string }>
  cancel: () => void
}

export async function startRecording(onAutoStop: () => void): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
  const mimeType = MIME_TYPES.find((t) => MediaRecorder.isTypeSupported(t)) ?? ''
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
  const chunks: Blob[] = []
  recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data)
  recorder.start()
  const timer = window.setTimeout(onAutoStop, MAX_RECORDING_MS)

  const release = () => {
    window.clearTimeout(timer)
    stream.getTracks().forEach((track) => track.stop())
  }
  return {
    stop: () =>
      new Promise((resolve) => {
        recorder.onstop = () => {
          release()
          const type = recorder.mimeType || 'audio/webm'
          const ext = type.includes('mp4') ? 'm4a' : type.includes('ogg') ? 'ogg' : 'webm'
          resolve({ blob: new Blob(chunks, { type }), filename: `command.${ext}` })
        }
        recorder.stop()
      }),
    cancel: () => {
      recorder.onstop = null
      if (recorder.state !== 'inactive') recorder.stop()
      release()
    },
  }
}

// ---------- Browser speech recognition (no API key needed) ----------

interface RecognitionResult {
  readonly isFinal: boolean
  readonly 0: { readonly transcript: string }
}
interface RecognitionEvent {
  readonly results: ArrayLike<RecognitionResult>
}
interface Recognition {
  lang: string
  interimResults: boolean
  continuous: boolean
  maxAlternatives: number
  onresult: ((event: RecognitionEvent) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}
type RecognitionCtor = new () => Recognition

function recognitionCtor(): RecognitionCtor | undefined {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
}

export const browserRecognitionAvailable = () => recognitionCtor() !== undefined
export const recordingAvailable = () =>
  typeof MediaRecorder !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia)

export interface Listening {
  stop: () => void
  cancel: () => void
}

/** Listens once (Indian English) and reports interim text, then the final text. */
export function listenInBrowser(handlers: {
  onInterim: (text: string) => void
  onFinal: (text: string) => void
  onError: (message: string) => void
}): Listening {
  const Ctor = recognitionCtor()
  if (!Ctor) throw new Error('Speech recognition is not available in this browser')
  const recognition = new Ctor()
  recognition.lang = 'en-IN'
  recognition.interimResults = true
  recognition.continuous = false
  recognition.maxAlternatives = 1
  let finalText = ''
  let cancelled = false
  recognition.onresult = (event) => {
    const text = Array.from(event.results, (r) => r[0].transcript).join(' ').trim()
    if (Array.from(event.results).every((r) => r.isFinal)) finalText = text
    else handlers.onInterim(text)
  }
  recognition.onerror = (event) => {
    if (event.error === 'no-speech' || event.error === 'aborted') return
    cancelled = true
    handlers.onError(event.error === 'not-allowed' ? 'Microphone permission was denied.' : `Speech recognition error: ${event.error}`)
  }
  recognition.onend = () => {
    if (!cancelled) handlers.onFinal(finalText)
  }
  recognition.start()
  return {
    stop: () => recognition.stop(),
    cancel: () => {
      cancelled = true
      recognition.abort()
    },
  }
}

// ---------- Read-aloud ----------

const SPEAK_KEY = 'voxfin.speak'

export function speakingEnabled(): boolean {
  try {
    return localStorage.getItem(SPEAK_KEY) !== 'off'
  } catch {
    return true
  }
}

export function setSpeakingEnabled(on: boolean) {
  try {
    localStorage.setItem(SPEAK_KEY, on ? 'on' : 'off')
  } catch {
    // storage blocked; the setting just won't persist
  }
}

export function speak(text: string) {
  if (!speakingEnabled() || !('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text.replace(/₹/g, 'rupees '))
  utterance.lang = 'en-IN'
  utterance.rate = 1.05
  window.speechSynthesis.speak(utterance)
}
