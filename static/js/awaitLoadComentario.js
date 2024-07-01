function loadScript(src, callback) {
    const script = document.createElement('script');
    script.src = src;
    script.defer = true;
    script.onload = callback;
    document.body.appendChild(script);
}

document.addEventListener('DOMContentLoaded', function () {
    setTimeout(() => {
        loadScript('https://commento.infomundi.net/comentario.js', () => {
            const cc = document.getElementsByTagName('comentario-comments').item(0);
            if (cc) {
                if (window.userAuthenticated) {
                    cc.main().then(() => cc.nonInteractiveSsoLogin()); // Activates the non interactive SSO
                } else {
                    cc.main();
                }
            }
        });
    }, 3000);
});
