"""
KMeans聚类分析模块 - 基于RFM指标进行用户聚类

增强版:
- Log1p 变换后 StandardScaler
- 双指标选K: 肘部法 + 轮廓系数
- 聚类画像含策略建议
"""
import sqlite3

import numpy as np
import pandas as pd

from config import DB_PATH
from utils.timing import get_perf_logger, TimerContext


class RFMClustering:
    """基于KMeans的RFM聚类分析（增强版）"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.scaler = None
        self.kmeans = None
        self.inertias = []
        self.silhouettes = []

    def _load_rfm_data(self) -> pd.DataFrame:
        """加载RFM数据"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM rfm_results", conn)
        conn.close()
        return df

    def _find_optimal_k(self, scaled_data: np.ndarray, max_k: int = 10) -> int:
        """使用肘部法 + 轮廓系数确定最优K值"""
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        max_k = min(max_k, len(scaled_data) - 1, 10)
        if max_k < 3:
            return 3

        self.inertias = []
        self.silhouettes = []
        K_range = range(2, max_k + 1)

        for k in K_range:
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(scaled_data)
            self.inertias.append(km.inertia_)
            self.silhouettes.append(silhouette_score(scaled_data, labels))

        # 肘部法: 二阶差分最大
        if len(self.inertias) >= 3:
            diffs = np.diff(self.inertias)
            diff2 = np.diff(diffs)
            elbow_k = list(K_range)[np.argmax(diff2) + 1]
        else:
            elbow_k = 4

        # 轮廓系数: 最大值对应的K
        silhouette_k = list(K_range)[np.argmax(self.silhouettes)]

        # 综合决策: 如果两个指标一致，直接采用；否则优先轮廓系数
        if elbow_k == silhouette_k:
            optimal_k = elbow_k
        else:
            optimal_k = silhouette_k
            print(f"  [INFO] 肘部法建议K={elbow_k}, 轮廓系数建议K={silhouette_k}, 采用轮廓系数")

        # 保证最少3个聚类
        return max(3, optimal_k)

    def cluster(self, n_clusters: int = None) -> pd.DataFrame:
        """
        执行KMeans聚类

        Args:
            n_clusters: 聚类数量，None则自动选择

        Returns:
            DataFrame: 添加了聚类标签的RFM数据
        """
        perf = get_perf_logger()
        with TimerContext("kmeans_cluster", perf):
            print("[CLUSTER] 开始KMeans聚类分析...")
            df = self._load_rfm_data()

            if len(df) < 10:
                print("  [WARN] 数据量不足，跳过聚类")
                df["cluster_label"] = 0
                return df

            # Log1p 变换 + StandardScaler
            from sklearn.preprocessing import StandardScaler
            from sklearn.cluster import KMeans

            rfm_features = df[["recency", "frequency", "monetary"]].values
            rfm_log = np.log1p(rfm_features)
            self.scaler = StandardScaler()
            scaled = self.scaler.fit_transform(rfm_log)

            # 确定聚类数量
            if n_clusters is None:
                n_clusters = self._find_optimal_k(scaled)
            n_clusters = max(2, min(n_clusters, 8))

            print(f"  [INFO] 聚类数量: {n_clusters}")

            # 执行KMeans
            self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            df["cluster_label"] = self.kmeans.fit_predict(scaled)

            # 生成聚类画像
            cluster_profiles = self._generate_cluster_profiles(df)
            print(f"\n  聚类画像:")
            for profile in cluster_profiles:
                print(f"    群体{profile['cluster']}: {profile['description']}")

            # 保存聚类结果到数据库
            self._save_cluster_labels(df)

            return df

    def _generate_cluster_profiles(self, df: pd.DataFrame) -> list:
        """生成聚类画像描述"""
        profiles = []
        cluster_stats = df.groupby("cluster_label").agg({
            "recency": "mean",
            "frequency": "mean",
            "monetary": "mean",
            "customer_id": "count"
        }).rename(columns={"customer_id": "count"})

        # 全局均值
        global_avg = df[["recency", "frequency", "monetary"]].mean()

        for cluster_id, row in cluster_stats.iterrows():
            traits = []
            r_ratio = row["recency"] / global_avg["recency"]
            f_ratio = row["frequency"] / global_avg["frequency"]
            m_ratio = row["monetary"] / global_avg["monetary"]

            if r_ratio < 0.8:
                traits.append("近期活跃")
            elif r_ratio > 1.2:
                traits.append("较长时间未购")

            if f_ratio > 1.3:
                traits.append("高频购买")
            elif f_ratio < 0.7:
                traits.append("低频购买")

            if m_ratio > 1.3:
                traits.append("高消费")
            elif m_ratio < 0.7:
                traits.append("低消费")

            description = "、".join(traits) if traits else "中等消费群体"

            profiles.append({
                "cluster": cluster_id,
                "count": int(row["count"]),
                "avg_recency": round(row["recency"], 1),
                "avg_frequency": round(row["frequency"], 1),
                "avg_monetary": round(row["monetary"], 2),
                "description": description,
            })

        return profiles

    def _save_cluster_labels(self, df: pd.DataFrame) -> None:
        """保存聚类标签到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        updates = [(int(row["cluster_label"]), row["customer_id"]) for _, row in df.iterrows()]
        cursor.executemany(
            "UPDATE rfm_results SET cluster_label = ? WHERE customer_id = ?",
            updates
        )
        conn.commit()
        conn.close()
        print(f"  [OK] 聚类标签已更新到数据库")

    def get_cluster_centers(self) -> pd.DataFrame:
        """获取聚类中心（用于雷达图）"""
        if self.kmeans is None:
            return pd.DataFrame()

        # 逆变换: StandardScaler逆 -> expm1逆log1p
        centers_scaled = self.kmeans.cluster_centers_
        centers_log = self.scaler.inverse_transform(centers_scaled)
        centers = np.expm1(centers_log)  # 逆log1p变换

        return pd.DataFrame(
            centers, columns=["recency", "frequency", "monetary"]
        ).round(2)

    def get_selection_metrics(self) -> dict:
        """获取K选择指标（用于可视化）"""
        return {
            "k_range": list(range(2, 2 + len(self.inertias))),
            "inertias": self.inertias,
            "silhouettes": self.silhouettes,
        }


if __name__ == "__main__":
    clustering = RFMClustering()
    results = clustering.cluster()
    print("\n聚类结果:")
    print(results["cluster_label"].value_counts().to_string())
