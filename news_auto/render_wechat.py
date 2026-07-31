from __future__ import annotations

import html
from pathlib import Path
from typing import Iterable, List

from bs4 import BeautifulSoup

from .models import NewsItem

ORANGE = "rgb(255, 129, 36)"


def render_wechat_html(items: Iterable[NewsItem], template_path: Path, output_path: Path) -> Path:
    item_list = list(items)
    article_html = build_article_html(item_list, template_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(article_html, encoding="utf-8")
    return output_path


def build_article_html(items: List[NewsItem], template_path: Path) -> str:
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
        body = merge_with_template(template, items)
    else:
        body = fallback_body(items)
    return (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8"><title>公众号推文</title></head>'
        f'<body><div class="rich_media_content"><div class="ProseMirror">{body}</div></div></body></html>'
    )


def merge_with_template(template: str, items: List[NewsItem]) -> str:
    soup = BeautifulSoup(template, "lxml")
    root = soup.select_one(".rich_media_content .ProseMirror")
    if root is None:
        return fallback_body(items)

    article = first_meaningful_child(root)
    if article is None:
        return fallback_body(items)

    children = [child for child in article.find_all(recursive=False)]
    hero_idx = find_child_index(children, "要闻速递")
    start_idx = hero_idx + 1 if hero_idx is not None else find_child_index(children, "要闻速览")
    end_idx = find_child_index(children, "end")
    if start_idx is None or end_idx is None or start_idx >= end_idx:
        return fallback_body(items)

    replacement = BeautifulSoup(build_news_middle(items), "lxml").body
    new_children = list(replacement.contents) if replacement else []
    anchor = children[end_idx]
    for child in children[start_idx:end_idx]:
        child.extract()
    for child in new_children:
        anchor.insert_before(child)
    return "".join(str(child) for child in root.contents)


def first_meaningful_child(root) -> object | None:
    for child in root.find_all(recursive=False):
        if child.name:
            return child
    return None


def find_child_index(children: List[object], needle: str) -> int | None:
    for index, child in enumerate(children):
        if needle in child.get_text(" ", strip=True):
            return index
    return None


def build_news_middle(items: List[NewsItem]) -> str:
    return overview_section(items) + separator_section() + "".join(news_item_sections(items))


def overview_section(items: List[NewsItem]) -> str:
    lines_list = []
    for idx, item in enumerate(items, start=1):
        margin = "0" if idx == len(items) else "0 0 6px"
        lines_list.append(
            f'<p style="margin: {margin};"><span>{idx}. {escape(item.title or "未填写标题")}</span></p>'
        )
    lines = "\n".join(lines_list)
    return f"""
<section style="margin-top: 10px;margin-bottom: 0;" powered-by="xiumi.us">
  <section style="display: inline-block;text-align: left;">
    <section style="border-left: 1px solid {ORANGE};">
      <section style="border-left: 5px solid {ORANGE};line-height: 1.5em;padding-left: 5px;">
        <section style="margin-top: 10px;margin-bottom: 10px;text-align: center;">
          <section style="display: inline-block;vertical-align: top;">
            <section style="margin-bottom: -6px;line-height: 1em;padding-left: 2px;padding-right: 2px;">
              <p><span>要闻速览</span></p>
            </section>
            <section style="width: 100%;height: 10px;background-color: {ORANGE};"></section>
          </section>
        </section>
      </section>
      <section style="margin-top: 10px;margin-left: 10px;">
        <section style="font-size: 15px;color: {ORANGE};text-align: justify;">
          {lines}
        </section>
      </section>
    </section>
  </section>
</section>
"""


def separator_section() -> str:
    return f"""
<section style="margin-top: 0;margin-bottom: 10px;text-align: center;" powered-by="xiumi.us">
  <section style="padding-right: 6px;padding-left: 6px;">
    <section style="border-bottom: 2px dotted {ORANGE};width: 100%;"></section>
  </section>
</section>
"""


def news_item_sections(items: List[NewsItem]) -> List[str]:
    result: List[str] = []
    for idx, item in enumerate(items, start=1):
        title = escape(item.title or "未填写标题")
        summary = escape(item.summary or "待补充摘要")
        link = item.link or item.official_link or ""
        link_html = (
            f'<a href="{escape_attr(link)}" target="_blank">{escape(link)}</a>'
            if link
            else '<span>待补充链接</span>'
        )
        result.append(
            f"""
<section style="margin-top: 0.5em;margin-bottom: 0.5em;" powered-by="xiumi.us">
  <section style="border-width: 0px 0px 1px;border-style: solid;border-bottom-color: {ORANGE};font-size: 15px;color: {ORANGE};">
    <p><br></p>
    <p><span>{idx}. {title}</span></p>
  </section>
</section>
<section style="margin-top: 10px;margin-bottom: 10px;" powered-by="xiumi.us">
  <section style="display: inline-block;width: 100%;border-width: 2px;border-style: dotted;border-color: {ORANGE};padding: 10px;box-sizing: border-box;">
    <section style="color: rgb(51, 51, 51);font-size: 15px;" powered-by="xiumi.us">
      <p><strong><span>摘要：</span></strong></p>
      <p>{summary}</p>
      <p><br></p>
      <p><strong><span>原文链接：</span></strong></p>
      <p>{link_html}</p>
    </section>
  </section>
</section>
"""
        )
    return result


def fallback_body(items: List[NewsItem]) -> str:
    return f'<section style="font-size: 16px;">{build_news_middle(items)}</section>'


def escape(value: str) -> str:
    return html.escape(value, quote=False)


def escape_attr(value: str) -> str:
    return html.escape(value, quote=True)








