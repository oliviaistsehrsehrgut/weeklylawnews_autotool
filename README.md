# 法律新闻自动化

本地运行的法律新闻整理工具。从粘贴文本或链接中提取网址，自动抓取正文，调用 LLM 生成摘要和分类，输出 Word 初稿或公众号 HTML。

---

## 快速开始

### 第一步：下载

打开 [GitHub 仓库页面](https://github.com/oliviaistsehrsehrgut/weeklylawnews_autotool)，点击右上角绿色 **Code → Download ZIP**，下载后解压到任意位置。

> 压缩包已内置 Python 运行环境，无需单独安装 Python。

---

### 第二步：安装

双击解压文件夹内的 **`install.bat`**。

脚本会自动完成以下步骤：
1. 解压内置 Python 运行环境
2. 联网下载所有依赖包（使用清华镜像，约需几分钟）
3. 生成 `config.toml` 配置文件

> 安装过程中会询问是否安装 Playwright 浏览器内核（约 150MB）。绝大多数网站无需它，**直接回车跳过即可**，后续有需要再补装。

---

### 第三步：填写 API Key

安装完成后，用**记事本**打开同目录下的 **`config.toml`**，找到 `[llm]` 部分，填入你的 API Key 和模型名：

```toml
[llm]
base_url = "https://api.deepseek.com"
api_key_env = "DEEPSEEK_API_KEY"
model = "deepseek-chat"
```

也可以不填 `config.toml`，直接在网页工作台右上角的「API 配置」弹窗中填写，每次启动程序后填一次即可。

> `config.toml` 已被 Git 忽略，不会上传到 GitHub，API Key 不会泄露。

---

### 第四步：启动

双击桌面上的 **「法讯自动化」** 图标（安装完成后自动创建），浏览器将自动打开：

```
http://127.0.0.1:8000
```

关闭命令行窗口即停止程序。以后每次使用只需双击桌面图标，或双击文件夹内的 **`法讯自动化.bat`**。

---

### 第五步：安装微信公众号编辑器插件（可选）

`wechat-extension/` 文件夹是一个 Chrome/Edge 浏览器插件，用于在微信公众号后台直接编辑和注入 HTML 排版。

1. 打开 Chrome 或 Edge，地址栏输入 `chrome://extensions/` 回车
2. 右上角开启**开发者模式**
3. 点击**加载已解压的扩展程序**
4. 选择解压文件夹内的 `wechat-extension` 文件夹
5. 打开[微信公众号图文编辑页](https://mp.weixin.qq.com)即可使用

---

## 网页工作台使用说明

启动后在浏览器打开 `http://127.0.0.1:8000`，工作台支持：

- **批量粘贴链接**：粘贴多条链接或文本，程序自动提取其中的 URL
- **设置周期**：设置本周起止日期，超出范围的条目会提示
- **上传 Word**：上传按标准格式整理的 `.docx`，自动解析为新闻条目
- **编辑条目**：修改标题、摘要、链接、正文；条目可拖动排序或删除
- **抓取正文**：勾选条目后点击「根据链接更新全文」，自动抓取网页正文
- **生成摘要**：勾选条目后点击「根据全文更新摘要」，调用 LLM 生成摘要
- **自动排序**：按发文机关级别（中央部委 → 地方 → 国外）和法律效力位阶排序
- **导出**：生成 Word 初稿或公众号 HTML 文件

---

## 配置说明

配置文件为 `config.toml`（首次安装时从 `config.example.toml` 自动复制）。

### LLM 接口

支持 DeepSeek 及其他兼容 OpenAI Chat Completions 的接口：

```toml
[llm]
enabled = true
base_url = "https://api.deepseek.com"
api_key_env = "DEEPSEEK_API_KEY"   # 从同名环境变量读取 Key
model = "deepseek-chat"
```

也可以直接在 `api_key` 字段填写 Key（不推荐提交到 Git）：

```toml
api_key = "sk-xxxxxxxxxxxxxxxx"
```

### 关键词筛选

```toml
[filters]
keywords = ["网络安全", "数据合规", "人工智能", ...]
```

---

## 文件结构

```
├── install.bat              一键安装脚本（含桌面快捷方式）
├── 法讯自动化.bat           一键启动脚本
├── icon.ico                 程序图标
├── python-embed.zip         内置 Python 3.11 运行环境
├── _python/                 安装后解压的 Python（自动生成，不提交 Git）
├── config.example.toml      配置模板（可提交 Git）
├── config.toml              本机配置，含 API Key（不提交 Git）
├── app.py                   服务器入口
├── news_auto/               Python 核心代码
├── static/                  网页前端 CSS / JavaScript
├── templates/               Word、HTML 和网页模板
│   ├── 法讯草稿模板.docx
│   └── 公众号编辑器模板.html
├── input/                   输入文件示例
├── output/                  生成的 Word / HTML（不提交 Git）
└── wechat-extension/        微信公众号编辑器浏览器插件
```

---

## 常见问题

**双击 `install.bat` 没有反应或闪退？**
右键 → 以管理员身份运行，或检查杀毒软件是否拦截了脚本。

**安装依赖时报网络错误？**
检查网络连接，重新双击 `install.bat`（已安装的步骤会自动跳过，不会重复安装）。

**提示找不到 python-embed.zip？**
说明下载的 ZIP 不完整，请重新从 GitHub 下载完整压缩包。

**如何补装 Playwright 浏览器？**
在命令行运行：
```
_python\Scripts\playwright.exe install chromium
```

**LLM 摘要没有生成？**
确认 `config.toml` 中填写了正确的 API Key 和模型名，或在网页工作台右上角的「API 配置」中填写。

---

## 当前限制

- 程序只处理用户粘贴或上传的文本/Word，不读取微信群消息。
- 某些网站会限制抓取或要求登录，失败时需要人工补全正文。
- 所有数据保存在本地，程序不提供云端同步或历史备份。
- 本程序为本地工具，不支持多人同时在线协作；每位使用者需在自己的电脑上单独安装和运行。
