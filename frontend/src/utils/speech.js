// Browser text-to-speech helpers for reading instructions aloud.

const LANG_CODES = { en: 'en-IN', hi: 'hi-IN', mr: 'mr-IN' };

export const isSpeechSupported = () =>
  typeof window !== 'undefined' && 'speechSynthesis' in window;

// Voices load asynchronously in Chrome, so wait for them once.
let voicesPromise = null;
export const loadVoices = () => {
  if (!isSpeechSupported()) return Promise.resolve([]);
  if (voicesPromise) return voicesPromise;
  voicesPromise = new Promise((resolve) => {
    const existing = window.speechSynthesis.getVoices();
    if (existing.length) return resolve(existing);
    const done = () => resolve(window.speechSynthesis.getVoices());
    window.speechSynthesis.addEventListener('voiceschanged', done, { once: true });
    setTimeout(done, 1500);
  });
  return voicesPromise;
};

export const findVoice = (voices, language) => {
  const code = LANG_CODES[language] || 'en-IN';
  const base = code.split('-')[0];
  return (
    voices.find((v) => v.lang === code) ||
    voices.find((v) => v.lang.replace('_', '-').toLowerCase().startsWith(base)) ||
    // Hindi voices read Marathi (same Devanagari script) far better than an English voice
    (language === 'mr' ? voices.find((v) => v.lang.toLowerCase().startsWith('hi')) : null) ||
    null
  );
};

/**
 * Speaks text. Long text is split into sentences because some browsers stop
 * reading after about 15 seconds of a single utterance.
 */
export const speak = async (text, language, { rate = 0.9, onStart, onEnd, onError } = {}) => {
  if (!isSpeechSupported()) {
    onError?.('Read-aloud is not supported in this browser.');
    return;
  }
  const synth = window.speechSynthesis;
  synth.cancel();
  if (!text?.trim()) return;

  const voices = await loadVoices();
  const voice = findVoice(voices, language);
  const chunks = text.match(/[^.!?।]+[.!?।]?/g)?.map((s) => s.trim()).filter(Boolean) || [text];

  chunks.forEach((chunk, index) => {
    const u = new SpeechSynthesisUtterance(chunk);
    u.lang = voice?.lang || LANG_CODES[language] || 'en-IN';
    if (voice) u.voice = voice;
    u.rate = rate;
    if (index === 0) u.onstart = () => onStart?.();
    if (index === chunks.length - 1) u.onend = () => onEnd?.();
    u.onerror = (e) => {
      if (e.error !== 'interrupted' && e.error !== 'canceled') onError?.(`Playback problem: ${e.error}`);
      onEnd?.();
    };
    synth.speak(u);
  });
};

export const pauseSpeech = () => isSpeechSupported() && window.speechSynthesis.pause();
export const resumeSpeech = () => isSpeechSupported() && window.speechSynthesis.resume();
export const stopSpeech = () => isSpeechSupported() && window.speechSynthesis.cancel();
