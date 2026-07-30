"""
CedNet Help - Módulo de Análise de Canais Wi-Fi
Coleta redes sem fio via Windows netsh wlan, analisa ocupação do espectro
e calcula automaticamente o melhor canal para 2.4 GHz e 5 GHz.

Funcionalidades:
  - Varredura de redes próximas (SSID, BSSID, Sinal, Canal, Frequência, Segurança)
  - Cálculo de RSSI em dBm (convertido de % de sinal)
  - Análise de interferência co-canal e sobreposição de canais adjacentes
  - Algoritmo de recomendação inteligente para 2.4 GHz (foco em 1, 3, 6, 11) e 5 GHz (36, 40, 44, 149, etc.)
  - Suporte a ambientes PT-BR e EN-US no Windows
"""

import subprocess
import re
import math
from typing import Optional


# Flag para ocultar janela do subprocesso
_NO_WINDOW = subprocess.CREATE_NO_WINDOW


class WiFiScanner:
    """Gerenciador de varredura e análise de canais Wi-Fi."""

    # ================================================================
    # Varredura Principal de Redes Wi-Fi
    # ================================================================

    @staticmethod
    def scan_networks() -> tuple[bool, str, list[dict]]:
        """
        Executa a varredura de redes Wi-Fi usando 'netsh wlan show networks mode=bssid'.

        Returns:
            Tupla (sucesso: bool, mensagem: str, lista_de_redes: list[dict])
        """
        try:
            output = subprocess.check_output(
                "netsh wlan show networks mode=bssid",
                encoding="cp850",
                errors="replace",
                creationflags=_NO_WINDOW,
                timeout=5.0,
            )

            networks = WiFiScanner._parse_netsh_output(output)
            if not networks:
                return True, "Nenhuma rede Wi-Fi encontrada ao alcance.", []

            return True, f"{len(networks)} BSSIDs de rede encontrados.", networks

        except subprocess.TimeoutExpired:
            return False, "Tempo de espera da busca Wi-Fi esgotado.", []
        except subprocess.CalledProcessError as e:
            return False, (
                "Serviço Wi-Fi (wlansvc) desativado ou adaptador Wi-Fi não encontrado.\n"
                "Verifique se a placa de rede sem fio está habilitada no Windows."
            ), []
        except Exception as e:
            return False, f"Erro ao acessar adaptador Wi-Fi: {str(e)}", []

    # ================================================================
    # Parser Bilíngue (PT-BR e EN-US)
    # ================================================================

    @staticmethod
    def _parse_netsh_output(output: str) -> list[dict]:
        """
        Analisa a saída textual do netsh wlan e extrai redes com BSSIDs.
        """
        networks = []
        current_ssid = ""
        current_auth = "WPA2"
        current_type = "Infraestrutura"

        lines = output.splitlines()

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # SSID
            ssid_match = re.match(r"^SSID\s+\d+\s*:\s*(.*)$", line_str, re.IGNORECASE)
            if ssid_match:
                current_ssid = ssid_match.group(1).strip()
                if not current_ssid:
                    current_ssid = "(Rede Oculta)"
                continue

            # Autenticação (Segurança)
            auth_match = re.match(r"^(?:Autenticação|Authentication)\s*:\s*(.*)$", line_str, re.IGNORECASE)
            if auth_match:
                current_auth = auth_match.group(1).strip()
                continue

            # BSSID (Endereço MAC da AP)
            bssid_match = re.match(r"^BSSID\s+\d+\s*:\s*([0-9a-fA-F:-]{17})$", line_str, re.IGNORECASE)
            if bssid_match:
                bssid_mac = bssid_match.group(1).upper().replace("-", ":")
                # Inicializa registro de BSSID
                networks.append({
                    "ssid": current_ssid,
                    "bssid": bssid_mac,
                    "security": current_auth,
                    "signal_pct": 50,
                    "rssi_dbm": -75,
                    "channel": 1,
                    "band": "2.4 GHz",
                    "frequency_mhz": 2412,
                    "radio_type": "802.11n",
                })
                continue

            # Dados do BSSID atual
            if networks:
                last_net = networks[-1]

                # Sinal em %
                sig_match = re.match(r"^(?:Sinal|Signal)\s*:\s*(\d+)%", line_str, re.IGNORECASE)
                if sig_match:
                    pct = int(sig_match.group(1))
                    last_net["signal_pct"] = pct
                    # Conversão % para RSSI em dBm: (pct / 2) - 100
                    last_net["rssi_dbm"] = int(pct / 2 - 100)
                    continue

                # Canal
                ch_match = re.match(r"^(?:Canal|Channel)\s*:\s*(\d+)$", line_str, re.IGNORECASE)
                if ch_match:
                    ch = int(ch_match.group(1))
                    last_net["channel"] = ch

                    # Determina a Banda e Frequência aproximada
                    if ch <= 14:
                        last_net["band"] = "2.4 GHz"
                        last_net["frequency_mhz"] = 2484 if ch == 14 else (2412 + 5 * (ch - 1))
                    else:
                        last_net["band"] = "5 GHz"
                        last_net["frequency_mhz"] = 5000 + 5 * ch
                    continue

                # Tipo de rádio
                radio_match = re.match(r"^(?:Tipo de rádio|Radio type)\s*:\s*(.*)$", line_str, re.IGNORECASE)
                if radio_match:
                    last_net["radio_type"] = radio_match.group(1).strip()
                    continue

        return networks

    # ================================================================
    # Análise de Espectro e Ocupação dos Canais
    # ================================================================

    @staticmethod
    def analyze_spectrum(networks: list[dict]) -> dict:
        """
        Analisa a ocupação dos canais para 2.4 GHz e 5 GHz.

        Returns:
            Dict com estatísticas por canal e recomendações.
        """
        # Agrupa redes por banda e por canal
        channels_24: dict[int, list[dict]] = {ch: [] for ch in range(1, 14)}
        channels_5g: dict[int, list[dict]] = {}

        # Preenche canais 5GHz comuns
        for ch in [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]:
            channels_5g[ch] = []

        for net in networks:
            ch = net["channel"]
            band = net["band"]

            if band == "2.4 GHz" and ch in channels_24:
                channels_24[ch].append(net)
            elif band == "5 GHz":
                if ch not in channels_5g:
                    channels_5g[ch] = []
                channels_5g[ch].append(net)

        # Gera recomendações inteligentes
        rec_24 = WiFiScanner._recommend_24ghz(channels_24)
        rec_5g = WiFiScanner._recommend_5ghz(channels_5g)

        return {
            "channels_24": channels_24,
            "channels_5g": channels_5g,
            "recommendation_24": rec_24,
            "recommendation_5g": rec_5g,
        }

    # ================================================================
    # Algoritmo de Recomendação Inteligente (2.4 GHz)
    # ================================================================

    @staticmethod
    def _recommend_24ghz(channels: dict[int, list[dict]]) -> dict:
        """
        Calcula o melhor canal para 2.4 GHz considerando:
          1. Pontuação de interferência (co-canal e sobreposição adjacente ±2)
          2. Priorização técnica dos canais 1, 3, 6, 11
        """
        scores: dict[int, float] = {}

        for ch in range(1, 14):
            score = 0.0

            # 1. Co-canal (redes no mesmo canal)
            for net in channels.get(ch, []):
                rssi = net["rssi_dbm"]
                # Converte RSSI para peso linear de potência (10^(RSSI/10))
                power = math.pow(10, (rssi + 100) / 10)
                score += power * 2.0

            # 2. Sobreposição de canais adjacentes (±1 e ±2)
            for adj in (ch - 2, ch - 1, ch + 1, ch + 2):
                if 1 <= adj <= 13:
                    for net in channels.get(adj, []):
                        rssi = net["rssi_dbm"]
                        dist = abs(ch - adj)
                        power = math.pow(10, (rssi + 100) / 10)
                        penalty = (1.5 / dist)
                        score += power * penalty

            # Prioriza levemente os canais padrão sugeridos (1, 3, 6)
            if ch in (1, 3, 6):
                score *= 0.85

            scores[ch] = score

        # Escolhe o canal com MENOR pontuação de interferência
        # Prioriza 1, 3, 6 se empatados ou próximos
        candidates = sorted(scores.keys(), key=lambda c: (scores[c], 0 if c in (1, 3, 6) else 1))
        best_ch = candidates[0]

        nets_on_best = len(channels.get(best_ch, []))
        reasons = []

        if nets_on_best == 0:
            reasons.append("• Canal totalmente livre (0 redes detectadas).")
        else:
            reasons.append(f"• Apenas {nets_on_best} rede(s) utilizando este canal.")

        reasons.append("• Menor nível de interferência e sobreposição no espectro 2.4 GHz.")
        if best_ch in (1, 3, 6):
            reasons.append("• Canal recomendado para melhor compatibilidade de equipamentos.")

        return {
            "best_channel": best_ch,
            "reasons": reasons,
            "score": round(scores[best_ch], 2),
            "nets_count": nets_on_best,
        }

    # ================================================================
    # Algoritmo de Recomendação Inteligente (5 GHz)
    # ================================================================

    @staticmethod
    def _recommend_5ghz(channels: dict[int, list[dict]]) -> dict:
        """
        Calcula o melhor canal para 5 GHz (foco em 36, 40, 44, 149, 153, 157, 161).
        """
        preferred_5g = [36, 40, 44, 48, 149, 153, 157, 161]
        all_channels = sorted(channels.keys())

        # Pontua cada canal 5 GHz
        scores: dict[int, float] = {}
        for ch in all_channels:
            nets = channels.get(ch, [])
            score = 0.0
            for net in nets:
                power = math.pow(10, (net["rssi_dbm"] + 100) / 10)
                score += power

            # Favorece os canais preferenciais não-DFS
            if ch in preferred_5g:
                score *= 0.7

            scores[ch] = score

        if not scores:
            best_ch = 36
        else:
            candidates = sorted(scores.keys(), key=lambda c: (scores[c], 0 if c in preferred_5g else 1))
            best_ch = candidates[0]

        nets_on_best = len(channels.get(best_ch, []))
        reasons = []

        if nets_on_best == 0:
            reasons.append("• Nenhuma rede detectada neste canal 5 GHz.")
            reasons.append("• Canal completamente livre e sem interferência.")
        else:
            reasons.append(f"• Apenas {nets_on_best} rede(s) utilizando este canal.")
            reasons.append("• Baixa ocupação no espectro 5 GHz.")

        if best_ch in preferred_5g:
            reasons.append("• Canal de alta velocidade recomendado (não-DFS).")

        return {
            "best_channel": best_ch,
            "reasons": reasons,
            "score": round(scores.get(best_ch, 0.0), 2),
            "nets_count": nets_on_best,
        }
