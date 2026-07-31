# 法律新闻自动化

阶段 1-9 已实现：从人工/元宝粘贴文本中提取链接，抓取公开网页正文，可选抓取威科公开列表，接入可配置 LLM 做筛选、摘要、分类和排序，生成 Word 初稿；人工审查 Word 后，可生成公众号 HTML，并可用浏览器自动化粘贴到公众号后台。

## 安装

```powershell
cd D:\蛋蛋的一口大锅\法讯自动化\news-automation
py -3.13 -m pip install -r requirements.txt
Copy-Item config.example.toml config.toml
```

如需使用 LLM，编辑 `config.toml`：

```toml
[llm]
base_url = "https://api.openai.com/v1"
api_key = ""
api_key_env = "OPENAI_API_KEY"
model = "你的模型名"
```

## 1. 准备输入

把元宝或人工整理出的链接放入文本文件，例如 `input/group_links.txt`。程序会自动提取其中的 URL。

元宝提示词可用：

```text
请列出本周群聊中出现的所有微信公众号文章链接，只输出：
标题：
链接：
发送日期：
不要总结正文，不要遗漏重复链接。
```

## 2. 生成 Word 初稿

```powershell
py -3.13 run.py draft --input-file input\group_links.txt --week-start 2026-07-20 --week-end 2026-07-26
```

禁用 LLM，仅生成占位摘要：

```powershell
py -3.13 run.py draft --input-file input\group_links.txt --week-start 2026-07-20 --week-end 2026-07-26 --no-llm
```

可选抓取威科公开列表：

```powershell
py -3.13 run.py draft --input-file input\group_links.txt --week-start 2026-07-20 --week-end 2026-07-26 --wk
```

输出文件在 `output/`：

- `法讯初稿_*.docx`：人工审查用 Word 初稿；
- `公众号推文_*.html`：人工审查后生成的公众号内容；
- `.debug/`：隐藏调试目录，保存 JSON 记录，默认仅保留最近 20 个文件；可在 `config.toml` 的 `[paths]` 中调整。

官网识别规则位于 `config.toml` 的 `[official]`：`.gov`、`.gov.cn` 以及域名中包含配置机关标识的链接会被初步识别为官网；其他链接会在 Word 的“原文链接”后标记 `【可能非官方网站，待核实修改】`。这是域名初筛，不等同于人工核验。

## 3. 人工审查 Word 后生成公众号 HTML

审查并另存 Word 后，运行：

```powershell
py -3.13 run.py wechat --reviewed-docx output\法讯初稿_2026-07-20_2026-07-26.docx
```

也可以指定输出路径：

```powershell
py -3.13 run.py wechat --reviewed-docx output\已审查.docx --output output\公众号推文.html
```

生成的 HTML 会读取 `templates\公众号编辑器模板.html`，保留模板头部、尾部和橙色样式结构，并替换中间的新闻列表与正文块。

## 4. 半自动粘贴到公众号后台

第一次使用需要安装浏览器驱动：

```powershell
py -3.13 -m playwright install chromium
```

然后运行：

```powershell
py -3.13 run.py upload-wechat --html output\公众号推文.html --editor-url "你的公众号图文编辑页 URL"
```

程序会打开浏览器。你扫码登录后，程序会等待正文编辑器出现并自动写入 HTML。默认不会自动保存，请肉眼检查样式、图片和链接后手动保存草稿。

实验性自动保存：

```powershell
py -3.13 run.py upload-wechat --html output\公众号推文.html --editor-url "你的公众号图文编辑页 URL" --auto-save
```

## 说明

- 程序不会读取微信群消息，只处理用户粘贴文本。
- 威科部分仅做公开列表和可访问页面的辅助抓取；如页面需要登录且无法读取，会保留候选供人工补全。
- LLM 摘要采用事实抽取后生成摘要的方式，并要求不得补充原文没有的信息。
- 公众号上传部分先采用浏览器自动粘贴，不直接调用发布接口；确认稳定后再考虑草稿箱 API。
