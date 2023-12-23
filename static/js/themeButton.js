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
  
  // Set a cookie indicating the current theme
  setCookie('theme', newTheme, 7);
};


const checkbox = document.getElementById("theme-checkbox");
checkbox.addEventListener('click', toggleTheme);

document.getElementById('themeToggleBtn').addEventListener('click', toggleTheme);