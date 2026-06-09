import logging
import random
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://quotes.toscrape.com"
TARGET_PATH = "/js"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def load_robots(base_url: str) -> RobotFileParser:
    rp = RobotFileParser()
    robots_url = urljoin(base_url, "/robots.txt")
    rp.set_url(robots_url)
    try:
        rp.read()
        logger.info("robots.txt を読み込みました")
    except Exception:
        logger.info("robots.txt が存在しません。全パスを許可扱いにします")
    return rp


def next_page_url(page) -> Optional[str]:
    next_btn = page.query_selector("li.next > a")
    if not next_btn:
        return None
    href = next_btn.get_attribute("href")
    return urljoin(BASE_URL, href) if href else None


def save_markdown(quotes: list, output_path: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# Quotes to Scrape — {today}",
        "",
        f"収集件数: {len(quotes)} 件",
        "",
        "| # | 名言 | 著者 |",
        "|---|------|------|",
    ]
    for i, q in enumerate(quotes, 1):
        text = q["text"].replace("|", "\\|")
        author = q["author"].replace("|", "\\|")
        lines.append(f"| {i} | {text} | {author} |")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info(f"Markdown を保存しました: {output_path}")


def main() -> None:
    rp = load_robots(BASE_URL)
    today = datetime.now().strftime("%Y%m%d")
    md_path = f"quotes_{today}.md"
    png_path = f"quotes_{today}.png"

    all_quotes = []
    url = BASE_URL + TARGET_PATH
    page_num = 1
    screenshot_taken = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        while url:
            if not rp.can_fetch(USER_AGENT, url):
                logger.warning(f"robots.txt によりアクセス禁止: {url}")
                break

            logger.info(f"ページ {page_num} を取得中: {url}")
            try:
                page.goto(url, timeout=15000)
                # JS描画完了を待つ
                page.wait_for_selector("div.quote", timeout=10000)
            except PlaywrightTimeoutError as e:
                logger.error(f"タイムアウト: {e}")
                break
            except Exception as e:
                logger.error(f"接続エラー: {e}")
                raise SystemExit(1)

            # 1ページ目のみスクリーンショット
            if not screenshot_taken:
                page.screenshot(path=png_path, full_page=True)
                logger.info(f"スクリーンショットを保存しました: {png_path}")
                screenshot_taken = True

            quote_elements = page.query_selector_all("div.quote")
            for el in quote_elements:
                text = el.query_selector("span.text").inner_text().strip()
                author = el.query_selector("small.author").inner_text().strip()
                all_quotes.append({"text": text, "author": author})

            logger.info(f"  → {len(quote_elements)} 件取得（累計: {len(all_quotes)} 件）")

            next_url = next_page_url(page)
            if next_url:
                wait = random.uniform(1, 3)
                logger.info(f"  次ページ前に {wait:.1f} 秒待機")
                time.sleep(wait)
                url = next_url
                page_num += 1
            else:
                url = None

        browser.close()

    save_markdown(all_quotes, md_path)


if __name__ == "__main__":
    main()
