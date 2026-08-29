"""生成示例数据：金融数据分析用的 Excel/CSV，以及金融文档问答用的示例年报 PDF。

用法：python experiments/prepare_data.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def make_financial_excel(path):
    import pandas as pd
    # 华辰科技 2021-2023 财务数据（单位：元）
    data = {
        "年份": [2021, 2022, 2023],
        "营业收入": [2_580_000_000, 3_120_000_000, 3_584_000_000],
        "营业成本": [1_720_000_000, 2_050_000_000, 2_330_000_000],
        "毛利": [860_000_000, 1_070_000_000, 1_254_000_000],
        "净利润": [320_000_000, 410_000_000, 480_000_000],
        "总资产": [3_900_000_000, 4_600_000_000, 5_100_000_000],
        "总负债": [2_000_000_000, 2_300_000_000, 2_450_000_000],
        "所有者权益": [1_900_000_000, 2_300_000_000, 2_650_000_000],
    }
    df = pd.DataFrame(data)
    df.to_excel(path, index=False)
    print("生成", path)


def make_stock_csv(path):
    import pandas as pd
    rng = random.Random(7)
    dates = pd.date_range("2023-01-02", periods=250, freq="B")
    price = 50.0
    rows = []
    for d in dates:
        ret = rng.gauss(0.0006, 0.018)
        price *= (1 + ret)
        rows.append({"日期": d.strftime("%Y-%m-%d"), "收盘价": round(price, 2)})
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print("生成", path)


def make_credit_csv(path):
    import pandas as pd
    rng = random.Random(11)
    names = ["华辰科技", "蓝海能源", "恒基制造", "中远物流", "新锐电子",
             "绿源环保", "天工机械", "丰泰食品", "远景通信", "奥维医疗"]
    rows = []
    for n in names:
        rows.append({
            "企业名称": n,
            "流动比率": round(rng.uniform(1.1, 2.6), 2),
            "速动比率": round(rng.uniform(0.7, 1.9), 2),
            "资产负债率(%)": round(rng.uniform(35, 78), 1),
            "营业收入增长率(%)": round(rng.uniform(-8, 35), 1),
            "净利润增长率(%)": round(rng.uniform(-12, 40), 1),
            "ROA(%)": round(rng.uniform(2.5, 14.0), 2),
            "ROE(%)": round(rng.uniform(5.0, 22.0), 2),
            "销售毛利率(%)": round(rng.uniform(18, 52), 1),
        })
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print("生成", path)


def make_sample_pdf(path):
    """用 reportlab 生成一份结构化的示例年度报告 PDF（含文字与财务报表表格）。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle, PageBreak)
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm

    # 注册中文字体（reportlab 内置 CID 字体，支持中文）
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    styles = getSampleStyleSheet()
    for s in styles.byName.values():
        s.fontName = "STSong-Light"
    story = []
    title = styles["Title"]
    h1, h2 = styles["Heading1"], styles["Heading2"]
    body = styles["BodyText"]

    story.append(Paragraph("华辰科技股份有限公司 2023 年年度报告", title))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("证券代码：600888    证券简称：华辰科技", body))
    story.append(PageBreak())

    story.append(Paragraph("第一节 公司基本情况", h1))
    story.append(Paragraph(
        "华辰科技股份有限公司（以下简称\"公司\"或\"华辰科技\"）成立于 2005 年，"
        "总部位于深圳市南山区，是一家专注于工业自动化和智能制造设备研发、生产与销售的高新技术企业。"
        "报告期内，公司业务覆盖工业机器人、智能物流装备和工业软件三大板块，产品远销欧洲、东南亚等地区。"
        "截至 2023 年 12 月 31 日，公司员工总数为 8,420 人，其中研发人员 1,960 人。", body))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("第二节 主要会计数据和财务指标", h1))
    story.append(Paragraph("报告期内主要会计数据如下表所示：", body))
    story.append(Spacer(1, 0.3 * cm))

    fin_data = [
        ["项目", "2023年", "2022年", "2021年"],
        ["营业收入（元）", "3,584,000,000", "3,120,000,000", "2,580,000,000"],
        ["营业成本（元）", "2,330,000,000", "2,050,000,000", "1,720,000,000"],
        ["毛利（元）", "1,254,000,000", "1,070,000,000", "860,000,000"],
        ["净利润（元）", "480,000,000", "410,000,000", "320,000,000"],
        ["总资产（元）", "5,100,000,000", "4,600,000,000", "3,900,000,000"],
        ["总负债（元）", "2,450,000,000", "2,300,000,000", "2,000,000,000"],
        ["所有者权益（元）", "2,650,000,000", "2,300,000,000", "1,900,000,000"],
        ["基本每股收益（元/股）", "1.92", "1.64", "1.28"],
        ["加权平均净资产收益率", "18.10%", "17.83%", "16.84%"],
    ]
    t = Table(fin_data, colWidths=[5.5 * cm, 3.2 * cm, 3.2 * cm, 3.2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E5E8C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF1F8")]),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "2023 年度，公司实现营业收入 35.84 亿元，同比增长 14.87%；实现归属于上市公司股东的净利润 4.80 亿元，"
        "同比增长 17.07%。营业收入的增长主要来源于智能制造装备业务的放量以及海外市场收入占比的提升。", body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("第三节 管理层讨论与分析", h1))
    story.append(Paragraph(
        "报告期内，公司毛利率为 34.99%，较上年同期提升 0.70 个百分点，主要得益于产品结构优化与供应链降本。"
        "公司资产负债率为 48.04%，处于行业合理水平。经营活动产生的现金流量净额为 5.10 亿元，现金流状况良好。"
        "研发投入 6.10 亿元，占营业收入的 17.02%。", body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("第四节 财务报表（节选）", h1))
    story.append(Paragraph("4.1 合并利润表（节选，单位：元）", h2))
    income = [
        ["项目", "本期金额", "上期金额"],
        ["一、营业收入", "3,584,000,000", "3,120,000,000"],
        ["    减：营业成本", "2,330,000,000", "2,050,000,000"],
        ["二、营业利润", "540,000,000", "460,000,000"],
        ["三、利润总额", "538,000,000", "458,000,000"],
        ["四、净利润", "480,000,000", "410,000,000"],
    ]
    t2 = Table(income, colWidths=[6 * cm, 3.5 * cm, 3.5 * cm])
    t2.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("4.2 合并资产负债表（节选，单位：元）", h2))
    bal = [
        ["项目", "期末余额", "期初余额"],
        ["流动资产：货币资金", "1,120,000,000", "950,000,000"],
        ["应收账款", "680,000,000", "590,000,000"],
        ["存货", "520,000,000", "460,000,000"],
        ["流动资产合计", "2,720,000,000", "2,310,000,000"],
        ["非流动资产合计", "2,380,000,000", "2,290,000,000"],
        ["资产总计", "5,100,000,000", "4,600,000,000"],
        ["负债合计", "2,450,000,000", "2,300,000,000"],
        ["所有者权益合计", "2,650,000,000", "2,300,000,000"],
    ]
    t3 = Table(bal, colWidths=[6 * cm, 3.5 * cm, 3.5 * cm])
    t3.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
    ]))
    story.append(t3)
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("第五节 公司治理与股东情况", h1))
    story.append(Paragraph(
        "报告期内公司共召开 12 次董事会会议、6 次股东大会，均依法合规。"
        "前十大股东合计持股比例为 42.35%。公司董事会下设战略、审计、提名、薪酬与考核四个专门委员会。", body))
    story.append(Paragraph(
        "公司注重投资者回报，2023 年度拟每 10 股派发现金红利 4.50 元（含税）。", body))

    SimpleDocTemplate(str(path), pagesize=A4).build(story)
    print("生成", path)


