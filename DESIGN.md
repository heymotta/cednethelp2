# CedNet Help - Especificação de Design (DESIGN.md)

Este documento define as diretrizes visuais, paleta semântica de cores, escalas tipográficas e regras de acessibilidade da aplicação desktop **CedNet Help**.

---

## 1. Identidade e Propósito
O **CedNet Help** é um utilitário técnico corporativo para diagnóstico e suporte de redes locais e equipamentos de telecomunicações.
O design deve priorizar:
- **Clareza técnica**: Dados de rede (IP, MAC, RSSI, Latência) devem ser imediatamente escaneáveis.
- **Sobriedade**: Sem decorações excessivas, gradientes purpúreos genéricos ou emojis redundantes.
- **Acessibilidade WCAG AA**: Alto contraste entre texto e plano de fundo (mínimo de 4.5:1 para texto normal e 3.0:1 para elementos de destaque).

---

## 2. Paleta de Cores

Todas as cores são centralizadas em `modules/utils.py` no dicionário `COLORS`.

| Token | Hex | Contraste (Fundo Escuro) | Uso |
| :--- | :--- | :--- | :--- |
| `bg_main` | `#1a1a2e` | - | Fundo principal da janela |
| `bg_sidebar` | `#16213e` | - | Barra lateral de navegação |
| `bg_card` | `#0f3460` | - | Cartões de conteúdo e blocos agrupados |
| `bg_card_alt` | `#132a4a` | - | Cartões alternados e linhas zebradas |
| `entry_bg` | `#0d2137` | - | Campos de entrada e caixas de busca |
| `border` | `#1e3a5f` | - | Divisores e bordas estruturais |
| `text_primary` | `#ffffff` | 17.06:1 | Títulos, cabeçalhos e texto com ênfase |
| `text_secondary` | `#94a3b8` | 4.87:1 | Rótulos, metadados e legendas |
| `accent` | `#1a73e8` | 4.51:1 (c/ texto branco) | Botões de ação primária |
| `accent_hover` | `#2196f3` | - | Estado hover de botões primários |
| `accent_cyan` | `#00bcd4` | 5.44:1 | Destaque numérico de métricas e valores |
| `status_ok` | `#4ade80` | 7.17:1 | Texto de status operacional positivo |
| `status_error` | `#f87171` | 4.52:1 | Texto de status com falha ou erro |
| `status_warning` | `#ff9800` | 5.80:1 | Texto de alertas ou advertências |
| `btn_success` | `#15803d` | 5.02:1 (c/ texto branco) | Botões de confirmação / atualização |
| `bg_error_banner` | `#3d1a1a` | - | Fundo do banner de erro ou permissão |
| `text_error_banner` | `#fca5a5` | 8.13:1 (no banner de erro) | Texto legível sobre o banner de erro |

---

## 3. Tipografia

Definida em `modules/utils.py` através da constante `FONTS`:
- **Interface Geral**: `Segoe UI` (fonte padrão nativa do Windows).
- **Dados Técnicos**: `Consolas` (monoespaçada para IPs, endereços MAC e latências).

| Token | Família | Tamanho | Peso | Aplicação |
| :--- | :--- | :--- | :--- | :--- |
| `title` | Segoe UI | 22 | Bold | Título principal da página |
| `subtitle` | Segoe UI | 16 | Bold | Títulos de cards e seções |
| `heading` | Segoe UI | 14 | Bold | Cabeçalhos de tabelas e grupos |
| `body` | Segoe UI | 13 | Regular | Texto padrão de interface |
| `body_bold` | Segoe UI | 13 | Bold | Texto de botões e destaques |
| `small` | Segoe UI | 11 | Regular | Legendas e mensagens de apoio |
| `mono` | Consolas | 13 | Regular | Endereços IP, máscaras e MAC |
| `mono_large` | Consolas | 15 | Bold | Valores de métricas principais |

---

## 4. Regras de Layout e Responsividade
- **Largura Mínima**: `900x600`.
- **Área Útil de Conteúdo**: O layout deve respeitar larguras mínimas sem cortar campos de busca ou truncar botões de ação rápida. Barras de ferramentas que excedam `500px` devem empilhar ou quebrar responsivamente.
- **Navegação por Teclado**: Todas as janelas modais (`CTkToplevel`) devem fechar com `Escape` e suportar confirmação por `Enter`.

