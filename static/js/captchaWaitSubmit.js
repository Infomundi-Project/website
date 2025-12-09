document.addEventListener("DOMContentLoaded", function() {
  const submitButton = document.getElementById("captchaSubmitButton");
  const captchaMessage = document.getElementById("captchaMessage");
  const captchaForm = document.getElementById("captcha-wait-form");

  // Check if we're in a local development environment
  function isLocalEnvironment() {
    const hostname = window.location.hostname;
    return (
      hostname === 'localhost' ||
      hostname === '127.0.0.1' ||
      hostname === '[::1]' ||
      hostname.endsWith('.local') ||
      hostname.startsWith('192.168.') ||
      hostname.startsWith('10.') ||
      /^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(hostname) // 172.16-31.x.x
    );
  }

  // If local development, bypass captcha entirely
  if (isLocalEnvironment()) {
    console.log('Captcha disabled: local development environment detected');
    
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.classList.remove("btn-secondary");
      submitButton.classList.add("btn-primary");
    }
    if (captchaMessage) {
      captchaMessage.hidden = true;
    }
    
    // No need to set up captcha handlers in local dev
    return;
  }

  // Production captcha handling
  window.onCaptchaSuccess = function(token) {
    // Check if submitButton and captchaMessage exist before modifying
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.classList.remove("btn-secondary");
      submitButton.classList.add("btn-primary");
    }
    if (captchaMessage) {
      captchaMessage.hidden = true;
    }
  };

  if (captchaForm) {
    captchaForm.addEventListener("reset", function() {
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.classList.remove("btn-primary");
        submitButton.classList.add("btn-secondary");
      }
      if (captchaMessage) {
        captchaMessage.hidden = false;
      }
    });
  }
});