function linkSafety() {
  const trustedDomain = "infomundi.net";
  const externalLinkModal = new bootstrap.Modal(
    document.getElementById('externalLinkModal')
  );
  const proceedLink = document.getElementById('proceedLink');

  document.body.addEventListener('click', function (event) {
    const link = event.target.closest('a');
    if (!link) return;

    const url = new URL(link.href);
    // is it exactly the master, or *any* subdomain?
    const isTrusted =
      url.hostname === trustedDomain ||
      url.hostname.endsWith(`.${trustedDomain}`);

    if (!isTrusted) {
      event.preventDefault();
      proceedLink.href = link.href;

      // hide any open modal
      const openModal = document.querySelector('.modal.show');
      if (openModal) {
        bootstrap.Modal.getInstance(openModal).hide();
      }

      externalLinkModal.show();
    }
  });

  proceedLink.addEventListener('click', function () {
    window.location.href = this.href;
  });
}

document.addEventListener("DOMContentLoaded", linkSafety);
