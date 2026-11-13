import { useEffect, useRef, useState } from 'react';
import Icon from './Icon';

const THEMES = [['light', 'Light', 'sun'], ['warm', 'Warm', 'leaf'], ['dark', 'Dark', 'moon']];
const KEY = 'su-theme';

function read() {
  try { const saved = localStorage.getItem(KEY); if (THEMES.some(t => t[0] === saved)) return saved; } catch { /* storage blocked */ }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

// Segmented Light / Warm / Dark control. Sets data-theme on <html>; the choice is remembered per browser.
export default function ThemeToggle({ compact = false }) {
  const [theme, setTheme] = useState(read);
  const timer = useRef(null);
  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); }, [theme]);
  function choose(next) {
    if (next === theme) return;
    document.documentElement.classList.add('theme-anim');
    clearTimeout(timer.current);
    timer.current = setTimeout(() => document.documentElement.classList.remove('theme-anim'), 500);
    setTheme(next);
    try { localStorage.setItem(KEY, next); } catch { /* storage blocked */ }
  }
  function keys(event) {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    event.preventDefault();
    const at = THEMES.findIndex(t => t[0] === theme);
    const next = THEMES[(at + (event.key === 'ArrowRight' ? 1 : 2)) % 3][0];
    choose(next);
    event.currentTarget.querySelector(`[data-theme-id="${next}"]`)?.focus();
  }
  return <div className={`theme-toggle${compact ? ' compact' : ''}`} role="radiogroup" aria-label="Colour theme"
    style={{ '--i': THEMES.findIndex(t => t[0] === theme) }} onKeyDown={keys}>
    {THEMES.map(([id, text, icon]) => <button key={id} type="button" role="radio" data-theme-id={id}
      aria-checked={theme === id} aria-label={compact ? text : undefined} title={text} tabIndex={theme === id ? 0 : -1}
      onClick={() => choose(id)}>
      {compact ? <Icon name={icon} size={16} /> : text}
    </button>)}
  </div>;
}
