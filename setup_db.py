"""
初始化演示电商数据库 - SQLite
运行一次即可生成 data/ecommerce.db
"""
import os
import random
import sqlite3
from datetime import datetime, timedelta

os.makedirs("data", exist_ok=True)

DB_PATH = "data/ecommerce.db"

# 如果已存在则删除重建
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ──────────────────────────────────────────────
# 建表
# ──────────────────────────────────────────────
cursor.executescript("""
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    gender TEXT NOT NULL,
    age INTEGER NOT NULL,
    city TEXT NOT NULL,
    register_date TEXT NOT NULL,
    vip_level TEXT NOT NULL DEFAULT '普通'
);

CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    category_name TEXT NOT NULL,
    parent_category TEXT
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    price REAL NOT NULL,
    cost REAL NOT NULL,
    brand TEXT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    total_amount REAL NOT NULL,
    status TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE reviews (
    review_id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    review_date TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);
""")

# ──────────────────────────────────────────────
# 生成数据
# ──────────────────────────────────────────────
random.seed(42)

# 城市和姓名池
cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆",
          "苏州", "长沙", "郑州", "青岛", "天津"]
last_names = ["张", "李", "王", "赵", "刘", "陈", "杨", "黄", "吴", "周", "孙", "马", "朱", "胡", "林"]
first_names_male = ["伟", "强", "磊", "洋", "勇", "军", "杰", "涛", "明", "辉", "浩", "宇", "鹏", "飞", "鑫"]
first_names_female = ["芳", "娜", "敏", "静", "丽", "婷", "雪", "慧", "玲", "萍", "莉", "燕", "琳", "晶", "瑶"]

# 类目
categories_data = [
    (1, "手机", "数码"), (2, "笔记本电脑", "数码"), (3, "平板电脑", "数码"),
    (4, "耳机", "配件"), (5, "充电器", "配件"), (6, "手机壳", "配件"),
    (7, "运动鞋", "服饰"), (8, "T恤", "服饰"), (9, "牛仔裤", "服饰"),
    (10, "面霜", "美妆"), (11, "口红", "美妆"), (12, "洗面奶", "美妆"),
]
cursor.executemany("INSERT INTO categories VALUES (?, ?, ?)", categories_data)

# 品牌
brands = {
    1: ["华为", "小米", "OPPO", "vivo", "苹果"],
    2: ["联想", "华为", "小米", "戴尔", "苹果"],
    3: ["苹果", "华为", "小米", "联想"],
    4: ["索尼", "苹果", "华为", "小米", "JBL"],
    5: ["安克", "小米", "华为", "品胜"],
    6: ["UAG", "倍决", "摩米士", "ESR"],
    7: ["耐克", "阿迪达斯", "李宁", "安踏", "新百伦"],
    8: ["优衣库", "耐克", "阿迪达斯", "李宁", "海澜之家"],
    9: ["Levi's", "优衣库", "李维斯", "杰克琼斯"],
    10: ["兰蔻", "雅诗兰黛", "欧莱雅", "资生堂"],
    11: ["MAC", "迪奥", "YSL", "兰蔻", "完美日记"],
    12: ["芙丽芳丝", "资生堂", "欧莱雅", "旁氏"],
}

# 商品
products_data = []
product_id = 1
for cat_id, cat_name, _ in categories_data:
    for i in range(8):
        brand = random.choice(brands[cat_id])
        if cat_id <= 3:
            price = round(random.uniform(1999, 9999), 2)
        elif cat_id <= 6:
            price = round(random.uniform(19, 599), 2)
        elif cat_id <= 9:
            price = round(random.uniform(79, 1299), 2)
        else:
            price = round(random.uniform(39, 899), 2)
        cost = round(price * random.uniform(0.3, 0.7), 2)
        name = f"{brand}{cat_name}{chr(65 + i)}款"
        products_data.append((product_id, name, cat_id, price, cost, brand))
        product_id += 1
cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", products_data)

# 客户
customers_data = []
for i in range(1, 501):
    gender = random.choice(["男", "女"])
    if gender == "男":
        name = random.choice(last_names) + random.choice(first_names_male)
    else:
        name = random.choice(last_names) + random.choice(first_names_female)
    age = random.randint(18, 60)
    city = random.choice(cities)
    reg_date = (datetime(2023, 1, 1) + timedelta(days=random.randint(0, 900))).strftime("%Y-%m-%d")
    vip = random.choices(["普通", "银卡", "金卡", "钻石"], weights=[50, 30, 15, 5])[0]
    customers_data.append((i, name, gender, age, city, reg_date, vip))
cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)", customers_data)

# 订单和订单明细
order_id = 1
orders_data = []
order_items_data = []
statuses = ["已完成", "已完成", "已完成", "已取消", "待发货", "配送中"]
payments = ["支付宝", "微信支付", "银行卡", "花呗", "信用卡"]

for cust_id in range(1, 501):
    n_orders = random.randint(0, 12)
    for _ in range(n_orders):
        order_date = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 520))).strftime("%Y-%m-%d")
        status = random.choice(statuses)
        payment = random.choice(payments)
        n_items = random.randint(1, 5)
        total = 0
        for _ in range(n_items):
            prod_id = random.randint(1, len(products_data))
            qty = random.randint(1, 3)
            unit_price = products_data[prod_id - 1][3]
            total += unit_price * qty
            order_items_data.append((len(order_items_data) + 1, order_id, prod_id, qty, unit_price))
        total = round(total, 2)
        orders_data.append((order_id, cust_id, order_date, total, status, payment))
        order_id += 1
cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", orders_data)
cursor.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", order_items_data)

# 评价
reviews_data = []
review_id = 1
for prod_id in range(1, len(products_data) + 1):
    n_reviews = random.randint(2, 20)
    for _ in range(n_reviews):
        cust_id = random.randint(1, 501)
        rating = random.choices([1, 2, 3, 4, 5], weights=[2, 5, 15, 40, 38])[0]
        rev_date = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 520))).strftime("%Y-%m-%d")
        reviews_data.append((review_id, prod_id, cust_id, rating, rev_date))
        review_id += 1
cursor.executemany("INSERT INTO reviews VALUES (?, ?, ?, ?, ?)", reviews_data)

conn.commit()
conn.close()

print(f"数据库已生成: {os.path.abspath(DB_PATH)}")
print(f"  客户: 500 条")
print(f"  类目: {len(categories_data)} 个")
print(f"  商品: {len(products_data)} 个")
print(f"  订单: {len(orders_data)} 条")
print(f"  订单明细: {len(order_items_data)} 条")
print(f"  评价: {len(reviews_data)} 条")
