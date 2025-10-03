
document.addEventListener('DOMContentLoaded', function () {
  const checkbox = document.getElementById("infThemeToggleClicker");
  if (checkbox) checkbox.addEventListener('click', toggleTheme);
});

const setCookie = (name, value, daysToExpire) => {
  const expires = new Date(Date.now() + daysToExpire * 864e5).toUTCString();
  document.cookie = `${name}=${value}; expires=${expires}; path=/`;
};

const toggleTheme = () => {
  const htmlEl = document.documentElement;
  const curr = htmlEl.getAttribute('data-bs-theme') || 'light';
  const next = curr === 'dark' ? 'light' : 'dark';
  htmlEl.setAttribute('data-bs-theme', next);

  // logos + icons
  Array.from(document.getElementsByClassName('infomundi-logo'))
       .forEach(img => img.src = `/static/img/logos/logo-wide-${next}-resized.webp`);
  Array.from(document.getElementsByClassName('infomundi-icon'))
       .forEach(img => img.src = `/static/img/logos/logo-icon-${next}.webp`);

  setCookie('theme', next, 30);
  updateButtonClasses(next);
  updateTurnstileTheme(next);

  // full reload so BS picks up new theme everywhere
  window.location.reload();
};

const updateButtonClasses = theme => {
  document.querySelectorAll('.btn-outline-light')
    .forEach(b => b.classList.replace('btn-outline-light', 'btn-outline-dark'));
  document.querySelectorAll('.btn-outline-dark')
    .forEach(b => b.classList.replace('btn-outline-dark', 'btn-outline-light'));
};

const updateTurnstileTheme = theme => {
  document.querySelectorAll('.cf-turnstile')
    .forEach(el => el.setAttribute('data-theme', theme));
};
