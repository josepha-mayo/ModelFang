const PROXY_URL = 'http://localhost:8080/unfetter/session';

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'syncSessions') {
    syncSessions().then(sendResponse);
    return true; // Keep message channel open for async response
  }
});

async function syncSessions() {
  const sessions = {};
  const services = [];

  try {
    // 1. ChatGPT
    const chatgpt = await chrome.cookies.get({ url: 'https://chatgpt.com', name: '__Secure-next-auth.session-token' });
    if (chatgpt) {
      sessions.openai = chatgpt.value;
      services.push('ChatGPT');
    }

    // 2. Claude
    const claude = await chrome.cookies.get({ url: 'https://claude.ai', name: 'sessionKey' });
    if (claude) {
      sessions.anthropic = claude.value;
      services.push('Claude');
    }

    // 3. Gemini (Google)
    // Google uses multiple cookies, __Secure-1PSID is often the key for auth, but we might need more.
    // We'll grab the main one for now.
    const gemini = await chrome.cookies.get({ url: 'https://gemini.google.com', name: '__Secure-1PSID' });
    if (gemini) {
      sessions.gemini = gemini.value;
      services.push('Gemini');
    }

    // 4. Groq
    // Groq uses supabase.auth.token - commonly stored in LocalStorage, but sometimes cookie.
    // We'll try to find a cookie starting with 'sb-' or just grab all from groq.com for analysis
    const groqCookies = await chrome.cookies.getAll({ domain: 'groq.com' });
    // Look for supabase token pattern or known auth cookie
    const groqAuth = groqCookies.find(c => c.name.startsWith('sb-') && c.name.includes('auth-token'));
    if (groqAuth) {
        sessions.groq = groqAuth.value;
        services.push('Groq');
    }


    if (services.length === 0) {
      return { success: false, error: 'No active sessions found. Please log in to ChatGPT, Claude, etc.' };
    }

    // Send to Proxy
    await fetch(PROXY_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sessions)
    });

    return { success: true, services };

  } catch (err) {
    return { success: false, error: err.message };
  }
}
