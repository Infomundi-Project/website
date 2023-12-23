document.addEventListener("DOMContentLoaded", function () {
  const cooldownButton = document.getElementById("cooldown-button");
  let cooldownTime = 7;

  function countdown() {
    if (cooldownTime > 0) {
      cooldownButton.innerHTML = `Cooldown: <span id="timer">${cooldownTime}</span> seconds`;
      cooldownButton.setAttribute("disabled", "true");
      cooldownTime--;
      setTimeout(countdown, 1000);
    } else {
      cooldownButton.innerHTML = 'Comment';
      cooldownButton.removeAttribute("disabled");
      cooldownButton.classList.remove("btn-outline-secondary");
      cooldownButton.classList.add("btn-outline-primary");
    }
  }

  countdown();
});