function start_countdown(buttonId, cooldownTime) {
    const cooldownButton = document.getElementById(buttonId);

    // Check if the button element exists
    if (!cooldownButton) {
        return;
    }

    let timeLeft = cooldownTime;
    function updateCountdown() {
        if (timeLeft > 0) {
            cooldownButton.innerHTML = `Cooldown: <span id="timer-${buttonId}">${timeLeft}</span> seconds`;
            cooldownButton.setAttribute("disabled", "true");
            cooldownButton.classList.add("btn-secondary");
            cooldownButton.classList.remove("btn-primary");
            timeLeft--;
            setTimeout(updateCountdown, 1000);
        } else {
            cooldownButton.innerHTML = 'Comment';
            cooldownButton.removeAttribute("disabled");
            cooldownButton.classList.remove("btn-secondary");
            cooldownButton.classList.add("btn-primary");
        }
    }
    updateCountdown();
}

// Call the start_countdown function with the cooldown-button by default
start_countdown('cooldown-button', 7);