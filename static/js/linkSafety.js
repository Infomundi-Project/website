function linkSafety() {
    var trustedDomain = "infomundi.net";
    var externalLinkModal = new bootstrap.Modal(document.getElementById('externalLinkModal'));
    var proceedLink = document.getElementById('proceedLink');

    // Use event delegation instead of adding multiple event listeners
    document.body.addEventListener('click', function(event) {
        var link = event.target.closest('a');
        if (!link) return; // Ignore clicks that are not on links

        var href = link.href;
        var url = new URL(href);

        if (url.hostname !== trustedDomain) {
            event.preventDefault();
            proceedLink.href = href;

            // Hide any currently open modals
            var openModal = document.querySelector('.modal.show');
            if (openModal) {
                var openModalInstance = bootstrap.Modal.getInstance(openModal);
                openModalInstance.hide();
            }

            // Show external link modal
            externalLinkModal.show();
        }
    });

    // Ensure the proceed button only has one event listener
    proceedLink.addEventListener('click', function() {
        window.location.href = this.href;
    });
}

// Run linkSafety once on DOMContentLoaded
document.addEventListener("DOMContentLoaded", linkSafety);
