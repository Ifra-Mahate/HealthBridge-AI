import React from 'react';
import {
  Activity, AlertTriangle, ArrowRight, Droplets, FileText, HeartPulse, History,
  LoaderCircle, Pill, Sparkles, Trash2, Wind, X,
} from 'lucide-react';

const MAX_CHARS = 4000;

const LANGUAGES = [
  { code: 'en', label: 'English', hint: 'Simple' },
  { code: 'hi', label: 'हिन्दी', hint: 'Hindi' },
  { code: 'mr', label: 'मराठी', hint: 'Marathi' },
];

const LANG_SHORT = { en: 'EN', hi: 'HI', mr: 'MR' };

const sampleIcon = (sample) => {
  const key = `${sample.category} ${sample.title}`.toLowerCase();
  if (key.includes('asthma') || key.includes('inhal')) return Wind;
  if (key.includes('diabet')) return Droplets;
  if (key.includes('blood pressure') || key.includes('cardio')) return HeartPulse;
  if (key.includes('pain')) return Activity;
  return Pill;
};

export default function InputSection({
  rawText, setRawText, targetLang, setTargetLang, samples, onSubmit, loading, error, onClear,
  history, onOpenHistory, onClearHistory,
}) {
  const over = rawText.length > MAX_CHARS;
  const canSubmit = !loading && rawText.trim().length >= 5 && !over;

  const handleKeyDown = (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && canSubmit) {
      event.preventDefault();
      onSubmit();
    }
  };

  return (
    <section className="panel panel-pad composer" id="prescription" aria-labelledby="composer-title">
      <div className="panel-head">
        <div className="panel-title">
          <span className="panel-icon"><FileText /></span>
          <div>
            <h2 id="composer-title">What did your doctor prescribe?</h2>
            <p className="panel-sub">Paste the instructions exactly as written, or start from an example.</p>
          </div>
        </div>
      </div>

      <div className="composer-grid">
        <div>
          <div className="field-label">
            <label htmlFor="rx-input">Prescription or medical instructions</label>
            {rawText && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={onClear}>
                <X /> Clear
              </button>
            )}
          </div>
          <div className="textarea-wrap">
            <textarea
              id="rx-input"
              className="textarea"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="For example: Tab Paracetamol 500 mg, 1 tablet three times a day after food for 5 days. Do not exceed 4 tablets in 24 hours."
              aria-describedby="rx-meta"
              aria-invalid={over}
              spellCheck="false"
            />
            <div className="textarea-meta" id="rx-meta">
              <span><kbd>Ctrl</kbd> + <kbd>Enter</kbd> to simplify</span>
              <span className={over ? 'over' : ''}>{rawText.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}</span>
            </div>
          </div>
        </div>

        <div className="samples" role="group" aria-label="Example prescriptions">
          <div className="samples-head">
            <span className="section-label">Try an example</span>
          </div>
          {samples.map((sample) => {
            const Icon = sampleIcon(sample);
            const selected = rawText === sample.raw_text;
            return (
              <button
                key={sample.id}
                type="button"
                className="sample"
                aria-pressed={selected}
                onClick={() => setRawText(sample.raw_text)}
              >
                <span className="sample-icon"><Icon /></span>
                <span className="sample-text">
                  <span className="sample-title">{sample.title}</span>
                  <span className="sample-cat">{sample.category}</span>
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <div className="notice notice-bad form-error" role="alert">
          <AlertTriangle />
          <div className="notice-body">
            <p><strong>We couldn't simplify that yet.</strong></p>
            <p>{error}</p>
          </div>
        </div>
      )}

      <div className="composer-foot">
        <div className="lang-group">
          <span className="section-label" id="lang-label">Show instructions in</span>
          <div className="segmented" role="group" aria-labelledby="lang-label">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                type="button"
                aria-pressed={targetLang === lang.code}
                onClick={() => setTargetLang(lang.code)}
                lang={lang.code}
              >
                {lang.label}
                <small>{lang.hint}</small>
              </button>
            ))}
          </div>
        </div>

        <div className="composer-submit">
          <button type="button" className="btn btn-primary btn-lg" onClick={onSubmit} disabled={!canSubmit}>
            {loading ? (
              <><LoaderCircle className="spin" /> Preparing your guide…</>
            ) : (
              <><Sparkles /> Simplify instructions <ArrowRight /></>
            )}
          </button>
        </div>
      </div>

      {history.length > 0 && (
        <div className="history" aria-label="Recent">
          <span className="section-label" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <History size={14} /> Recent
          </span>
          {history.map((entry) => (
            <button key={entry.id} type="button" className="history-chip" onClick={() => onOpenHistory(entry)} title={entry.text}>
              <span>{entry.title}</span>
              <span className="pill pill-neutral" style={{ padding: '0 .4rem', fontSize: '.65rem' }}>{LANG_SHORT[entry.lang]}</span>
            </button>
          ))}
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClearHistory} aria-label="Clear recent history">
            <Trash2 />
          </button>
        </div>
      )}
    </section>
  );
}
