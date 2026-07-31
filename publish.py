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
        print(f"[ERRO] Falha ao executar comando:\n{res.stderr or res.stdout}")
        sys.exit(1)
    return res


def get_github_token() -> Optional[str]:
    """Tenta obter o token do GitHub a partir do ambiente ou arquivos locais."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()

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


def update_installer_iss(version: str):
    """Atualiza a versão no arquivo installer.iss."""
    iss_path = os.path.join(APP_DIR, "installer.iss")
    if not os.path.exists(iss_path):
        return

    with open(iss_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = re.sub(r'#define MyAppVersion "[^"]+"', f'#define MyAppVersion "{version}"', content)

    with open(iss_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"  [OK] installer.iss atualizado para a versão '{version}'")


def build_inno_setup():
    """Tenta localizar e executar o compilador do Inno Setup (ISCC.exe)."""
    iss_path = os.path.join(APP_DIR, "installer.iss")
    if not os.path.exists(iss_path):
        return

    possible_paths = [
        "iscc",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    ]

    iscc_cmd = None
    for p in possible_paths:
        if p == "iscc":
            if shutil.which("iscc"):
                iscc_cmd = "iscc"
                break
        elif os.path.exists(p):
            iscc_cmd = f'"{p}"'
            break

    if iscc_cmd:
        print("\n  [+] Compilando Instalador Inno Setup (CedNet_Help_Setup.exe)...")
        run_cmd(f'{iscc_cmd} "{iss_path}"')
        print("  [OK] Instalador CedNet_Help_Setup.exe gerado com sucesso em dist_setup/")
    else:
        print("\n  [i] Inno Setup (ISCC.exe) não foi encontrado no sistema.")
        print("      Para gerar o instalador automático .exe, instale o Inno Setup 6 em seu PC.")


def update_utils_py(version: str):

    """Atualiza APP_VERSION em modules/utils.py."""
    utils_path = os.path.join(APP_DIR, "modules", "utils.py")
    if not os.path.exists(utils_path):
        print(f"[ERRO] Arquivo não encontrado: {utils_path}")
        sys.exit(1)

    with open(utils_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = re.sub(r'APP_VERSION = "[^"]+"', f'APP_VERSION = "{version}"', content)

    with open(utils_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"  [OK] modules/utils.py atualizado para APP_VERSION = '{version}'")


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

    print(f"  [OK] version.json atualizado para a versão '{version}'")


def build_executables():
    """Compila CedNet Help e CedNet Updater via PyInstaller."""
    try:
        subprocess.run('taskkill /F /IM "CedNet_Help.exe"', shell=True, capture_output=True)
        subprocess.run('taskkill /F /IM "CedNet_Updater.exe"', shell=True, capture_output=True)
    except Exception:
        pass

    print("\n  [1/2] Compilando CedNet Help.exe...")
    run_cmd('python -m PyInstaller --noconfirm --onedir --windowed --uac-admin --name "CedNet_Help" --collect-all customtkinter --collect-all dns main.py')


    print("\n  [2/2] Compilando CedNet Updater.exe...")
    updater_dir = os.path.join(APP_DIR, "updater")
    run_cmd('python -m PyInstaller --noconfirm --onedir --windowed --name "CedNet_Updater" --collect-all customtkinter updater_main.py', cwd=updater_dir)

    src_updater = os.path.join(updater_dir, "dist", "CedNet_Updater")
    dst_updater = os.path.join(APP_DIR, "dist", "CedNet_Help", "CedNet_Updater")
    
    if os.path.exists(dst_updater):
        shutil.rmtree(dst_updater, ignore_errors=True)
    shutil.copytree(src_updater, dst_updater)

    # Copia versão e dados de configuração
    shutil.copy2(os.path.join(APP_DIR, "version.json"), os.path.join(APP_DIR, "dist", "CedNet_Help", "version.json"))

    dst_data = os.path.join(APP_DIR, "dist", "CedNet_Help", "data")
    os.makedirs(dst_data, exist_ok=True)
    if os.path.exists(os.path.join(APP_DIR, "data", "dns_providers.json")):
        shutil.copy2(os.path.join(APP_DIR, "data", "dns_providers.json"), os.path.join(dst_data, "dns_providers.json"))

    print("  [OK] Compilação de ambos os executáveis concluída!")



def create_zip_and_hash() -> str:
    """Compacta dist/CedNet_Help em CedNet_Help.zip e retorna o hash SHA-256."""
    dist_dir = os.path.join(APP_DIR, "dist", "CedNet_Help")
    zip_path = os.path.join(APP_DIR, "dist", "CedNet_Help.zip")

    if os.path.exists(zip_path):
        os.remove(zip_path)

    print("  Compactando arquivos...")
    shutil.make_archive(os.path.join(APP_DIR, "dist", "CedNet_Help"), "zip", dist_dir)

    sha256 = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    hash_hex = sha256.hexdigest()

    print("  [OK] CedNet_Help.zip gerado!")
    print(f"  [OK] SHA-256: {hash_hex}")
    return hash_hex


def create_github_release_api(token: str, version: str, changelog: list[str], zip_path: str) -> bool:
    """Cria a Release no GitHub e envia o CedNet_Help.zip via REST API."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    tag_name = f"v{version}"
    release_name = f"CedNet Help v{version}"
    body_text = "### Novidades desta versão:\n\n" + "\n".join([f"- {item}" for item in changelog])

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

        print(f"  [OK] Release {tag_name} criada com sucesso no GitHub! (ID: {release_id})")

    except urllib.error.HTTPError as e:
        if e.code == 422:
            print(f"  [i] Release {tag_name} já existe no GitHub. Atualizando asset da Release existente...")
            url_get_release = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/tags/{tag_name}"
            req_get = urllib.request.Request(url_get_release, headers=headers)
            try:
                with urllib.request.urlopen(req_get, context=ctx) as resp_get:
                    res_data = json.loads(resp_get.read().decode("utf-8"))
                    upload_url_template = res_data.get("upload_url", "")
                    release_id = res_data.get("id")
                    
                    # Remove asset antigo se existir
                    assets = res_data.get("assets", [])
                    for asset in assets:
                        if asset.get("name") == "CedNet_Help.zip":
                            asset_del_url = asset.get("url")
                            req_del = urllib.request.Request(asset_del_url, headers=headers, method="DELETE")
                            try:
                                urllib.request.urlopen(req_del, context=ctx)
                                print("  [OK] Asset antigo CedNet_Help.zip removido da Release.")
                            except Exception:
                                pass
            except Exception as ex:
                print(f"[ERRO] Não foi possível obter Release existente: {str(ex)}")
                return False
        else:
            err_body = e.read().decode("utf-8", errors="ignore")
            print(f"[ERRO] Falha na API do GitHub ({e.code}): {err_body}")
            return False
    except Exception as e:
        print(f"[ERRO] Falha ao criar Release via API: {str(e)}")
        return False

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
    try:
        req_upload = urllib.request.Request(upload_url, data=zip_bytes, headers=upload_headers)
        with urllib.request.urlopen(req_upload, context=ctx) as resp_up:
            print("  [OK] Arquivo CedNet_Help.zip anexado com sucesso na Release!")

        return True
    except Exception as e:
        print(f"[ERRO] Falha no upload do arquivo ZIP: {str(e)}")
        return False



