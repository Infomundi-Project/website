document.querySelectorAll('.inf-language-menu a').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      var dropdownButton = document.getElementById('infLanguageMenu');
      dropdownButton.textContent = e.target.textContent;
    });
  });