$(window).scroll(function() {
    if ($(this).scrollTop() > 500) {
        $('#scrollTopBtn').fadeIn();
    } else {
        $('#scrollTopBtn').fadeOut();
    }
});

// Scroll to the top of the document when the user clicks the button
$('#scrollTopBtn').click(function() {
    $('html, body').animate({ scrollTop: 0 });
    return false;
});