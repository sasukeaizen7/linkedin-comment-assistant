// Service worker: forwards suggestion requests to the local model server.
// Content scripts can't call localhost themselves (LinkedIn's CORS and
// Chrome's Private Network Access rules); the worker can, via host_permissions.
const API = 'http://127.0.0.1:8008';

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || msg?.type !== 'suggest') return false;
  fetch(`${API}/suggest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ post: msg.post, n: 3 }),
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then((data) => sendResponse({ ok: true, data }))
    .catch((err) => sendResponse({ ok: false, error: err.message }));
  return true; // async response
});
