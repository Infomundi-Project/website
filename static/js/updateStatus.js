async function updateUserStatus() {
    await fetch(`/api/user/status/update`, {
        method: 'GET',
    });
}

function startPolling() {
    updateUserStatus();
    
    setInterval(async () => {
        await updateUserStatus();
    }, 60000);  // Poll every 60 seconds
}

startPolling();