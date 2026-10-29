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
    # Diagnóstico de Adaptador Wi-Fi
    # ================================================================

    @staticmethod
    def check_adapter_status() -> tuple[bool, str]:
        """
        Verifica o estado do serviço Wi-Fi (wlansvc) e da interface de rede sem fio.

        Returns:
            Tupla (disponível: bool, mensagem_diagnostico: str)
        """
        try:
            output = subprocess.check_output(
                "netsh wlan show interfaces",
                encoding="cp850",
                errors="replace",
                creationflags=_NO_WINDOW,
                timeout=4.0,
            )

            if not isinstance(output, str):
                output = output.decode("cp850", errors="replace")

            output_lower = output.lower()

            if "serviço de configuração automática sem fio" in output_lower or "wlansvc" in output_lower:
                if "não está em execução" in output_lower or "is not running" in output_lower:
                    return False, "Nenhum adaptador Wi-Fi habilitado foi encontrado."

            if "não há nenhuma interface sem fio" in output_lower or "there is no wireless interface" in output_lower:
                return False, "Nenhum adaptador Wi-Fi habilitado foi encontrado."

            if "não suporta" in output_lower or "not supported" in output_lower:
                return False, "O adaptador de rede não suporta escaneamento de redes Wi-Fi."

            return True, "Adaptador Wi-Fi detectado e pronto."

        except subprocess.CalledProcessError as e:
            return False, "Nenhum adaptador Wi-Fi habilitado foi encontrado."
        except Exception:
            return False, "Nenhum adaptador Wi-Fi habilitado foi encontrado."

    @staticmethod
    def get_connected_wifi_info() -> tuple[bool, str, Optional[dict]]:
        """
        Obtém os detalhes da rede Wi-Fi atualmente conectada e sua respectiva senha.

        Returns:
            Tupla (sucesso: bool, mensagem: str, dados: Optional[dict])
        """
        try:
            res = subprocess.run(
                "netsh wlan show interfaces",
                capture_output=True,
                text=True,
                encoding="cp850",
                errors="replace",
                creationflags=_NO_WINDOW,
                timeout=5.0,
            )
            output = res.stdout or ""
            output_lower = output.lower()

            if "serviço de configuração automática" in output_lower or "wlansvc" in output_lower:
                if "não está em execução" in output_lower or "is not running" in output_lower:
                    return False, "O serviço de Wi-Fi do Windows (wlansvc) está desativado.", None

            if "não há nenhuma interface" in output_lower or "there is no wireless" in output_lower:
                return False, "Nenhum adaptador Wi-Fi foi encontrado neste computador.", None

            state_match = re.search(r"(?:Estado|State)\s*:\s*([^\r\n]+)", output, re.IGNORECASE)
            state_val = state_match.group(1).strip().lower() if state_match else ""
            if "conectado" not in state_val and "connected" not in state_val:
                return False, "O computador não está conectado a nenhuma rede Wi-Fi no momento.", None

            ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", output, re.MULTILINE | re.IGNORECASE)
            if not ssid_match:
                return False, "Não foi possível identificar o nome (SSID) da rede conectada.", None

            ssid = ssid_match.group(1).strip()

            bssid_match = re.search(r"^\s*BSSID\s*:\s*([^\r\n]+)", output, re.MULTILINE | re.IGNORECASE)
            bssid = bssid_match.group(1).strip() if bssid_match else "Não disponível"

            signal_match = re.search(r"^\s*(?:Sinal|Signal)\s*:\s*([^\r\n]+)", output, re.MULTILINE | re.IGNORECASE)
            signal = signal_match.group(1).strip() if signal_match else "Não disponível"

            channel_match = re.search(r"^\s*(?:Canal|Channel)\s*:\s*([^\r\n]+)", output, re.MULTILINE | re.IGNORECASE)
            channel = channel_match.group(1).strip() if channel_match else "Não disponível"

            auth_match = re.search(r"^\s*(?:Autentica[çc][ãa]o|Authentication)\s*:\s*([^\r\n]+)", output, re.MULTILINE | re.IGNORECASE)
            auth = auth_match.group(1).strip() if auth_match else "WPA2-Personal"

            # Consulta o perfil com chave em texto claro
            pw_res = subprocess.run(
                f'netsh wlan show profile name="{ssid}" key=clear',
                capture_output=True,
                text=True,
                encoding="cp850",
                errors="replace",
                creationflags=_NO_WINDOW,
                timeout=5.0,
            )
            pw_output = pw_res.stdout or ""

            key_match = re.search(r"(?:Conte[úu]do da Chave|Key Content)\s*:\s*([^\r\n]+)", pw_output, re.IGNORECASE)
            if key_match:
                password = key_match.group(1).strip()
            else:
                if "abert" in auth.lower() or "open" in auth.lower():
                    password = "(Rede aberta - Sem senha)"
                else:
                    password = "(Senha não armazenada ou sem permissão)"

            data = {
                "ssid": ssid,
                "password": password,
                "bssid": bssid,
                "signal": signal,
                "channel": channel,
                "auth": auth,
            }
            return True, "Informações obtidas com sucesso.", data

        except Exception as e:
            return False, f"Falha ao consultar Wi-Fi: {str(e)}", None

    @staticmethod
    def scan_networks(cancel_checker=None) -> tuple[bool, str, list[dict]]:
        """
        Executa a varredura de redes Wi-Fi usando 'netsh wlan show networks mode=bssid'.

        Returns:
            Tupla (sucesso: bool, mensagem: str, lista_de_redes: list[dict])
        """
        # 1. Checa status do adaptador Wi-Fi antes de tentar o scan
        adapter_ok, adapter_msg = WiFiScanner.check_adapter_status()
        if not adapter_ok:
            return False, adapter_msg, []

        if cancel_checker and cancel_checker():
            return False, "Varredura Wi-Fi cancelada pelo usuário.", []

        # 2. Executa comando netsh de varredura
        try:
            output = subprocess.check_output(
                "netsh wlan show networks mode=bssid",
                encoding="cp850",
                errors="replace",
                creationflags=_NO_WINDOW,
                timeout=6.0,
            )

            if cancel_checker and cancel_checker():
                return False, "Varredura Wi-Fi cancelada pelo usuário.", []

            if not isinstance(output, str):
                output = output.decode("cp850", errors="replace")

            networks = WiFiScanner._parse_netsh_output(output)
            if not networks:
                return True, "Nenhuma rede Wi-Fi foi encontrada.", []

            return True, f"{len(networks)} BSSIDs de rede encontrados.", networks

        except subprocess.TimeoutExpired:
            return False, "Tempo de espera da busca Wi-Fi esgotado.", []
        except subprocess.CalledProcessError:
            return False, "Nenhum adaptador Wi-Fi habilitado foi encontrado.", []
        except Exception as e:
            return False, f"Erro ao acessar adaptador Wi-Fi: {str(e)}", []

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
        Calcula o melhor canal para 2.4 GHz considerando todo o espectro (1 a 13),
        porém restringindo a RECOMENDAÇÃO FINAL estritamente aos canais 1 a 6.
        """
        allowed_24ghz = [1, 2, 3, 4, 5, 6]
        scores: dict[int, float] = {}

        for ch in range(1, 14):
            score = 0.0

            # 1. Co-canal (redes no mesmo canal)
            for net in channels.get(ch, []):
                rssi = net.get("rssi_dbm", -75)
                power = math.pow(10, (rssi + 100) / 10)
                score += power * 2.0

            # 2. Sobreposição de canais adjacentes (±1 e ±2)
            for adj in (ch - 2, ch - 1, ch + 1, ch + 2):
                if 1 <= adj <= 13:
                    for net in channels.get(adj, []):
                        rssi = net.get("rssi_dbm", -75)
                        dist = abs(ch - adj)
                        power = math.pow(10, (rssi + 100) / 10)
                        penalty = (1.5 / dist)
                        score += power * penalty

            scores[ch] = score

        # Filtra e escolhe exclusivamente entre os canais permitidos (1 ao 6)
        best_ch = min(allowed_24ghz, key=lambda c: (scores.get(c, 0.0), len(channels.get(c, []))))

        nets_on_best = len(channels.get(best_ch, []))
        reasons = []

        reasons.append(f"• Canal {best_ch}: Menor interferência entre os canais permitidos (1 ao 6).")
        if nets_on_best == 0:
            reasons.append("• Canal totalmente livre no momento (0 redes detectadas).")
        else:
            reasons.append(f"• Apenas {nets_on_best} rede(s) utilizando este canal diretamente.")

        reasons.append("• Análise considerando sinal (RSSI), redes vizinhas e sobreposição de canais adjacentes.")

        return {
            "best_channel": best_ch,
            "reasons": reasons,
            "score": round(scores.get(best_ch, 0.0), 2),
            "nets_count": nets_on_best,
            "allowed_range": "1 ao 6",
        }

    # ================================================================
    # Algoritmo de Recomendação Inteligente (5 GHz)
    # ================================================================

    @staticmethod
    def _recommend_5ghz(channels: dict[int, list[dict]]) -> dict:
        """
        Calcula o melhor canal para 5 GHz analisando todo o espectro,
        porém restringindo a RECOMENDAÇÃO FINAL estritamente aos canais 36, 40 e 44.
        """
        allowed_5ghz = [36, 40, 44]

        scores: dict[int, float] = {}
        for ch in allowed_5ghz:
            nets = channels.get(ch, [])
            score = 0.0
            for net in nets:
                rssi = net.get("rssi_dbm", -75)
                power = math.pow(10, (rssi + 100) / 10)
                score += power * 2.0

            # Verifica também adjacência próxima se houver
            for adj in (ch - 4, ch + 4):
                for net in channels.get(adj, []):
                    rssi = net.get("rssi_dbm", -75)
                    power = math.pow(10, (rssi + 100) / 10)
                    score += power * 1.0

            scores[ch] = score

        best_ch = min(allowed_5ghz, key=lambda c: (scores.get(c, 0.0), len(channels.get(c, []))))
        nets_on_best = len(channels.get(best_ch, []))
        reasons = []

        reasons.append(f"• Canal {best_ch}: Melhor opção entre 36, 40 e 44.")
        if nets_on_best == 0:
            reasons.append("• Nenhuma rede detectada neste canal de 5 GHz.")
        else:
            reasons.append(f"• Apenas {nets_on_best} rede(s) utilizando este canal.")

        reasons.append("• Faixa recomendada para máxima compatibilidade e menor interferência.")

        return {
            "best_channel": best_ch,
            "reasons": reasons,
            "score": round(scores.get(best_ch, 0.0), 2),
            "nets_count": nets_on_best,
            "allowed_range": "36, 40 e 44",
        }

