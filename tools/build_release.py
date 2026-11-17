"""Build the project's versioned skill ZIPs and a public, path-free manifest."""
from pathlib import Path
import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skill/agent-skill-publisher'
spec = importlib.util.spec_from_file_location('publisher', SKILL / 'scripts/publish.py')
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    meta = json.loads((SKILL / 'assets/skill-version.json').read_text(encoding='utf-8'))
    version = meta['version']
    expert_version = json.loads((ROOT / 'expert/config.json').read_text(encoding='utf-8'))['version']
    dist = args.output.resolve()
    dist.mkdir(parents=True, exist_ok=True)
    reports = []
    profiles = {'standard': 'standard', 'workbuddy': 'WorkBuddy_skill', 'trae': 'Trae_skill', 'folder': 'AgentSkills_folder'}
    targets = [dist / f'{SKILL.name}-v{version}_{suffix}.zip' for suffix in profiles.values()]
    targets.append(dist / f'{SKILL.name}-v{expert_version}_WorkBuddy_expert.zip')
    for target in targets:
        pub.output_preflight(target, [SKILL, ROOT / 'expert'])
    # A reviewed local source is staged with its license. No source files are rewritten.
    # Antivirus/indexers can briefly lock new ZIPs on Windows; leftover scratch
    # files stay inside ignored dist and must not turn successful checks into failure.
    with tempfile.TemporaryDirectory(prefix='release-', dir=dist.resolve(), ignore_cleanup_errors=True) as directory:
        source = Path(directory) / SKILL.name
        shutil.copytree(SKILL, source, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copyfile(ROOT / 'LICENSE', source / 'LICENSE.txt')
        for profile, suffix in profiles.items():
            output = dist / f'{SKILL.name}-v{version}_{suffix}.zip'
            report = pub.package(source, output, profile,
                                 source / 'assets/workbuddy-market.json' if profile == 'workbuddy' else None,
                                 force=False)
            unpacked = Path(directory) / ('unpacked-' + profile)
            for name, data in pub.load_files(output).items():
                path = unpacked / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            packaged_root = unpacked / SKILL.name if profile == 'folder' else unpacked
            # Run the actual distributed tool against an external known fixture;
            # this is separate from running it inside a real Agent client.
            smoke = subprocess.run([sys.executable, '-X', 'utf8', str(packaged_root / 'scripts/publish.py'),
                                    'package', str(source), str(Path(directory) / ('smoke-' + profile + '.zip'))],
                                   capture_output=True, text=True, encoding='utf-8', timeout=30)
            if smoke.returncode:
                raise RuntimeError(f'Packaged CLI smoke failed for {profile}: {smoke.stderr}')
            report['packaged_cli_smoke'] = 'passed'
            output.with_suffix(output.suffix + '.report.json').write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            reports.append(report)
        expert_output = dist / f'{SKILL.name}-v{expert_version}_WorkBuddy_expert.zip'
        report = pub.build_expert(ROOT / 'expert/config.json', ROOT / 'expert/agent.md',
                                  ROOT / 'expert/avatar.png', expert_output, [source])
        expert_files = pub.load_files(expert_output)
        prefix = f'skills/{SKILL.name}/'
        embedded = {n[len(prefix):]: b for n, b in expert_files.items() if n.startswith(prefix)}
        pub.need(embedded == pub.load_files(source), 'Embedded skill differs from staged skill')
        unpacked = Path(directory) / 'expert-embedded' / SKILL.name
        for name, data in embedded.items():
            target = unpacked / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        smoke = subprocess.run([sys.executable, '-X', 'utf8', str(unpacked / 'scripts/publish.py'),
                                'check', str(unpacked)], capture_output=True, text=True, encoding='utf-8', timeout=30)
        pub.need(smoke.returncode == 0, 'Expert embedded CLI smoke failed: ' + smoke.stderr)
        report.update(embedded_skill_byte_identical=True, packaged_cli_smoke='passed')
        expert_output.with_suffix('.zip.report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        reports.append(report)
    manifest = {'artifact_role': 'release-manifest', 'importable_workflow': False,
                'name': SKILL.name, 'version': version, 'expert_version': expert_version,
                'build_id': meta.get('build_id'), 'release_date': meta['release_date'],
                'repository': 'https://github.com/EnderZhou/agent-skill-publisher',
                'client_import': 'not_verified', 'packages': reports}
    for file in (ROOT / 'latest.json', dist / 'manifest.json'):
        file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (dist / 'SHA256SUMS.txt').write_text(''.join(f'{x["sha256"]}  {x["zip"]}\n' for x in reports), encoding='utf-8')
    print(json.dumps({'version': version, 'packages': len(reports), 'static_validation': 'passed'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
