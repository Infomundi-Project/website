let scriptLoaded = false;

// Set up everything once the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const modalEl = document.getElementById('translationModal');
  const modal = new bootstrap.Modal(modalEl);
  const preferred = localStorage.getItem('preferredLanguage');
  const autoLang = detectLang();

  setupDropdown();

  if (preferred) {
    if (preferred === 'none') {
      // User has disabled translation
      setActiveNone();
    } else {
      // Already chosen a language: load widget and apply
      loadGoogleTranslate(() => applyTranslation(preferred, false));
    }
  } else {
    // No preference yet: load widget first, then translate+show modal
    loadGoogleTranslate(() => {
      applyTranslation(autoLang, false);
      showModal(autoLang, modal);
    });
  }
});

// Dynamically inject Google Translate script, cb when ready
function loadGoogleTranslate(onReady) {
  if (scriptLoaded) return onReady();
  window.googleTranslateElementInit = () => {
    new google.translate.TranslateElement(
      { pageLanguage: 'en', autoDisplay: false },
      'google_translate_element'
    );
    scriptLoaded = true;
    onReady();
  };
  const script = document.createElement('script');
  script.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
  script.defer = true;
  document.body.appendChild(script);
}

// Wire the navbar dropdown for immediate switching
function setupDropdown() {
  document.querySelectorAll('[data-lang]').forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      const lang = item.getAttribute('data-lang');
      localStorage.setItem('preferredLanguage', lang);
      if (lang === 'none') {
        setActiveNone();
      } else {
        loadGoogleTranslate(() => applyTranslation(lang, false));
      }
    });
  });
}

function detectLang() {
  const userLang = (navigator.language || 'en').toLowerCase();
  let match = 'en';
  document.querySelectorAll('[data-lang]').forEach(it => {
    const code = it.getAttribute('data-lang').toLowerCase();
    if (
      code !== 'none' &&
      (userLang === code || userLang.split('-')[0] === code.split('-')[0])
    ) {
      match = it.getAttribute('data-lang');
    }
  });
  return match;
}

function showModal(autoLang, modal) {
  const link = document.querySelector(`[data-lang="${autoLang}"]`);
  const name = link ? link.textContent.trim() : 'English';
  document.getElementById('detectedLangDisplay').textContent = name;
  document.getElementById('detectedLangInline').textContent = name;
  document.getElementById('otherLangSelect').value = autoLang;

  document.querySelectorAll('input[name="translationOption"]').forEach(radio => {
    radio.addEventListener('change', () => {
      document.getElementById('other-lang-group').style.display =
        radio.id === 'opt-other' ? 'block' : 'none';
    });
  });

  document.getElementById('saveTranslationChoice').addEventListener('click', () => {
    const opt = document.querySelector('input[name="translationOption"]:checked').id;
    let target;
    if (opt === 'opt-auto') target = autoLang;
    else if (opt === 'opt-none') target = 'none';
    else target = document.getElementById('otherLangSelect').value;

    localStorage.setItem('preferredLanguage', target);
    if (target === 'none') {
      setActiveNone();
    } else {
      applyTranslation(target, false);
    }
    modal.hide();
  });

  modal.show();
}

function applyTranslation(lang, store) {
  const interval = setInterval(() => {
    const combo = document.querySelector('.goog-te-combo');
    if (!combo) return;
    clearInterval(interval);
    combo.value = lang;
    combo.dispatchEvent(new Event('change'));
    setActive(lang);
  }, 200);
}

function setActiveNone() {
  document.querySelectorAll('[data-lang]').forEach(it => {
    const check = it.querySelector('.bi-check-lg');
    if (it.getAttribute('data-lang') === 'none') {
      it.classList.add('active');
      check && check.classList.remove('d-none');
    } else {
      it.classList.remove('active');
      check && check.classList.add('d-none');
    }
  });
  document.getElementById('current-lang').textContent = 'English';
}

function setActive(lang) {
  document.querySelectorAll('[data-lang]').forEach(it => {
    const check = it.querySelector('.bi-check-lg');
    if (it.getAttribute('data-lang') === lang) {
      it.classList.add('active');
      check && check.classList.remove('d-none');
      document.getElementById('current-lang').textContent = it.textContent.trim();
    } else {
      it.classList.remove('active');
      check && check.classList.add('d-none');
    }
  });
}