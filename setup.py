"""Run on the HOST with Python 3. Creates secrets without printing them."""
from pathlib import Path
import os
import secrets
import ssl

root = Path(__file__).resolve().parent
path = root / ".env"
if not path.exists():
    old_umask = os.umask(0o077)
    try:
        with path.open("x") as f:
            for key in ("EDITOR_PASSWORD", "MYSQL_PASSWORD", "MYSQL_ROOT_PASSWORD"):
                f.write(f"{key}={secrets.token_urlsafe(32)}\n")
            f.write("STUDY_PORT=8080\n")
    finally:
        os.umask(old_umask)
    print("Created private .env. Open it locally to obtain the editor password.")
else:
    print("Kept existing .env; credentials have not changed.")
ca_path = root / "build-ca.pem"
if not ca_path.exists():
    context = ssl.create_default_context()
    certs = context.get_ca_certs(binary_form=True)
    if not certs:
        raise SystemExit("No system CA certificates found. Set BUILD_CA_FILE to your trusted PEM bundle.")
    ca_path.write_text("".join(ssl.DER_cert_to_PEM_cert(cert) for cert in certs))
    print("Prepared system CA bundle for verified build downloads.")
print("Next: docker compose up --build -d")
print("Then open http://localhost:8080")
