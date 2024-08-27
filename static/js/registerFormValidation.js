(() => {
    'use strict';

    const forms = document.querySelectorAll('.needs-validation');

    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            let isValid = true;

            const emailField = form.querySelector('input[name="email"]');
            const usernameField = form.querySelector('input[name="username"]');
            const emailPattern = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
            const usernamePattern = /^[\-a-zA-Z0-9_]{3,25}$/;

            if (!emailPattern.test(emailField.value)) {
                emailField.setCustomValidity('Invalid email address.');
                isValid = false;
            } else {
                emailField.setCustomValidity('');
            }

            if (!usernamePattern.test(usernameField.value)) {
                usernameField.setCustomValidity('Invalid username.');
                isValid = false;
            } else {
                usernameField.setCustomValidity('');
            }

            if (!form.checkValidity() || !isValid) {
                event.preventDefault();
                event.stopPropagation();
            } else {
                const signUpButton = document.getElementById('signUpButton');
                signUpButton.textContent = 'Loading...';
                signUpButton.disabled = true;

                setTimeout(() => {
                    signUpButton.textContent = 'Sign up';
                    signUpButton.disabled = false;
                }, 5000);
            }

            form.classList.add('was-validated');
        }, false);
    });

    const password = document.getElementById('floatingPassword');
    const confirmPassword = document.getElementById('floatingConfirmPassword');
    const validatePasswords = () => {
        if (password.value !== confirmPassword.value) {
            confirmPassword.setCustomValidity('Passwords do not match');
        } else {
            confirmPassword.setCustomValidity('');
        }
    };
    password.addEventListener('input', validatePasswords);
    confirmPassword.addEventListener('input', validatePasswords);
})();
