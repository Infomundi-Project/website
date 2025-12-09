function linkSafety() {
  const trustedDomain = "infomundi.net";
  const externalLinkModal = new bootstrap.Modal(
    document.getElementById('externalLinkModal')
  );
  const proceedLink = document.getElementById('proceedLink');

  // Check if we're in a local development environment
  function isLocalEnvironment() {
    const hostname = window.location.hostname;
    return (
      hostname === 'localhost' ||
      hostname === '127.0.0.1' ||
      hostname === '[::1]' ||
      hostname.endsWith('.local') ||
      hostname.startsWith('192.168.') ||
      hostname.startsWith('10.') ||
      /^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(hostname) // 172.16-31.x.x
    );
  }

  // Check if a URL is a local/development URL
  function isLocalUrl(url) {
    const hostname = url.hostname;
    return (
      hostname === 'localhost' ||
      hostname === '127.0.0.1' ||
      hostname === '[::1]' ||
      hostname.endsWith('.local') ||
      hostname.startsWith('192.168.') ||
      hostname.startsWith('10.') ||
      /^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(hostname)
    );
  }

  // Skip the link safety check entirely if we're in local dev
  if (isLocalEnvironment()) {
    console.log('Link safety disabled: local development environment detected');
    return;
  }

  document.body.addEventListener('click', function (event) {
    const link = event.target.closest('a');
    if (!link) return;

    const url = new URL(link.href);
    
    // Check if it's a trusted domain
    const isTrusted =
      url.hostname === trustedDomain ||
      url.hostname.endsWith(`.${trustedDomain}`);

    // Also skip modal for local URLs (in case you're linking to localhost from prod)
    const isLocal = isLocalUrl(url);

    if (!isTrusted && !isLocal) {
      event.preventDefault();
      proceedLink.href = link.href;

      // Hide any open modal
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