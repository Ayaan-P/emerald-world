const key = 'emerald-launcher-capability';

export function getCapability() {
  const fragment = window.location.hash.slice(1);
  if (fragment) {
    sessionStorage.setItem(key, fragment);
    history.replaceState(null, '', window.location.pathname);
  }
  return fragment || sessionStorage.getItem(key) || '';
}

async function request(path, options = {}) {
  const token = getCapability();
  if (!token) throw new Error('Start the launcher from the local Python command to connect.');
  const response = await fetch(path, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...(options.headers || {}) },
  });
  let result;
  try { result = await response.json(); } catch { throw new Error('The local launcher is unavailable.'); }
  if (!response.ok) throw new Error(result.error || 'The local launcher could not complete that action.');
  return result;
}

export const loadState = (options = {}) => request('/api/state', options);
export const forgetCapability = () => sessionStorage.removeItem(key);
export const perform = (action, payload = {}) => request('/api/action', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ action, payload }),
});
