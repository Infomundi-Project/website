(() => {
    'use strict';

    // Fetch all the forms we want to apply custom Bootstrap validation styles to
    const forms = document.querySelectorAll('.needs-validation');

    // Loop over them and prevent submission
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            } else {
                // If the form is valid, change the button text and disable it
                const signUpButton = document.getElementById('signUpButton');
                signUpButton.textContent = 'Loading...'; // Change button text
                signUpButton.disabled = true; // Disable the button

                // Set a timeout to re-enable the button after 5 seconds
                setTimeout(() => {
                    signUpButton.textContent = 'Sign up'; // Revert button text to original
                    signUpButton.disabled = false; // Re-enable the button
                }, 5000); // 5000 milliseconds = 5 seconds
            }

            form.classList.add('was-validated');
        }, false);
    });

    // Real-time password match validation
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
