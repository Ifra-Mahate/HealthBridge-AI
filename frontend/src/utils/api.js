// Thin wrapper around the FastAPI backend.
// In development Vite proxies /api to http://127.0.0.1:8000. In production the
// backend serves this app itself. Set VITE_API_BASE to point elsewhere.
const BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');

async function request(path, options = {}, timeoutMs = 120000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const detail = Array.isArray(body.detail)
        ? body.detail.map((d) => d.msg).join('; ')
        : body.detail;
      const error = new Error(detail || `Server responded with status ${res.status}`);
      error.status = res.status;
      throw error;
    }
    return await res.json();
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('The server took too long to respond. Please try again.');
    if (err instanceof TypeError) {
      const offline = new Error('Cannot reach the HealthBridge server.');
      offline.offline = true;
      throw offline;
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export const getHealth = () => request('/api/health', {}, 6000);
export const getSamples = () => request('/api/samples', {}, 6000);
export const simplify = (rawText, targetLanguage) =>
  request('/api/simplify', {
    method: 'POST',
    body: JSON.stringify({ raw_text: rawText, target_language: targetLanguage }),
  });
