import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from configure_env import configure


class ConfigureEnvironmentTests(unittest.TestCase):
    def test_creates_secret_and_preserves_it_on_second_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.example").write_text("POSTGRES_PASSWORD=local\nJWT_SECRET=\n")
            configure(root)
            first = (root / ".env").read_text()
            self.assertEqual(len(first.split("JWT_SECRET=", 1)[1].strip()), 64)
            configure(root)
            self.assertEqual((root / ".env").read_text(), first)

    def test_failed_replacement_leaves_existing_credentials_intact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.example").write_text("JWT_SECRET=\n")
            original = "POSTGRES_PASSWORD=keep-me\nJWT_SECRET=existing-secret\n"
            (root / ".env").write_text(original)
            with patch("configure_env.os.replace", side_effect=OSError("disk unavailable")):
                with self.assertRaises(OSError):
                    configure(root)
            self.assertEqual((root / ".env").read_text(), original)
            self.assertEqual(list(root.glob(".env.*")), [root / ".env.example"])

    def test_rejects_duplicate_keys_without_overwriting_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.example").write_text("JWT_SECRET=\n")
            original = "JWT_SECRET=first\nJWT_SECRET=second\n"
            (root / ".env").write_text(original)
            with self.assertRaises(ValueError):
                configure(root)
            self.assertEqual((root / ".env").read_text(), original)

    def test_fills_blank_secret_with_whitespace_and_export_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.example").write_text("JWT_SECRET=\n")
            (root / ".env").write_text("export JWT_SECRET = ''\n")
            configure(root)
            self.assertEqual(len((root / ".env").read_text().split("=", 1)[1].strip()), 64)


if __name__ == "__main__":
    unittest.main()
