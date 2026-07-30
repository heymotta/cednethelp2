/**
 * CedNet Help - Popup Script v2.1
 * Login Automático e Bloco de Notas
 */

// Elementos do DOM
let errorContainer, pageStatus;
let autoLoginBtn, loginStatus, loginResult;
let deviceTypeSelect;

// Credenciais organizadas por modelo de roteador
const CREDENTIALS_BY_TYPE = {
    zte: [
        { user: 'cednet', pass: 'GCrouter@734' },
        { user: 'multipro', pass: 'multipro' },
        { user: 'user', pass: 'user' },
    ],
    datacom: [
        { user: 'user', pass: 'user' },
        { user: 'cednet', pass: 'GCrouter@734' },
    ],
    tplink: [
        { user: 'admin', pass: 'admin' },
        { user: 'admin', pass: 'cednetrouter' },
        { user: 'admin', pass: 'GCrouter@734' },
    ],
    radio: [
        { user: 'admin', pass: '%W2sajuB' },
        { user: 'admin', pass: 'dITcd34A9' },
        { user: 'admin', pass: 'DitCD34a9' },
        { user: 'admin', pass: '%Ph8rehu' },
        { user: 'admin', pass: 'Fcd24cli' },
        { user: 'admin', pass: '%Ph8rehuGC' },
        { user: 'ubnt', pass: 'ubnt' },
        { user: 'admin', pass: '0D03BD7' },
        { user: 'admin', pass: '5SNRAv06' },
        { user: 'admin', pass: 'Xbd74BN2' },
        { user: 'admin', pass: 'Erebro2h' },
    ],
};

// Função para obter credenciais baseado no tipo selecionado
function getCredentials(deviceType) {
    return CREDENTIALS_BY_TYPE[deviceType] || CREDENTIALS_BY_TYPE.zte;
}

/**
 * Inicialização
 */
document.addEventListener('DOMContentLoaded', async () => {
    console.log('[CedNet Help] Popup carregado');

    // Capturar referências dos elementos
    errorContainer = document.getElementById('error-container');
    pageStatus = document.getElementById('page-status');

    // Elementos de login automático
    autoLoginBtn = document.getElementById('auto-login-btn');
    loginStatus = document.getElementById('login-status');
    loginResult = document.getElementById('login-result');
    deviceTypeSelect = document.getElementById('device-type');

    // Verificar página atual
    await checkCurrentPage();

    // Carregar notas salvas
    await loadNotes();

    // Configurar event listeners
    setupEventListeners();
});

/**
 * Verifica se a página atual é um roteador
 */
async function checkCurrentPage() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (!tab || !tab.url) {
            updateStatus('error', '❌', 'Não foi possível acessar a página');
            return;
        }

        const url = tab.url;
        console.log('[CedNet Help] URL atual:', url);

        // Verificar se é uma página de roteador (IPs privados)
        const isRouterPage = /^https?:\/\/(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|localhost)/.test(url);

        if (isRouterPage) {
            updateStatus('success', '✅', 'Página de roteador detectada');
        } else {
            updateStatus('warning', '⚠️', 'Navegue até a página do roteador');
        }

    } catch (error) {
        console.error('[CedNet Help] Erro ao verificar página:', error);
        updateStatus('error', '❌', 'Erro ao verificar página');
    }
}

/**
 * Atualiza a caixa de status
 */
function updateStatus(type, icon, text) {
    const statusIcon = pageStatus.querySelector('.status-icon');
    const statusText = pageStatus.querySelector('.status-text');

    statusIcon.textContent = icon;
    statusText.textContent = text;

    pageStatus.className = 'status-box';
    if (type === 'error') pageStatus.classList.add('error');
    if (type === 'success') pageStatus.classList.add('success');
    if (type === 'warning') pageStatus.classList.add('warning');
}

/**
 * Configura os event listeners
 */
