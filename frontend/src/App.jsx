import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import Header from './components/Header';
import StatusNotice from './components/StatusNotice';
import Hero from './components/Hero';
import InputSection from './components/InputSection';
import LoadingState from './components/LoadingState';
import Results from './components/Results';
import DisclaimerModal from './components/DisclaimerModal';
import Footer from './components/Footer';
import { CLIENT_SAMPLES } from './utils/samples';
import { getHealth, getSamples, simplify } from './utils/api';
import { load, save, saveRaw } from './utils/storage';

const HISTORY_KEY = 'hb-history';
const MAX_HISTORY = 5;

const historyTitle = (text) => {
  const med = text.match(/\b([A-Z][a-zA-Z]{3,})\s+\d/);
  return med ? med[1] : text.replace(/^rx:\s*/i, '').slice(0, 32);
};

export default function App() {
  const [health, setHealth] = useState(null);
  const [backend, setBackend] = useState('checking'); // checking | online | offline
  const [samples, setSamples] = useState(CLIENT_SAMPLES);
  const [rawText, setRawText] = useState(CLIENT_SAMPLES[0].raw_text);
  const [targetLang, setTargetLang] = useState(() => load('hb-lang', 'en'));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState(() => load(HISTORY_KEY, []));
  const [disclaimerOpen, setDisclaimerOpen] = useState(() => !load('hb-disclaimer-ack', false));
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'system');
  const [textSize, setTextSize] = useState(() => document.documentElement.dataset.size || 'md');
  const [toast, setToast] = useState(null);
  const resultsRef = useRef(null);
  const toastTimer = useRef(null);

  const checkBackend = useCallback(async () => {
    setBackend('checking');
    try {
      const data = await getHealth();
      setHealth(data);
      setBackend('online');
      getSamples()
        .then((list) => Array.isArray(list) && list.length && setSamples(list))
        .catch(() => {});
    } catch {
      setBackend('offline');
    }
  }, []);

  useEffect(() => {
    checkBackend();
  }, [checkBackend]);

  // Theme: 'system' follows the OS, otherwise force light or dark
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'system') delete root.dataset.theme;
    else root.dataset.theme = theme;
    saveRaw('hb-theme', theme);
  }, [theme]);

  useEffect(() => {
    const root = document.documentElement;
    if (textSize === 'md') delete root.dataset.size;
    else root.dataset.size = textSize;
    saveRaw('hb-text-size', textSize);
  }, [textSize]);

  useEffect(() => save('hb-lang', targetLang), [targetLang]);

  const showToast = useCallback((message) => {
    setToast(message);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2400);
  }, []);

  const scrollToResults = () =>
    requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));

  const handleSimplify = async () => {
    const text = rawText.trim();
    if (text.length < 5) {
      setError('Please enter the prescription text, or choose one of the examples.');
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    scrollToResults();
    try {
      const data = { ...(await simplify(text, targetLang)), source_text: text };
      setResult(data);
      setBackend('online');
      const entry = { id: Date.now(), title: historyTitle(text), text, lang: targetLang, result: data };
      setHistory((prev) => {
        const next = [entry, ...prev.filter((h) => !(h.text === text && h.lang === targetLang))].slice(0, MAX_HISTORY);
        save(HISTORY_KEY, next);
        return next;
      });
      scrollToResults();
    } catch (err) {
      if (err.offline) setBackend('offline');
      setError(err.offline
        ? 'The HealthBridge server is not running. Start the backend (see the notice at the top of the page), then try again.'
        : err.message);
    } finally {
      setLoading(false);
    }
  };

  const openHistory = (entry) => {
    setRawText(entry.text);
    setTargetLang(entry.lang);
    setResult(entry.result);
    setError(null);
    scrollToResults();
  };

  const clearHistory = () => {
    setHistory([]);
    save(HISTORY_KEY, []);
  };

  const startOver = () => {
    setResult(null);
    setRawText('');
    setError(null);
    document.getElementById('prescription')?.scrollIntoView({ behavior: 'smooth' });
    setTimeout(() => document.getElementById('rx-input')?.focus(), 400);
  };

  const closeDisclaimer = () => {
    setDisclaimerOpen(false);
    save('hb-disclaimer-ack', true);
  };

  return (
    <div className="app">
      <a className="skip-link" href="#prescription">Skip to the prescription form</a>
      <Header
        backend={backend}
        health={health}
        theme={theme}
        onThemeChange={setTheme}
        textSize={textSize}
        onTextSizeChange={setTextSize}
        onOpenDisclaimer={() => setDisclaimerOpen(true)}
      />

      <main className="main">
        <div className="container">
          <StatusNotice backend={backend} health={health} onRetry={checkBackend} />
          <Hero />
          <InputSection
            rawText={rawText}
            setRawText={setRawText}
            targetLang={targetLang}
            setTargetLang={setTargetLang}
            samples={samples}
            onSubmit={handleSimplify}
            loading={loading}
            error={error}
            onClear={() => { setRawText(''); setError(null); }}
            history={history}
            onOpenHistory={openHistory}
            onClearHistory={clearHistory}
          />
          <div ref={resultsRef} className="results-anchor">
            {loading && <LoadingState />}
            {!loading && result && (
              <Results
                key={result.simplified_text + result.target_language}
                result={result}
                originalText={result.source_text || rawText}
                onStartOver={startOver}
                onToast={showToast}
              />
            )}
          </div>
        </div>
      </main>

      <Footer onOpenDisclaimer={() => setDisclaimerOpen(true)} />
      <DisclaimerModal isOpen={disclaimerOpen} onClose={closeDisclaimer} />
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 /> {toast}
        </div>
      )}
    </div>
  );
}
