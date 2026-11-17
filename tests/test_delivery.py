"""Delivery regressions from real expert/skill packaging failures."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_publisher as base
from test_publisher import pub, SKILL

sys.modules['publish'] = pub
spec = importlib.util.spec_from_file_location('verifier', SKILL / 'scripts/verify_install.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class DeliveryTests(unittest.TestCase):
    setUp = base.PublisherTests.setUp
    tearDown = base.PublisherTests.tearDown
    build = base.PublisherTests.build
    expert_inputs = base.PublisherTests.expert_inputs

    def test_locked_scratch_does_not_invalidate_verified_output(self):
        with patch.object(pub.Path, 'unlink', side_effect=PermissionError('fixture lock')), patch.object(pub.time, 'sleep'):
            release, report = self.build()
        self.assertEqual(report['temporary_cleanup'], 'deferred_file_in_use')
        self.assertEqual(pub.validate(pub.load_files(release), 'standard')['static_validation'], 'passed')
        saved = json.loads(release.with_suffix('.zip.report.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['temporary_cleanup'], 'deferred_file_in_use')
    def installed(self, release, folder=False):
        target = self.root / 'installed'
        for name, data in pub.load_files(release).items():
            if folder:
                name = name.split('/', 1)[1]
            p = target / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return target

    def test_install_match_and_extra_runtime_file(self):
        release, _ = self.build()
        target = self.installed(release)
        self.assertTrue(verifier.compare(release, target, 'standard')['exact_file_set'])
        (target / '.downloaded_at').write_text('local timestamp')
        result = verifier.compare(release, target, 'standard')
        self.assertTrue(result['passed'])
        self.assertFalse(result['exact_file_set'])
        self.assertEqual(result['extra'], ['.downloaded_at'])

    def test_install_same_version_changed_or_missing_content(self):
        release, _ = self.build()
        target = self.installed(release)
        (target / 'references/guide.md').write_text('old build')
        result = verifier.compare(release, target, 'standard')
        self.assertFalse(result['passed'])
        self.assertEqual(result['changed'], ['references/guide.md'])
        (target / 'references/guide.md').unlink()
        self.assertEqual(verifier.compare(release, target, 'standard')['missing'], ['references/guide.md'])

    def test_folder_install_root(self):
        release, _ = self.build('folder')
        target = self.installed(release, folder=True)
        self.assertTrue(verifier.compare(release, target, 'folder')['passed'])

    def test_independent_expert_and_skill_versions(self):
        path, body, avatar, config = self.expert_inputs()
        config['version'] = '3.0.4'
        path.write_text(json.dumps(config), encoding='utf-8')
        release = self.root / 'expert.zip'
        report = pub.build_expert(path, body, avatar, release, [self.source])
        self.assertEqual(report['version'], '3.0.4')
        self.assertEqual(report['embedded_skills'][0]['version'], '1.0.0')
        self.assertEqual(report['version_source'], '.codebuddy-plugin/plugin.json')
        target = self.installed(release)
        self.assertTrue(verifier.compare(release, target, 'expert')['passed'])
        (target / '.codebuddy-plugin/plugin.json').unlink()
        self.assertFalse(verifier.compare(release, target, 'expert')['passed'])

    def test_old_valid_avatar_rejected_against_selected_image(self):
        config, body, avatar, _ = self.expert_inputs()
        release = self.root / 'expert.zip'
        pub.build_expert(config, body, avatar, release, [self.source])
        files = pub.load_files(release)
        self.assertTrue(pub.check_avatar(files, avatar)['selected_avatar_match'])
        # A different valid 512x512 fixture still passes dimensions; identity must fail.
        files['avatars/expert.png'] += b'old-artwork-marker'
        pub.validate(files, 'expert')
        with self.assertRaisesRegex(pub.Invalid, 'differs from selected image'):
            pub.check_avatar(files, avatar)

    def test_avatar_missing_or_reference_broken(self):
        config, body, avatar, _ = self.expert_inputs()
        release = self.root / 'expert.zip'
        pub.build_expert(config, body, avatar, release, [self.source])
        for missing in (True, False):
            files = pub.load_files(release)
            if missing:
                del files['avatars/expert.png']
            else:
                c = json.loads(files['.codebuddy-plugin/plugin.json'])
                c['avatar'] = 'avatars/missing.png'
                files['.codebuddy-plugin/plugin.json'] = json.dumps(c).encode()
            with self.assertRaisesRegex(pub.Invalid, 'Missing avatar'):
                pub.validate(files, 'expert')

    def test_manifest_identity_and_top_level_version(self):
        files = pub.load_files(self.source)
        files['assets/skill-version.json'] = b'{"name":"example-skill","version":"1.0.0","build_id":"test-r2"}'
        self.assertEqual(pub.validate(files, 'standard')['build_id'], 'test-r2')
        meta, body = pub.frontmatter(files['SKILL.md'])
        meta['version'] = '0.9.0'
        files['SKILL.md'] = pub.encode_frontmatter(meta, body)
        with self.assertRaisesRegex(pub.Invalid, 'version mismatch'):
            pub.validate(files, 'standard')
        del meta['version']
        files['SKILL.md'] = pub.encode_frontmatter(meta, body)
        files['assets/skill-version.json'] = b'{"name":"wrong-skill","version":"1.0.0"}'
        with self.assertRaisesRegex(pub.Invalid, 'manifest/name mismatch'):
            pub.validate(files, 'standard')
