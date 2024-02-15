function googleTranslateElementInit() {
        new google.translate.TranslateElement({
          pageLanguage: '{{ country_code }}'
        },
        'google_translate_element'
        );
      }