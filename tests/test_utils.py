"""Tests for wol_app.utils validation helpers."""

import base64
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from wol_app.utils import (
    _build_rdp_content,
    auto_rdp_resolution,
    get_ip_key,
    launch_remote_desktop,
    validate_device_name,
    validate_ip,
    validate_mac,
    validate_password,
    validate_username,
)


class TestValidateIP(unittest.TestCase):
    def test_valid_ip(self):
        self.assertTrue(validate_ip("192.168.1.1"))
        self.assertTrue(validate_ip("255.255.255.255"))
        self.assertTrue(validate_ip("0.0.0.0"))

    def test_invalid_ip(self):
        self.assertFalse(validate_ip("999.1.1.1"))
        self.assertFalse(validate_ip("1.2.3"))
        self.assertFalse(validate_ip("not-an-ip"))
        self.assertFalse(validate_ip(""))
        self.assertFalse(validate_ip("256.256.256.256"))


class TestValidateMac(unittest.TestCase):
    def test_valid_mac(self):
        self.assertTrue(validate_mac("AA:BB:CC:DD:EE:FF"))
        self.assertTrue(validate_mac("AA-BB-CC-DD-EE-FF"))
        self.assertTrue(validate_mac("aa:bb:cc:dd:ee:ff"))

    def test_invalid_mac(self):
        self.assertFalse(validate_mac(""))
        self.assertFalse(validate_mac("AA:BB:CC:DD:EE:GG"))
        self.assertFalse(validate_mac("AA:BB:CC:DD:EE"))
        self.assertFalse(validate_mac("not-a-mac"))


class TestValidateDeviceName(unittest.TestCase):
    def test_valid_name(self):
        self.assertTrue(validate_device_name("Living Room PC"))
        self.assertTrue(validate_device_name("PC-1"))

    def test_invalid_name(self):
        self.assertFalse(validate_device_name(""))
        self.assertFalse(validate_device_name("A" * 65))
        self.assertFalse(validate_device_name("bad<script>"))
        self.assertFalse(validate_device_name("semi;colon"))


class TestValidateUsername(unittest.TestCase):
    def test_optional(self):
        self.assertTrue(validate_username(""))
        self.assertTrue(validate_username("user"))

    def test_invalid(self):
        self.assertFalse(validate_username("A" * 65))
        self.assertFalse(validate_username("bad\x00"))


class TestValidatePassword(unittest.TestCase):
    def test_optional(self):
        self.assertTrue(validate_password(""))
        self.assertTrue(validate_password("pass"))

    def test_invalid(self):
        self.assertFalse(validate_password("A" * 129))
        self.assertFalse(validate_password("p\xff"))


class TestGetIPKey(unittest.TestCase):
    def test_sorts_ip(self):
        self.assertLess(get_ip_key("192.168.1.2"), get_ip_key("192.168.1.10"))

    def test_invalid_returns_zeros(self):
        self.assertEqual(get_ip_key(""), (0, 0, 0, 0))
        self.assertEqual(get_ip_key("invalid"), (0, 0, 0, 0))


class TestAutoRdpResolution(unittest.TestCase):
    def test_2560x1440_default_fraction(self):
        # Default fraction now comes from config: REMOTE_DESKTOP_AUTO_FRACTION = 0.8.
        self.assertEqual(auto_rdp_resolution(2560, 1440), (2048, 1152))

    def test_1920x1080_default_fraction(self):
        self.assertEqual(auto_rdp_resolution(1920, 1080), (1536, 864))

    def test_explicit_fraction_0_9(self):
        # Legacy behavior preserved when fraction is passed explicitly.
        self.assertEqual(auto_rdp_resolution(2560, 1440, fraction=0.9), (2304, 1296))
        self.assertEqual(auto_rdp_resolution(1920, 1080, fraction=0.9), (1728, 972))

    def test_clamps_to_minimum(self):
        # Very small screens must not go below the (1280, 720) floor.
        self.assertEqual(auto_rdp_resolution(800, 600), (1280, 720))

    def test_nonpositive_returns_minimum(self):
        self.assertEqual(auto_rdp_resolution(0, 0), (1280, 720))
        self.assertEqual(auto_rdp_resolution(-100, -100), (1280, 720))


