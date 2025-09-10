document.addEventListener("DOMContentLoaded", function () {
  let lastScrollTop = 0;
  const navbar = document.getElementById(
  'mainNavbar'); // Select the navbar by ID
  var commentsReturnButton = document.getElementById(
  'commentsReturnButton');
  var commentsReturnButtonMobile = document.getElementById(
    'commentsReturnButtonMobile');

  window.addEventListener('scroll', function () {
    let currentScroll = window.pageYOffset || document.documentElement
      .scrollTop;

    if (currentScroll > lastScrollTop) {
      // Scrolling down
      navbar.classList.add('navbar-hidden');
      navbar.classList.remove('navbar-visible');
      if (commentsReturnButton) {
        commentsReturnButton.style.top = '2vh';
      }

      if (commentsReturnButtonMobile) {
        commentsReturnButtonMobile.classList.add('invisible');
      }
    } else {
      // Scrolling up
      navbar.classList.remove('navbar-hidden');
      navbar.classList.add('navbar-visible');
      if (commentsReturnButton) {
        commentsReturnButton.style.top = '12vh';
      }

      if (commentsReturnButtonMobile) {
        commentsReturnButtonMobile.classList.remove('invisible');
      }
    }
    lastScrollTop = currentScroll <= 0 ? 0 : currentScroll;
  }, false);
});