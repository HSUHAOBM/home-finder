from pathlib import Path


def test_windows_launcher_keeps_console_visible_and_forwards_arguments():
    launcher = Path(__file__).resolve().parents[1] / "開啟找房介面.cmd"
    content = launcher.read_bytes()

    assert b"\r\n" in content
    assert b"\n" not in content.replace(b"\r\n", b"")
    assert b"%*" in content
    assert b'.venv\\Scripts\\python.exe' in content
    assert b"--reload" in content
    assert b"pythonw.exe" not in content
    assert b"wscript.exe" not in content
    assert "Ctrl+C".encode() in content
