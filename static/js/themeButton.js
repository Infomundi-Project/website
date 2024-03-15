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
  const currentTheme = htmlElement.getAttribute('data-bs-theme');

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

  const hyvorTalk = document.querySelector('hyvor-talk-comments')

  if (hyvorTalk){ 
    hyvorTalk.setAttribute('colors', newTheme);
  }

  // Set a cookie indicating the current theme
  setCookie('theme', newTheme, 14);
};
