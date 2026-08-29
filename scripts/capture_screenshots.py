"""用 Playwright 对演示应用截图，生成报告素材（report/screenshots/）。

用法：
  1. 先启动：streamlit run scripts/demo_app.py --server.port 8599 --server.headless true
  2. 再运行：python scripts/capture_screenshots.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

OUT = config.REPORT_DIR / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE_URL = "http://localhost:8599"

SECTIONS = [
    ("① Coding Agent", "module1_coding.png"),
    ("② 金融文档问答", "module2_docqa.png"),
    ("③ 金融数据分析", "module3_dataanalysis.png"),
    ("④ 数学建模", "module4_modeling.png"),
    ("🧾 Financial Agent", "overview.png"),
]


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000},
                                device_scale_factor=1.5)
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=120000)
        # 等待页面渲染完成（最后一个模块头部出现）
        try:
            page.wait_for_selector("text=④ 数学建模", timeout=180000)
        except Exception as e:
            print("等待渲染超时:", e)
        time.sleep(2)
        for header, fname in SECTIONS:
            try:
                loc = page.get_by_text(header, exact=False).first
                loc.evaluate("el => el.scrollIntoView({block: 'start'})")
                time.sleep(1.0)
                page.screenshot(path=str(OUT / fname))
                print("已截图", fname)
            except Exception as e:
                print("截图失败", header, e)
        # 首页顶部（封面/总览）
        try:
            page.evaluate("() => window.scrollTo(0, 0)")
            time.sleep(1.0)
            page.screenshot(path=str(OUT / "overview.png"))
        except Exception as e:
            print("overview 截图失败", e)
        browser.close()
    print("截图完成，保存到", OUT)


if __name__ == "__main__":
    main()
