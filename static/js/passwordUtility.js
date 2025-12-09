// Function to toggle password visibility
function togglePassword(event) {
  const passwordInputId = event.target.getAttribute('data-toggle');
  const passwordInput = document.getElementById(passwordInputId);
  const toggleIcon = event.target;

  if (passwordInput) {
    if (passwordInput.type === 'password') {
      passwordInput.type = 'text';
      toggleIcon.classList.remove('fa-eye');
      toggleIcon.classList.add('fa-eye-slash');
    } else {
      passwordInput.type = 'password';
      toggleIcon.classList.remove('fa-eye-slash');
      toggleIcon.classList.add('fa-eye');
    }
  }
}

// Function to initialize password toggle functionality
function initializePasswordToggle() {
  const toggleIcons = document.querySelectorAll('.password-toggle i');
  if (toggleIcons.length > 0) {
    toggleIcons.forEach(icon => {
      icon.addEventListener('click', togglePassword);
    });
  }
}

// Function to check password strength
function checkPasswordStrength(password) {
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/\d/.test(password)) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  return Math.min(score, 5);
}

// Function to get strength color
function getStrengthColor(score) {
  switch (score) {
  case 1:
    return '#ff3e36'; // red
  case 2:
    return '#ff691f'; // orange
  case 3:
    return '#ffda36'; // yellow
  case 4:
    return '#0be881'; // light green
  case 5:
    return '#05c46b'; // green
  default:
    return 'transparent';
  }
}

// Function to initialize password strength checker
function initializePasswordStrengthChecker() {
  const passwordInput = document.getElementById('floatingPassword');
  const strengthDisplay = document.getElementById('passwordStrengthDisplay');

  if (passwordInput && strengthDisplay) {
    passwordInput.addEventListener('input', () => {
      const strengths = {
        1: 'Very Weak',
        2: 'Weak',
        3: 'Medium',
        4: 'Strong',
        5: 'Very Strong'
      };
      let strengthScore = checkPasswordStrength(passwordInput.value);
      strengthDisplay.textContent = strengths[strengthScore];
      // Update the display color based on the strength
      strengthDisplay.style.color = getStrengthColor(strengthScore);
    });
  }
}

// Initialize all functionalities on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function () {
  initializePasswordToggle();
  initializePasswordStrengthChecker();
});