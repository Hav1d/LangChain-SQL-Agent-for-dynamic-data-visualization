"""
KMeans聚类分析模块 - 基于RFM指标进行用户聚类
"""
import sqlite3

import numpy as np
import pandas as pd

from config import DB_PATH


class RFMClustering:
    """基于KMeans的RFM聚类分析"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.scaler = None
        self.kmeans = None

    def _load_rfm_data(self) -> pd.DataFrame:
        """加载RFM数据"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM rfm_results", conn)
        conn.close()
        return df

    def _find_optimal_k(self, scaled_data: np.ndarray, max_k: int = 10) -> int:
        """使用肘部法则确定最优K值（最少3个聚类以保证分析有意义）"""
        max_k = min(max_k, len(scaled_data) - 1, 10)
        if max_k < 3:
            return 3

        inertias = []
        K_range = range(2, max_k + 1)

        from sklearn.cluster import KMeans
        for k in K_range:
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            km.fit(scaled_data)
            inertias.append(km.inertia_)

        # 计算肘部点（二阶差分最大）
        if len(inertias) >= 3:
            diffs = np.diff(inertias)
            diff2 = np.diff(diffs)
            optimal_k = list(K_range)[np.argmax(diff2) + 1]
        else:
            optimal_k = 4

        # 保证最少3个聚类，使RFM分析有实际意义
        return max(3, optimal_k)

    def cluster(self, n_clusters: int = None) -> pd.DataFrame:
        """
        执行KMeans聚类

        Args:
            n_clusters: 聚类数量，None则自动选择

        Returns:
            DataFrame: 添加了聚类标签的RFM数据
        """
        print("[CLUSTER] 开始KMeans聚类分析...")
        df = self._load_rfm_data()

        if len(df) < 10:
            print("  [WARN] 数据量不足，跳过聚类")
            df["cluster_label"] = 0
            return df

        # 标准化RFM指标
        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans
        self.scaler = StandardScaler()
        rfm_features = df[["recency", "frequency", "monetary"]].values
        scaled = self.scaler.fit_transform(rfm_features)

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

        centers = self.scaler.inverse_transform(self.kmeans.cluster_centers_)
        return pd.DataFrame(
            centers, columns=["recency", "frequency", "monetary"]
        ).round(2)


if __name__ == "__main__":
    clustering = RFMClustering()
    results = clustering.cluster()
    print("\n聚类结果:")
    print(results["cluster_label"].value_counts().to_string())
