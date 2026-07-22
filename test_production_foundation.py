from pathlib import Path


def frontend_source(root=None):
    """Return the browser source. v1627 dan boshlab CSS va JS index.html ichida;
    agar alohida app.css/app.js mavjud bo'lsa, ular ham qo'shib qaytariladi."""
    static_root = Path(root or "static")
    parts = [(static_root / "index.html").read_text(encoding="utf-8")]
    for filename in ("app.css", "app.js"):
        path = static_root / filename
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)
