function googleTranslateElementInit() {
  var pageLanguage = document.documentElement.lang || 'en'; // Default to English if not specified
  new google.translate.TranslateElement({
    pageLanguage: pageLanguage
  },
  'google_translate_element'
  );
}
