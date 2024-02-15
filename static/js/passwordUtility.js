function togglePasswordVisibility(inputId) {
        const input = document.getElementById(inputId);
        const icon = document.getElementById(inputId + 'Icon');
        if (input.type === "password") {
            input.type = "text";
            icon.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
        } else {
            input.type = "password";
            icon.innerHTML = '<i class="fa-solid fa-eye"></i>';
        }
    }

document.addEventListener('DOMContentLoaded', (event) => {
    const passwordInput = document.getElementById('floatingPassword');
    const strengthDisplay = document.getElementById('passwordStrengthDisplay');

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

    function checkPasswordStrength(password) {
        let score = 0;
        if (password.length >= 8) score++;
        if (password.length >= 12) score++;
        if (/\d/.test(password)) score++;
        if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
        if (/[^A-Za-z0-9]/.test(password)) score++;
        return Math.min(score, 5);
    }

    function getStrengthColor(score) {
        switch (score) {
            case 1: return '#ff3e36'; // red
            case 2: return '#ff691f'; // orange
            case 3: return '#ffda36'; // yellow
            case 4: return '#0be881'; // light green
            case 5: return '#05c46b'; // green
            default: return 'transparent';
        }
    }
});