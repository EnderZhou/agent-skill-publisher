from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skill/agent-skill-publisher'
spec = importlib.util.spec_from_file_location('publisher', SKILL / 'scripts/publish.py')
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)


def png():
    # Synthetic solid-color format fixture, not an expert's production artwork.
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    header = chunk(b'IHDR', struct.pack('>IIBBBBB', 512, 512, 8, 0, 0, 0, 0))
    return b'\x89PNG\r\n\x1a\n' + header + chunk(b'IDAT', zlib.compress((b'\0' * 513) * 512)) + chunk(b'IEND', b'')


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'example-skill'
        self.source.mkdir()
        (self.source / 'SKILL.md').write_text('---\nname: example-skill\ndescription: "Build example files when requested."\nmetadata:\n  version: "1.0.0"\n---\n\nRead [guide](references/guide.md).\n', encoding='utf-8')
        (self.source / 'references').mkdir()
        (self.source / 'references/guide.md').write_text('Example guide.\n', encoding='utf-8')
        self.market = self.root / 'market.json'
        self.market.write_bytes((SKILL / 'assets/workbuddy-market.json').read_bytes())

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, profile='standard', output='test.zip'):
        target = self.root / output
        report = pub.package(self.source, target, profile, self.market if profile == 'workbuddy' else None)
        return target, report

    def test_all_profiles_and_source_unchanged(self):
        before = pub.load_files(self.source)
        for profile in ('standard', 'workbuddy', 'trae', 'folder'):
            path, report = self.build(profile, profile + '.zip')
            self.assertEqual(pub.validate(pub.load_files(path), profile)['static_validation'], 'passed')
            self.assertEqual(report['target_import'], 'not_verified')
        self.assertEqual(pub.load_files(self.source), before)

    def test_reproducible_binary_and_zip_readback(self):
        (self.source / 'assets').mkdir()
        data = bytes(range(256)) * 100
        (self.source / 'assets/binary.dat').write_bytes(data)
        a, report_a = self.build(output='a.zip')
        b, report_b = self.build(output='b.zip')
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(pub.load_files(a)['assets/binary.dat'], data)
        self.assertEqual(report_a['sha256'], hashlib.sha256(a.read_bytes()).hexdigest())

    def test_deep_workbuddy_rejected_without_modifying_source(self):
        (self.source / 'assets/deep').mkdir(parents=True)
        (self.source / 'assets/deep/example.json').write_text('{}')
        before = pub.load_files(self.source)
        with self.assertRaisesRegex(pub.Invalid, 'adapt deep resources'):
            self.build('workbuddy')
        self.assertEqual(pub.load_files(self.source), before)
        self.assertFalse((self.root / 'test.zip').exists())

    def test_duplicate_yaml_and_missing_description(self):
        for content in ('---\nname: a\nname: b\ndescription: x\n---\nbody', '---\nname: example-skill\n---\nbody'):
            (self.source / 'SKILL.md').write_text(content)
            with self.assertRaises(pub.Invalid):
                self.build()

    def test_missing_local_link(self):
        (self.source / 'references/guide.md').unlink()
        with self.assertRaisesRegex(pub.Invalid, 'Missing local link'):
            self.build()

    def test_relative_and_encoded_links(self):
        (self.source / 'references/another guide.md').write_text('Guide')
        (self.source / 'references/guide.md').write_text('[a](another%20guide.md) [entry](../SKILL.md#title) [web](https://example.com/anything)')
        self.build()

    def test_source_output_overlap_rejected(self):
        with self.assertRaisesRegex(pub.Invalid, 'outside source'):
            pub.package(self.source, self.source / 'out/package.zip', 'standard')

    def test_existing_output_not_overwritten(self):
        self.build()
        before = (self.root / 'test.zip').read_bytes()
        with self.assertRaises(pub.Invalid):
            self.build()
        self.assertEqual((self.root / 'test.zip').read_bytes(), before)

    def test_workbuddy_missing_or_empty_fields(self):
        base = json.loads(self.market.read_text(encoding='utf-8'))
        for field in base:
            for value in (None, ''):
                altered = dict(base)
                if value is None:
                    del altered[field]
                else:
                    altered[field] = value
                self.market.write_text(json.dumps(altered), encoding='utf-8')
                with self.assertRaises(pub.Invalid, msg=field):
                    self.build('workbuddy')

    def test_version_mismatch(self):
        market = json.loads(self.market.read_text(encoding='utf-8'))
        market['version'] = '2.0.0'
        self.market.write_text(json.dumps(market))
        with self.assertRaisesRegex(pub.Invalid, 'version mismatch'):
            self.build('workbuddy')

    def test_unsafe_and_nonportable_paths(self):
        for name in ('../escape', '/absolute', 'C:/x', 'a\\b', 'a/../b', 'CON.txt', 'a/b.', 'a//b'):
            with self.assertRaises(pub.Invalid, msg=name):
                pub.check_entries({name: b'x'})

    def test_case_unicode_and_file_directory_collisions(self):
        for names in (('a.txt', 'A.txt'), ('é.txt', 'e\u0301.txt'), ('a', 'a/b')):
            with self.assertRaises(pub.Invalid):
                pub.check_entries(dict.fromkeys(names, b'x'))

    def test_zip_traversal_and_symlink(self):
        for mode, name in ((stat.S_IFREG | 0o644, '../outside'), (stat.S_IFLNK | 0o777, 'link')):
            path = self.root / 'unsafe.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = mode << 16
                archive.writestr(info, b'target')
            with self.assertRaises(pub.Invalid):
                pub.load_files(path)

    def test_secret_is_not_returned(self):
        token = 'ghp_' + 'A' * 36
        (self.source / 'token.txt').write_text(token)
        with self.assertRaises(pub.Invalid) as context:
            self.build()
        self.assertNotIn(token, str(context.exception))
        self.assertIn('value suppressed', str(context.exception))

    def test_dotenv_rejected(self):
        (self.source / '.env').write_text('password=example')
        with self.assertRaisesRegex(pub.Invalid, 'credential file'):
            self.build()

    def test_directory_skill_name_must_match(self):
        (self.source / 'SKILL.md').write_text('---\nname: wrong-name\ndescription: okay\n---\nbody')
        with self.assertRaisesRegex(pub.Invalid, 'folder must equal'):
            self.build()

    def expert_inputs(self):
        config = json.loads((SKILL / 'assets/expert-config.example.json').read_text(encoding='utf-8'))
        path = self.root / 'expert.json'
        path.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
        body = self.root / 'body.md'
        body.write_text('Read `skills/example-skill/SKILL.md` and complete the task.', encoding='utf-8')
        avatar = self.root / 'avatar.png'
        avatar.write_bytes(png())
        return path, body, avatar, config

    def test_expert_embedded_deep_resources_preserved(self):
        (self.source / 'assets/deep').mkdir(parents=True)
        (self.source / 'assets/deep/binary.dat').write_bytes(b'\x00\xff')
        config, body, avatar, _ = self.expert_inputs()
        output = self.root / 'expert.zip'
        report = pub.build_expert(config, body, avatar, output, [self.source])
        self.assertEqual(report['embedded_skills'][0]['version'], '1.0.0')
        files = pub.load_files(output)
        prefix = 'skills/example-skill/'
        embedded = {n[len(prefix):]: data for n, data in files.items() if n.startswith(prefix)}
        self.assertEqual(embedded, pub.load_files(self.source))
        pub.validate(files, 'expert')

    def test_17_character_name_rejected_before_output(self):
        path, body, avatar, config = self.expert_inputs()
        config['displayName']['zh'] = 'FastGPT 工作流与知识库专家'
        self.assertEqual(len(config['displayName']['zh']), 17)
        path.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
        with self.assertRaisesRegex(pub.Invalid, '17 characters'):
            pub.build_expert(path, body, avatar, self.root / 'expert.zip', [self.source])
        self.assertFalse((self.root / 'expert.zip').exists())

    def test_long_english_name_rejected(self):
        path, body, avatar, config = self.expert_inputs()
        config['displayName']['en'] = 'Example Skill Publication Expert'
        path.write_text(json.dumps(config))
        with self.assertRaisesRegex(pub.Invalid, 'displayName.en'):
            pub.build_expert(path, body, avatar, self.root / 'expert.zip', [])

    def test_expert_invalid_prompt_or_avatar(self):
        path, body, avatar, config = self.expert_inputs()
        config['quickPrompts'] = config['quickPrompts'][:2]
        path.write_text(json.dumps(config))
        with self.assertRaises(pub.Invalid):
            pub.build_expert(path, body, avatar, self.root / 'expert.zip', [])
        path, body, avatar, config = self.expert_inputs()
        avatar.write_bytes(b'not an image')
        with self.assertRaises(pub.Invalid):
            pub.build_expert(path, body, avatar, self.root / 'expert.zip', [])

    def test_duplicate_json_is_rejected(self):
        with self.assertRaises(pub.Invalid):
            pub.json_object(b'{"a": 1, "a": 2}', 'example')

    def test_source_self_check_and_cli_exit_status(self):
        env = dict(os.environ, PYTHONUTF8='1')
        result = subprocess.run([sys.executable, str(SKILL / 'scripts/publish.py'), 'check', str(SKILL)],
                                capture_output=True, text=True, encoding='utf-8', env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['name'], 'agent-skill-publisher')
        failure = subprocess.run([sys.executable, str(SKILL / 'scripts/publish.py'), 'check', str(self.root / 'absent')],
                                 capture_output=True, text=True, encoding='utf-8', env=env)
        self.assertNotEqual(failure.returncode, 0)


if __name__ == '__main__':
    unittest.main()
