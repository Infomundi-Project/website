document.addEventListener('DOMContentLoaded', function() {
  const checkbox = document.getElementById("theme-checkbox");

  if (checkbox) { // Check if the checkbox element exists
    checkbox.addEventListener('click', toggleTheme);
  }
});

const setCookie = (name, value, daysToExpire) => {
  const expirationDate = new Date();
  expirationDate.setDate(expirationDate.getDate() + daysToExpire);

  const cookieString = `${name}=${value}; expires=${expirationDate.toUTCString()}; path=/`;
  document.cookie = cookieString;
};

const toggleTheme = () => {
  const htmlElement = document.querySelector('html');
  const currentTheme = htmlElement.getAttribute('data-bs-theme') || 'light';

  // Toggle between 'dark' and 'light'
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

  // Set the new theme value
  htmlElement.setAttribute('data-bs-theme', newTheme);

  // Change infomundi logos and icons
  const infomundiLogos = document.getElementsByClassName('infomundi-logo');
  const infomundiIcons = document.getElementsByClassName('infomundi-icon');

  if (newTheme === 'dark') {
    // Update all logos
    for (let logo of infomundiLogos) {
      logo.src = '/static/img/logos/logo-wide-dark-resized.webp';
    }
    // Update all icons
    for (let icon of infomundiIcons) {
      icon.src = '/static/img/logos/logo-icon-dark.webp';
    }
  } else {
    // Update all logos
    for (let logo of infomundiLogos) {
      logo.src = '/static/img/logos/logo-wide-light-resized.webp';
    }
    // Update all icons
    for (let icon of infomundiIcons) {
      icon.src = '/static/img/logos/logo-icon-light.webp';
    }
  }

  // Set a cookie indicating the current theme
  setCookie('theme', newTheme, 14);

  // Update button classes
  updateButtonClasses(newTheme);

  // Update Cloudflare Turnstile theme
  updateTurnstileTheme(newTheme);
};

const updateButtonClasses = (theme) => {
  const lightButtons = document.querySelectorAll('.btn-outline-light');
  const darkButtons = document.querySelectorAll('.btn-outline-dark');

  if (theme === 'dark') {
    lightButtons.forEach(button => {
      button.classList.remove('btn-outline-light');
      button.classList.add('btn-outline-dark');
    });
    darkButtons.forEach(button => {
      button.classList.remove('btn-outline-dark');
      button.classList.add('btn-outline-light');
    });
  } else {
    lightButtons.forEach(button => {
      button.classList.remove('btn-outline-light');
      button.classList.add('btn-outline-dark');
    });
    darkButtons.forEach(button => {
      button.classList.remove('btn-outline-dark');
      button.classList.add('btn-outline-light');
    });
  }
};

const updateTurnstileTheme = (theme) => {
  const turnstileElements = document.querySelectorAll('.cf-turnstile');
  turnstileElements.forEach(element => {
    element.setAttribute('data-theme', theme);
  });
};
