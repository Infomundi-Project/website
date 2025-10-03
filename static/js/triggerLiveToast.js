const toastLiveExample = document.getElementById('liveToast');

// Check if the element exists
if (toastLiveExample) {
    const toastBootstrap = bootstrap.Toast.getOrCreateInstance(toastLiveExample);
    toastBootstrap.show();
}