def make_portfolio_csv(path):
    """三只资产的日收益率序列（投资组合优化用）。"""
    import pandas as pd
    rng = random.Random(13)
    dates = pd.date_range("2023-01-02", periods=250, freq="B")
    assets = {"沪深300ETF": (0.0005, 0.012), "中证500ETF": (0.0008, 0.016),
              "国债ETF": (0.0002, 0.002)}
    rows = []
    for d in dates:
        row = {"日期": d.strftime("%Y-%m-%d")}
        for name, (mu, sigma) in assets.items():
            row[name] = round(rng.gauss(mu, sigma), 6)
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print("生成", path)


def make_announcement_pdf(path):
    """生成第二份测试 PDF：董事会公告。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle, PageBreak)
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    for s in styles.byName.values():
        s.fontName = "STSong-Light"
    title, h1, body = styles["Title"], styles["Heading1"], styles["BodyText"]

    story = []
    story.append(Paragraph("华辰科技股份有限公司 2023 年年度权益分派实施公告", title))
    story.append(Paragraph("证券代码：600888    证券简称：华辰科技", body))
    story.append(PageBreak())

    story.append(Paragraph("一、分红方案", h1))
    story.append(Paragraph(
        "华辰科技股份有限公司（以下简称\"公司\"）2023 年年度利润分配方案已获公司 2024 年 4 月 26 日"
        "召开的 2023 年年度股东大会审议通过。公司 2023 年度权益分派方案为：以公司总股本 250,000,000 股"
        "为基数，向全体股东每 10 股派发现金红利 4.50 元（含税），合计派发现金红利 112,500,000 元。", body))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("二、除权除息安排", h1))
    story.append(Paragraph(
        "本次权益分派股权登记日为 2024 年 5 月 20 日，除权除息日为 2024 年 5 月 21 日。"
        "现金红利将于 2024 年 5 月 21 日通过托管券商直接划入股东资金账户。", body))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("三、相关数据", h1))
    div = [
        ["项目", "数值"],
        ["总股本（股）", "250,000,000"],
        ["每 10 股派现金红利（元，含税）", "4.50"],
        ["派发现金红利总额（元）", "112,500,000"],
        ["股权登记日", "2024-05-20"],
        ["除权除息日", "2024-05-21"],
    ]
    t = Table(div, colWidths=[8 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
    ]))
    story.append(t)

    SimpleDocTemplate(str(path), pagesize=A4).build(story)
    print("生成", path)


def main():
    make_financial_excel(config.SAMPLE_DATA_DIR / "示例公司财务数据.xlsx")
    make_stock_csv(config.SAMPLE_DATA_DIR / "示例股票日收盘价.csv")
    make_credit_csv(config.SAMPLE_DATA_DIR / "企业信用评价示例数据.csv")
    make_portfolio_csv(config.SAMPLE_DATA_DIR / "投资组合日收益率.csv")
    make_sample_pdf(config.PDF_DIR / "示例财务报告.pdf")
    make_announcement_pdf(config.PDF_DIR / "示例分红公告.pdf")


if __name__ == "__main__":
    main()
