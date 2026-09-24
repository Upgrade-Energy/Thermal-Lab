import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from thermal_lab import topview_setup as setup
from thermal_lab.desktop import Desktop


class TopViewSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.good=self.base/'Installed TopView'
        dll=self.good/setup.LIBRARY;dll.parent.mkdir(parents=True);dll.write_bytes(b'qualified fixture')
        self.digest=patch.object(setup,'DLL_SHA256',hashlib.sha256(b'qualified fixture').hexdigest())
        self.digest.start();self.addCleanup(self.digest.stop)

    def test_new_user_and_stale_other_user_path_find_installation(self):
        for saved in (None, '', self.base/'Other User'/'missing'):
            self.assertEqual(setup.resolve_topview(saved,locations=[self.good]),self.good.resolve())

    def test_valid_custom_folder_has_priority(self):
        self.assertEqual(setup.resolve_topview(self.good,locations=[]),self.good.resolve())

    def test_normalizes_dll_exe_and_parent_selection(self):
        for folder in (self.good/setup.LIBRARY,self.good/'TopView.exe'):
            self.assertEqual(setup.qualified_root(folder),self.good.resolve())
        parent=self.base/'Vendor';app=parent/'app';dll=app/setup.LIBRARY
        dll.parent.mkdir(parents=True);dll.write_bytes(b'qualified fixture')
        self.assertEqual(setup.resolve_topview(parent,locations=[]),app.resolve())

    def test_unknown_library_does_not_load_and_search_continues(self):
        bad=self.base/'unsupported';dll=bad/setup.LIBRARY
        dll.parent.mkdir(parents=True);dll.write_bytes(b'unknown ABI')
        self.assertEqual(setup.resolve_topview(bad,locations=[bad,self.good]),self.good.resolve())
        with self.assertRaisesRegex(setup.TopViewSetupError,'compatibility verification'):
            setup.resolve_topview(bad,locations=[bad])

    def test_unreadable_saved_folder_falls_back(self):
        original=Path.read_bytes
        def read(path):
            if 'blocked' in str(path):raise PermissionError('other user')
            return original(path)
        blocked=self.base/'blocked';dll=blocked/setup.LIBRARY
        dll.parent.mkdir(parents=True);dll.write_bytes(b'qualified fixture')
        with patch.object(Path,'read_bytes',read):
            self.assertEqual(setup.resolve_topview(blocked,locations=[self.good]),self.good.resolve())

    def test_no_installation_gives_actionable_setup_error(self):
        with self.assertRaisesRegex(setup.TopViewSetupError,'Camera.*Find TopView'):
            setup.resolve_topview(self.base/'absent',locations=[])

    def test_standard_locations_include_machine_and_current_user(self):
        with patch.object(setup,'registry_locations',return_value=[]),patch.dict(setup.os.environ,{'ProgramFiles':str(self.base/'machine'),'LOCALAPPDATA':str(self.base/'user')},clear=True):
            locations=setup.installation_locations()
        self.assertIn(self.base/'machine/TOPDON/TopView',locations)
        self.assertIn(self.base/'user/Programs/TOPDON/TopView',locations)

    def app(self):
        app=object.__new__(Desktop);app.process=None;app.path=Mock();app.path.get.return_value='stale other-user folder'
        app.status=Mock();app.args=SimpleNamespace(recordings=self.base/'recordings')
        return app

    def test_corrected_path_is_persisted_before_connection(self):
        app=self.app()
        with patch('thermal_lab.desktop.resolve_topview',return_value=self.good),patch('thermal_lab.service_manager.save_preferences') as save:
            self.assertTrue(app.detect_topview(quiet=True))
        app.path.set.assert_called_once_with(str(self.good));save.assert_called_once_with(str(self.good),app.args.recordings)

    def test_failure_preserves_settings_and_busy_camera_is_untouched(self):
        app=self.app()
        with patch('thermal_lab.desktop.resolve_topview',side_effect=setup.TopViewSetupError('Browse to TopView')),patch('thermal_lab.service_manager.save_preferences') as save:
            self.assertFalse(app.detect_topview());save.assert_not_called();app.path.set.assert_not_called()
        app.process=Mock();app.process.is_alive.return_value=True
        with patch('thermal_lab.desktop.resolve_topview') as resolve:
            self.assertFalse(app.detect_topview());resolve.assert_not_called()
