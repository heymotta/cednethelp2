# WiFi Credential Grabber

## 📶 Extensão Chrome para Captura de Credenciais Wi-Fi

Uma extensão para Google Chrome (Manifest V3) que captura automaticamente credenciais Wi-Fi (SSID e senha) de páginas de configuração de roteadores após login manual.

---

## ⚙️ Funcionalidades

- ✅ Detecta automaticamente se a página é de um roteador (IPs locais)
- ✅ Captura SSID (nome da rede) e senha Wi-Fi
- ✅ Múltiplas estratégias de busca no DOM
- ✅ Histórico de capturas anteriores
- ✅ Botão de copiar para área de transferência
- ✅ Interface moderna e intuitiva
- ✅ Funciona com diversos modelos de roteadores

---

## 📦 Estrutura do Projeto

```
wifi-credential-grabber/
├── manifest.json      # Configuração da extensão (Manifest V3)
├── popup.html         # Interface do popup
├── popup.js           # Lógica do popup
├── content.js         # Script de extração de credenciais
├── style.css          # Estilos da interface
├── icons/             # Ícones da extensão
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── README.md          # Este arquivo
```

---

## 🚀 Como Instalar no Chrome

### Passo 1: Abrir o Gerenciador de Extensões
1. Abra o Google Chrome
2. Digite na barra de endereços: `chrome://extensions/`
3. Pressione **Enter**

### Passo 2: Ativar o Modo Desenvolvedor
1. No canto superior direito da página, localize o toggle **"Modo do desenvolvedor"**
2. Clique para ativar (deve ficar azul)

### Passo 3: Carregar a Extensão
1. Clique no botão **"Carregar sem compactação"** que apareceu
2. Navegue até a pasta `wifi-credential-grabber`
3. Selecione a pasta e clique em **"Selecionar pasta"**

### Passo 4: Verificar Instalação
- A extensão deve aparecer na lista com o ícone 📶
- Você pode clicar no ícone da extensão na barra de ferramentas para abrir o popup

---

## 📖 Como Usar

1. **Acesse a página do seu roteador** (ex: `http://192.168.0.1` ou `http://192.168.1.1`)
2. **Faça login manualmente** com suas credenciais de administrador
3. **Navegue até a página de configurações Wi-Fi** onde o SSID e a senha estão visíveis
4. **Clique no ícone da extensão** na barra de ferramentas do Chrome
5. **Clique no botão "Capturar Credenciais"**
6. Se encontrar os dados, eles serão exibidos e salvos no histórico

---

## ⚠️ Limitações Conhecidas

### 1. Senhas Ocultas
A extensão **só consegue capturar senhas que estão visíveis no HTML**. Se o campo de senha estiver mascarado (com asteriscos) e o valor real não estiver no DOM, não será possível capturar.

**Solução:** Muitos roteadores têm um botão "Mostrar senha" ou "👁️" - clique nele antes de usar a extensão.

### 2. Interfaces Dinâmicas (JavaScript/Ajax)
Alguns roteadores modernos carregam o conteúdo dinamicamente. Se o campo não estiver presente no DOM quando a extensão executar, não será capturado.

**Solução:** Aguarde o carregamento completo da página antes de usar a extensão.

### 3. iFrames com Origens Diferentes
Por segurança, navegadores não permitem acesso a iframes de origens diferentes. Se o roteador usar iframes de outros domínios, o conteúdo interno não será acessível.

### 4. Interfaces Não Padronizadas
Cada fabricante de roteador usa nomes diferentes para os campos. A extensão tenta cobrir os padrões mais comuns, mas pode não funcionar com interfaces muito customizadas.

**Solução:** Abra o console do desenvolvedor (F12) para ver quais campos foram encontrados.

### 5. HTTPS com Certificados Inválidos
Alguns roteadores usam HTTPS com certificados autoassinados. O Chrome pode bloquear o acesso.

**Solução:** Aceite o certificado manualmente antes de usar a extensão.

### 6. Páginas Protegidas por Frame
Algumas interfaces usam proteção contra frames (`X-Frame-Options`). A extensão não consegue contornar essas proteções.

---

## 🔧 Debug e Troubleshooting

### Ver Logs no Console
1. Clique com o botão direito no ícone da extensão
2. Selecione **"Inspecionar popup"**
3. Vá para a aba **Console**
4. Execute a captura e veja os logs detalhados

### Logs do Content Script
1. Abra o DevTools da página do roteador (F12)
2. Vá para a aba **Console**
3. Procure por mensagens iniciando com `[WiFi Grabber]`

---

## 🛡️ Segurança e Privacidade

- **Uso Local:** Todos os dados são armazenados localmente no navegador usando `chrome.storage.local`
- **Sem Rede:** A extensão não envia dados para nenhum servidor externo
- **Permissões Mínimas:** Usa apenas as permissões necessárias (`activeTab`, `scripting`, `storage`)
- **Uso Pessoal:** Esta extensão é destinada apenas para uso pessoal em redes que você administra

---

## 📋 Permissões Necessárias

| Permissão | Motivo |
|-----------|--------|
| `activeTab` | Acessar a aba atual quando o usuário clica na extensão |
| `scripting` | Injetar o content script para analisar o DOM |
| `storage` | Salvar histórico de credenciais localmente |
| `host_permissions` | Acessar páginas em IPs de rede local (192.168.*, 10.*, 172.16-31.*) |

---

## 🧪 Roteadores Testados

A extensão foi projetada para funcionar com interfaces comuns de:
- TP-Link
- D-Link
- Intelbras
- Multilaser
- Huawei
- ZTE
- E outros roteadores com interfaces web padrão

---

## 📝 Changelog

### v1.0.0
- Versão inicial
- Suporte a Manifest V3
- Múltiplas estratégias de detecção
- Interface moderna com tema escuro
- Histórico de capturas

---

## 📄 Licença

Esta extensão é fornecida "como está" para uso pessoal. Use apenas em redes que você tem autorização para administrar.
