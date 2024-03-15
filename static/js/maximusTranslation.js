document.addEventListener("DOMContentLoaded", function() {
  var maximusTranslationSwitch = document.getElementById('maximusTranslationSwitch');

  if (!maximusTranslationSwitch) {
    return; // Exit the function early
  }

  // Function to get a cookie value
  function getCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for(var i=0;i < ca.length;i++) {
      var c = ca[i];
      while (c.charAt(0) == ' ') c = c.substring(1,c.length);
      if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
    }
    return null;
  }

  // Check the cookie at load and set the switch state
  var maximusTranslation = getCookie('maximusTranslation');
  if (maximusTranslation === 'disabled') {
    maximusTranslationSwitch.checked = false;
  }

  if (maximusTranslation === 'enabled') {
    maximusTranslationSwitch.checked = true;
  }

  // Listen for the switch change event
  maximusTranslationSwitch.addEventListener('change', function() {
    if (this.checked) {
      setCookie('maximusTranslation', 'enabled', 24); // Enable toast and set cookie
      location.reload();
    } else {
      setCookie('maximusTranslation', 'disabled', 24); // Disable toast and set cookie
      location.reload();
    }
  });
});