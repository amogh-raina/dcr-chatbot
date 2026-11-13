import { createRoot } from 'react-dom/client';
import './theme.css';
import './styles.css';
import App from './App.jsx';

// Themes belong to the application pages only. The FAQ page (with the SU-support chat) always uses its own light look.
const themed = ['/application', '/mitid'].includes(location.pathname);
try {
  const saved = themed ? localStorage.getItem('su-theme') : 'light';
  if (['light', 'warm', 'dark'].includes(saved)) document.documentElement.setAttribute('data-theme', saved);
} catch { if (!themed) document.documentElement.setAttribute('data-theme', 'light'); }

createRoot(document.getElementById('root')).render(<App />);