function setupEventListeners() {
    if (autoLoginBtn) {
        autoLoginBtn.addEventListener('click', handleAutoLogin);
    }

    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', handleCopy);
    });

    // Event listeners do Bloco de Notas
    const saveNotesBtn = document.getElementById('save-notes-btn');
    const clearNotesBtn = document.getElementById('clear-notes-btn');
    const notesArea = document.getElementById('notes-area');

    if (saveNotesBtn) {
        saveNotesBtn.addEventListener('click', saveNotes);
    }

    if (clearNotesBtn) {
        clearNotesBtn.addEventListener('click', clearNotes);
    }

    // AUTO-SAVE
    if (notesArea) {
        let saveTimeout;
        notesArea.addEventListener('input', () => {
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(() => {
                saveNotes(true);
            }, 500);
        });

        notesArea.addEventListener('blur', () => {
            saveNotes(true);
        });
    }
}

// ========================================
// FUNÇÕES DO BLOCO DE NOTAS
// ========================================

/**
 * Carrega notas salvas do storage
 */
async function loadNotes() {
    try {
        const result = await chrome.storage.local.get(['cednetNotes']);
        const notesArea = document.getElementById('notes-area');
        if (result.cednetNotes && notesArea) {
            notesArea.value = result.cednetNotes;
        }
    } catch (e) {
        console.log('[CedNet Help] Erro ao carregar notas:', e);
    }
}

/**
 * Salva notas no storage local
 * @param {boolean} silent - Se true, não mostra feedback visual
 */
async function saveNotes(silent = false) {
    const notesArea = document.getElementById('notes-area');
    const saveStatus = document.getElementById('save-status');

    if (!notesArea) return;

    try {
        await chrome.storage.local.set({ cednetNotes: notesArea.value });

        // Mostrar feedback (apenas se não for silent)
        if (!silent && saveStatus) {
            saveStatus.classList.remove('hidden');
            setTimeout(() => {
                saveStatus.classList.add('hidden');
            }, 2000);
        }

        console.log('[CedNet Help] Notas salvas!');
    } catch (e) {
        console.log('[CedNet Help] Erro ao salvar notas:', e);
    }
}

/**
 * Limpa as notas
 */
async function clearNotes() {
    const notesArea = document.getElementById('notes-area');
    if (!notesArea) return;

    if (confirm('Limpar todas as anotações?')) {
        notesArea.value = '';
        await saveNotes();
    }
}

/**
 * Adiciona WiFi capturado às notas
 */
function addCapturedWifiToNotes() {
    const notesArea = document.getElementById('notes-area');
    const ssid = ssidValue?.textContent || '-';
    const pass = passwordValue?.textContent || '-';

    if (!notesArea || ssid === '-') return;

    const wifiEntry = `${ssid}\n${pass}\n`;
    notesArea.value += wifiEntry;

    // Esconder container de resultados
    resultsContainer?.classList.add('hidden');

    // Salvar automaticamente
    saveNotes();
}

// ========================================
// FUNÇÃO DE LOGIN AUTOMÁTICO
// ========================================

/**
 * Inicia o processo de login automático
 */
