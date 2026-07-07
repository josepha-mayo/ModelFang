document.getElementById('syncBtn').addEventListener('click', async () => {
    const statusDiv = document.getElementById('status');
    statusDiv.textContent = 'Syncing...';
    statusDiv.className = 'status';
  
    try {
      // Send message to background script to start extraction
      const response = await chrome.runtime.sendMessage({ action: 'syncSessions' });
      
      if (response && response.success) {
        statusDiv.textContent = `Synced: ${response.services.join(', ')}`;
        statusDiv.className = 'status success';
      } else {
        throw new Error(response?.error || 'Unknown error');
      }
    } catch (err) {
      statusDiv.textContent = 'Error: ' + err.message;
      statusDiv.className = 'status error';
    }
  });
