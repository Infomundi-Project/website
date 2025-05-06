/* translation.js – ✨ 2025 remix */
(() => {
  'use strict';

  // ────────────── state ──────────────
  const STATE = { scriptLoaded: false };
  const PAGE_LANG = 'en';                   // whatever you set in TranslateElement
  const ONE_YEAR  = 365 * 24 * 60 * 60 * 1e3;

  function updateGoogTransCookie(target) {
    // clear it if user picked “none”
    if (target === 'none') {
      document.cookie =
        'googtrans=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT;SameSite=Lax';
      return;
    }

    const expires = new Date(Date.now() + ONE_YEAR).toUTCString();
    // If you need cross‑sub‑domain scope, add:  domain=.yourdomain.com;
    document.cookie = `googtrans=/${PAGE_LANG}/${target};path=/;expires=${expires};SameSite=Lax`;
  }


  // ────────────── bootstrap ──────────────
  document.addEventListener('DOMContentLoaded', init, { once: true });

  async function init() {
    const modalEl   = document.getElementById('translationModal');
    const modal     = new bootstrap.Modal(modalEl);
    const preferred = localStorage.getItem('preferredLanguage');
    const autoLang  = detectLang();

    wireDropdown();

    try {
      if (preferred) {
        preferred === 'none'
          ? activateNone()
          : (await loadGoogleTranslate(), applyTranslation(preferred));
      } else {
        await loadGoogleTranslate();
        applyTranslation(autoLang);
        showModal(autoLang, modal);
      }
    } catch (err) {
      console.warn('[Translate] ', err);
      // Optional: toast the user, fall back to English, whatever fits your UX
    }
  }

  // ────────────── loaders ──────────────
  function loadGoogleTranslate() {
    return new Promise((resolve, reject) => {
      if (STATE.scriptLoaded) return resolve();

      window.googleTranslateElementInit = () => {
        new google.translate.TranslateElement(
          { pageLanguage: 'en', autoDisplay: false },
          'google_translate_element'
        );
        STATE.scriptLoaded = true;
        resolve();
      };

      const s = document.createElement('script');
      s.src =
        'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
      s.defer = true;
      s.onerror = () =>
        reject(new Error('Failed to load Google Translate – maybe offline?'));
      document.head.appendChild(s);
    });
  }

  // ────────────── UI wiring ──────────────
  function wireDropdown() {
    document.querySelectorAll('[data-lang]').forEach(el =>
      el.addEventListener('click', async e => {
        e.preventDefault();
        const lang = el.dataset.lang;
        localStorage.setItem('preferredLanguage', lang);
        lang === 'none'
          ? activateNone()
          : (await loadGoogleTranslate(), applyTranslation(lang));
      })
    );
  }

  // ────────────── translation helpers ──────────────
  function applyTranslation(lang) {
    updateGoogTransCookie(lang);               // <‑‑ NEW
    waitForCombo().then(combo => {
      combo.value = lang;
      combo.dispatchEvent(new Event('change'));
      setActive(lang);
    });
  }

  function waitForCombo() {
    return new Promise(resolve => {
      const combo = document.querySelector('.goog-te-combo');
      if (combo) return resolve(combo);

      const obs = new MutationObserver(() => {
        const found = document.querySelector('.goog-te-combo');
        if (found) {
          obs.disconnect();
          resolve(found);
        }
      });
      obs.observe(document.body, { childList: true, subtree: true });
    });
  }

  // ────────────── language detection ──────────────
  function detectLang() {
    const userLang = (navigator.language || 'en').toLowerCase();
    let match = 'en';

    for (const el of document.querySelectorAll('[data-lang]')) {
      const code = el.dataset.lang.toLowerCase();
      if (
        code !== 'none' &&
        (userLang === code || userLang.split('-')[0] === code.split('-')[0])
      ) {
        match = el.dataset.lang;
        break;
      }
    }
    return match;
  }

  // ────────────── modal logic ──────────────
  function showModal(autoLang, modal) {
    const link = document.querySelector(`[data-lang="${autoLang}"]`);
    const name = link ? link.textContent.trim() : 'English';

    // update modal copy
    document.getElementById('detectedLangDisplay').textContent = name;
    document.getElementById('detectedLangInline').textContent  = name;
    document.getElementById('otherLangSelect').value           = autoLang;

    // radio‑toggle reveal
    document.querySelectorAll('input[name="translationOption"]').forEach(radio =>
      radio.addEventListener('change', () => {
        document.getElementById('other-lang-group').style.display =
          radio.id === 'opt-other' ? 'block' : 'none';
      })
    );

    // save
    document
      .getElementById('saveTranslationChoice')
      .addEventListener('click', () => {
        const optId = document.querySelector(
          'input[name="translationOption"]:checked'
        ).id;

        const target =
          optId === 'opt-auto'
            ? autoLang
            : optId === 'opt-none'
            ? 'none'
            : document.getElementById('otherLangSelect').value;

        localStorage.setItem('preferredLanguage', target);
        target === 'none' ? activateNone() : applyTranslation(target);
        modal.hide();
      });

    modal.show();
  }

  // ────────────── active states ──────────────
  function activateNone() {
    setActive('none');
    document.getElementById('current-lang').textContent = 'English';
  }

  function setActive(lang) {
    document.querySelectorAll('[data-lang]').forEach(el => {
      const isMatch = el.dataset.lang === lang;
      el.classList.toggle('active', isMatch);
      el.querySelector('.bi-check-lg')?.classList.toggle('d-none', !isMatch);

      if (isMatch && lang !== 'none') {
        document.getElementById('current-lang').textContent =
          el.textContent.trim();
      }
    });
  }
})();