async function handleAutoLogin() {
    console.log('[CedNet Help] Iniciando login automático...');

    autoLoginBtn.disabled = true;
    autoLoginBtn.querySelector('.btn-text').textContent = 'Verificando...';
    loginStatus.classList.add('hidden');
    loginResult.classList.add('hidden');
    errorContainer.classList.add('hidden');

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (!tab || !tab.id) {
            throw new Error('Não foi possível acessar a aba atual');
        }

        // PRIMEIRO: Verificar se existe uma página de login
        const hasLoginPage = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: checkIfLoginPage
        });

        if (!hasLoginPage || !hasLoginPage[0] || !hasLoginPage[0].result) {
            // Não há página de login
            console.log('[CedNet Help] Nenhuma página de login detectada');
            autoLoginBtn.disabled = false;
            autoLoginBtn.querySelector('.btn-text').textContent = 'Login';
            handleError('Nenhuma página de login detectada. Navegue até a tela de login do dispositivo.');
            return;
        }

        console.log('[CedNet Help] Página de login detectada! Iniciando tentativas...');

        autoLoginBtn.querySelector('.btn-text').textContent = 'Tentando...';
        loginStatus.classList.remove('hidden');

        // Obter tipo de dispositivo selecionado
        const deviceType = deviceTypeSelect ? deviceTypeSelect.value : 'cednet';
        const credentials = getCredentials(deviceType);
        console.log(`[CedNet Help] Tipo: ${deviceType}, Credenciais: ${credentials.length}`);

        // Salvar URL inicial para comparar depois
        let initialUrl = tab.url;
        console.log('[CedNet Help] URL inicial:', initialUrl);

        // Desabilitar alerts/confirms do roteador para não travar
        try {
            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: () => {
                    window._originalAlert = window.alert;
                    window._originalConfirm = window.confirm;
                    window.alert = function (msg) { console.log('[CedNet Help] Alert suprimido:', msg); };
                    window.confirm = function (msg) { console.log('[CedNet Help] Confirm suprimido:', msg); return true; };
                }
            });
        } catch (e) {
            console.log('[CedNet Help] Não foi possível suprimir alerts');
        }

        // Tentar cada credencial
        for (let i = 0; i < credentials.length; i++) {
            const cred = credentials[i];

            // Atualizar UI
            document.getElementById('login-attempt').textContent = `${deviceType.toUpperCase()}`;
            document.getElementById('login-count').textContent = `${i + 1}/${credentials.length}`;
            document.getElementById('login-current').textContent = `${cred.user} / ${cred.pass || '(vazio)'}`;

            // Executar tentativa de login
            try {
                await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    func: tryLogin,
                    args: [cred.user, cred.pass]
                });
            } catch (e) {
                console.log('[CedNet Help] Erro na execução (página pode ter mudado):', e.message);
            }

            console.log(`[CedNet Help] Tentativa ${i + 1}:`, cred.user, '/', cred.pass);

            // Aguardar a página carregar após clique
            await new Promise(resolve => setTimeout(resolve, 2000));

            // Verificar se a URL mudou (método mais confiável)
            try {
                const [currentTab] = await chrome.tabs.query({ active: true, currentWindow: true });
                const currentUrl = currentTab.url;

                console.log('[CedNet Help] URL atual:', currentUrl);

                // Se a URL mudou, o login provavelmente funcionou!
                if (currentUrl !== initialUrl) {
                    console.log('[CedNet Help] ✅ URL mudou! Login bem-sucedido!');

                    loginStatus.classList.add('hidden');
                    loginResult.classList.remove('hidden');
                    document.getElementById('found-user').textContent = cred.user;
                    document.getElementById('found-pass').textContent = cred.pass || '(vazio)';

                    updateStatus('success', '✅', 'Login encontrado!');

                    autoLoginBtn.disabled = false;
                    autoLoginBtn.querySelector('.btn-text').textContent = 'Tentar Login';
                    return;
                }

                // Verificar se ainda tem campo de senha (página de login)
                const checkResult = await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    func: checkIfLoggedIn
                });

                if (checkResult && checkResult[0] && checkResult[0].result === true) {
                    console.log('[CedNet Help] ✅ Página mudou! Login bem-sucedido!');

                    loginStatus.classList.add('hidden');
                    loginResult.classList.remove('hidden');
                    document.getElementById('found-user').textContent = cred.user;
                    document.getElementById('found-pass').textContent = cred.pass || '(vazio)';

                    updateStatus('success', '✅', 'Login encontrado!');

                    autoLoginBtn.disabled = false;
                    autoLoginBtn.querySelector('.btn-text').textContent = 'Tentar Login';
                    return;
                }
            } catch (e) {
                // Se deu erro ao verificar, provavelmente a página mudou (login funcionou!)
                console.log('[CedNet Help] ✅ Erro na verificação (página mudou?) - Login pode ter funcionado!');

                loginStatus.classList.add('hidden');
                loginResult.classList.remove('hidden');
                document.getElementById('found-user').textContent = cred.user;
                document.getElementById('found-pass').textContent = cred.pass || '(vazio)';

                updateStatus('success', '✅', 'Login encontrado!');

                autoLoginBtn.disabled = false;
                autoLoginBtn.querySelector('.btn-text').textContent = 'Tentar Login';
                return;
            }
        }

        // Nenhuma credencial funcionou
        loginStatus.classList.add('hidden');
        updateStatus('error', '❌', 'Nenhuma credencial funcionou');
        handleError('Nenhuma combinação de usuário/senha funcionou. Tente adicionar novas credenciais.');

    } catch (error) {
        console.error('[CedNet Help] Erro no login automático:', error);
        handleError(`Erro: ${error.message}`);
    } finally {
        autoLoginBtn.disabled = false;
        autoLoginBtn.querySelector('.btn-text').textContent = 'Login';

        // Restaurar alerts originais
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (tab && tab.id) {
                await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    func: () => {
                        if (window._originalAlert) window.alert = window._originalAlert;
                        if (window._originalConfirm) window.confirm = window._originalConfirm;
                    }
                });
            }
        } catch (e) { }
    }
}

