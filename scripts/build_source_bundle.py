"""Build the maintained source distribution without weights or local manga data.

Historical benchmarks remain in the development workspace. The public bundle
contains runtime modules, maintained tools, portable tests and documentation.
"""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('manga_ai', 'docs', '.github')
FILES = (
    'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md', '.gitignore', '.gitattributes', '.editorconfig',
    'Photoshop_Typeset.jsx', 'Photoshop_CheckPython.jsx',
    'manga_typesetter.py', 'manga_scan.py', 'setup_macos.command', 'setup.py', 'setup_windows.cmd', 'setup_linux.sh',
    'models/NOTICE.md', 'models/README.md', 'models/manifest.json',
    'demo_project/pages/001_page1/original.png',
    'demo_project/pages/001_page1/bubbles.tsv',
    'assets/fonts/README.md', 'assets/fonts/itim/Itim-Regular.ttf', 'assets/fonts/itim/OFL.txt',
    'assets/fonts/patrickhand/PatrickHand-Regular.ttf', 'assets/fonts/patrickhand/OFL.txt',
    'assets/fonts/bangers/Bangers-Regular.ttf', 'assets/fonts/bangers/OFL.txt',
    'assets/fonts/mali/Mali-Regular.ttf', 'assets/fonts/mali/Mali-Bold.ttf', 'assets/fonts/mali/OFL.txt',
    'assets/fonts/pangolin/Pangolin-Regular.ttf', 'assets/fonts/pangolin/OFL.txt',
    'assets/fonts/sriracha/Sriracha-Regular.ttf', 'assets/fonts/sriracha/OFL.txt',
    # Shared by the Python and JS lettering tests.
    'tests/fixtures/textnorm_cases.json',
    'tests/fixtures/honorific_cases.json',
)
SCRIPTS = (
    'core.jsxinc', 'lettering_styles.jsxinc', 'style_manager.jsxinc', 'dialogue_policy.jsxinc', 'repair.jsxinc', 'json.jsxinc', 'download_models.py', 'build_source_bundle.py',
    'clean_generated.py', 'compact_png_cache.py', 'setup_ai.py', 'setup_aot.py', 'setup_assist_models.py',
    'setup_heavy_assist.py', 'setup_preview_models.py',
    'audit_fill_color.py', 'bubble_crop_compare.py', 'bubble_decision_trace.py', 'benchmark_ocr.py',
    # Thin compatibility adapter covered by the ownership regression suite.
    'cross_manga_ownership_shadow.py',
)
NATIVE_TESTS = ('photoshop_engine_smoke.jsx', 'photoshop_smoke.jsx')
# This tests a retired, page-policy benchmark, not the current engine.
LOCAL_ONLY_TESTS = {'test_shadow_v2_components.py'}
TEXT_EXTENSIONS = {'.py', '.js', '.jsx', '.jsxinc', '.md', '.txt', '.yml', '.yaml', '.json'}
EXCLUDED_PARTS = {'__pycache__', 'archive', '.git', 'work', 'output', 'node_modules'}


def source_files(root):
    root = Path(root)
    candidates = [root / name for name in FILES]
    candidates.extend(root.glob('requirements*.txt'))
    candidates.extend(root / 'scripts' / name for name in SCRIPTS)
    candidates.extend(root / 'tests' / name for name in NATIVE_TESTS)
    candidates.append(root / 'tests/chapter_dialog.js')
    for pattern in ('test_*.py', 'test_*.js'):
        candidates.extend(p for p in (root / 'tests').glob(pattern) if p.name not in LOCAL_ONLY_TESTS)
    for name in DIRECTORIES:
        for path in (root / name).rglob('*'):
            if path.suffix in TEXT_EXTENSIONS:
                candidates.append(path)
    result = []
    for path in sorted(set(candidates)):
        relative = path.relative_to(root)
        if not path.is_file() or any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        # Check every parent too: a symlinked docs/scripts directory must never
        # pull files from elsewhere on the user's computer into a release.
        if any((root / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts)+1)):
            continue
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Source path escapes project: ' + str(relative))
        result.append(path)
    return result


def audit(root):
    root = Path(root)
    files = source_files(root)
    rows = []
    for path in files:
        size = path.stat().st_size
        if size > 5 * 1024 * 1024:
            raise ValueError('Unexpected large source file: ' + str(path))
        rows.append({'path': path.relative_to(root).as_posix(), 'bytes': size,
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return files, {'files': rows, 'count': len(rows), 'bytes': sum(row['bytes'] for row in rows),
                   'models_included': False, 'user_data_included': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--check', action='store_true', help='Audit without writing an export')
    args = parser.parse_args()
    files, report = audit(ROOT)
    if args.out:
        if args.out.exists():
            raise FileExistsError('Export directory already exists')
        args.out.mkdir(parents=True)
        for path in files:
            target = args.out / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        args.out.with_suffix('.manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        with zipfile.ZipFile(args.out.with_suffix('.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
            for row in report['files']:
                archive.write(args.out / row['path'], row['path'])
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}))


if __name__ == '__main__':
    main()
