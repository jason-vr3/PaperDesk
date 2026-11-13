# 参与贡献

欢迎通过 [Issues](https://github.com/jason-vr3/PaperDesk/issues) 提交问题和功能建议，或发起 Pull Request。

## 报告问题

请说明软件版本、Windows 版本、复现步骤、期望结果和实际结果。如果需要示例文件，请自行创建不含私人内容的最小样本。不要上传真实办公合同、个人资料、密码或其他敏感信息。

## 开发

使用 Windows x64 和 Python 3.12，按 README 安装依赖。提交前运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

涉及页面排版、旋转或导出时，同时检查渲染结果；修改界面时，检查中文显示、缩略图和常用操作。一个 Pull Request 尽量解决一个具体问题，描述修改原因和实际运行的检查。

不要提交虚拟环境、构建输出、私人 PDF 或密钥。保留第三方版权及许可声明。提交贡献即表示你有权按本项目的 AGPL-3.0-or-later 许可证提供该贡献。使用 AI 辅助编写代码是允许的，但请说明涉及范围，并自行审查和验证。

`.github/workflow-templates/windows-check.yml.example` 提供可选的 Windows CI 示例，复制到 `.github/workflows/check.yml` 后可启用。首版检查在本机执行，未声称 GitHub Actions 已运行。