/**
 * Verifica se a página atual é uma página de login
 * (verifica se existe campo de senha visível)
 */
function checkIfLoginPage() {
    console.log('[CedNet Help] Verificando se é página de login...');

    // Buscar campos de senha visíveis
    const passFields = document.querySelectorAll('input[type="password"]');

    for (const field of passFields) {
        const style = window.getComputedStyle(field);
        const isVisible = field.offsetParent !== null &&
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            field.offsetWidth > 0;

        if (isVisible) {
            console.log('[CedNet Help] Campo de senha encontrado - É página de login!');
            return true;
        }
    }

    console.log('[CedNet Help] Nenhum campo de senha visível - NÃO é página de login');
    return false;
}

/**
 * Função injetada para tentar login
 */
function tryLogin(username, password) {
    console.log('[CedNet Help] Tentando login:', username, '/', password);

    // ========================================
    // BUSCA UNIVERSAL DE CAMPOS DE LOGIN
    // ========================================

    let userInput = null;
    let passInput = null;

    // 1. Buscar campo de senha primeiro (mais fácil de identificar)
    const passFields = document.querySelectorAll('input[type="password"]');
    for (const field of passFields) {
        const style = window.getComputedStyle(field);
        if (field.offsetParent !== null && style.display !== 'none' && style.visibility !== 'hidden') {
            passInput = field;
            break;
        }
    }

    // 2. Buscar campo de usuário por vários métodos
    const userSelectors = [
        'input[type="text"]',
        'input[name*="user" i]',
        'input[name*="login" i]',
        'input[name*="name" i]',
        'input[name*="email" i]',
        'input[id*="user" i]',
        'input[id*="login" i]',
        'input[id*="name" i]',
        'input[autocomplete="username"]',
        'input[placeholder*="user" i]',
        'input[placeholder*="login" i]',
        'input[placeholder*="usuário" i]',
        'input:not([type="password"]):not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="checkbox"]):not([type="radio"])'
    ];

    for (const selector of userSelectors) {
        try {
            const fields = document.querySelectorAll(selector);
            for (const field of fields) {
                const style = window.getComputedStyle(field);
                if (field.offsetParent !== null && style.display !== 'none' && style.visibility !== 'hidden' && field.offsetWidth > 0) {
                    userInput = field;
                    break;
                }
            }
            if (userInput) break;
        } catch (e) { }
    }

    if (!userInput || !passInput) {
        console.log('[CedNet Help] Campos de login não encontrados');
        return false;
    }

    console.log('[CedNet Help] Campos encontrados - User:', userInput.id || userInput.name, 'Pass:', passInput.id || passInput.name);

    // Preencher campos
    userInput.value = username;
    userInput.dispatchEvent(new Event('input', { bubbles: true }));
    userInput.dispatchEvent(new Event('change', { bubbles: true }));
    userInput.dispatchEvent(new Event('blur', { bubbles: true }));

    passInput.value = password;
    passInput.dispatchEvent(new Event('input', { bubbles: true }));
    passInput.dispatchEvent(new Event('change', { bubbles: true }));
    passInput.dispatchEvent(new Event('blur', { bubbles: true }));

    console.log('[CedNet Help] Campos preenchidos, buscando botão...');

    // Buscar botão de login - múltiplas estratégias
    let loginButton = null;

    // 1. Buscar por botões com texto específico
    const allButtons = document.querySelectorAll('button, input[type="submit"], input[type="button"], a.btn, a.button, [onclick], [role="button"]');

    // Palavras-chave universais para botões de login
    const loginKeywords = [
        // Português
        'entrar', 'login', 'acessar', 'enviar', 'confirmar', 'ok', 'conectar',
        // Inglês
        'sign in', 'log in', 'submit', 'go', 'enter', 'connect', 'authenticate'
    ];

    for (const btn of allButtons) {
        const text = (btn.textContent || btn.value || btn.title || '').toLowerCase().trim();
        const id = (btn.id || '').toLowerCase();
        const className = (btn.className || '').toLowerCase();

        // Verificar palavras-chave
        let isLoginButton = loginKeywords.some(kw => text.includes(kw));

        // Verificar ID e classe
        if (!isLoginButton) {
            isLoginButton = id.includes('login') || id.includes('submit') || id.includes('btn') ||
                className.includes('login') || className.includes('submit') || className.includes('primary');
        }

        if (isLoginButton && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
            loginButton = btn;
            console.log('[CedNet Help] Botão encontrado:', text || id || 'sem texto');
            break;
        }
    }

    // 2. Se não encontrou, buscar qualquer botão próximo ao form
    if (!loginButton) {
        const form = passInput.closest('form') || userInput.closest('form');
        if (form) {
            loginButton = form.querySelector('button, input[type="submit"], input[type="button"]');
            if (loginButton) {
                console.log('[CedNet Help] Botão encontrado no form');
            }
        }
    }

    // 3. Fallback: buscar qualquer botão na página
    if (!loginButton) {
        const buttons = document.querySelectorAll('button:not([disabled]), input[type="submit"]:not([disabled])');
        for (const btn of buttons) {
            if (btn.offsetParent !== null) {
                loginButton = btn;
                console.log('[CedNet Help] Usando primeiro botão visível');
                break;
            }
        }
    }

    // Clicar no botão
    if (loginButton) {
        console.log('[CedNet Help] Clicando no botão de login...');

        // Tentar múltiplas formas de clicar
        try {
            loginButton.focus();
            loginButton.click();
        } catch (e) {
            console.log('[CedNet Help] Erro no click, tentando dispatchEvent');
        }

        // Também disparar evento de click
        try {
            loginButton.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        } catch (e) {
            console.log('[CedNet Help] Erro no dispatchEvent');
        }

        return true;
    }

    // 4. Última tentativa: submit do form
    const form = passInput.closest('form') || userInput.closest('form');
    if (form) {
        console.log('[CedNet Help] Fazendo submit do form diretamente');
        try {
            form.submit();
            return true;
        } catch (e) {
            console.log('[CedNet Help] Erro no form.submit');
        }
    }

    console.log('[CedNet Help] Nenhum botão de login encontrado!');
    return false;
}

