"""
CedNet Help - Script de Automação de Publicação de Versões (publish.py)

Automatiza 100% do processo de lançamento de novas versões:
  1. Atualiza a versão em modules/utils.py e version.json
  2. Compila CedNet_Help.exe e CedNet_Updater.exe
  3. Gera o arquivo CedNet_Help.zip e calcula o SHA-256
  4. Realiza commit e push para o repositório GitHub
  5. Cria a Release no GitHub e envia o ZIP automaticamente (se token configurado)
     ou abre a página de upload no navegador.

Uso:
  python publish.py 1.0.2 "Mensagem do changelog"
  python publish.py
"""

import sys
import os
import re
import json
import shutil
import hashlib
import subprocess
import urllib.request
import urllib.error
import ssl
import time
import webbrowser
from typing import Optional

# Configurações do Repositório
GITHUB_OWNER = "heymotta"
GITHUB_REPO = "cednethelp2"
APP_DIR = os.path.dirname(os.path.abspath(__file__))


def write_step(step_num: int, title: str):
    """Exibe título estilizado para a etapa."""
    print(f"\n=======================================================")
    print(f"  [{step_num}/6] {title}")
    print(f"=======================================================")


def run_cmd(cmd: str, cwd: str = APP_DIR, check: bool = True) -> subprocess.CompletedProcess:
    """Executa um comando no shell de forma limpa."""
    print(f" Executando: {cmd}")
    res = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"❌ ERRO ao executar comando:\n{res.stderr or res.stdout}")
        sys.exit(1)
    return res


def get_github_token() -> Optional[str]:
    """Tenta obter o token do GitHub a partir do ambiente ou arquivos locais."""
    # 1. Variável de ambiente
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()

    # 2. Arquivos locais (.env, token.txt, data/github_token.txt)
    candidate_paths = [
        os.path.join(APP_DIR, ".env"),
        os.path.join(APP_DIR, "token.txt"),
        os.path.join(APP_DIR, "data", "github_token.txt"),
    ]

    for path in candidate_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    match = re.search(r"(?:GITHUB_TOKEN=)?(ghp_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)", content)
                    if match:
                        return match.group(1).strip()
            except Exception:
                pass

    return None


