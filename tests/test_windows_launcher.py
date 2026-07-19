from pathlib import Path


def test_windows_launcher_uses_hidden_helper_and_forwards_arguments():
    launcher = Path(__file__).resolve().parents[1] / "開啟找房介面.cmd"
    content = launcher.read_bytes()

    assert b"\r\n" in content
    assert b"\n" not in content.replace(b"\r\n", b"")
    assert "啟動找房介面_隱藏.vbs".encode() in content
    assert b"%*" in content
    assert b'.venv\\Scripts\\pythonw.exe' in content


def test_hidden_launcher_starts_web_app_without_a_visible_window():
    helper = Path(__file__).resolve().parents[1] / "啟動找房介面_隱藏.vbs"
    content = helper.read_text(encoding="utf-8")

    assert 'command = """.venv\\Scripts\\pythonw.exe"" -m home_finder.web_app_v7"' in content
    assert "shell.Run command, 0, False" in content
