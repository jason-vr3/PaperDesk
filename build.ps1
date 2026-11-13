$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE) { throw '创建 Python 环境失败' }
}
& ./.venv/Scripts/python.exe -m pip install -r requirements-build.txt
if ($LASTEXITCODE) { throw '安装依赖失败' }
& ./.venv/Scripts/python.exe -m unittest discover -v
if ($LASTEXITCODE) { throw '测试未通过' }
& ./.venv/Scripts/python.exe scripts/build.py
if ($LASTEXITCODE) { throw '打包失败' }
