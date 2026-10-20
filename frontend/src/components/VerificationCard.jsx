import React, { useState } from 'react';
import {
  AlertTriangle, Ban, CheckCircle2, ChevronDown, Clock3, FileSearch, Hash, Info, Siren, Utensils, XCircle,
} from 'lucide-react';

const CHECKS = [
  { key: 'numeric_check', label: 'Numbers & doses', icon: Hash, severity: 'bad' },
  { key: 'negation_check', label: 'Prohibitions', icon: Ban, severity: 'warn' },
  { key: 'frequency_check', label: 'Schedule', icon: Clock3, severity: 'warn' },
  { key: 'timing_check', label: 'Food & timing', icon: Utensils, severity: 'warn' },
  { key: 'warning_check', label: 'Warning signs', icon: Siren, severity: 'bad' },
];

const tone = (score) => (score >= 85 ? 'ok' : score >= 60 ? 'warn' : 'bad');

const HEADLINE = {
  VERIFIED: 'All key facts were preserved',
  CAUTION: 'Mostly preserved: please review the flags below',
  CRITICAL_MISMATCH: 'Important details could not be confirmed',
};

function ScoreRing({ score }) {
  const r = 42;
  const circumference = 2 * Math.PI * r;
  const t = tone(score);
  return (
    <div className={`score-ring tone-${t}`} role="img" aria-label={`Safety score ${score} out of 100`}>
      <svg viewBox="0 0 100 100">
        <circle className="track" cx="50" cy="50" r={r} />
        <circle
          className={`value tone-${t}`}
          cx="50" cy="50" r={r}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - score / 100)}
        />
      </svg>
      <div className="score-ring-label">
        <strong className={`tone-${t}`}>{score}</strong>
        <span>of 100</span>
      </div>
    </div>
  );
}

function Tags({ items, verified = [], missing = [], empty }) {
  if (!items?.length) return <span className="tag-empty">{empty}</span>;
  return (
    <div className="tags">
      {items.map((item, i) => {
        const isMissing = missing.includes(item);
        const isOk = !isMissing && verified.includes(item);
        return (
          <span key={i} className={`tag ${isMissing ? 'bad' : isOk ? 'ok' : ''}`}>
            {isMissing ? <XCircle /> : isOk ? <CheckCircle2 /> : null}
            {item}
          </span>
        );
      })}
    </div>
  );
}

export default function VerificationCard({ verification, extracted, originalText, simplifiedText, language }) {
  const [open, setOpen] = useState(false);
  if (!verification) return null;
  const { score, status, numeric_check: numeric, flags = [], ambiguity_warnings: ambiguities = [] } = verification;

  return (
    <section className="panel panel-pad" aria-labelledby="audit-title">
      <div className="audit-top">
        <ScoreRing score={score} />
        <div className="audit-summary">
          <span className="section-label">Safety check</span>
          <h3 id="audit-title">{HEADLINE[status] || verification.summary}</h3>
          <p>
            HealthBridge compared the simplified text with your original prescription, checking that every
            number, prohibition, schedule and warning sign was kept.
          </p>
        </div>
      </div>

      <div className="checks">
        {CHECKS.map(({ key, label, icon: Icon, severity }) => {
          const check = verification[key];
          if (!check) return null;
          const passed = check.passed;
          const cls = passed ? '' : severity === 'bad' ? 'is-bad' : 'is-warn';
          return (
            <div key={key} className={`check ${cls}`}>
              <div className="check-top">
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <Icon style={{ width: 16, height: 16, color: 'var(--text-3)' }} /> {label}
                </span>
                {passed
                  ? <CheckCircle2 className="tone-ok" style={{ stroke: 'currentColor' }} aria-label="Passed" />
                  : severity === 'bad'
                    ? <XCircle className="tone-bad" style={{ stroke: 'currentColor' }} aria-label="Failed" />
                    : <AlertTriangle className="tone-warn" style={{ stroke: 'currentColor' }} aria-label="Needs review" />}
              </div>
              <p>{check.details}</p>
            </div>
          );
        })}
      </div>

      {(flags.length > 0 || ambiguities.length > 0) && (
        <div className="flags">
          {flags.map((flag, i) => (
            <div key={`f${i}`} className="notice notice-bad">
              <AlertTriangle />
              <div className="notice-body"><p>{flag}</p></div>
            </div>
          ))}
          {ambiguities.map((text, i) => (
            <div key={`a${i}`} className="notice notice-warn">
              <Info />
              <div className="notice-body"><p>{text.replace(/^Ambiguity:\s*/i, '')}</p></div>
            </div>
          ))}
        </div>
      )}

      <div className="disclosure no-print">
        <button type="button" className="disclosure-btn" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          <FileSearch /> {open ? 'Hide details' : 'Compare with the original and see what was checked'} <ChevronDown />
        </button>

        {open && (
          <>
            <div className="compare">
              <div className="compare-col">
                <span className="section-label">Original prescription</span>
                <p>{originalText}</p>
              </div>
              <div className="compare-col">
                <span className="section-label">Simplified</span>
                <p lang={language}>{simplifiedText}</p>
              </div>
            </div>

            <div className="facts">
              <div className="fact-group">
                <h4>Medicines found</h4>
                <Tags items={extracted?.medications} empty="No named medicines detected" />
              </div>
              <div className="fact-group">
                <h4>Numbers and doses</h4>
                <Tags items={numeric?.items_original} verified={numeric?.items_verified} missing={numeric?.items_missing} empty="No numbers detected" />
              </div>
              <div className="fact-group">
                <h4>Schedule</h4>
                <Tags items={[...(extracted?.frequencies || []).map((f) => f.replace(/^.*\[(.*)\]$/, '$1')), ...(extracted?.durations || [])]} empty="No schedule detected" />
              </div>
              <div className="fact-group">
                <h4>Food and timing</h4>
                <Tags items={extracted?.timings} empty="No food or timing rules detected" />
              </div>
              <div className="fact-group">
                <h4>Prohibitions</h4>
                <Tags items={extracted?.negations} empty="No prohibitions detected" />
              </div>
              <div className="fact-group">
                <h4>Warning signs</h4>
                <Tags items={extracted?.warnings} empty="No warning signs detected" />
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
