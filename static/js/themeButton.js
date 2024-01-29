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

  // Change infomundi logo and icon
  const infomundiLogo = document.getElementById('infomundiLogo');
  const infomundiIcon = document.getElementById('infomundiIcon');

  if (newTheme === 'dark') {
    if (infomundiLogo) {
      infomundiLogo.src = '/static/img/logos/logo-wide-dark-resized.webp';
    }
    if (infomundiIcon) {
      infomundiIcon.src = '/static/img/logos/logo-icon-dark.webp';
    }
  } else {
    if (infomundiLogo) {
      infomundiLogo.src = '/static/img/logos/logo-wide-light-resized.webp';
    }
    if (infomundiIcon) {
      infomundiIcon.src = '/static/img/logos/logo-icon-light.webp';
    }
  }

  // Set a cookie indicating the current theme
  setCookie('theme', newTheme, 14);
};


const checkbox = document.getElementById("theme-checkbox");
checkbox.addEventListener('click', toggleTheme);