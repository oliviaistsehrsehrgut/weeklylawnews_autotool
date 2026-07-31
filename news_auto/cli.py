from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
from typing import List

from .classify import apply_rule_classification, sort_items
from .config import load_config
from .fetch_article import fetch_items
from .ingest_text import dedupe_items, items_from_file, items_from_text
from .ingest_wk import fetch_wk_list
from .llm import enrich_with_llm, llm_enabled
from .models import NewsItem
from .official_discovery import discover_official_sources
from .output_naming import next_word_path
from .parse_reviewed_docx import parse_reviewed_docx
from .render_docx import render_word_draft
from .render_wechat import render_wechat_html
from .storage import prepare_debug_dir, write_jsonl
from .upload_wechat import upload_to_wechat_editor


def main() -> None:
    parser = argparse.ArgumentParser(description="法律新闻采集整理工具")
    subparsers = parser.add_subparsers(dest="command")

    draft_parser = subparsers.add_parser("draft", help="生成 Word 初稿")
    draft_parser.add_argument("--input-file", type=Path, help="包含链接的文本文件")
    draft_parser.add_argument("--input-text", help="直接传入包含链接的文本")
    draft_parser.add_argument("--week-start", required=True, help="起始日期，例如 2026-07-20")
    draft_parser.add_argument("--week-end", required=True, help="结束日期，例如 2026-07-26")
    draft_parser.add_argument("--config", type=Path, default=Path("config.toml"))
    draft_parser.add_argument("--output-dir", type=Path)
    draft_parser.add_argument("--wk", action="store_true", help="抓取威科公开列表候选")
    draft_parser.add_argument("--wk-cookie", default="", help="可选威科 Cookie")
    draft_parser.add_argument("--no-llm", action="store_true", help="不调用 LLM，仅生成占位摘要")
    draft_parser.add_argument("--limit", type=int, default=0, help="限制处理条数，调试用")
    draft_parser.add_argument("--no-official-search", action="store_true", help="不主动搜索规范性文件官方原文")

    wechat_parser = subparsers.add_parser("wechat", help="从审查后的 Word 生成公众号 HTML")
    wechat_parser.add_argument("--reviewed-docx", required=True, type=Path, help="人工审查后的 Word 文件")
    wechat_parser.add_argument("--config", type=Path, default=Path("config.toml"))
    wechat_parser.add_argument("--template", type=Path, help="公众号编辑器 HTML 模板")
    wechat_parser.add_argument("--output", type=Path, help="输出 HTML 路径")

    upload_parser = subparsers.add_parser("upload-wechat", help="半自动打开公众号后台并粘贴 HTML")
    upload_parser.add_argument("--html", required=True, type=Path, help="由 wechat 命令生成的 HTML")
    upload_parser.add_argument("--editor-url", required=True, help="公众号图文编辑页 URL")
    upload_parser.add_argument("--config", type=Path, default=Path("config.toml"))
    upload_parser.add_argument("--profile-dir", type=Path, help="浏览器登录状态保存目录")
    upload_parser.add_argument("--title", default="", help="可选：自动填写标题")
    upload_parser.add_argument("--auto-save", action="store_true", help="实验功能：自动点击保存为草稿")

    args = parser.parse_args()
    if args.command == "draft":
        run_draft(args)
    elif args.command == "wechat":
        run_wechat(args)
    elif args.command == "upload-wechat":
        run_upload_wechat(args)
    else:
        parser.print_help()


