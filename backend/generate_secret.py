from pathlib import Path
import secrets
import re

ENV_FILE = Path(__file__).resolve().parent / ".env"
secret = secrets.token_urlsafe(48)
content = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
pattern = r"(?m)^SECRET_KEY=.*$"
if re.search(pattern, content):
    content = re.sub(pattern, f"SECRET_KEY={secret}", content)
else:
    if content and not content.endswith("\n"):
        content += "\n"
    content += f"SECRET_KEY={secret}\n"
ENV_FILE.write_text(content, encoding="utf-8")
print("SECRET_KEY generated successfully and saved to backend/.env")
