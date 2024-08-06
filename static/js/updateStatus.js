async function updateUserStatus() {
    await fetch(`https://infomundi.net/api/user/status/update`, {
        method: 'GET',
    });
}

function startPolling() {
    updateUserStatus();
    
    setInterval(async () => {
        await updateUserStatus();
    }, 50000);  // Poll every 50 seconds
}

startPolling();