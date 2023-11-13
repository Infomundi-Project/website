$(function() {
    $(".autocomplete").autocomplete({
        source: function(request, response) {
            $.ajax({
                url: "/autocomplete",
                method: "GET",
                dataType: "json",
                data: {
                    query: request.term,
                },
                success: function(data) {
                    response(data);
                },
                error: function(err) {
                    console.error("Error fetching autocomplete suggestions:", err);
                },
            });
        },
        minLength: 2
    });
});