document.addEventListener("DOMContentLoaded", function() {
  const submitButton = document.getElementById("captchaSubmitButton");
  const captchaMessage = document.getElementById("captchaMessage");
  const captchaForm = document.getElementById("captcha-wait-form");

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
