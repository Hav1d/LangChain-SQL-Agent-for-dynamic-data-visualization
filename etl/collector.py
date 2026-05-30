"""
数据采集模块 - 生成模拟Olist电商数据集
模拟Brazilian E-Commerce的真实数据结构，用于RFM分析和仪表盘展示
"""
import random
import string
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


class DataCollector:
    """生成模拟Olist数据集，结构与Kaggle Brazilian E-Commerce一致"""

    # 巴西州和城市映射
    BRAZIL_STATES = {
        "SP": ["Sao Paulo", "Campinas", "Santos", "Ribeirao Preto"],
        "RJ": ["Rio de Janeiro", "Niteroi", "Petropolis", "Volta Redonda"],
        "MG": ["Belo Horizonte", "Uberlandia", "Contagem", "Juiz de Fora"],
        "BA": ["Salvador", "Feira de Santana", "Vitoria da Conquista"],
        "RS": ["Porto Alegre", "Caxias do Sul", "Pelotas"],
        "PR": ["Curitiba", "Londrina", "Maringa"],
        "PE": ["Recife", "Olinda", "Jaboatao dos Guararapes"],
        "CE": ["Fortaleza", "Caucaia", "Juazeiro do Norte"],
        "PA": ["Belem", "Ananindeua", "Santarem"],
        "GO": ["Goiania", "Aparecida de Goiania", "Anapolis"],
        "SC": ["Florianopolis", "Joinville", "Blumenau"],
        "MA": ["Sao Luis", "Imperatriz", "Timon"],
        "ES": ["Vitoria", "Vila Velha", "Serra"],
        "MT": ["Cuiaba", "Varzea Grande", "Rondonopolis"],
        "DF": ["Brasilia", "Taguatinga", "Ceilandia"],
    }

    # 商品类目（葡萄牙语 → 英文/中文）
    PRODUCT_CATEGORIES = [
        ("cama_mesa_banho", "bed_bath_table", "床品浴室"),
        ("beleza_saude", "health_beauty", "健康美容"),
        ("esporte_lazer", "sports_leisure", "运动休闲"),
        ("informatica_acessorios", "computers_accessories", "电脑配件"),
        ("moveis_decoracao", "furniture_decor", "家具装饰"),
        ("utilidades_domesticas", "housewares", "家居用品"),
        ("relogios_presentes", "watches_gifts", "手表礼品"),
        ("telefonia", "telephony", "手机通讯"),
        ("automotivo", "auto", "汽车用品"),
        ("brinquedos", "toys", "玩具"),
        ("cool_stuff", "cool_stuff", "酷玩"),
        ("ferramentas_jardim", "garden_tools", "花园工具"),
        ("perfumaria", "perfumery", "香水"),
        ("bebes", "baby", "母婴"),
        ("eletronicos", "electronics", "电子产品"),
    ]

    # 支付方式
    PAYMENT_METHODS = ["credit_card", "boleto", "voucher", "debit_card"]

    # 订单状态
    ORDER_STATUSES = [
        "delivered", "delivered", "delivered", "delivered",  # 40% delivered
        "shipped", "shipped",  # 20%
        "processing",  # 10%
        "approved",  # 10%
        "canceled",  # 10%
        "unavailable",  # 10%
    ]

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.np_rng = np.random.RandomState(seed)

    def generate_customer_id(self) -> str:
        """生成32位十六进制客户ID"""
        return "".join(self.rng.choices(string.hexdigits[:16], k=32))

    def generate_order_id(self) -> str:
        """生成32位十六进制订单ID"""
        return "".join(self.rng.choices(string.hexdigits[:16], k=32))

    def generate_product_id(self) -> str:
        """生成32位十六进制商品ID"""
        return "".join(self.rng.choices(string.hexdigits[:16], k=32))

    def generate_seller_id(self) -> str:
        """生成32位十六进制卖家ID"""
        return "".join(self.rng.choices(string.hexdigits[:16], k=32))

    def _generate_customers(self, n: int = 5000) -> pd.DataFrame:
        """生成客户数据"""
        customers = []
        states = list(self.BRAZIL_STATES.keys())
        # 权重：SP和RJ人口多，客户也多
        state_weights = [0.25, 0.15, 0.12, 0.08, 0.07, 0.06, 0.05, 0.04,
                         0.03, 0.03, 0.03, 0.02, 0.02, 0.02, 0.03]

        unique_ids = set()
        for _ in range(n):
            cust_unique_id = self.generate_customer_id()
            while cust_unique_id in unique_ids:
                cust_unique_id = self.generate_customer_id()
            unique_ids.add(cust_unique_id)

            state = self.rng.choices(states, weights=state_weights)[0]
            city = self.rng.choice(self.BRAZIL_STATES[state])
            zip_prefix = self.rng.randint(1000, 99999)

            customers.append({
                "customer_id": cust_unique_id,
                "customer_unique_id": cust_unique_id,  # 简化：1:1映射
                "customer_zip_code_prefix": zip_prefix,
                "customer_city": city.lower().replace(" ", "_"),
                "customer_state": state,
            })

        return pd.DataFrame(customers)

    def _generate_sellers(self, n: int = 500) -> pd.DataFrame:
        """生成卖家数据"""
        sellers = []
        states = list(self.BRAZIL_STATES.keys())

        for _ in range(n):
            seller_id = self.generate_seller_id()
            state = self.rng.choice(states)
            city = self.rng.choice(self.BRAZIL_STATES[state])
            zip_prefix = self.rng.randint(1000, 99999)

            sellers.append({
                "seller_id": seller_id,
                "seller_zip_code_prefix": zip_prefix,
                "seller_city": city.lower().replace(" ", "_"),
                "seller_state": state,
            })

        return pd.DataFrame(sellers)

    def _generate_products(self, n: int = 2000) -> pd.DataFrame:
        """生成商品数据"""
        products = []
        for i in range(n):
            cat_idx = self.rng.randint(0, len(self.PRODUCT_CATEGORIES) - 1)
            cat_pt, cat_en, cat_cn = self.PRODUCT_CATEGORIES[cat_idx]

            # 价格分布：对数正态分布
            price = round(self.np_rng.lognormal(mean=4.0, sigma=0.8), 2)
            price = max(5.0, min(price, 5000.0))  # 限制范围

            # 商品属性
            name_len = self.rng.randint(20, 80)
            desc_len = self.rng.randint(100, 1000)
            weight = self.rng.randint(50, 30000)  # 克
            length = self.rng.randint(10, 100)  # cm
            height = self.rng.randint(5, 80)
            width = self.rng.randint(5, 80)

            products.append({
                "product_id": self.generate_product_id(),
                "product_category_name": cat_pt,
                "product_name_lenght": name_len,
                "product_description_lenght": desc_len,
                "product_photos_qty": self.rng.randint(1, 10),
                "product_weight_g": weight,
                "product_length_cm": length,
                "product_height_cm": height,
                "product_width_cm": width,
            })

        return pd.DataFrame(products)

    def _generate_orders(self, customers_df: pd.DataFrame, n: int = 12000) -> pd.DataFrame:
        """生成订单数据 - 关键：确保有足够的RFM分析数据"""
        orders = []
        cust_ids = customers_df["customer_id"].tolist()

        # 设置时间范围：2017-01 到 2018-09
        start_date = datetime(2017, 1, 1)
        end_date = datetime(2018, 9, 3)
        total_days = (end_date - start_date).days

        # 客户购买频率分布（大部分只买1次，少数多次购买）
        customer_order_counts = {}
        for cust_id in cust_ids:
            # 幂律分布：大多数客户1-2单，少数客户10+单
            n_orders = max(1, int(self.np_rng.pareto(1.5) + 1))
            n_orders = min(n_orders, 25)  # 上限
            customer_order_counts[cust_id] = n_orders

        # 选择有购买记录的客户（不是所有客户都有订单）
        active_customers = self.rng.sample(cust_ids, k=min(len(cust_ids), int(n * 0.7)))

        order_count = 0
        for cust_id in active_customers:
            if order_count >= n:
                break

            n_cust_orders = customer_order_counts[cust_id]
            for _ in range(min(n_cust_orders, n - order_count)):
                # 购买日期 - 有季节性（年末促销多）
                days_offset = self.np_rng.exponential(scale=total_days / 3)
                days_offset = min(int(days_offset), total_days)
                purchase_date = start_date + timedelta(days=days_offset)

                # 审批时间
                approve_offset = timedelta(hours=self.rng.randint(0, 48))
                approve_date = purchase_date + approve_offset

                # 状态
                status = self.rng.choice(self.ORDER_STATUSES)

                # 交付时间
                if status == "delivered":
                    deliver_offset = timedelta(days=self.rng.randint(3, 30))
                    delivered_date = approve_date + deliver_offset
                    carrier_date = approve_date + timedelta(days=self.rng.randint(1, 5))
                    estimated_date = purchase_date + timedelta(days=self.rng.randint(15, 60))
                else:
                    delivered_date = None
                    carrier_date = None
                    estimated_date = purchase_date + timedelta(days=self.rng.randint(15, 60))

                orders.append({
                    "order_id": self.generate_order_id(),
                    "customer_id": cust_id,
                    "order_status": status,
                    "order_purchase_timestamp": purchase_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "order_approved_at": approve_date.strftime("%Y-%m-%d %H:%M:%S") if approve_date else None,
                    "order_delivered_carrier_date": carrier_date.strftime("%Y-%m-%d %H:%M:%S") if carrier_date else None,
                    "order_delivered_customer_date": delivered_date.strftime("%Y-%m-%d %H:%M:%S") if delivered_date else None,
                    "order_estimated_delivery_date": estimated_date.strftime("%Y-%m-%d %H:%M:%S"),
                })
                order_count += 1

        return pd.DataFrame(orders)

    def _generate_order_items(self, orders_df: pd.DataFrame, products_df: pd.DataFrame,
                               sellers_df: pd.DataFrame) -> pd.DataFrame:
        """生成订单明细"""
        items = []
        prod_ids = products_df["product_id"].tolist()
        seller_ids = sellers_df["seller_id"].tolist()

        # 构建产品权重查找表（避免O(n*m)过滤）
        prod_weight_map = dict(zip(products_df["product_id"], products_df["product_weight_g"]))

        for _, order in orders_df.iterrows():
            n_items = self.rng.choices([1, 2, 3, 4, 5], weights=[50, 25, 15, 7, 3])[0]
            for seq in range(1, n_items + 1):
                prod_id = self.rng.choice(prod_ids)
                weight = prod_weight_map.get(prod_id, 500)
                price = round(float(weight) * 0.01 + self.np_rng.lognormal(3.5, 0.6), 2)
                price = max(5.0, min(price, 3000.0))
                freight = round(self.np_rng.lognormal(2.5, 0.5), 2)
                freight = max(2.0, min(freight, 200.0))

                items.append({
                    "order_id": order["order_id"],
                    "order_item_id": seq,
                    "product_id": prod_id,
                    "seller_id": self.rng.choice(seller_ids),
                    "shipping_limit_date": (
                        datetime.strptime(order["order_purchase_timestamp"], "%Y-%m-%d %H:%M:%S")
                        + timedelta(days=self.rng.randint(3, 15))
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "price": price,
                    "freight_value": freight,
                })

        return pd.DataFrame(items)

    def _generate_payments(self, orders_df: pd.DataFrame) -> pd.DataFrame:
        """生成支付数据"""
        payments = []
        for _, order in orders_df.iterrows():
            n_payments = self.rng.choices([1, 2, 3], weights=[85, 12, 3])[0]
            # 总金额从订单明细计算（这里先用随机值）
            total = round(self.np_rng.lognormal(4.5, 0.8), 2)
            total = max(10.0, min(total, 10000.0))

            remaining = total
            for seq in range(1, n_payments + 1):
                if seq == n_payments:
                    amount = remaining
                else:
                    amount = round(remaining * self.rng.uniform(0.2, 0.6), 2)
                    remaining -= amount

                payments.append({
                    "order_id": order["order_id"],
                    "payment_sequential": seq,
                    "payment_type": self.rng.choices(
                        self.PAYMENT_METHODS,
                        weights=[60, 20, 10, 10]
                    )[0],
                    "payment_installments": self.rng.choices(
                        [1, 2, 3, 4, 5, 6, 10, 12],
                        weights=[40, 20, 15, 10, 5, 5, 3, 2]
                    )[0],
                    "payment_value": round(amount, 2),
                })

        return pd.DataFrame(payments)

    def _generate_reviews(self, orders_df: pd.DataFrame) -> pd.DataFrame:
        """生成评价数据"""
        reviews = []
        review_messages = [
            "Produto excelente, recomendo!", "Otimo produto, entrega rapida",
            "Bom custo beneficio", "Produto de boa qualidade",
            "Muito satisfeito com a compra", "Entrega demorou um pouco",
            "Produto OK, nada demais", "Nao gostei muito",
            "Produto com defeito", "Pessimo, quero devolver",
            "Adorei! Super recomendo", "Razoavel pelo preco",
            "Chegou antes do prazo", "Produto conforme descrito",
            "Qualidade inferior ao esperado",
        ]

        for _, order in orders_df.iterrows():
            # 约70%的订单有评价
            if self.rng.random() > 0.7:
                continue

            # 评价日期在交付后
            try:
                purchase = datetime.strptime(order["order_purchase_timestamp"], "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue

            review_date = purchase + timedelta(days=self.rng.randint(2, 60))

            # 评分分布：偏向高分（4-5星居多）
            score = self.rng.choices([1, 2, 3, 4, 5], weights=[5, 8, 15, 35, 37])[0]

            # 低分更可能有评论文字
            has_comment = score <= 3 or self.rng.random() > 0.5

            reviews.append({
                "review_id": "".join(self.rng.choices(string.hexdigits[:16], k=32)),
                "order_id": order["order_id"],
                "review_score": score,
                "review_comment_title": self.rng.choice(review_messages[:5]) if has_comment and self.rng.random() > 0.5 else None,
                "review_comment_message": self.rng.choice(review_messages) if has_comment else None,
                "review_creation_date": review_date.strftime("%Y-%m-%d %H:%M:%S"),
                "review_answer_timestamp": (review_date + timedelta(days=self.rng.randint(0, 3))).strftime("%Y-%m-%d %H:%M:%S"),
            })

        return pd.DataFrame(reviews)

    def _generate_category_translation(self) -> pd.DataFrame:
        """生成类目翻译表"""
        return pd.DataFrame([
            {"product_category_name": pt, "product_category_name_english": en}
            for pt, en, _ in self.PRODUCT_CATEGORIES
        ])

    def collect_all(self, n_customers: int = 5000, n_orders: int = 12000,
                    n_products: int = 2000, n_sellers: int = 500) -> dict:
        """
        生成完整数据集

        Returns:
            dict: 包含所有DataFrame的字典
        """
        print("[DATA] 开始生成模拟Olist数据集...")

        print(f"  [GEN] 生成 {n_customers} 条客户数据...")
        customers = self._generate_customers(n_customers)

        print(f"  [GEN] 生成 {n_sellers} 条卖家数据...")
        sellers = self._generate_sellers(n_sellers)

        print(f"  [GEN] 生成 {n_products} 条商品数据...")
        products = self._generate_products(n_products)

        print(f"  [GEN] 生成订单数据...")
        orders = self._generate_orders(customers, n_orders)

        print(f"  [GEN] 生成订单明细...")
        order_items = self._generate_order_items(orders, products, sellers)

        print(f"  [GEN] 生成支付数据...")
        payments = self._generate_payments(orders)

        print(f"  [GEN] 生成评价数据...")
        reviews = self._generate_reviews(orders)

        print(f"  [GEN] 生成类目翻译表...")
        category_translation = self._generate_category_translation()

        # 更新支付金额与订单明细一致
        item_totals = order_items.groupby("order_id")["price"].sum().reset_index()
        item_totals.columns = ["order_id", "calculated_total"]
        payments = payments.merge(item_totals, on="order_id", how="left")
        # 按比例分配
        payments["payment_value"] = payments.apply(
            lambda r: r["calculated_total"] if r["payment_sequential"] == 1
            else round(r["calculated_total"] * 0.1, 2), axis=1
        )
        payments = payments.drop(columns=["calculated_total"])

        # 更新订单总金额
        order_totals = order_items.groupby("order_id").agg(
            total_price=("price", "sum"),
            total_freight=("freight_value", "sum")
        ).reset_index()
        orders = orders.merge(order_totals, on="order_id", how="left")
        orders["total_price"] = orders["total_price"].fillna(0)
        orders["total_freight"] = orders["total_freight"].fillna(0)

        datasets = {
            "customers": customers,
            "sellers": sellers,
            "products": products,
            "orders": orders,
            "order_items": order_items,
            "order_payments": payments,
            "order_reviews": reviews,
            "category_translation": category_translation,
        }

        # 打印摘要
        print("\n[OK] 数据生成完成！")
        for name, df in datasets.items():
            print(f"  {name}: {len(df):,} 条记录")

        return datasets
