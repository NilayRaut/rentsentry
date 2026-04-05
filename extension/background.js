const DEFAULT_API = "https://rentsentry.onrender.com";

// Unified Promise-based storage.get (Firefox browser.* is Promise-only;
// Chrome chrome.* uses callbacks — wrap it so both work the same way)
function storageGet(key) {
  if (typeof browser !== "undefined") {
    return browser.storage.local.get(key);
  }
  return new Promise((resolve) => chrome.storage.local.get(key, resolve));
}

const _runtime = typeof browser !== "undefined" ? browser.runtime : chrome.runtime;

_runtime.onMessage.addListener((msg, _sender, respond) => {
  if (msg.type !== "ANALYZE") return false;

  storageGet("apiUrl")
    .then(({ apiUrl }) => {
      const base = apiUrl || DEFAULT_API;
      return fetch(`${base}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(msg.payload),
      });
    })
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((data) => respond({ ok: true, data }))
    .catch((err) => respond({ ok: false, error: err.message }));

  return true; // keep message channel open for async response
});