/**
 * Verifica se logou com sucesso
 */
function checkIfLoggedIn() {
    console.log('[CedNet Help] Verificando se logou...');

    // 1. Verificar se ainda tem campo de senha VISÍVEL
    const passFields = document.querySelectorAll('input[type="password"]');
    let hasVisiblePasswordField = false;

    for (const field of passFields) {
        // Verificar se está visível (não escondido)
        const style = window.getComputedStyle(field);
        const isVisible = field.offsetParent !== null &&
            style.display !== 'none' &&
            style.visibility !== 'hidden' &&
            field.offsetWidth > 0;

        if (isVisible) {
            hasVisiblePasswordField = true;
            console.log('[CedNet Help] Campo de senha ainda visível');
            break;
        }
    }

    // Se ainda tem campo de senha visível, ainda está na tela de login
    if (hasVisiblePasswordField) {
        return false;
    }

    console.log('[CedNet Help] Campo de senha sumiu!');

    // 2. Verificar se apareceram menus de navegação (indicador de login bem-sucedido)
    // Termos UNIVERSAIS para vários dispositivos
    const loggedInIndicators = [
        // ZTE / Huawei
        'topologia', 'internet', 'rede local', 'voip', 'gerência', 'wlan', 'wan', 'lan',
        // Ubiquiti (airOS)
        'airmax', 'wireless', 'network', 'services', 'system', 'main', 'ubnt',
        // MikroTik
        'webfig', 'winbox', 'quick set', 'interfaces', 'bridge', 'routing',
        // TP-Link / D-Link / Intelbras
        'quick setup', 'basic settings', 'advanced', 'wireless settings',
        // Genéricos
        'configuração', 'status', 'início', 'home', 'dashboard', 'menu',
        'bem-vindo', 'welcome', 'logout', 'sair', 'sign out', 'disconnect',
        'device', 'tools', 'monitor', 'statistics', 'logs'
    ];

    const pageText = document.body.textContent.toLowerCase();
    let foundMenus = 0;

    for (const indicator of loggedInIndicators) {
        if (pageText.includes(indicator)) {
            foundMenus++;
        }
    }

    // Se encontrou vários menus, provavelmente logou
    if (foundMenus >= 3) {
        console.log('[CedNet Help] Menus de navegação encontrados:', foundMenus);
        return true;
    }

    // 3. Verificar se tem elementos de navegação
    const navElements = document.querySelectorAll('nav, .nav, .menu, #menu, [class*="navigation"], [class*="sidebar"]');
    if (navElements.length > 0) {
        console.log('[CedNet Help] Elementos de navegação encontrados');
        return true;
    }

    // 4. Se o campo de senha sumiu, considera como logado
    console.log('[CedNet Help] Campo de senha sumiu - considerando como logado');
    return true;
}

