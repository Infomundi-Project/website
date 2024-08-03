function linkSafety() {
    var trustedDomain = "infomundi.net";
    var externalLinkModal = new bootstrap.Modal(document.getElementById('externalLinkModal'));
    var proceedLink = document.getElementById('proceedLink');

    document.querySelectorAll('a').forEach(function(link) {
        link.addEventListener('click', function(event) {
            var href = this.href;
            var url = new URL(href);
            if (url.hostname !== trustedDomain) {
                event.preventDefault();
                proceedLink.href = href;
                externalLinkModal.show();

                // Check and hide any active modals
                var openModal = document.querySelector('.modal.show');
                if (openModal) {
                    var openModalInstance = bootstrap.Modal.getInstance(openModal);
                    openModalInstance.hide();
                }

                // Adding event listener to proceed button to navigate to the external link
                proceedLink.addEventListener('click', function() {
                    window.location.href = href;
                }, { once: true });
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", linkSafety);
