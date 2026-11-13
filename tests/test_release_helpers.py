import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

from dcrai.observability.redaction import redact

ROOT = Path(__file__).resolve().parents[1]


class ReleaseHelperTests(unittest.TestCase):
    def test_auth_parameters_are_redacted_without_mutating_runtime_data(self):
        data = {'eventType': {'Parameters': [
            {'Name': 'header#X-API-Key', 'Value': 'private'},
            {'title': 'header#Authorization', 'value': 'Bearer private'},
            {'name': 'q', 'value': 'a fictional question'}]}, 'X-DCR-AuthToken': 'private'}
        cleaned = redact(data)
        self.assertNotIn('private', str(cleaned))
        self.assertIn('a fictional question', str(cleaned))
        self.assertEqual(data['X-DCR-AuthToken'], 'private')

    def test_skill_installer_copies_supporting_files_and_refuses_overwrite(self):
        spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install_dcr_skill.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'skill'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(['--dest', str(target)]), 0)
            for name in ('SKILL.md', 'references/semantics.md', 'references/rest-simulation-api.md',
                         'scripts/validate_dcr_xml.py', 'assets/full-graph-template.xml'):
                self.assertTrue((target / name).is_file(), name)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                module.main(['--dest', str(target)])
            self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
