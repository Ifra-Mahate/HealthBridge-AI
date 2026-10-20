import React from 'react';
import { HeartPulse, Monitor, Moon, ShieldCheck, Sun } from 'lucide-react';

const THEMES = ['system', 'light', 'dark'];
const THEME_ICON = { system: Monitor, light: Sun, dark: Moon };
const THEME_LABEL = { system: 'Theme: follows device', light: 'Theme: light', dark: 'Theme: dark' };

export default function Header({ backend, health, theme, onThemeChange, textSize, onTextSizeChange, onOpenDisclaimer }) {
  const ThemeIcon = THEME_ICON[theme] || Monitor;
  const nextTheme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];

  let status = { cls: 'pill-neutral status-checking', text: 'Connecting…' };
  if (backend === 'offline') status = { cls: 'pill-bad', text: 'Server offline' };
  else if (backend === 'online' && health?.ai_configured) status = { cls: 'pill-ok', text: 'AI connected' };
  else if (backend === 'online') status = { cls: 'pill-brand', text: 'Rule engine ready' };

  return (
    <header className="site-header">
      <div className="container header-inner">
        <a className="brand" href="#top" onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>
          <span className="brand-mark"><HeartPulse /></span>
          <span className="brand-name">HealthBridge <span>AI</span></span>
        </a>

        <div className="header-actions">
          <span className={`pill ${status.cls}`} role="status" title={status.text}>
            <span className="status-dot" />
            <span className="header-status-text">{status.text}</span>
          </span>

          <div className="size-toggle" role="group" aria-label="Text size">
            {[['md', 'Normal text'], ['lg', 'Large text'], ['xl', 'Extra large text']].map(([size, label]) => (
              <button
                key={size}
                type="button"
                aria-pressed={textSize === size}
                aria-label={label}
                title={label}
                onClick={() => onTextSizeChange(size)}
              >
                A
              </button>
            ))}
          </div>

          <button
            type="button"
            className="btn btn-ghost btn-icon"
            onClick={() => onThemeChange(nextTheme)}
            aria-label={`${THEME_LABEL[theme]}. Switch to ${nextTheme}.`}
            title={THEME_LABEL[theme]}
          >
            <ThemeIcon />
          </button>

          <button type="button" className="btn btn-ghost btn-sm" onClick={onOpenDisclaimer}>
            <ShieldCheck />
            <span className="header-safety-text">Safety</span>
          </button>
        </div>
      </div>
    </header>
  );
}
