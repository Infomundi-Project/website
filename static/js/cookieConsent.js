// Enable dark mode
document.documentElement.classList.add('cc--darkmode');

CookieConsent.run({
  guiOptions: {
    consentModal: {
      layout: "box",
      position: "bottom left",
      equalWeightButtons: true,
      flipButtons: false
    },
    preferencesModal: {
      layout: "box",
      position: "right",
      equalWeightButtons: true,
      flipButtons: false
    }
  },
  categories: {
    necessary: {
      readOnly: true
    }
  },
  language: {
    default: "en",
    autoDetect: "browser",
    translations: {
      en: {
        consentModal: {
          title: "About cookies",
          description: "When you visit our website (https://infomundi.net/), and use our services, you trust us with your personal information.",
          closeIconLabel: "",
          acceptAllBtn: "Accept",
          acceptNecessaryBtn: "",
          showPreferencesBtn: "Manage preferences",
          footer: "<a href=\"https://infomundi.net/policies#privacy-policy\">Privacy Policy</a>"
        },
        preferencesModal: {
          title: "Consent Preferences Center",
          closeIconLabel: "Close modal",
          acceptAllBtn: "Accept all",
          acceptNecessaryBtn: "",
          savePreferencesBtn: "Save preferences",
          serviceCounterLabel: "",
          sections: [{
              title: "Strictly Necessary Cookies <span class=\"pm__badge\">Always Enabled</span>",
              description: "We only use necessary cookies that are crucial for the proper operation of the website. These are:<br>theme - (expires in 7 days): is only created if you change the website theme;<br>remember_token - (expires in 15 days or when user logs out): is created when you choose to remember your session when you sign in.<br>infomundi-session (expires 15 days after user login or upon browser closure if the user prefer to stay logged out): is created/updated when you view almost every page of this website. Holds information regarding the last country you visited in our website, the last story you clicked, and a lot more. This cookie is essential for the website to work properly.",
              linkedCategory: "necessary"
            },
            {
              title: "More information",
              description: "For any query in relation to our <a class=\"cc__link\" href=\"https://infomundi.net/policies#privacy-policy\">privacy policy</a> and your choices, please <a class=\"cc__link\" href=\"https://infomundi.net/contact\">contact us</a>. "
            }
          ]
        }
      }
    }
  }
});