/**
 * Inicia o processo de captura (simples, sem navegação)
 */
async function handleCapture() {
    console.log('[CedNet Help] Iniciando captura...');

    captureBtn.classList.add('loading');
    captureBtn.querySelector('.btn-icon').textContent = '⏳';
    captureBtn.querySelector('.btn-text').textContent = 'Buscando...';

    resultsContainer.classList.add('hidden');
    errorContainer.classList.add('hidden');

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (!tab || !tab.id) {
            throw new Error('Não foi possível acessar a aba atual');
        }

        // Executar busca simples na página atual
        const results = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: searchWiFiCredentials
        });

        console.log('[WiFi Grabber] Resultado:', results);

        if (results && results[0] && results[0].result) {
            const credentials = results[0].result;

            if (credentials.ssid || credentials.password) {
                handleSuccess(credentials, tab.url);
            } else {
                handleError('Não foi possível encontrar credenciais WiFi nesta página. Navegue até a página de configuração WLAN.');
            }
        } else {
            handleError('Não foi possível executar a busca.');
        }

    } catch (error) {
        console.error('[WiFi Grabber] Erro:', error);
        handleError(`Erro: ${error.message}`);
    } finally {
        resetCaptureButton();
    }
}

/**
 * Função que será injetada na página para buscar credenciais WiFi
 */
