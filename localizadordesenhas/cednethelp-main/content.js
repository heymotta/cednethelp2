/**
 * WiFi Credential Grabber - Content Script com Navegação Automática
 * 
 * Este script é injetado para buscar credenciais e navegar automaticamente
 * pelas páginas do roteador se necessário.
 * 
 * VERSÃO 2.2: Navegação automática entre páginas.
 */

(function () {
    'use strict';

    console.log('[WiFi Grabber] Content script v2.2 executando...');

    // ============================================
    // CONFIGURAÇÃO
    // ============================================

    const NAVIGATION_DELAY = 1500; // Delay após clicar em um menu
    const MAX_NAVIGATION_ATTEMPTS = 5;

    // ============================================
    // PADRÕES DE BUSCA - WIFI
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
    // PADRÕES DE BUSCA - PPPOE
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

    // Menus para navegar (em ordem de prioridade)
    const MENU_PATTERNS = [
        // WLAN/WiFi (para SSID e senha)
        { patterns: ['wlan básica', 'wlan basica', 'wlan basic'], priority: 10 },
        { patterns: ['configuração ssid', 'configuracao ssid', 'ssid config'], priority: 10 },
        { patterns: ['wireless settings', 'wireless config'], priority: 9 },
        { patterns: ['wlan', 'wireless', 'wifi', 'wi-fi'], priority: 8 },
        { patterns: ['sem fio', 'rede sem fio'], priority: 7 },

        // WAN (para PPPoE)
        { patterns: ['wan', 'internet', 'conexão wan', 'conexao wan'], priority: 6 },
        { patterns: ['pppoe', 'ppp'], priority: 5 },

        // Redes
        { patterns: ['network', 'rede', 'redes'], priority: 3 }
    ];

    const IGNORE_VALUES = [
        /^ssid\d*$/i,
        /^wlan\d*$/i,
        /^\d{1,5}$/,
        /^[a-z0-9]{1,4}$/i,
        /^(on|off|enabled|disabled|yes|no|true|false)$/i
    ];

    // ============================================
    // RESULTADO GLOBAL
    // ============================================

    const result = {
        ssid: null,
        password: null,
        pppoeUser: null,
        pppoePassword: null,
        fieldsFound: [],
        pagesVisited: [],
        status: 'searching'
    };

    // ============================================
    // FUNÇÃO PRINCIPAL
    // ============================================

    async function searchCredentials() {
        console.log('[WiFi Grabber] Iniciando busca com navegação automática...');
        console.log('[WiFi Grabber] URL:', window.location.href);

        result.pagesVisited.push(window.location.href);

        // Primeira tentativa na página atual
        extractFromCurrentPage();

        // Se encontrou tudo, retornar
        if (hasAllCredentials()) {
            result.status = 'complete';
            console.log('[WiFi Grabber] ✅ Todas as credenciais encontradas!');
            return result;
        }

        // Se não encontrou tudo, tentar navegar
        console.log('[WiFi Grabber] Buscando menus para navegar...');

        const menuElements = findMenuElements();
        console.log('[WiFi Grabber] Menus encontrados:', menuElements.length);

        // Tentar cada menu até encontrar as credenciais
        for (let i = 0; i < Math.min(menuElements.length, MAX_NAVIGATION_ATTEMPTS); i++) {
            const menu = menuElements[i];

            if (!menu.element || !menu.element.isConnected) continue;

            console.log(`[WiFi Grabber] Navegando para: "${menu.text}"`);

            try {
                // Clicar no menu
                menu.element.click();

                // Aguardar a página carregar
                await sleep(NAVIGATION_DELAY);

                // Tentar extrair novamente
                extractFromCurrentPage();

                // Verificar se encontrou
                if (hasAllCredentials()) {
                    result.status = 'complete';
                    console.log('[WiFi Grabber] ✅ Todas as credenciais encontradas!');
                    return result;
                }

            } catch (err) {
                console.log('[WiFi Grabber] Erro ao navegar:', err.message);
            }
        }

        // Retornar o que conseguiu encontrar
        result.status = hasAnyCredentials() ? 'partial' : 'not_found';
        console.log('[WiFi Grabber] Busca finalizada. Status:', result.status);

        return result;
    }

    function hasAllCredentials() {
        return result.ssid && result.password && result.pppoeUser;
    }

    function hasAnyCredentials() {
        return result.ssid || result.password || result.pppoeUser || result.pppoePassword;
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ============================================
    // EXTRAÇÃO DA PÁGINA ATUAL
    // ============================================

    function extractFromCurrentPage() {
        const candidates = {
            ssid: [],
            password: [],
            pppoeUser: [],
            pppoePassword: []
        };

        // Executar todas as estratégias
        findByTableRows(candidates);
        findByLabelElements(candidates);
        findByTextProximity(candidates);
        findByInputAttributes(candidates);

        // Selecionar melhores candidatos
        selectBestCandidates(candidates);
    }

    // ============================================
    // BUSCA DE MENUS PARA NAVEGAÇÃO
    // ============================================

    function findMenuElements() {
        const found = [];
        const clickables = document.querySelectorAll('a, button, div[onclick], span[onclick], li, td, nav a, .menu a, .nav a, [class*="menu"] a, [class*="nav"] a');

        clickables.forEach(el => {
            const text = el.textContent.toLowerCase().trim();

            // Ignorar textos muito longos ou vazios
            if (text.length > 30 || text.length < 2) return;

            // Ignorar se já visitamos essa página
            const href = el.href || el.getAttribute('onclick') || '';
            if (result.pagesVisited.some(p => href.includes(p))) return;

            // Verificar se corresponde a algum padrão de menu
            for (const menuGroup of MENU_PATTERNS) {
                for (const pattern of menuGroup.patterns) {
                    if (text.includes(pattern)) {
                        found.push({
                            element: el,
                            text: text,
                            pattern: pattern,
                            priority: menuGroup.priority
                        });
                        return; // Já encontrou, não precisa continuar
                    }
                }
            }
        });

        // Ordenar por prioridade (maior primeiro)
        found.sort((a, b) => b.priority - a.priority);

        return found;
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

            checkAndAddCandidate(labelText, value, SSID_PATTERNS, 'ssid', candidates, 20);
            checkAndAddCandidate(labelText, value, PASSWORD_PATTERNS, 'password', candidates, 20);
            checkAndAddCandidate(labelText, value, PPPOE_USER_PATTERNS, 'pppoeUser', candidates, 20);
            checkAndAddCandidate(labelText, value, PPPOE_PASSWORD_PATTERNS, 'pppoePassword', candidates, 20);
        });
    }

    function findByLabelElements(candidates) {
        const labels = document.querySelectorAll('label');

        labels.forEach(label => {
            const labelText = label.textContent.trim().toLowerCase();
            const input = findInputForLabel(label);

            if (!input || !input.value || isIgnoredValue(input.value)) return;

            checkAndAddCandidate(labelText, input.value, SSID_PATTERNS, 'ssid', candidates, 15);
            checkAndAddCandidate(labelText, input.value, PASSWORD_PATTERNS, 'password', candidates, 15);
            checkAndAddCandidate(labelText, input.value, PPPOE_USER_PATTERNS, 'pppoeUser', candidates, 15);
            checkAndAddCandidate(labelText, input.value, PPPOE_PASSWORD_PATTERNS, 'pppoePassword', candidates, 15);
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

            checkAndAddCandidate(text, input.value, SSID_PATTERNS, 'ssid', candidates, 10);
            checkAndAddCandidate(text, input.value, PASSWORD_PATTERNS, 'password', candidates, 10);
            checkAndAddCandidate(text, input.value, PPPOE_USER_PATTERNS, 'pppoeUser', candidates, 10);
            checkAndAddCandidate(text, input.value, PPPOE_PASSWORD_PATTERNS, 'pppoePassword', candidates, 10);
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

            checkAndAddCandidate(attrs, input.value, SSID_PATTERNS, 'ssid', candidates, 0);
            checkAndAddCandidate(attrs, input.value, PASSWORD_PATTERNS, 'password', candidates, 0);
            checkAndAddCandidate(attrs, input.value, PPPOE_USER_PATTERNS, 'pppoeUser', candidates, 0);
            checkAndAddCandidate(attrs, input.value, PPPOE_PASSWORD_PATTERNS, 'pppoePassword', candidates, 0);
        });
    }

    // ============================================
    // FUNÇÕES AUXILIARES
    // ============================================

    function checkAndAddCandidate(text, value, patterns, candidateType, candidates, bonus) {
        const score = getPatternScore(text, patterns);
        if (score > 0) {
            candidates[candidateType].push({ value, score: score + bonus, identifier: text });
        }
    }

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

    function selectBestCandidates(candidates) {
        // Ordenar por score
        candidates.ssid.sort((a, b) => b.score - a.score);
        candidates.password.sort((a, b) => b.score - a.score);
        candidates.pppoeUser.sort((a, b) => b.score - a.score);
        candidates.pppoePassword.sort((a, b) => b.score - a.score);

        // Selecionar melhores (apenas se não tiver sido encontrado antes)
        if (!result.ssid && candidates.ssid.length > 0 && candidates.ssid[0].score >= 50) {
            result.ssid = candidates.ssid[0].value;
            console.log('[WiFi Grabber] ✓ SSID encontrado:', result.ssid);
        }
        if (!result.password && candidates.password.length > 0 && candidates.password[0].score >= 50) {
            result.password = candidates.password[0].value;
            console.log('[WiFi Grabber] ✓ Senha WiFi encontrada');
        }
        if (!result.pppoeUser && candidates.pppoeUser.length > 0 && candidates.pppoeUser[0].score >= 50) {
            result.pppoeUser = candidates.pppoeUser[0].value;
            console.log('[WiFi Grabber] ✓ PPPoE User encontrado:', result.pppoeUser);
        }
        if (!result.pppoePassword && candidates.pppoePassword.length > 0 && candidates.pppoePassword[0].score >= 50) {
            result.pppoePassword = candidates.pppoePassword[0].value;
            console.log('[WiFi Grabber] ✓ PPPoE Password encontrada');
        }
    }

    // ============================================
    // EXECUÇÃO
    // ============================================

    return searchCredentials();

})();
