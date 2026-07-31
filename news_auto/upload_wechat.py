from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup


def extract_paste_html(path: Path) -> str:
    html = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    root = soup.select_one(".rich_media_content .ProseMirror") or soup.body
    if root is None:
        return html
    return "".join(str(child) for child in root.contents)


def upload_to_wechat_editor(
    html_path: Path,
    editor_url: str,
    profile_dir: Path,
    title: str = "",
    auto_save: bool = False,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "缺少 Playwright。请先运行：py -3.13 -m pip install playwright && py -3.13 -m playwright install chromium"
        ) from exc

    paste_html = extract_paste_html(html_path)
    profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1440, "height": 960},
        )
        page = browser.new_page()
        page.goto(editor_url, wait_until="domcontentloaded")
        print("浏览器已打开。请扫码登录并进入图文编辑页，程序会等待正文编辑器出现。")
        editor = page.locator("#ueditor_0 .rich_media_content .ProseMirror, .rich_media_content .ProseMirror").first
        editor.wait_for(timeout=180_000)
        if title:
            title_editor = page.locator('.title-editor__input .ProseMirror, [name="title"] .ProseMirror').first
            if title_editor.count():
                title_editor.click()
                page.keyboard.press("Control+A")
                page.keyboard.type(title)
        page.evaluate(
            """async ({selector, html}) => {
                const editor = document.querySelector(selector);
                if (!editor) throw new Error('找不到正文编辑器');
                editor.focus();
                editor.innerHTML = html;
                editor.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertHTML', data: html}));
                editor.dispatchEvent(new Event('change', {bubbles: true}));
            }""",
            {
                "selector": "#ueditor_0 .rich_media_content .ProseMirror, .rich_media_content .ProseMirror",
                "html": paste_html,
            },
        )
        print("正文已写入编辑器。请在浏览器中肉眼检查样式和图片。")
        if auto_save:
            page.locator("text=保存为草稿").first.click(timeout=30_000)
            print("已尝试点击保存为草稿。")
        else:
            print("当前未自动保存，请确认无误后手动保存草稿。")
        input("检查完成后按 Enter 关闭自动化浏览器...")
        browser.close()