function searchWiFiCredentials() {
    console.log('[WiFi Grabber] Buscando credenciais WiFi...');

    const result = { ssid: null, password: null };

    // Lista de valores a ignorar (inclui valores de configuração que não são senhas)
    const IGNORE_VALUES = [
        /^ssid\d*$/i, /^wlan\d*$/i, /^\d{1,5}$/, /^[a-z0-9]{1,3}$/i,
        /^(on|off|enabled|disabled|yes|no|true|false|auto|none|select)$/i,
        /^-?\d+(\.\d+)?$/, /^[A-Z0-9]{2}:[A-Z0-9]{2}/i,
        /^(aplicar|cancelar|salvar|ok|submit|apply|cancel|save|reset|refresh|atualizar)$/i,
        /^(ligado|desligado|ativado|desativado|habilitado|manual|automático)$/i,
        // Valores de configuração que NÃO são senhas
        /PSKAuthentication/i,
        /^(WPA|WPA2|WPA3|WEP|TKIP|AES|PSK|EAP|RADIUS|Open|Shared)/i,
        /^(WPA2-PSK|WPA-PSK|WPA2-PSK-AES|WPA-PSK-TKIP)/i
    ];

    function isIgnored(val) {
        if (!val || typeof val !== 'string' || val.trim().length < 4) return true;
        return IGNORE_VALUES.some(r => r.test(val.trim()));
    }

    // ======================================
    // BUSCA ESPECÍFICA POR LINHAS DA PÁGINA
    // ======================================
    console.log('[WiFi Grabber] Buscando por labels específicos...');

    // Buscar todas as linhas (apenas .row divs para evitar containers grandes)
    const rows = document.querySelectorAll('.row, tr');
    console.log('[WiFi Grabber] Linhas encontradas:', rows.length);

    rows.forEach(row => {
        // Pegar o texto do label (primeira célula ou label)
        const labelEl = row.querySelector('.left, td:first-child, th:first-child, label');
        if (!labelEl) return;

        const labelText = labelEl.textContent.toLowerCase().trim();

        // Pegar o input desta linha específica
        const input = row.querySelector('input[type="text"], input[type="password"]');
        if (!input || !input.value || isIgnored(input.value)) return;

        console.log('[WiFi Grabber] Linha:', labelText, '=', input.value.substring(0, 10));

        // Verificar SSID
        if (!result.ssid && labelText.includes('nome ssid')) {
            result.ssid = input.value;
            console.log('[WiFi Grabber] ✓ SSID encontrado:', result.ssid);
        }

        // Verificar Senha WPA (deve ser diferente do SSID)
        if (!result.password && labelText.includes('senha wpa')) {
            if (input.value !== result.ssid) { // Garantir que é diferente do SSID
                result.password = input.value;
                console.log('[WiFi Grabber] ✓ Senha WPA encontrada');
            }
        }
    });

    // ======================================
    // BUSCA POR IDs CONHECIDOS (fallback)
    // ======================================
    if (!result.ssid || !result.password) {
        console.log('[WiFi Grabber] Buscando por IDs conhecidos...');

        const SSID_IDS = ['SSID1Name', 'SSID2Name', 'SSIDName'];
        const PASSWORD_IDS = ['KeyPassphrase', 'WPAKey', 'WPAPassphrase', 'WPA2Key', 'PSKValue'];

        // Buscar SSID
        if (!result.ssid) {
            for (const id of SSID_IDS) {
                let el = document.getElementById(id);
                if (!el) el = document.querySelector(`input[id*="${id}" i]`);

                if (el && el.tagName === 'INPUT' && el.value && !isIgnored(el.value)) {
                    result.ssid = el.value;
                    console.log('[WiFi Grabber] SSID encontrado por ID:', result.ssid);
                    break;
                }
            }
        }

        // Buscar Senha
        if (!result.password) {
            for (const id of PASSWORD_IDS) {
                let el = document.getElementById(id);
                if (!el) el = document.querySelector(`input[id*="${id}" i]`);

                if (el && el.tagName === 'INPUT' && el.value && !isIgnored(el.value)) {
                    // Garantir que é diferente do SSID
                    if (el.value !== result.ssid) {
                        result.password = el.value;
                        console.log('[WiFi Grabber] Senha encontrada por ID');
                        break;
                    }
                }
            }
        }
    }

    // ======================================
    // BUSCA GENÉRICA SE NÃO ENCONTROU
    // ======================================
    if (!result.ssid || !result.password) {
        console.log('[WiFi Grabber] Buscando de forma genérica...');

        const SSID_PATTERNS = ['ssid', 'nome da rede', 'network name'];
        const PASSWORD_PATTERNS = ['senha wpa', 'wpa password', 'wpa key', 'passphrase'];

        // Buscar apenas inputs tipo text ou password (NÃO selects!)
        document.querySelectorAll('input[type="text"], input[type="password"]').forEach(input => {
            if (!input.value || isIgnored(input.value)) return;

            // Pegar label/identificador
            let labelText = '';

            if (input.id) labelText += ' ' + input.id.toLowerCase();
            if (input.name) labelText += ' ' + input.name.toLowerCase();

            const row = input.closest('tr, .row');
            if (row) {
                const firstCell = row.querySelector('td, th, label, .left');
                if (firstCell) labelText += ' ' + firstCell.textContent.toLowerCase();
            }

            // Verificar se é SSID
            if (!result.ssid) {
                for (const pattern of SSID_PATTERNS) {
                    if (labelText.includes(pattern)) {
                        result.ssid = input.value;
                        console.log('[WiFi Grabber] SSID genérico:', result.ssid);
                        break;
                    }
                }
            }

            // Verificar se é Password (apenas se label contém "senha" ou "wpa")
            if (!result.password) {
                for (const pattern of PASSWORD_PATTERNS) {
                    if (labelText.includes(pattern)) {
                        result.password = input.value;
                        console.log('[WiFi Grabber] Senha genérica encontrada');
                        break;
                    }
                }
            }
        });
    }

    console.log('[CedNet Help] Resultado final:', result);
    return result;
}