class TestBuildRdpContent(unittest.TestCase):
    def test_fullscreen_mode(self):
        content = _build_rdp_content("192.168.1.10", "user", "pw", True, 1920, 1080)
        self.assertIn("full address:s:192.168.1.10", content)
        self.assertIn("fullscreen:i:1", content)
        # Windowed-mode keys must be absent in fullscreen mode
        self.assertNotIn("desktopwidth", content)
        self.assertNotIn("desktopheight", content)
        self.assertIn("username:s:user", content)

    def test_windowed_mode(self):
        content = _build_rdp_content("10.0.0.5", "", "", False, 2560, 1440)
        self.assertIn("fullscreen:i:0", content)
        self.assertIn("desktopwidth:i:2560", content)
        self.assertIn("desktopheight:i:1440", content)
        self.assertIn("use multimon:i:0", content)
        # Window must be positioned at 10,10 (winposstr = left,top,right,bottom)
        self.assertIn("winposstr:s:0,1,10,10,2570,1450", content)

    def test_fullscreen_has_no_position_line(self):
        content = _build_rdp_content("10.0.0.5", "", "", True, 2560, 1440)
        self.assertNotIn("winposstr", content)

    def test_password_is_base64_utf16le(self):
        content = _build_rdp_content("10.0.0.5", "", "pw", True, 1920, 1080)
        expected = base64.b64encode("pw".encode("utf-16-le")).decode("ascii")
        self.assertIn(f"password:54:{expected}", content)
        # mstsc must be told to use the embedded password, not prompt
        self.assertIn("prompt for password:i:0", content)

    def test_no_credentials_no_credential_lines(self):
        content = _build_rdp_content("10.0.0.5", "", "", True, 1920, 1080)
        self.assertNotIn("password:54:", content)
        self.assertNotIn("username:s:", content)
        self.assertIn("prompt for password:i:1", content)


class TestLaunchRemoteDesktop(unittest.TestCase):
    def setUp(self):
        # Isolate writes from the real ~/.wol_app/rdp directory.
        patcher = patch("wol_app.utils._RDP_DIR", new=Path(tempfile.mkdtemp()))
        self.mock_rdp_dir = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.mock_rdp_dir, ignore_errors=True)

    def test_launch_fullscreen_uses_f_flag(self):
        with patch("wol_app.utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            launch_remote_desktop(
                "192.168.1.10", "user", "pw",
                fullscreen=True, cleanup_delay=60.0,
                device_name="Wohnzimmer PC",
            )
        cmd = mock_popen.call_args[0][0]
        # Geometry is forced on the command line; the .rdp file (last arg)
        # supplies the credentials.
        self.assertEqual(cmd[0], "mstsc")
        self.assertEqual(cmd[1], "/v:192.168.1.10")
        self.assertIn("/f", cmd)
        self.assertEqual(Path(cmd[-1]).suffix, ".rdp")
        # File is named after the device and lives in ~/.wol_app/rdp/.
        self.assertEqual(Path(cmd[-1]), self.mock_rdp_dir / "Wohnzimmer_PC.rdp")
        # File must still exist (cleanup is delayed) and carry credentials
        rdp_path = cmd[-1]
        self.assertTrue(os.path.exists(rdp_path))
        with open(rdp_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("full address:s:192.168.1.10", content)
        self.assertIn("fullscreen:i:1", content)
        self.assertIn("username:s:user", content)
        os.remove(rdp_path)  # test cleanup

    def test_launch_falls_back_to_ip_when_no_device_name(self):
        with patch("wol_app.utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            launch_remote_desktop(
                "192.168.1.10", "user", "pw",
                fullscreen=True, cleanup_delay=60.0,
            )
        cmd = mock_popen.call_args[0][0]
        # Empty device_name -> filename derived from the IP address.
        self.assertEqual(Path(cmd[-1]), self.mock_rdp_dir / "192.168.1.10.rdp")

    def test_launch_windowed_uses_w_h_flags(self):
        with patch("wol_app.utils.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            launch_remote_desktop(
                "10.0.0.5", fullscreen=False, width=3440, height=1440,
                cleanup_delay=60.0, device_name="Office",
            )
        cmd = mock_popen.call_args[0][0]
        # Windowed mode is forced via /w: and /h: (mstsc ignores
        # fullscreen:i:0 in the file, so the command line is authoritative).
        self.assertEqual(cmd[0], "mstsc")
        self.assertEqual(cmd[1], "/v:10.0.0.5")
        self.assertIn("/w:3440", cmd)
        self.assertIn("/h:1440", cmd)
        self.assertNotIn("/f", cmd)
        rdp_path = Path(cmd[-1])
        self.assertEqual(rdp_path.suffix, ".rdp")
        with open(rdp_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("fullscreen:i:0", content)
        self.assertIn("desktopwidth:i:3440", content)
        self.assertIn("desktopheight:i:1440", content)
        self.assertIn("winposstr:s:0,1,10,10,3450,1450", content)
        os.remove(rdp_path)  # test cleanup

    def test_launch_empty_ip_raises(self):
        with self.assertRaises(ValueError):
            launch_remote_desktop("")

    def test_launch_popen_failure_cleans_up_rdp_file(self):
        with patch("wol_app.utils.subprocess.Popen",
                   side_effect=OSError("mstsc not found")) as mock_popen:
            with self.assertRaises(OSError):
                launch_remote_desktop("192.168.1.10", cleanup_delay=60.0,
                                       device_name="Server")
        rdp_path = mock_popen.call_args[0][0][-1]
        self.assertFalse(os.path.exists(rdp_path))


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
