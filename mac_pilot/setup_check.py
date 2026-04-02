"""Startup checks — detect what's installed and connected."""

import subprocess
import json
import shutil


def check_gws_installed() -> bool:
    return shutil.which("gws") is not None


def check_gws_authenticated() -> bool:
    if not check_gws_installed():
        return False
    try:
        r = subprocess.run(["gws", "auth", "status"], capture_output=True, text=True, timeout=5)
        data = json.loads(r.stdout)
        return data.get("token_valid", False)
    except Exception:
        return False


def check_gcloud_authenticated() -> bool:
    try:
        r = subprocess.run(["gcloud", "auth", "application-default", "print-access-token"],
                          capture_output=True, text=True, timeout=5)
        return r.returncode == 0 and r.stdout.strip().startswith("ya29.")
    except Exception:
        return False


def run_gws_auth():
    """Launch gws auth login — opens browser for OAuth."""
    subprocess.Popen(["gws", "auth", "login"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def get_setup_status() -> dict:
    """Return status of all integrations."""
    return {
        "gws_installed": check_gws_installed(),
        "gws_authenticated": check_gws_authenticated(),
        "gcloud_authenticated": check_gcloud_authenticated(),
    }
