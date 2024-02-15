function submitSearch() {
    const queryValue = document.getElementById("query").value;

    const languageButton = document.getElementById("infLanguageMenu");
    const languageValue = languageButton.textContent.trim().toLowerCase();

    const currentUrl = new URL(window.location.href);
    const searchParams = new URLSearchParams(currentUrl.search);

    searchParams.set("query", queryValue);

    if (!languageValue.includes('language')) {
      searchParams.set("translation", languageValue);
    }

    currentUrl.search = searchParams.toString();
    window.location.href = currentUrl.toString();
  }