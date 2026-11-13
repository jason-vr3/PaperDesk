"""Reproducible portable folder + ZIP; no admin installation needed."""
from pathlib import Path
import hashlib
import importlib.metadata as metadata
import json
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from paperdesk import __version__
release = ROOT / 'release'
release.mkdir(exist_ok=True)

subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
    '--windowed', '--onedir', '--name', 'PaperDesk',
    '--icon', str(ROOT / 'assets/PaperDesk.ico'),
    '--add-data', str(ROOT / 'assets') + ';assets',
    '--exclude-module', 'numpy', '--exclude-module', 'onnxruntime',
    '--exclude-module', 'PySide6.QtQml', '--exclude-module', 'PySide6.QtQuick',
    '--exclude-module', 'PySide6.QtNetwork', '--exclude-module', 'PySide6.QtOpenGL',
    '--exclude-module', 'PySide6.QtSql', '--exclude-module', 'PySide6.QtTest',
    '--exclude-module', 'PySide6.QtDBus', '--exclude-module', 'PySide6.QtXml',
    str(ROOT / 'main.py')], cwd=ROOT, check=True)

portable = ROOT / 'dist' / 'PaperDesk'
licenses = portable / 'licenses'
licenses.mkdir(exist_ok=True)
for file in (ROOT / 'legal').glob('*'):
    shutil.copy2(file, licenses / file.name)
shutil.copy2(Path(sys.base_prefix) / 'LICENSE.txt', licenses / 'CPython-LICENSE.txt')
for package in ('PyMuPDF', 'PySide6-Essentials', 'shiboken6', 'Pillow', 'pyinstaller'):
    dist = metadata.distribution(package)
    for file in dist.files or []:
        if any(token in str(file).lower() for token in ('license', 'copying', 'notice')):
            source = Path(dist.locate_file(file))
            if source.is_file():
                dest = licenses / package / str(file).replace('..', '_')
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
for filename in ('README.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'NOTICE', 'CHANGELOG.md', 'AI_ASSISTANCE.md'):
    shutil.copy2(ROOT / filename, portable / filename)

source_zip = release / f'PaperDesk-v{__version__}-source.zip'
with zipfile.ZipFile(source_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
    for folder in ('paperdesk', 'tests', 'scripts', '.github', 'assets', 'legal'):
        for file in (ROOT / folder).rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts:
                archive.write(file, Path('PaperDesk-source') / file.relative_to(ROOT))
    for filename in ('main.py','README.md','LICENSE','THIRD_PARTY_NOTICES.md',
                     'requirements.txt','requirements-build.txt','.gitignore','build.ps1','VALIDATION.md',
                     'NOTICE','CHANGELOG.md','AI_ASSISTANCE.md','CONTRIBUTING.md','SECURITY.md','CODE_OF_CONDUCT.md'):
        archive.write(ROOT / filename, Path('PaperDesk-source') / filename)
    for file in licenses.rglob('*'):
        if file.is_file():
            archive.write(file, Path('PaperDesk-source/licenses') / file.relative_to(licenses))

zip_path = release / f'PaperDesk-v{__version__}-Windows-x64.zip'
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive:
    for file in portable.rglob('*'):
        if file.is_file():
            archive.write(file, Path('PaperDesk') / file.relative_to(portable))

hashes = {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in (zip_path, source_zip)}
(release / 'SHA256.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
(release / f'SHA256-v{__version__}.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
print(json.dumps({'portable':str(portable),'packages':[
    {'name':p.name, 'size_mb':round(p.stat().st_size / 1024**2, 1)} for p in (zip_path, source_zip)]}, indent=2))
