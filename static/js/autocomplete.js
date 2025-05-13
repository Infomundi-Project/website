$(function () {
  $(".autocomplete").autocomplete({
    source: function (request, response) {
      $.ajax({
        url: "/api/autocomplete",
        method: "GET",
        dataType: "json",
        data: {
          query: request.term,
        },
        success: function (data) {
          response(data);
        },
        error: function (err) {
          console.error(
            "Error fetching autocomplete suggestions:", err);
        },
      });
    },
    minLength: 2,
    select: function (event, ui) {
      var selectedCountry = ui.item.value;

      // Make an AJAX request to get the country code
      $.ajax({
        url: "/api/get_country_code",
        method: "GET",
        data: {
          country: selectedCountry,
        },
        dataType: "json",
        success: function (data) {
          // Redirect to the news page with the retrieved country code
          var countryCode = data.countryCode;
          window.location.href =
            "/news?country=" +
            encodeURIComponent(countryCode);
        },
        error: function (err) {
          console.error("Error fetching country code:", err);
        },
      });
    }
  });
});