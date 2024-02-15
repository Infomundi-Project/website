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

            // Username special character validation allowing specific characters
            const username = document.getElementById('floatingUsername');
            const validateUsername = () => {
                // Regular expression to match any character that is not alphanumeric or the allowed special characters
                const specialCharRegex = /[^A-Za-z0-9!@#$%¨&*()_\-]/;
                if (specialCharRegex.test(username.value)) {
                    username.setCustomValidity('Username contains invalid characters');
                } else {
                    username.setCustomValidity('');
                }
            };
            username.addEventListener('input', validateUsername);
        })();