def run_draft(args: argparse.Namespace) -> None:
    root = Path.cwd()
    config = load_config(args.config)
    output_dir = args.output_dir or root / config["paths"]["output_dir"]
    week_start = parse_date(args.week_start)
    week_end = parse_date(args.week_end)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    items: List[NewsItem] = []
    if args.input_file:
        items.extend(items_from_file(args.input_file))
    if args.input_text:
        items.extend(items_from_text(args.input_text))
    if args.wk or config.get("wk", {}).get("enabled"):
        wk_cfg = config.get("wk", {})
        cookie = args.wk_cookie or wk_cfg.get("cookie", "")
        items.extend(
            fetch_wk_list(
                wk_cfg.get("list_url", "https://law.wkinfo.com.cn/news/list"),
                cookie=cookie,
                week_start=week_start,
                week_end=week_end,
            )
        )
    items = dedupe_items(items)
    if args.limit:
        items = items[: args.limit]
    if not items:
        raise SystemExit("未找到任何候选链接。请通过 --input-file 或 --input-text 提供链接文本。")

    print(f"候选新闻：{len(items)} 条")
    authority_tokens = config.get("official", {}).get("authority_tokens", [])
    fetched = fetch_items(items, authority_tokens=authority_tokens)
    paths_cfg = config["paths"]
    debug_dir = prepare_debug_dir(
        output_dir,
        debug_dir_name=paths_cfg.get("debug_dir", ".debug"),
        keep_count=int(paths_cfg.get("debug_keep_count", 20)),
    )
    write_jsonl(debug_dir / f"items_raw_{stamp}.jsonl", fetched)

    official_search_enabled = config.get("official_search", {}).get("enabled", True)
    if args.no_official_search or not official_search_enabled:
        print("官网识别：已启用；主动搜索：已关闭")
        write_jsonl(debug_dir / f"items_sources_{stamp}.jsonl", fetched)
    else:
        before = sum(1 for item in fetched if item.official_link)
        fetched = discover_official_sources(fetched, config)
        after = sum(1 for item in fetched if item.official_link)
        print(f"官方原文发现：已有 {before} 条，处理后 {after} 条")
        write_jsonl(debug_dir / f"items_sources_{stamp}.jsonl", fetched)

    classified = apply_rule_classification(fetched, config["filters"]["keywords"])
    if args.no_llm:
        print("LLM：已通过 --no-llm 禁用")
    elif llm_enabled(config):
        print("LLM：已启用，开始调用接口...")
    else:
        print("LLM：未启用或配置不完整，使用占位摘要")
    if not args.no_llm:
        classified = enrich_with_llm(classified, config)
        llm_errors = [item for item in classified if item.metadata.get("llm_error")]
        if llm_errors:
            print(f"LLM：{len(llm_errors)} 条失败，{len(classified) - len(llm_errors)} 条成功")
            print(f"LLM错误示例：{llm_errors[0].metadata['llm_error']}")
        else:
            print(f"LLM：{len(classified)} 条全部处理成功")
    final_items = sort_items(classified)
    if not final_items and classified:
        print("提示：没有候选命中筛选关键词，已将全部候选保留到 Word 供人工复核。")
        for item in classified:
            item.include = True
            if not item.reason:
                item.reason = "未命中关键词，已保留供人工复核"
        final_items = classified
    write_jsonl(debug_dir / f"items_final_{stamp}.jsonl", final_items)

    template_path = root / config["paths"]["word_template"]
    docx_path = next_word_path(output_dir, week_end)
    render_word_draft(
        final_items,
        template_path,
        docx_path,
        authority_tokens=authority_tokens,
        non_official_warning=config.get("official", {}).get(
            "non_official_warning", "【可能非官方网站，待核实修改】"
        ),
    )

    print(f"已生成调试清单：{debug_dir}")
    print(f"已生成 Word 初稿：{docx_path}")


def run_wechat(args: argparse.Namespace) -> None:
    root = Path.cwd()
    config = load_config(args.config)
    output_dir = root / config["paths"].get("output_dir", "output")
    template_path = args.template or root / config["paths"].get("wechat_template", "templates/公众号编辑器模板.html")
    output_path = args.output or output_dir / f"公众号推文_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    items = parse_reviewed_docx(args.reviewed_docx)
    if not items:
        raise SystemExit("未能从 Word 中解析出任何新闻条目。请确认格式包含标题、摘要：、原文链接：。")
    render_wechat_html(items, template_path, output_path)
    print(f"已解析 Word 条目：{len(items)} 条")
    print(f"已生成公众号 HTML：{output_path}")


def run_upload_wechat(args: argparse.Namespace) -> None:
    root = Path.cwd()
    config = load_config(args.config)
    profile_dir = args.profile_dir or root / config["paths"].get("wechat_profile_dir", ".wechat-browser")
    upload_to_wechat_editor(
        html_path=args.html,
        editor_url=args.editor_url,
        profile_dir=profile_dir,
        title=args.title,
        auto_save=args.auto_save,
    )


def parse_date(value: str) -> date:
    return date.fromisoformat(value)






