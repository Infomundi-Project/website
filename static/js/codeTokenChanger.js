    document.addEventListener('DOMContentLoaded', function () {
        const toggleDeviceLink = document.getElementById('toggle-device-link');
        const totpInputGroup = document.getElementById('totp-input-group');
        const recoveryTokenInputGroup = document.getElementById('recovery-token-input-group');

        toggleDeviceLink.addEventListener('click', function (event) {
		    event.preventDefault(); // Prevent default link behavior

		    if (totpInputGroup.style.display === 'none') {
		        // Show TOTP input group, hide Recovery Token input group
		        totpInputGroup.style.display = 'block';
		        recoveryTokenInputGroup.style.display = 'none';
		        
		        // Add 'required' to TOTP input and remove from recovery token
		        document.getElementById('floatingInputCurrentTOTP').setAttribute('required', true);
		        document.getElementById('floatingInputRecoveryToken').removeAttribute('required');
		        
		        toggleDeviceLink.textContent = "I don't have access to my two factor device";
		    } else {
		        // Hide TOTP input group, show Recovery Token input group
		        totpInputGroup.style.display = 'none';
		        recoveryTokenInputGroup.style.display = 'block';
		        
		        // Add 'required' to recovery token and remove from TOTP input
		        document.getElementById('floatingInputRecoveryToken').setAttribute('required', true);
		        document.getElementById('floatingInputCurrentTOTP').removeAttribute('required');
		        
		        toggleDeviceLink.textContent = "Nevermind, I have access to my two factor device";
		    }
		});
    });