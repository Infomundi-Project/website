$(document).ready(function() {
    // Function to get a cookie
    function getCookie(name) {
      var nameEQ = name + "=";
      var ca = document.cookie.split(';');
      for (var i = 0; i < ca.length; i++) {
        var c = ca[i];
        while (c.charAt(0) == ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
      }
      return null;
    }

    // Check if the cookieConsent cookie is set, if not, show the modal
    if (!getCookie('cookieConsent')) {
      $('#cookieConsentModal').modal('show');
    }

    // Set the cookieConsent cookie to 'true' when the 'I Agree' button is clicked
    $('#acceptCookieConsent').click(function() {
      setCookie('cookieConsent', 'true', 30); // Set the cookie to expire in 30 days
      $('#cookieConsentModal').modal('hide');
    });
  });