def update_utils_py(version: str):
    """Atualiza APP_VERSION em modules/utils.py."""
    utils_path = os.path.join(APP_DIR, "modules", "utils.py")
    if not os.path.exists(utils_path):
        print(f"❌ Arquivo não encontrado: {utils_path}")
        sys.exit(1)

    with open(utils_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = re.sub(r'APP_VERSION = "[^"]+"', f'APP_VERSION = "{version}"', content)

    with open(utils_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"  ✓ modules/utils.py atualizado para APP_VERSION = '{version}'")


def update_version_json(version: str, changelog: list[str], sha256_hash: str = ""):
    """Atualiza o manifesto version.json."""
    vjson_path = os.path.join(APP_DIR, "version.json")
    
    data = {
        "version": version,
        "minimum_version": "1.0.0",
        "download_url": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/v{version}/CedNet_Help.zip",
        "changelog": changelog,
        "sha256": sha256_hash,
    }

    with open(vjson_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"  ✓ version.json atualizado para a versão '{version}'")


def build_executables():
    """Compila CedNet Help e CedNet Updater via PyInstaller."""
    # Encerra instâncias em execução que possam travar arquivos
    try:
        subprocess.run('taskkill /F /IM "CedNet_Help.exe"', shell=True, capture_output=True)
        subprocess.run('taskkill /F /IM "CedNet_Updater.exe"', shell=True, capture_output=True)
    except Exception:
        pass

    # 1. Compila CedNet Help
    print("\n  [1/2] Compilando CedNet Help.exe...")
    run_cmd('python -m PyInstaller --noconfirm --onedir --windowed --uac-admin --name "CedNet_Help" --collect-all customtkinter main.py')

    # 2. Compila CedNet Updater
    print("\n  [2/2] Compilando CedNet Updater.exe...")
    updater_dir = os.path.join(APP_DIR, "updater")
    run_cmd('python -m PyInstaller --noconfirm --onedir --windowed --name "CedNet_Updater" --collect-all customtkinter updater_main.py', cwd=updater_dir)

    # 3. Copia Updater para a pasta dist do CedNet Help
    src_updater = os.path.join(updater_dir, "dist", "CedNet_Updater")
    dst_updater = os.path.join(APP_DIR, "dist", "CedNet_Help", "CedNet_Updater")
    
    if os.path.exists(dst_updater):
        shutil.rmtree(dst_updater, ignore_errors=True)
    shutil.copytree(src_updater, dst_updater)

    # 4. Copia version.json para a pasta dist
    shutil.copy2(os.path.join(APP_DIR, "version.json"), os.path.join(APP_DIR, "dist", "CedNet_Help", "version.json"))

    print("  ✓ Compilação de ambos os executáveis concluída!")


def create_zip_and_hash() -> str:
    """Compacta dist/CedNet_Help em CedNet_Help.zip e retorna o hash SHA-256."""
    dist_dir = os.path.join(APP_DIR, "dist", "CedNet_Help")
    zip_path = os.path.join(APP_DIR, "dist", "CedNet_Help.zip")

    if os.path.exists(zip_path):
        os.remove(zip_path)

    print("  Compactando arquivos...")
    shutil.make_archive(os.path.join(APP_DIR, "dist", "CedNet_Help"), "zip", dist_dir)

    # Calcula SHA-256
    sha256 = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    hash_hex = sha256.hexdigest()

    print(f"  ✓ CedNet_Help.zip gerado!")
    print(f"  ✓ SHA-256: {hash_hex}")
    return hash_hex


def create_github_release_api(token: str, version: str, changelog: list[str], zip_path: str) -> bool:
    """Cria a Release no GitHub e envia o CedNet_Help.zip via REST API."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    tag_name = f"v{version}"
    release_name = f"CedNet Help v{version}"
    body_text = "### Novidades desta versão:\n\n" + "\n".join([f"- {item}" for item in changelog])

    # 1. Cria a Release
    url_create = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "CedNet-Help-Publisher/1.0",
        "Content-Type": "application/json",
    }

    payload = {
        "tag_name": tag_name,
        "target_commitish": "main",
        "name": release_name,
        "body": body_text,
        "draft": False,
        "prerelease": False,
    }

    try:
        req = urllib.request.Request(url_create, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, context=ctx) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            upload_url_template = res_data.get("upload_url", "")
            release_id = res_data.get("id")

        print(f"  ✓ Release {tag_name} criada com sucesso no GitHub! (ID: {release_id})")

        # 2. Faz o upload do arquivo ZIP
        upload_url = upload_url_template.split("{")[0] + "?name=CedNet_Help.zip"
        
        with open(zip_path, "rb") as f:
            zip_bytes = f.read()

        upload_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "CedNet-Help-Publisher/1.0",
            "Content-Type": "application/zip",
        }

        print("  Enviando CedNet_Help.zip para os servidores do GitHub...")
        req_upload = urllib.request.Request(upload_url, data=zip_bytes, headers=upload_headers)
        with urllib.request.urlopen(req_upload, context=ctx) as resp_up:
            print("  ✓ Arquivo CedNet_Help.zip anexado com sucesso na Release!")

        return True

    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        print(f"❌ Erro na API do GitHub ({e.code}): {err_body}")
        return False
    except Exception as e:
        print(f"❌ Erro ao criar Release via API: {str(e)}")
        return False


def main():
    print("=======================================================")
    print("      CedNet Help - Automação de Publicação")
    print("=======================================================")

    # Captura parâmetros via CLI ou prompt
    if len(sys.argv) >= 2:
        new_version = sys.argv[1].strip()
    else:
        new_version = input("Digite a nova versão (ex: 1.0.2): ").strip()

    if not re.match(r"^\d+\.\d+\.\d+$", new_version):
        print("❌ Versão inválida! Use o formato numérico semântico (ex: 1.0.2)")
        sys.exit(1)

    if len(sys.argv) >= 3:
        changelog_raw = sys.argv[2].strip()
    else:
        changelog_raw = input("Digite as novidades/changelog (separadas por vírgula ou ponto): ").strip()

    changelog = [item.strip() for item in re.split(r"[,;.]", changelog_raw) if item.strip()]
    if not changelog:
        changelog = [f"Atualizações e melhorias gerais na versão v{new_version}"]

    print(f"\n🚀 Iniciando publicação da versão v{new_version}...")
    print(f"📋 Changelog: {changelog}")

    # ETAPA 1: Atualiza versão nos arquivos fonte
    write_step(1, "Atualizando código-fonte e manifesto de versão")
    update_utils_py(new_version)
    update_version_json(new_version, changelog)

    # ETAPA 2: Compilação dos Executáveis
    write_step(2, "Compilando CedNet Help e CedNet Updater")
    build_executables()

    # ETAPA 3: Empacotamento ZIP e cálculo SHA-256
    write_step(3, "Gerando pacote ZIP e calculando hash SHA-256")
    zip_path = os.path.join(APP_DIR, "dist", "CedNet_Help.zip")
    sha256_hash = create_zip_and_hash()
    
    # Atualiza version.json definitivo com a hash SHA-256
    update_version_json(new_version, changelog, sha256_hash)
    shutil.copy2(os.path.join(APP_DIR, "version.json"), os.path.join(APP_DIR, "dist", "CedNet_Help", "version.json"))

    # ETAPA 4: Git Commit & Push
    write_step(4, "Enviando código e versão para o repositório GitHub")
    run_cmd("git add -A")
    run_cmd(f'git commit -m "release: v{new_version}"')
    run_cmd("git push origin main")
    print("  ✓ Commit e Push concluídos!")

    # ETAPA 5: Publicação da Release no GitHub
    write_step(5, "Publicando Release no GitHub")
    token = get_github_token()

    if token:
        print("  🔑 Token do GitHub encontrado. Publicando automaticamente via API...")
        success = create_github_release_api(token, new_version, changelog, zip_path)
        if success:
            write_step(6, "CONCLUÍDO COM SUCESSO!")
            print(f"🎉 Versão v{new_version} foi compilada, enviada e publicada!")
            print(f"📢 Todos os técnicos receberão o aviso de atualização automaticamente ao abrir o app.")
            return

    # Se não houver token ou se a API falhar, abre no navegador pré-preenchido
    print("\n  ℹ️ Nenhum Token de Acesso Pessoal (GITHUB_TOKEN) foi detectado.")
    print("  Abrindo o navegador para envio rápido de 1 clique...")

    release_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/new?tag=v{new_version}&title=CedNet%20Help%20v{new_version}"
    webbrowser.open(release_url)

    write_step(6, "QUASE PRONTO!")
    print(f"  1. A página do GitHub Releases foi aberta no seu navegador.")
    print(f"  2. Arraste o arquivo: dist\\CedNet_Help.zip para a página.")
    print(f"  3. Clique em 'Publish release'.")
    print("\n💡 DICA: Para automatizar essa última etapa no futuro, salve seu GitHub Token no arquivo 'token.txt'!")


if __name__ == "__main__":
    main()