def main():
    print("=======================================================")
    print("      CedNet Help - Automacao de Publicacao")
    print("=======================================================")

    if len(sys.argv) >= 2:
        new_version = sys.argv[1].strip()
    else:
        new_version = input("Digite a nova versao (ex: 1.0.2): ").strip()

    if not re.match(r"^\d+\.\d+\.\d+$", new_version):
        print("[ERRO] Versao invalida! Use o formato numerico semantico (ex: 1.0.2)")
        sys.exit(1)

    if len(sys.argv) >= 3:
        changelog_raw = sys.argv[2].strip()
    else:
        changelog_raw = input("Digite as novidades/changelog (separadas por virgula ou ponto): ").strip()

    changelog = [item.strip() for item in re.split(r"[,;.]", changelog_raw) if item.strip()]
    if not changelog:
        changelog = [f"Atualizacoes e melhorias gerais na versao v{new_version}"]

    print(f"\n[+] Iniciando publicacao da versao v{new_version}...")
    print(f"[+] Changelog: {changelog}")

    # ETAPA 1: Atualiza versão nos arquivos fonte
    write_step(1, "Atualizando codigo-fonte e manifesto de versao")
    update_utils_py(new_version)
    update_version_json(new_version, changelog)
    update_installer_iss(new_version)

    # ETAPA 2: Compilação dos Executáveis e Instalador Inno Setup
    write_step(2, "Compilando CedNet Help, CedNet Updater e Instalador")
    build_executables()
    build_inno_setup()


    # ETAPA 3: Empacotamento ZIP e cálculo SHA-256
    write_step(3, "Gerando pacote ZIP e calculando hash SHA-256")
    zip_path = os.path.join(APP_DIR, "dist", "CedNet_Help.zip")
    sha256_hash = create_zip_and_hash()
    
    update_version_json(new_version, changelog, sha256_hash)
    shutil.copy2(os.path.join(APP_DIR, "version.json"), os.path.join(APP_DIR, "dist", "CedNet_Help", "version.json"))

    # ETAPA 4: Git Commit & Push
    write_step(4, "Enviando codigo e versao para o repositorio GitHub")
    run_cmd("git add -A")
    run_cmd(f'git commit -m "release: v{new_version}"')
    run_cmd("git push origin main")
    print("  [OK] Commit e Push concluidos!")

    # ETAPA 5: Publicação da Release no GitHub
    write_step(5, "Publicando Release no GitHub")
    token = get_github_token()

    if token:
        print("  [OK] Token do GitHub encontrado. Publicando automaticamente via API...")
        success = create_github_release_api(token, new_version, changelog, zip_path)
        if success:
            write_step(6, "CONCLUIDO COM SUCESSO!")
            print(f"Versao v{new_version} foi compilada, enviada e publicada!")
            print(f"Todos os tecnicos receberao o aviso de atualizacao automaticamente ao abrir o app.")
            return

    print("\n  [i] Nenhum Token de Acesso Pessoal (GITHUB_TOKEN) foi detectado.")
    print("  Abrindo o navegador para envio rapido de 1 clique...")

    release_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/new?tag=v{new_version}&title=CedNet%20Help%20v{new_version}"
    webbrowser.open(release_url)

    write_step(6, "QUASE PRONTO!")
    print(f"  1. A pagina do GitHub Releases foi aberta no seu navegador.")
    print(f"  2. Arraste o arquivo: dist\\CedNet_Help.zip para a pagina.")
    print(f"  3. Clique em 'Publish release'.")
    print("\n[DICA] Para automatizar essa ultima etapa no futuro, salve seu GitHub Token no arquivo 'token.txt'!")


if __name__ == "__main__":
    main()
