import logging
import random
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"
USER_AGENT = "Mozilla/5.0 (compatible; BookScraper/1.0)"

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
        # robots.txt が存在しない場合は全パス許可として扱う
        logger.info("robots.txt が存在しません。全パスを許可扱いにします")
    return rp


def can_fetch(rp: RobotFileParser, url: str) -> bool:
    return rp.can_fetch(USER_AGENT, url)


def get_page(session: requests.Session, url: str) -> BeautifulSoup:
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"接続エラー: {e}")
        raise SystemExit(1)
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTPエラー: {e}")
        raise SystemExit(1)
    except requests.exceptions.Timeout as e:
        logger.error(f"タイムアウト: {e}")
        raise SystemExit(1)


def parse_books(soup: BeautifulSoup) -> list[dict]:
    books = []
    for article in soup.select("article.product_pod"):
        title = article.select_one("h3 > a")["title"]
        price = article.select_one("p.price_color").text.strip()
        availability = article.select_one("p.availability").text.strip()
        books.append({"title": title, "price": price, "availability": availability})
    return books


def next_page_url(soup: BeautifulSoup, current_url: str) -> Optional[str]:
    next_btn = soup.select_one("li.next > a")
    if not next_btn:
        return None
    # カタログの相対パスを解決する
    current_dir = current_url.rsplit("/", 1)[0] + "/"
    return urljoin(current_dir, next_btn["href"])


def save_markdown(books: list[dict], output_path: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# Books to Scrape — {today}",
        "",
        f"収集件数: {len(books)} 件",
        "",
        "| # | タイトル | 価格 | 在庫状況 |",
        "|---|---------|------|---------|",
    ]
    for i, book in enumerate(books, 1):
        lines.append(f"| {i} | {book['title']} | {book['price']} | {book['availability']} |")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info(f"結果を保存しました: {output_path}")


def main() -> None:
    rp = load_robots(BASE_URL)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    all_books: list[dict] = []
    url = BASE_URL
    page = 1

    while url:
        if not can_fetch(rp, url):
            logger.warning(f"robots.txt によりアクセス禁止: {url}")
            break

        logger.info(f"ページ {page} を取得中: {url}")
        soup = get_page(session, url)
        books = parse_books(soup)
        all_books.extend(books)
        logger.info(f"  → {len(books)} 件取得（累計: {len(all_books)} 件）")

        url = next_page_url(soup, url)
        if url:
            wait = random.uniform(1, 3)
            logger.info(f"  次ページ前に {wait:.1f} 秒待機")
            time.sleep(wait)
            page += 1

    today = datetime.now().strftime("%Y%m%d")
    output_path = f"books_{today}.md"
    save_markdown(all_books, output_path)


if __name__ == "__main__":
    main()
