/**
 * WiFi Credential Grabber - Background Service Worker
 * 
 * Este script roda em background e coordena a busca automática
 * de credenciais em páginas de roteadores.
 */

console.log('[WiFi Grabber BG] Service Worker iniciado');

// ============================================
// LISTENERS
// ============================================

/**
 * Listener para mensagens do content script
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('[WiFi Grabber BG] Mensagem recebida:', message);

    if (message.type === 'CREDENTIALS_FOUND') {
        // Salvar credenciais encontradas automaticamente
        saveCredentials(message.data, sender.tab?.url);

        // Notificar o popup se estiver aberto
        chrome.runtime.sendMessage({
            type: 'CREDENTIALS_UPDATE',
            data: message.data
        }).catch(() => {
            // Popup não está aberto, ignorar
        });

        sendResponse({ success: true });
    }

    if (message.type === 'GET_AUTO_CREDENTIALS') {
        // Popup está pedindo as credenciais encontradas automaticamente
        getLastCredentials().then(credentials => {
            sendResponse({ credentials });
        });
        return true; // Indica resposta assíncrona
    }

    if (message.type === 'PAGE_LOADED') {
        // Uma página de roteador foi carregada
        console.log('[WiFi Grabber BG] Página de roteador detectada:', sender.tab?.url);
    }

    return true;
});

/**
 * Listener para quando uma aba é atualizada
 */
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url) {
        // Verificar se é uma página de roteador
        if (isRouterPage(tab.url)) {
            console.log('[WiFi Grabber BG] Aba de roteador atualizada:', tab.url);

            // Marcar badge para indicar que está monitorando
            chrome.action.setBadgeText({ tabId, text: '👁️' });
            chrome.action.setBadgeBackgroundColor({ tabId, color: '#4f46e5' });
        }
    }
});

// ============================================
// FUNÇÕES AUXILIARES
// ============================================

/**
 * Verifica se a URL é de um roteador
 */
function isRouterPage(url) {
    if (!url) return false;

    try {
        const urlObj = new URL(url);
        const hostname = urlObj.hostname;

        const patterns = [
            /^192\.168\.\d{1,3}\.\d{1,3}$/,
            /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
            /^172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}$/
        ];

        return patterns.some(p => p.test(hostname));
    } catch {
        return false;
    }
}

/**
 * Salva as credenciais no storage
 */
async function saveCredentials(credentials, sourceUrl) {
    try {
        const { history = [] } = await chrome.storage.local.get('history');

        // Verificar se já existe essa credencial recentemente (evitar duplicatas)
        const isDuplicate = history.some(item =>
            item.ssid === credentials.ssid &&
            item.password === credentials.password &&
            item.pppoeUser === credentials.pppoeUser &&
            (Date.now() - item.timestamp) < 60000 // Menos de 1 minuto
        );

        if (isDuplicate) {
            console.log('[WiFi Grabber BG] Credencial duplicada, ignorando');
            return;
        }

        // Adicionar nova credencial
        history.unshift({
            ssid: credentials.ssid,
            password: credentials.password,
            pppoeUser: credentials.pppoeUser,
            pppoePassword: credentials.pppoePassword,
            source: sourceUrl,
            timestamp: Date.now(),
            auto: true // Indica que foi capturada automaticamente
        });

        // Limitar histórico
        if (history.length > 50) {
            history.pop();
        }

        await chrome.storage.local.set({ history });

        // Salvar também como "última credencial" para acesso rápido
        await chrome.storage.local.set({
            lastCredential: {
                ...credentials,
                timestamp: Date.now()
            }
        });

        const label = credentials.ssid || credentials.pppoeUser || 'Credenciais';
        console.log('[WiFi Grabber BG] Credenciais salvas:', label);

        // Atualizar badge para indicar sucesso
        chrome.action.setBadgeText({ text: '✓' });
        chrome.action.setBadgeBackgroundColor({ color: '#22c55e' });

    } catch (error) {
        console.error('[WiFi Grabber BG] Erro ao salvar:', error);
    }
}

/**
 * Obtém as últimas credenciais encontradas
 */
async function getLastCredentials() {
    try {
        const { lastCredential } = await chrome.storage.local.get('lastCredential');
        return lastCredential || null;
    } catch {
        return null;
    }
}