/**
 * Processa credenciais encontradas
 */
function handleSuccess(credentials, sourceUrl) {
    console.log('[CedNet Help] Credenciais encontradas:', credentials);

    ssidValue.textContent = credentials.ssid || '(não encontrado)';
    passwordValue.textContent = credentials.password || '(não encontrado)';

    resultsContainer.classList.remove('hidden');
    updateStatus('success', '✅', 'Credenciais capturadas!');
}

/**
 * Salva como arquivo TXT (abre no bloco de notas)
 */
function handleSaveTxt() {
    const ssid = ssidValue.textContent;
    const password = passwordValue.textContent;

    if (ssid === '-' || ssid === '(não encontrado)') {
        alert('Nenhuma credencial para salvar!');
        return;
    }

    // Criar conteúdo do arquivo
    const content = `${ssid}
${password}
`;

    // Criar blob e fazer download
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);

    // Nome do arquivo com SSID
    const fileName = `${ssid.replace(/[^a-zA-Z0-9]/g, '_')}.txt`;

    // Criar link e clicar para download
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log('[WiFi Grabber] Arquivo TXT salvo:', fileName);
}

/**
 * Exibe mensagem de erro
 */
function handleError(message) {
    console.error('[CedNet Help] Erro:', message);

    const errorMessage = document.getElementById('error-message');
    errorMessage.textContent = message;
    errorContainer.classList.remove('hidden');

    updateStatus('error', '❌', 'Falha na captura');
}

/**
 * Reseta o botão de captura
 */
function resetCaptureButton() {
    captureBtn.classList.remove('loading');
    captureBtn.querySelector('.btn-icon').textContent = '🔐';
    captureBtn.querySelector('.btn-text').textContent = 'Capturar WiFi';
}

/**
 * Copia valor para a área de transferência
 */
async function handleCopy(event) {
    const targetId = event.currentTarget.dataset.target;
    const targetElement = document.getElementById(targetId);
    const value = targetElement.textContent;

    if (value === '-' || value === '(não encontrado)') {
        return;
    }

    try {
        await navigator.clipboard.writeText(value);
        event.currentTarget.textContent = '✅';
        setTimeout(() => {
            event.currentTarget.textContent = '📋';
        }, 1500);
    } catch (err) {
        console.error('[CedNet Help] Erro ao copiar:', err);
    }
}
