(() => {
  // Unified Promise-based sendMessage (Firefox browser.* returns Promise;
  // Chrome chrome.* uses callbacks)
  function sendMessage(msg) {
    if (typeof browser !== "undefined") {
      return browser.runtime.sendMessage(msg);
    }
    return new Promise((resolve) => chrome.runtime.sendMessage(msg, resolve));
  }

  const titleEl = document.querySelector("#titletextonly");
  if (!titleEl) return; // not a listing page

  const title = titleEl.textContent.trim() || null;

  const priceRaw = document.querySelector(".price")?.textContent ?? "";
  const price = priceRaw ? parseFloat(priceRaw.replace(/[^0-9.]/g, "")) || null : null;

  // Strip the QR code footer the same way scraper.py does
  let desc = null;
  const descEl = document.querySelector("#postingbody");
  if (descEl) {
    const clone = descEl.cloneNode(true);
    clone.querySelector(".print-qrcode-container")?.remove();
    desc = clone.innerText.trim() || null;
  }

  const images = [...document.querySelectorAll("#thumbs a")].map((a) => a.href);

  window.RentSentryBadge.mount(titleEl);

  sendMessage({ type: "ANALYZE", payload: { title, description: desc, price_usd: price, image_urls: images } })
    .then((response) => {
      if (!response || !response.ok) {
        window.RentSentryBadge.showError(response?.error);
        return;
      }
      window.RentSentryBadge.showResult(response.data);
    })
    .catch((err) => window.RentSentryBadge.showError(err?.message));
})();
