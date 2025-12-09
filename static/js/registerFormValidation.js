(() => {
  'use strict'

  // Password strength check function
  const isStrongPassword = (password) => {
    const strongPasswordPattern = /^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>]).{8,50}$/;
    return strongPasswordPattern.test(password);
  };

  // Username validation function
  const isValidUsername = (username) => {
    const usernamePattern = /^[a-zA-Z0-9_-]{3,25}$/;
    return usernamePattern.test(username);
  };

  // Function to handle validation feedback
  const handleValidation = (field, isValid, message) => {
    if (isValid) {
      field.setCustomValidity('');
      field.classList.remove('is-invalid');
      field.classList.add('is-valid');
    } else {
      field.setCustomValidity(message);
      field.classList.remove('is-valid');
      field.classList.add('is-invalid');
    }
  };

  // Fetch the form and input fields
  const form = document.querySelector('.needs-validation');
  const passwordField = form.querySelector('#floatingPassword');
  const confirmPasswordField = form.querySelector('#floatingConfirmPassword');
  const usernameField = form.querySelector('#floatingUsername');
  
  // Password field input event
  passwordField.addEventListener('input', () => {
    const isValid = isStrongPassword(passwordField.value);
    handleValidation(passwordField, isValid, 'Password must be 8-50 characters long, contain at least one uppercase letter, one lowercase letter, one number, and one special character.');
  });

  // Confirm password field input event
  confirmPasswordField.addEventListener('input', () => {
    const isValid = passwordField.value === confirmPasswordField.value;
    handleValidation(confirmPasswordField, isValid, 'Passwords must match.');
  });

  // Username field input event
  usernameField.addEventListener('input', () => {
    const isValid = isValidUsername(usernameField.value);
    handleValidation(usernameField, isValid, 'Username must be 3-25 characters long and contain only alphanumeric characters, underscores, or hyphens.');
  });

  // Form submit event to prevent submission if invalid
  form.addEventListener('submit', (event) => {
    if (!form.checkValidity()) {
      event.preventDefault();
      event.stopPropagation();
    }
    form.classList.add('was-validated');
  }, false);

})();
