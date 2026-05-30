"""
报告生成器 - 自动生成Markdown格式的分析报告（供RAG使用）
"""
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import DB_PATH, REPORTS_DIR


class ReportGenerator:
    """自动生成分析报告"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.reports_dir = Path(REPORTS_DIR)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def _query(self, sql: str) -> pd.DataFrame:
        """执行SQL查询"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return df

    def generate_rfm_report(self) -> str:
        """生成RFM分析报告"""
        df = self._query("SELECT * FROM rfm_results")

        if df.empty:
            return "暂无RFM分析数据，请先运行ETL和RFM分析。"

        total = len(df)
        segment_counts = df["segment"].value_counts()
        cluster_counts = df["cluster_label"].value_counts()

        avg_recency = df["recency"].mean()
        avg_frequency = df["frequency"].mean()
        avg_monetary = df["monetary"].mean()

        report = f"""# RFM客户价值分析报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**分析客户数**: {total:,}

## 一、总体概况

| 指标 | 平均值 | 最小值 | 最大值 | 中位数 |
|------|--------|--------|--------|--------|
| Recency (天) | {avg_recency:.1f} | {df['recency'].min()} | {df['recency'].max()} | {df['recency'].median():.0f} |
| Frequency (次) | {avg_frequency:.1f} | {df['frequency'].min()} | {df['frequency'].max()} | {df['frequency'].median():.0f} |
| Monetary (R$) | {avg_monetary:.2f} | {df['monetary'].min():.2f} | {df['monetary'].max():.2f} | {df['monetary'].median():.2f} |

## 二、客户分群分布

"""
        for segment, count in segment_counts.items():
            pct = count / total * 100
            strategy = self._get_strategy(segment)
            seg_df = df[df["segment"] == segment]
            report += f"### {segment}\n"
            report += f"- **人数**: {count:,} ({pct:.1f}%)\n"
            report += f"- **平均Recency**: {seg_df['recency'].mean():.1f} 天\n"
            report += f"- **平均Frequency**: {seg_df['frequency'].mean():.1f} 次\n"
            report += f"- **平均Monetary**: R${seg_df['monetary'].mean():.2f}\n"
            report += f"- **营销策略**: {strategy}\n\n"

        report += """## 三、聚类分析

基于KMeans聚类算法，将客户分为以下群体：

"""
        for cluster_id in sorted(cluster_counts.keys()):
            count = cluster_counts[cluster_id]
            cluster_df = df[df["cluster_label"] == cluster_id]
            report += f"### 群体 {cluster_id}\n"
            report += f"- **人数**: {count:,}\n"
            report += f"- **平均Recency**: {cluster_df['recency'].mean():.1f} 天\n"
            report += f"- **平均Frequency**: {cluster_df['frequency'].mean():.1f} 次\n"
            report += f"- **平均Monetary**: R${cluster_df['monetary'].mean():.2f}\n\n"

        # 需要挽留的客户分析
        retention_segments = ["重要挽留客户", "一般挽留客户"]
        report += "## 四、需要挽留的客户分析\n\n"
        for seg in retention_segments:
            if seg in segment_counts.index:
                seg_df = df[df["segment"] == seg]
                report += f"### {seg}\n"
                report += f"- **人数**: {len(seg_df):,} ({len(seg_df)/total*100:.1f}%)\n"
                report += f"- **平均Recency**: {seg_df['recency'].mean():.1f} 天（距上次购买）\n"
                report += f"- **平均Frequency**: {seg_df['frequency'].mean():.1f} 次\n"
                report += f"- **平均Monetary**: R${seg_df['monetary'].mean():.2f}\n"
                report += f"- **特征**: 长时间未购买，消费频率低\n"
                report += f"- **挽留策略**: {self._get_strategy(seg)}\n\n"

        report += """## 五、营销建议

1. **高价值客户**（重要价值/发展客户）：提供VIP专属服务、个性化推荐
2. **高潜力客户**（一般价值/发展客户）：通过优惠券和积分激励提升消费
3. **需唤醒客户**（重要保持/挽留客户）：发送限时优惠，电话回访
4. **低活跃客户**（一般保持/挽留客户）：自动化邮件维护，低成本运营

---
*本报告由RFM分析引擎自动生成*
"""
        return report

    def generate_sales_report(self) -> str:
        """生成销售分析报告"""
        # 按月统计
        monthly = self._query("""
            SELECT
                strftime('%Y-%m', order_purchase_timestamp) as month,
                COUNT(DISTINCT o.order_id) as order_count,
                SUM(op.payment_value) as total_revenue,
                COUNT(DISTINCT o.customer_id) as customer_count
            FROM orders o
            JOIN order_payments op ON o.order_id = op.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY month
            ORDER BY month
        """)

        # 按类目统计
        categories = self._query("""
            SELECT
                COALESCE(ct.product_category_name_english, p.product_category_name) as category,
                COUNT(DISTINCT oi.order_id) as order_count,
                SUM(oi.price) as total_revenue,
                AVG(oi.price) as avg_price
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name
            GROUP BY category
            ORDER BY total_revenue DESC
            LIMIT 15
        """)

        # 支付方式统计
        payments = self._query("""
            SELECT
                payment_type,
                COUNT(*) as count,
                SUM(payment_value) as total_value
            FROM order_payments
            GROUP BY payment_type
            ORDER BY total_value DESC
        """)

        # 客户地理分布
        geo = self._query("""
            SELECT
                customer_state,
                COUNT(DISTINCT customer_id) as customer_count
            FROM customers
            GROUP BY customer_state
            ORDER BY customer_count DESC
            LIMIT 10
        """)

        report = f"""# 销售分析报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 一、月度销售趋势

| 月份 | 订单数 | 总收入 (R$) | 客户数 |
|------|--------|------------|--------|
"""
        for _, row in monthly.iterrows():
            report += f"| {row['month']} | {row['order_count']:,} | {row['total_revenue']:,.2f} | {row['customer_count']:,} |\n"

        report += f"""
## 二、类目销售TOP15

| 类目 | 订单数 | 总收入 (R$) | 平均价格 (R$) |
|------|--------|------------|--------------|
"""
        for _, row in categories.iterrows():
            report += f"| {row['category']} | {row['order_count']:,} | {row['total_revenue']:,.2f} | {row['avg_price']:.2f} |\n"

        report += f"""
## 三、支付方式分布

| 支付方式 | 笔数 | 总金额 (R$) |
|---------|------|------------|
"""
        for _, row in payments.iterrows():
            report += f"| {row['payment_type']} | {row['count']:,} | {row['total_value']:,.2f} |\n"

        report += f"""
## 四、客户地域分布TOP10

| 州 | 客户数 |
|----|--------|
"""
        for _, row in geo.iterrows():
            report += f"| {row['customer_state']} | {row['customer_count']:,} |\n"

        report += "\n---\n*本报告由销售分析模块自动生成*\n"
        return report

    def _get_strategy(self, segment: str) -> str:
        """获取营销策略"""
        strategies = {
            "重要价值客户": "VIP维护，专属优惠，优先客服",
            "重要发展客户": "提升复购频率，个性化推荐",
            "重要保持客户": "唤醒召回，限时优惠券",
            "重要挽留客户": "重点挽留，大额优惠券，电话回访",
            "一般价值客户": "提升客单价，交叉销售",
            "一般发展客户": "培养消费习惯，新客礼包",
            "一般保持客户": "定期触达，节日关怀",
            "一般挽留客户": "低成本维护，自动化邮件",
        }
        return strategies.get(segment, "暂无策略")

    def save_report(self, content: str, report_type: str, title: str) -> str:
        """保存报告到文件和数据库"""
        # 保存到文件
        filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = self.reports_dir / filename
        filepath.write_text(content, encoding="utf-8")

        # 保存到数据库
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO analysis_reports (report_type, title, content, created_at) VALUES (?, ?, ?, ?)",
            (report_type, title, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()

        return str(filepath)

    def generate_all_reports(self) -> list:
        """生成所有分析报告"""
        print("[REPORT] 开始生成分析报告...")

        reports = []

        # RFM报告
        rfm_report = self.generate_rfm_report()
        path = self.save_report(rfm_report, "rfm_analysis", "RFM客户价值分析报告")
        reports.append(("rfm_analysis", path))
        print(f"  [OK] RFM报告: {path}")

        # 销售报告
        sales_report = self.generate_sales_report()
        path = self.save_report(sales_report, "sales_analysis", "销售分析报告")
        reports.append(("sales_analysis", path))
        print(f"  [OK] 销售报告: {path}")

        print(f"\n[OK] 报告生成完成！共 {len(reports)} 份")
        return reports


if __name__ == "__main__":
    generator = ReportGenerator()
    generator.generate_all_reports()
