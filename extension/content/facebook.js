(() => {
  // Unified Promise-based sendMessage (Firefox browser.* returns Promise;
  // Chrome chrome.* uses callbacks)
  function sendMessage(msg) {
    if (typeof browser !== "undefined") {
      return browser.runtime.sendMessage(msg);
    }
    return new Promise((resolve) => chrome.runtime.sendMessage(msg, resolve));
  }

  let analyzed = false;
  let debounceTimer = null;

  function extractAndAnalyze() {
    if (analyzed) return;

    const titleEl = document.querySelector("h1");
    if (!titleEl || !titleEl.textContent.trim()) return;

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      if (analyzed) return;

      const title = titleEl.textContent.trim() || null;

      const priceEl = [...document.querySelectorAll("span")].find((el) =>
        /^\$[\d,]+/.test(el.textContent.trim())
      );
      const price = priceEl
        ? parseFloat(priceEl.textContent.replace(/[^0-9.]/g, "")) || null
        : null;

      const descEl =
        document.querySelector('[aria-label*="description" i]') ||
        document.querySelector('[data-testid*="description" i]') ||
        [...document.querySelectorAll("div, span")].reduce((best, el) => {
          const text = el.innerText?.trim() ?? "";
          return text.length > (best?.innerText?.trim().length ?? 0) && el.children.length < 5
            ? el
            : best;
        }, null);
      const desc = descEl?.innerText?.trim() || null;

      const ogImg = document.querySelector('meta[property="og:image"]')?.content;
      const imgEls = [...document.querySelectorAll("img[src]")].filter(
        (img) => img.src.startsWith("https://") && img.naturalWidth > 100 && img.naturalHeight > 100
      );
      const images = [...new Set([ogImg, ...imgEls.map((i) => i.src)].filter(Boolean))].slice(0, 10);

      if (!title) return;

      analyzed = true;
      observer.disconnect();

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
    }, 800);
  }

  const observer = new MutationObserver(extractAndAnalyze);
  observer.observe(document.body, { childList: true, subtree: true });

  extractAndAnalyze();

  // Stop observing after 15s to avoid memory leaks
  setTimeout(() => observer.disconnect(), 15000);
})();
