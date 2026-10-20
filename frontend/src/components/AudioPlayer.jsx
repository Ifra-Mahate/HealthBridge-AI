import React, { useEffect, useState } from 'react';
import { Headphones, Pause, Play, Square } from 'lucide-react';
import { findVoice, isSpeechSupported, loadVoices, pauseSpeech, resumeSpeech, speak, stopSpeech } from '../utils/speech';

const RATES = [
  { value: 0.75, label: 'Slow' },
  { value: 0.9, label: 'Normal' },
  { value: 1.1, label: 'Fast' },
];

const LANG_NAME = { en: 'English', hi: 'Hindi', mr: 'Marathi' };

export default function AudioPlayer({ text, language }) {
  const [state, setState] = useState('idle'); // idle | playing | paused
  const [rate, setRate] = useState(0.9);
  const [error, setError] = useState(null);
  const [voiceNote, setVoiceNote] = useState(null);
  const supported = isSpeechSupported();

  useEffect(() => {
    if (!supported) return undefined;
    let cancelled = false;
    loadVoices().then((voices) => {
      if (cancelled) return;
      const voice = findVoice(voices, language);
      if (!voice) setVoiceNote(`No ${LANG_NAME[language]} voice is installed on this device, so pronunciation may be poor.`);
      else if (language === 'mr' && voice.lang.toLowerCase().startsWith('hi')) setVoiceNote('Using a Hindi voice to read Marathi.');
      else setVoiceNote(null);
    });
    return () => { cancelled = true; stopSpeech(); };
  }, [language, supported]);

  const start = (r = rate) => {
    setError(null);
    speak(text, language, {
      rate: r,
      onStart: () => setState('playing'),
      onEnd: () => setState('idle'),
      onError: (msg) => { setError(msg); setState('idle'); },
    });
    setState('playing');
  };

  const toggle = () => {
    if (state === 'playing') { pauseSpeech(); setState('paused'); }
    else if (state === 'paused') { resumeSpeech(); setState('playing'); }
    else start();
  };

  const stop = () => { stopSpeech(); setState('idle'); };

  const changeRate = (value) => {
    setRate(value);
    if (state !== 'idle') start(value);
  };

  if (!text) return null;

  return (
    <div className="audio">
      <div className="audio-top">
        {state === 'playing' ? <span className="eq" aria-hidden="true"><i /><i /><i /></span> : <Headphones />}
        <span>{state === 'playing' ? 'Reading aloud…' : state === 'paused' ? 'Paused' : 'Listen to these instructions'}</span>
      </div>

      {supported ? (
        <>
          <div className="audio-controls">
            <button type="button" className="btn btn-primary btn-sm" onClick={toggle}>
              {state === 'playing' ? <><Pause /> Pause</> : <><Play /> {state === 'paused' ? 'Resume' : 'Play'}</>}
            </button>
            {state !== 'idle' && (
              <button type="button" className="btn btn-secondary btn-sm btn-icon" onClick={stop} aria-label="Stop reading">
                <Square />
              </button>
            )}
          </div>
          <div className="audio-rate">
            <span id="rate-label">Speed</span>
            <div className="segmented" role="group" aria-labelledby="rate-label">
              {RATES.map((r) => (
                <button key={r.value} type="button" aria-pressed={rate === r.value} onClick={() => changeRate(r.value)}>
                  {r.label}
                </button>
              ))}
            </div>
          </div>
          {voiceNote && <p className="audio-note">{voiceNote}</p>}
        </>
      ) : (
        <p className="audio-note">Read-aloud is not available in this browser. Try Chrome or Edge.</p>
      )}
      {error && <p className="audio-note bad" role="alert">{error}</p>}
    </div>
  );
}
