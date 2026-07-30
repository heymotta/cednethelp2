/**
 * WiFi Credential Grabber - Content Script Automático
 * 
 * Este script é injetado AUTOMATICAMENTE em todas as páginas de roteadores
 * e monitora continuamente por credenciais Wi-Fi.
 */

(function () {
    'use strict';

    // ============================================
    // VERIFICAÇÃO DE IP LOCAL (ROTEADOR)
    // ============================================

    /**
     * Verifica se a página atual é um IP de rede local (roteador)
     */
    function isLocalIP() {
        const hostname = window.location.hostname;

        const localPatterns = [
            /^192\.168\.\d{1,3}\.\d{1,3}$/,
            /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
            /^172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}$/,
            /^localhost$/,
            /^127\.0\.0\.1$/
        ];

        return localPatterns.some(pattern => pattern.test(hostname));
    }

    // Sair imediatamente se não for IP local
    if (!isLocalIP()) {
        return;
    }

    // Evitar execução múltipla
    if (window.__wifiGrabberLoaded) return;
    window.__wifiGrabberLoaded = true;

    console.log('[WiFi Grabber AUTO] Script automático carregado:', window.location.href);

    // ============================================
    // CONFIGURAÇÃO
    // ============================================

    const CONFIG = {
        // Intervalo para re-verificar a página (ms)
        CHECK_INTERVAL: 2000,

        // Delay inicial antes de começar a buscar (ms)
        INITIAL_DELAY: 1000,

        // Tempo máximo para tentar encontrar credenciais (ms)
        MAX_SEARCH_TIME: 60000,

        // Se deve tentar navegar automaticamente para WLAN
        AUTO_NAVIGATE: true
    };

    // ============================================
    // PADRÕES DE BUSCA
    // ============================================

    const SSID_PATTERNS = [
        { pattern: 'nome ssid', score: 100 },
        { pattern: 'nome do ssid', score: 100 },
        { pattern: 'wireless network name', score: 95 },
        { pattern: 'nome da rede wireless', score: 95 },
        { pattern: 'nome da rede wifi', score: 95 },
        { pattern: 'nome da rede wi-fi', score: 95 },
        { pattern: 'network name', score: 90 },
        { pattern: 'nome da rede', score: 90 },
        { pattern: 'wifi name', score: 85 },
        { pattern: 'wi-fi name', score: 85 },
        { pattern: 'wireless name', score: 85 },
        { pattern: 'nome wifi', score: 85 },
        { pattern: 'nome wi-fi', score: 85 },
        { pattern: 'wlan ssid', score: 70 },
        { pattern: 'wireless ssid', score: 70 },
        { pattern: 'primary ssid', score: 70 },
        { pattern: 'main ssid', score: 70 },
        { pattern: 'essid', score: 65 },
        { pattern: 'ssid', score: 30 }
    ];

    const PASSWORD_PATTERNS = [
        { pattern: 'senha wpa', score: 100 },
        { pattern: 'senha wpa2', score: 100 },
        { pattern: 'chave wpa', score: 100 },
        { pattern: 'chave wpa2', score: 100 },
        { pattern: 'wpa password', score: 95 },
        { pattern: 'wpa2 password', score: 95 },
        { pattern: 'wireless password', score: 95 },
        { pattern: 'wifi password', score: 95 },
        { pattern: 'wi-fi password', score: 95 },
        { pattern: 'senha wifi', score: 95 },
        { pattern: 'senha wi-fi', score: 95 },
        { pattern: 'senha wireless', score: 95 },
        { pattern: 'senha da rede', score: 95 },
        { pattern: 'security key', score: 90 },
        { pattern: 'chave de segurança', score: 90 },
        { pattern: 'network key', score: 90 },
        { pattern: 'pre-shared key', score: 80 },
        { pattern: 'preshared key', score: 80 },
        { pattern: 'pre shared key', score: 80 },
        { pattern: 'wpa key', score: 75 },
        { pattern: 'wpa-key', score: 75 },
        { pattern: 'wpa psk', score: 75 },
        { pattern: 'wpa-psk', score: 75 },
        { pattern: 'passphrase', score: 70 },
        { pattern: 'shared key', score: 65 },
        { pattern: 'psk', score: 40 },
        { pattern: 'senha', score: 35 },
        { pattern: 'password', score: 30 }
    ];

    // ============================================
    // PADRÕES PPPOE
    // ============================================

    const PPPOE_USER_PATTERNS = [
        { pattern: 'usuário pppoe', score: 100 },
        { pattern: 'usuario pppoe', score: 100 },
        { pattern: 'pppoe user', score: 100 },
        { pattern: 'pppoe username', score: 100 },
        { pattern: 'ppp user', score: 95 },
        { pattern: 'ppp username', score: 95 },
        { pattern: 'wan user', score: 90 },
        { pattern: 'wan username', score: 90 },
        { pattern: 'usuário ppp', score: 90 },
        { pattern: 'usuario ppp', score: 90 },
        { pattern: 'nome de usuário', score: 80 },
        { pattern: 'nome de usuario', score: 80 },
        { pattern: 'user name', score: 70 },
        { pattern: 'username', score: 60 },
        { pattern: 'usuário', score: 50 },
        { pattern: 'usuario', score: 50 }
    ];

    const PPPOE_PASSWORD_PATTERNS = [
        { pattern: 'senha pppoe', score: 100 },
        { pattern: 'pppoe password', score: 100 },
        { pattern: 'ppp password', score: 95 },
        { pattern: 'senha ppp', score: 95 },
        { pattern: 'wan password', score: 90 },
        { pattern: 'senha wan', score: 90 },
        { pattern: 'connection password', score: 85 },
        { pattern: 'senha de conexão', score: 85 },
        { pattern: 'senha de conexao', score: 85 }
    ];

    // Padrões de menu para navegar até WLAN ou WAN
    const WLAN_MENU_PATTERNS = [
        'wlan',
        'wireless',
        'wifi',
        'wi-fi',
        'sem fio',
        'rede sem fio',
        'wlan básica',
        'wlan basica',
        'configuração wireless',
        'configuracao wireless',
        'wireless settings',
        'wireless basic',
        'network',
        '2.4ghz',
        '5ghz'
    ];

    const IGNORE_VALUES = [
        /^ssid\d*$/i,
        /^wlan\d*$/i,
        /^\d{1,5}$/,
        /^[a-z0-9]{1,4}$/i,
        /^(on|off|enabled|disabled|yes|no|true|false)$/i
    ];

    // ============================================
    // ESTADO
    // ============================================

    let searchStartTime = Date.now();
    let credentialsFound = false;
    let lastFoundCredentials = null;
    let checkInterval = null;
    let observer = null;

    // ============================================
    // FUNÇÕES PRINCIPAIS
    // ============================================

    /**
     * Inicia a busca automática
     */
    function startAutoSearch() {
        console.log('[WiFi Grabber AUTO] Iniciando busca automática...');

        // Notificar background que a página foi carregada
        chrome.runtime.sendMessage({ type: 'PAGE_LOADED' }).catch(() => { });

        // Delay inicial
        setTimeout(() => {
            // Primeira verificação
            performSearch();

            // Configurar verificação periódica
            checkInterval = setInterval(() => {
                if (Date.now() - searchStartTime > CONFIG.MAX_SEARCH_TIME) {
                    console.log('[WiFi Grabber AUTO] Tempo máximo de busca atingido');
                    stopAutoSearch();
                    return;
                }

                if (!credentialsFound) {
                    performSearch();
                }
            }, CONFIG.CHECK_INTERVAL);

            // Observar mudanças no DOM (para páginas SPA)
            setupMutationObserver();

        }, CONFIG.INITIAL_DELAY);
    }

    /**
     * Para a busca automática
     */
    function stopAutoSearch() {
        if (checkInterval) {
            clearInterval(checkInterval);
            checkInterval = null;
        }
        if (observer) {
            observer.disconnect();
            observer = null;
        }
    }

    /**
     * Executa uma busca por credenciais
     */
    function performSearch() {
        const candidates = {
            ssid: [],
            password: [],
            pppoeUser: [],
            pppoePassword: []
        };

        // Executar estratégias de busca
        findByTableRows(candidates);
        findByLabelElements(candidates);
        findByTextProximity(candidates);
        findByInputAttributes(candidates);

        // Ordenar e selecionar melhores
        candidates.ssid.sort((a, b) => b.score - a.score);
        candidates.password.sort((a, b) => b.score - a.score);
        candidates.pppoeUser.sort((a, b) => b.score - a.score);
        candidates.pppoePassword.sort((a, b) => b.score - a.score);

        const bestSsid = candidates.ssid[0];
        const bestPassword = candidates.password[0];
        const bestPppoeUser = candidates.pppoeUser[0];
        const bestPppoePassword = candidates.pppoePassword[0];

        // Verificar se encontrou credenciais válidas (wifi OU pppoe)
        const hasWifi = bestSsid && bestPassword && bestSsid.score >= 50 && bestPassword.score >= 50;
        const hasPppoe = bestPppoeUser && bestPppoeUser.score >= 50;

        if (hasWifi || hasPppoe) {
            const credentials = {
                ssid: bestSsid?.value || null,
                password: bestPassword?.value || null,
                pppoeUser: bestPppoeUser?.value || null,
                pppoePassword: bestPppoePassword?.value || null
            };

            // Verificar se é diferente do último encontrado
            if (!lastFoundCredentials ||
                lastFoundCredentials.ssid !== credentials.ssid ||
                lastFoundCredentials.password !== credentials.password ||
                lastFoundCredentials.pppoeUser !== credentials.pppoeUser) {

                console.log('[WiFi Grabber AUTO] ✅ Credenciais encontradas!');
                if (credentials.ssid) console.log('[WiFi Grabber AUTO] SSID:', credentials.ssid);
                if (credentials.password) console.log('[WiFi Grabber AUTO] WiFi Password: ****');
                if (credentials.pppoeUser) console.log('[WiFi Grabber AUTO] PPPoE User:', credentials.pppoeUser);
                if (credentials.pppoePassword) console.log('[WiFi Grabber AUTO] PPPoE Password: ****');

                credentialsFound = true;
                lastFoundCredentials = credentials;

                // Enviar para o background
                chrome.runtime.sendMessage({
                    type: 'CREDENTIALS_FOUND',
                    data: credentials
                }).catch(err => {
                    console.log('[WiFi Grabber AUTO] Erro ao enviar:', err);
                });

                // Parar busca
                stopAutoSearch();
            }
        } else {
            // Não encontrou, tentar navegar para WLAN
            if (CONFIG.AUTO_NAVIGATE && !hasTriedNavigation) {
                tryNavigateToWlan();
            }
        }
    }

    let hasTriedNavigation = false;

    /**
     * Tenta navegar para a página de WLAN
     */
    function tryNavigateToWlan() {
        console.log('[WiFi Grabber AUTO] Tentando navegar para WLAN...');
        hasTriedNavigation = true;

        // Buscar links/botões de menu
        const clickables = document.querySelectorAll('a, button, div[onclick], span[onclick], li, td');

        for (const el of clickables) {
            const text = el.textContent.toLowerCase().trim();

            // Verificar se o texto corresponde a um menu WLAN
            for (const pattern of WLAN_MENU_PATTERNS) {
                if (text.includes(pattern) && text.length < 50) {
                    console.log('[WiFi Grabber AUTO] Encontrado menu:', text);

                    // Tentar clicar
                    try {
                        el.click();
                        console.log('[WiFi Grabber AUTO] Clicou em:', text);

                        // Resetar flag após um tempo para permitir nova navegação
                        setTimeout(() => {
                            hasTriedNavigation = false;
                        }, 5000);

                        return;
                    } catch (e) {
                        console.log('[WiFi Grabber AUTO] Erro ao clicar:', e);
                    }
                }
            }
        }
    }

    /**
     * Configura observer para mudanças no DOM
     */
    function setupMutationObserver() {
        observer = new MutationObserver((mutations) => {
            // Se houve mudanças significativas, re-verificar
            const hasSignificantChanges = mutations.some(m =>
                m.addedNodes.length > 0 ||
                (m.type === 'attributes' && m.attributeName === 'value')
            );

            if (hasSignificantChanges && !credentialsFound) {
                // Debounce
                clearTimeout(window.__wifiGrabberDebounce);
                window.__wifiGrabberDebounce = setTimeout(() => {
                    performSearch();
                }, 500);
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['value']
        });
    }

    // ============================================
    // ESTRATÉGIAS DE BUSCA
    // ============================================

    function findByTableRows(candidates) {
        const rows = document.querySelectorAll('tr');

        rows.forEach(row => {
            const cells = row.querySelectorAll('td, th');
            if (cells.length < 2) return;

            const labelText = cells[0].textContent.trim().toLowerCase();
            const valueCell = cells[1];

            const input = valueCell.querySelector('input');
            const value = input ? input.value : valueCell.textContent.trim();

            if (!value || isIgnoredValue(value)) return;

            const ssidScore = getPatternScore(labelText, SSID_PATTERNS);
            if (ssidScore > 0) {
                candidates.ssid.push({ value, score: ssidScore + 20, method: 'table', identifier: labelText });
            }

            const pwdScore = getPatternScore(labelText, PASSWORD_PATTERNS);
            if (pwdScore > 0) {
                candidates.password.push({ value, score: pwdScore + 20, method: 'table', identifier: labelText });
            }

            // PPPoE
            const pppoeUserScore = getPatternScore(labelText, PPPOE_USER_PATTERNS);
            if (pppoeUserScore > 0) {
                candidates.pppoeUser.push({ value, score: pppoeUserScore + 20, method: 'table', identifier: labelText });
            }

            const pppoePwdScore = getPatternScore(labelText, PPPOE_PASSWORD_PATTERNS);
            if (pppoePwdScore > 0) {
                candidates.pppoePassword.push({ value, score: pppoePwdScore + 20, method: 'table', identifier: labelText });
            }
        });
    }

    function findByLabelElements(candidates) {
        const labels = document.querySelectorAll('label');

        labels.forEach(label => {
            const labelText = label.textContent.trim().toLowerCase();
            const input = findInputForLabel(label);

            if (!input || !input.value || isIgnoredValue(input.value)) return;

            const ssidScore = getPatternScore(labelText, SSID_PATTERNS);
            if (ssidScore > 0) {
                candidates.ssid.push({ value: input.value, score: ssidScore + 15, method: 'label', identifier: labelText });
            }

            const pwdScore = getPatternScore(labelText, PASSWORD_PATTERNS);
            if (pwdScore > 0) {
                candidates.password.push({ value: input.value, score: pwdScore + 15, method: 'label', identifier: labelText });
            }

            // PPPoE
            const pppoeUserScore = getPatternScore(labelText, PPPOE_USER_PATTERNS);
            if (pppoeUserScore > 0) {
                candidates.pppoeUser.push({ value: input.value, score: pppoeUserScore + 15, method: 'label', identifier: labelText });
            }

            const pppoePwdScore = getPatternScore(labelText, PPPOE_PASSWORD_PATTERNS);
            if (pppoePwdScore > 0) {
                candidates.pppoePassword.push({ value: input.value, score: pppoePwdScore + 15, method: 'label', identifier: labelText });
            }
        });
    }

    function findByTextProximity(candidates) {
        const textElements = document.querySelectorAll('span, div, p, td, th, dt, dd, strong, b');

        textElements.forEach(el => {
            const text = el.textContent.trim().toLowerCase();

            if (text.length > 50 || text.length < 3) return;
            if (el.querySelector('input')) return;

            const input = findNearbyInput(el);
            if (!input || !input.value || isIgnoredValue(input.value)) return;

            const ssidScore = getPatternScore(text, SSID_PATTERNS);
            if (ssidScore > 0) {
                candidates.ssid.push({ value: input.value, score: ssidScore + 10, method: 'proximity', identifier: text });
            }

            const pwdScore = getPatternScore(text, PASSWORD_PATTERNS);
            if (pwdScore > 0) {
                candidates.password.push({ value: input.value, score: pwdScore + 10, method: 'proximity', identifier: text });
            }

            // PPPoE
            const pppoeUserScore = getPatternScore(text, PPPOE_USER_PATTERNS);
            if (pppoeUserScore > 0) {
                candidates.pppoeUser.push({ value: input.value, score: pppoeUserScore + 10, method: 'proximity', identifier: text });
            }

            const pppoePwdScore = getPatternScore(text, PPPOE_PASSWORD_PATTERNS);
            if (pppoePwdScore > 0) {
                candidates.pppoePassword.push({ value: input.value, score: pppoePwdScore + 10, method: 'proximity', identifier: text });
            }
        });
    }

    function findByInputAttributes(candidates) {
        const inputs = document.querySelectorAll('input');

        inputs.forEach(input => {
            if (!input.value || isIgnoredValue(input.value)) return;

            const attrs = [
                input.name,
                input.id,
                input.placeholder,
                input.title,
                input.getAttribute('aria-label')
            ].filter(Boolean).join(' ').toLowerCase();

            const ssidScore = getPatternScore(attrs, SSID_PATTERNS);
            if (ssidScore > 0) {
                candidates.ssid.push({ value: input.value, score: ssidScore, method: 'attribute', identifier: attrs });
            }

            const pwdScore = getPatternScore(attrs, PASSWORD_PATTERNS);
            if (pwdScore > 0) {
                candidates.password.push({ value: input.value, score: pwdScore, method: 'attribute', identifier: attrs });
            }

            // PPPoE
            const pppoeUserScore = getPatternScore(attrs, PPPOE_USER_PATTERNS);
            if (pppoeUserScore > 0) {
                candidates.pppoeUser.push({ value: input.value, score: pppoeUserScore, method: 'attribute', identifier: attrs });
            }

            const pppoePwdScore = getPatternScore(attrs, PPPOE_PASSWORD_PATTERNS);
            if (pppoePwdScore > 0) {
                candidates.pppoePassword.push({ value: input.value, score: pppoePwdScore, method: 'attribute', identifier: attrs });
            }
        });
    }

    // ============================================
    // FUNÇÕES AUXILIARES
    // ============================================

    function findInputForLabel(label) {
        if (label.htmlFor) {
            const input = document.getElementById(label.htmlFor);
            if (input) return input;
        }

        const innerInput = label.querySelector('input');
        if (innerInput) return innerInput;

        let sibling = label.nextElementSibling;
        for (let i = 0; i < 5 && sibling; i++) {
            if (sibling.tagName === 'INPUT') return sibling;
            const nestedInput = sibling.querySelector('input');
            if (nestedInput) return nestedInput;
            sibling = sibling.nextElementSibling;
        }

        const parent = label.parentElement;
        if (parent) {
            const inputs = parent.querySelectorAll('input');
            if (inputs.length === 1) return inputs[0];
        }

        return null;
    }

    function findNearbyInput(element) {
        let sibling = element.nextElementSibling;
        for (let i = 0; i < 3 && sibling; i++) {
            if (sibling.tagName === 'INPUT') return sibling;
            const input = sibling.querySelector('input');
            if (input) return input;
            sibling = sibling.nextElementSibling;
        }

        const parent = element.parentElement;
        if (parent) {
            const input = parent.querySelector('input');
            if (input) return input;

            const row = element.closest('tr');
            if (row) {
                const input = row.querySelector('input');
                if (input) return input;
            }
        }

        return null;
    }

    function getPatternScore(text, patterns) {
        if (!text) return 0;

        let bestScore = 0;

        for (const { pattern, score } of patterns) {
            if (text.includes(pattern)) {
                const specificity = pattern.length / text.length;
                const adjustedScore = score * (0.5 + specificity * 0.5);

                if (adjustedScore > bestScore) {
                    bestScore = adjustedScore;
                }
            }
        }

        return bestScore;
    }

    function isIgnoredValue(value) {
        if (!value || typeof value !== 'string') return true;

        const trimmed = value.trim();
        if (trimmed.length < 2) return true;

        return IGNORE_VALUES.some(regex => regex.test(trimmed));
    }

    // ============================================
    // INICIALIZAÇÃO
    // ============================================

    // Verificar se é página de login (não buscar ainda)
    function isLoginPage() {
        const loginIndicators = ['login', 'password', 'senha', 'usuário', 'user', 'entrar', 'sign in'];
        const pageText = document.body?.textContent?.toLowerCase() || '';
        const inputs = document.querySelectorAll('input[type="password"]');

        // Se tem campo de senha mas poucos inputs, provavelmente é login
        if (inputs.length === 1) {
            const hasLoginText = loginIndicators.some(i => pageText.includes(i));
            if (hasLoginText) return true;
        }

        return false;
    }

    // Iniciar busca
    if (document.readyState === 'complete') {
        if (!isLoginPage()) {
            startAutoSearch();
        } else {
            console.log('[WiFi Grabber AUTO] Página de login detectada, aguardando...');
            // Observar mudanças para detectar quando sair do login
            const loginObserver = new MutationObserver(() => {
                if (!isLoginPage()) {
                    loginObserver.disconnect();
                    startAutoSearch();
                }
            });
            loginObserver.observe(document.body, { childList: true, subtree: true });
        }
    } else {
        window.addEventListener('load', () => {
            if (!isLoginPage()) {
                startAutoSearch();
            }
        });
    }

})();
