from pathlib import Path


def test_windows_launcher_uses_crlf_and_forwards_arguments():
    launcher = Path(__file__).resolve().parents[1] / "開啟找房介面.cmd"
    content = launcher.read_bytes()

    assert b"\r\n" in content
    assert b"\n" not in content.replace(b"\r\n", b"")
    assert b"home_finder.web_app_v7 %*" in content
