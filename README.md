# 法律新闻自动化

这是一个在本地运行的法律新闻整理工具。它可以从粘贴文本或 TXT 文件中提取网址，抓取可访问的网页正文，调用可配置的 LLM 生成摘要和分类，并输出 Word 初稿或公众号 HTML。

## 运行边界

- 这是本地 Python 程序，不是已经部署好的公网网站。
- 用户下载 ZIP 后，不能只双击 HTML 就运行完整工作台；仍需安装 Python 和项目依赖。
- 已经生成的公众号 HTML 文件可以直接用浏览器打开，但它只是输出文件，不包含抓取、摘要、编辑和生成 Word 的功能。
- `config.toml` 缺失时程序会使用内置默认配置，因此最基础的启动不一定需要配置文件；自定义 LLM、筛选关键词或路径时，应复制 `config.example.toml`。
- GitHub 用于保存项目代码。GitHub Pages 只能发布静态文件，不能运行本项目的 FastAPI、网页抓取、摘要和 Word 生成接口。
- 如果不部署云服务，每个使用者都需要在自己的电脑上安装 Python 和依赖，并在本地启动程序。

## 安装环境

建议使用 Windows 和 Python 3.13。项目也使用 Python 3.11 及以上语法和标准库特性。

```powershell
cd "D:\蛋蛋的一口大锅\法讯自动化\news-automation"
py -3.13 -m pip install -r requirements.txt
```

需要自定义配置时：

```powershell
Copy-Item config.example.toml config.toml
```

`config.toml` 已被 Git 忽略，不应提交到公开仓库。`config.example.toml` 是不含真实密钥的配置模板，可以提交。

## 命令行模式

### 生成 Word 初稿

将网址放入 TXT 文件。程序会提取其中所有 HTTP 或 HTTPS 链接，并自动去重。

```powershell
py -3.13 run.py draft --input-file input\group_links.txt --week-start 2026-07-20 --week-end 2026-07-26
```

例如，周结束日期为 2026-08-02 时，Word 输出文件名为：

```text
0802法讯_v1.docx
```

同一周再次生成时会递增为 `0802法讯_v2.docx`。文件默认写入 `output\`。

不调用 LLM、只生成占位摘要：

```powershell
py -3.13 run.py draft --input-file input\group_links.txt --week-start 2026-07-20 --week-end 2026-07-26 --no-llm
```

可选抓取威科公开列表：

```powershell
py -3.13 run.py draft --input-file input\group_links.txt --week-start 2026-07-20 --week-end 2026-07-26 --wk
```

### 从审查后的 Word 生成 HTML

Word 按程序生成的格式审查或修改后运行：

```powershell
py -3.13 run.py wechat --reviewed-docx output\0802法讯_v1.docx
```

也可以指定输出路径：

```powershell
py -3.13 run.py wechat --reviewed-docx output\0802法讯_v1.docx --output output\公众号推文.html
```

生成的 HTML 是普通文件，可以直接用浏览器打开，也可以复制到公众号编辑器。HTML 模板位于 `templates\公众号编辑器模板.html`。

### 半自动粘贴到公众号后台

第一次使用需要安装 Playwright 浏览器：

```powershell
py -3.13 -m playwright install chromium
```

然后运行：

```powershell
py -3.13 run.py upload-wechat --html output\公众号推文.html --editor-url "你的公众号图文编辑页 URL"
```

程序会打开浏览器。扫码登录后，程序等待正文编辑器出现并粘贴 HTML。默认不会自动保存，请检查样式、图片和链接后手动保存草稿。

## 网页工作台

启动本地网页：

```powershell
py -3.13 app.py
```

浏览器打开：

```text
http://127.0.0.1:8000/
```

网页工作台支持：

- 批量粘贴多条链接，并导出为 `batch-links.txt`；
- 设置周起止日期；非完整周时显示提示；
- 上传按标准格式整理的 `.docx` 并解析为新闻条目；
- 修改标题、摘要、原文链接和全文；全文框可上下拖动调整高度；
- 增加、删除和拖动交换新闻条目顺序；
- 打开原文链接；
- 使用“根据链接更新全文”或“根据全文更新摘要”，只处理勾选的条目；
- 使用法律效力位阶和先国内后国外规则自动排序；
- 通过弹窗配置 OpenAI-compatible API 的 Base URL、模型名和 API Key；
- 下载 Word 和 HTML 模板；
- 根据当前网页条目生成 Word 初稿或公众号 HTML 文件。

网页中的 API Key 只保存在当前页面会话中，不写入 `config.toml`、历史文件或 GitHub。刷新页面后需要重新填写。不要把真实 Key 提交到公开仓库。

网页上传 Word 解析要求标题、摘要和原文链接大体符合程序生成的标准格式。任意复杂表格、文本框或完全自定义排版不保证能够识别，建议先用模板或程序生成的 Word。

## 配置 LLM

命令行模式可以在 `config.toml` 的 `[llm]` 中填写 OpenAI-compatible 接口，并优先使用环境变量保存 Key：

```toml
[llm]
base_url = "https://api.example.com/v1"
api_key = ""
api_key_env = "YOUR_API_KEY_ENV_NAME"
model = "你的模型名"
```

PowerShell 临时设置环境变量的示例：

```powershell
$env:YOUR_API_KEY_ENV_NAME = "你的 API Key"
```

也可以直接在网页 API 配置弹窗中填写 Base URL、模型名和 Key。程序支持 DeepSeek 以及其他兼容 OpenAI Chat Completions 的接口，具体取决于接口提供方的兼容程度。

## 文件说明

```text
news_auto/                 Python 核心代码
static/                    网页前端 CSS 和 JavaScript
templates/                 Word、HTML 和网页模板
input/                     输入链接示例和本地输入文件
output/                    生成的 Word、HTML 和调试输出，不提交 Git
work/.sessions/            网页运行会话，不提交 Git
config.example.toml        可公开的配置模板
config.toml                本机配置，不提交 Git
```

## GitHub 和公网访问

项目可以推送到 GitHub 保存和协作，但 GitHub 仓库本身不会运行 Python 程序。

GitHub Pages 可以发布静态 `index.html`，但当前工作台由 FastAPI 返回页面并依赖 `/api/...` 接口，因此不能只通过 GitHub Pages 提供完整功能。完整公网部署需要一个能运行 Python/FastAPI 的云服务；如果不使用云服务，每位用户只能在自己的电脑本地运行。

当前项目没有提供无需安装环境的 Windows `.exe` 或一键安装包。若以后需要让用户下载后直接运行，需要另外制作打包版本，并处理 Python 依赖、模板文件和可选的 Playwright 浏览器安装。

## 当前限制

- 程序只处理用户粘贴或上传的文本/Word，不读取微信群消息。
- 某些网站会限制抓取、要求登录或阻止自动访问，失败时需要人工补全文本。
- LLM 摘要依赖接口可用性和正确配置；未启用 LLM 时使用占位摘要或规则分类。
- 输出 Word、HTML 和调试文件保存在本地 `output\`，程序不会替用户做历史记录或云端备份。
