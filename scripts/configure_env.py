"""Create local configuration without overwriting existing credentials."""

import os
import secrets
import sys
import tempfile
from pathlib import Path


def assignment(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.removeprefix("export ").split("=", 1)
    return key.strip(), value


def configure(root: Path) -> None:
    destination = root / ".env"
    example = (root / ".env.example").read_text(encoding="utf-8")
    content = destination.read_text(encoding="utf-8") if destination.exists() else example
    lines = content.splitlines()
    entries = [entry for line in lines if (entry := assignment(line)) is not None]
    keys = {key for key, _ in entries}
    if len(keys) != len(entries):
        raise ValueError("Duplicate configuration keys; remove duplicate assignments first")
    for line in example.splitlines():
        if (entry := assignment(line)) is not None:
            key, _ = entry
            if key not in keys:
                lines.append(line)
                keys.add(key)
    for index, line in enumerate(lines):
        entry = assignment(line)
        if entry is not None and entry[0] == "JWT_SECRET" and not entry[1].strip(" \"'"):
            lines[index] = f"JWT_SECRET={secrets.token_hex(32)}"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=root, prefix=".env.", delete=False
        ) as output:
            temporary = Path(output.name)
            output.write("\n".join(lines) + "\n")
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    try:
        configure(Path(__file__).resolve().parents[1])
    except (OSError, UnicodeError, ValueError) as exc:
        print(
            f"Could not prepare .env ({type(exc).__name__}). Check permissions and duplicate keys.",
            file=sys.stderr,
        )
        return 1
    print("Local configuration is ready: .env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
