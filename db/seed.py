"""
seed.py — creates and populates orders.db with ~200 customers, ~30 products, ~1000 orders.
Safe to re-run: drops and recreates all tables each time.
"""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

DB_PATH = Path(__file__).parent / "orders.db"
SCHEMA  = Path(__file__).parent / "schema.sql"

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

REGIONS    = ["North", "South", "East", "West"]
PLANS      = ["free", "starter", "pro", "enterprise"]
PLAN_WEIGHTS = [0.30, 0.35, 0.25, 0.10]

SALES_REPS = [
    "Alice Chen", "Bob Martinez", "Carol White", "David Kim",
    "Eva Rossi",  "Frank Nguyen", "Grace Patel",
]

CATEGORIES = ["Software", "Hardware", "Services", "Support"]

PRODUCTS = [
    # Software
    ("SW-001", "Analytics Dashboard Pro",    "Software",  29900),
    ("SW-002", "Data Pipeline Suite",        "Software",  49900),
    ("SW-003", "ML Model Toolkit",           "Software",  79900),
    ("SW-004", "API Gateway License",        "Software",  19900),
    ("SW-005", "Cloud Storage Manager",      "Software",  14900),
    ("SW-006", "Security Audit Platform",    "Software",  59900),
    ("SW-007", "DevOps Automation Suite",    "Software",  39900),
    ("SW-008", "Reporting Engine",           "Software",   9900),
    # Hardware
    ("HW-001", "Enterprise Server Node",     "Hardware", 299900),
    ("HW-002", "Network Switch 48-port",     "Hardware",  89900),
    ("HW-003", "SSD Storage Array 10TB",     "Hardware", 149900),
    ("HW-004", "GPU Compute Card",           "Hardware", 199900),
    ("HW-005", "Rack Mount UPS 3kVA",        "Hardware",  69900),
    ("HW-006", "Fiber Optic Transceiver",    "Hardware",   4900),
    ("HW-007", "Workstation Pro",            "Hardware", 249900),
    # Services
    ("SV-001", "Implementation Package",     "Services",  99900),
    ("SV-002", "Data Migration Service",     "Services",  49900),
    ("SV-003", "Custom Integration",         "Services", 149900),
    ("SV-004", "Training Workshop",          "Services",  19900),
    ("SV-005", "Architecture Review",        "Services",  34900),
    ("SV-006", "Performance Audit",          "Services",  24900),
    # Support
    ("SP-001", "Standard Support Plan",      "Support",   9900),
    ("SP-002", "Priority Support Plan",      "Support",  19900),
    ("SP-003", "Enterprise Support Plan",    "Support",  39900),
    ("SP-004", "24/7 Monitoring Add-on",     "Support",  14900),
    ("SP-005", "Dedicated Success Manager",  "Support",  29900),
    ("SP-006", "SLA Guarantee Package",      "Support",   4900),
    ("SP-007", "Incident Response Retainer", "Support",  49900),
]

FIRST_NAMES = [
    "James","Mary","John","Patricia","Robert","Jennifer","Michael","Linda",
    "William","Barbara","David","Elizabeth","Richard","Susan","Joseph","Jessica",
    "Thomas","Sarah","Charles","Karen","Christopher","Lisa","Daniel","Nancy",
    "Matthew","Betty","Anthony","Margaret","Mark","Sandra","Donald","Ashley",
    "Steven","Emily","Paul","Dorothy","Andrew","Kimberly","Joshua","Helen",
]
LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
    "Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson",
    "Thomas","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson","White",
    "Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker","Young",
]
EMAIL_DOMAINS = [
    "acme.com","globex.com","initech.com","umbrella.co","piedpiper.io",
    "hooli.net","dunder.biz","vandelay.io","bluth.co","prestige.com",
]

# Plan → likely categories (weighted)
PLAN_CATEGORY_WEIGHTS = {
    "free":       {"Software": 0.70, "Hardware": 0.05, "Services": 0.15, "Support": 0.10},
    "starter":    {"Software": 0.50, "Hardware": 0.15, "Services": 0.20, "Support": 0.15},
    "pro":        {"Software": 0.40, "Hardware": 0.25, "Services": 0.20, "Support": 0.15},
    "enterprise": {"Software": 0.30, "Hardware": 0.30, "Services": 0.25, "Support": 0.15},
}


def random_date(start: date, end: date) -> date:
    return start + timedelta(days=random.randint(0, (end - start).days))


def weighted_choice(options, weights):
    total = sum(weights.values()) if isinstance(weights, dict) else sum(weights)
    r = random.uniform(0, total)
    cumulative = 0
    items = list(weights.items()) if isinstance(weights, dict) else list(zip(options, weights))
    for item, w in items:
        cumulative += w
        if r <= cumulative:
            return item
    return items[-1][0]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_customers(n=200):
    customers = []
    used_emails = set()
    for i in range(1, n + 1):
        first = random.choice(FIRST_NAMES)
        last  = random.choice(LAST_NAMES)
        name  = f"{first} {last}"
        domain = random.choice(EMAIL_DOMAINS)
        base = f"{first.lower()}.{last.lower()}"
        email = f"{base}{random.randint(1,99)}@{domain}"
        while email in used_emails:
            email = f"{base}{random.randint(1,999)}@{domain}"
        used_emails.add(email)

        region  = random.choice(REGIONS)
        plan    = random.choices(PLANS, weights=PLAN_WEIGHTS)[0]
        joined  = random_date(date(2022, 1, 1), date(2024, 12, 31))
        # ~65% of non-free customers have a rep; free customers rarely do
        has_rep = random.random() < (0.65 if plan != "free" else 0.10)
        rep     = random.choice(SALES_REPS) if has_rep else None

        customers.append((i, name, email, region, plan, joined.isoformat(), rep))
    return customers


def generate_orders(customers, products_by_cat, n=1000):
    orders = []
    prod_list = [p for prods in products_by_cat.values() for p in prods]

    for oid in range(1, n + 1):
        cust = random.choice(customers)
        cust_id, _, _, _, plan, joined_str, _ = cust
        joined = date.fromisoformat(joined_str)

        # Order date: after signup, up to end of 2025
        earliest = joined + timedelta(days=1)
        latest   = date(2025, 12, 31)
        if earliest > latest:
            earliest = latest
        dt = random_date(earliest, latest)

        # Pick category weighted by plan type
        cat_weights = PLAN_CATEGORY_WEIGHTS[plan]
        cat = weighted_choice(None, cat_weights)
        product = random.choice(products_by_cat[cat])
        sku = product[0]
        unit_price = product[3]  # list price in cents (sku, product, cat, price)

        qty = random.choices([1, 2, 3, 4, 5], weights=[0.55, 0.25, 0.10, 0.06, 0.04])[0]

        # Discount: most orders have none; enterprise more likely to get one
        disc_prob = {"free": 0.05, "starter": 0.10, "pro": 0.20, "enterprise": 0.35}[plan]
        if random.random() < disc_prob:
            discount = random.choice([0.05, 0.10, 0.15, 0.20, 0.25, 0.30])
        else:
            discount = 0.0

        revenue = round(qty * unit_price * (1 - discount))

        # Refund rate ~8%
        refunded = 1 if random.random() < 0.08 else 0

        orders.append((oid, cust_id, sku, dt.isoformat(), qty, unit_price, discount, revenue, refunded))

    return orders


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    con = sqlite3.connect(DB_PATH)

    # Drop and recreate
    con.executescript("""
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS products;
    """)
    con.executescript(SCHEMA.read_text())

    # Products
    con.executemany(
        "INSERT INTO products VALUES (?,?,?,?)",
        [(p[0], p[1], p[2], p[3]) for p in PRODUCTS],
    )

    products_by_cat = {}
    for p in PRODUCTS:
        products_by_cat.setdefault(p[2], []).append(p)

    # Customers
    customers = generate_customers(200)
    con.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?)", customers)

    # Orders
    orders = generate_orders(customers, products_by_cat, 1000)
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", orders)

    con.commit()

    # Sanity check
    print("Seeding complete:")
    print(f"  customers : {con.execute('SELECT COUNT(*) FROM customers').fetchone()[0]}")
    print(f"  products  : {con.execute('SELECT COUNT(*) FROM products').fetchone()[0]}")
    print(f"  orders    : {con.execute('SELECT COUNT(*) FROM orders').fetchone()[0]}")
    print()

    # Quick join sanity checks
    print("Revenue by region (orders JOIN customers):")
    for row in con.execute("""
        SELECT c.region, COUNT(*) AS n, ROUND(SUM(o.revenue)/100.0, 2) AS rev_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        GROUP BY c.region ORDER BY rev_dollars DESC
    """):
        print(f"  {row}")

    print("\nRevenue by category (orders JOIN products):")
    for row in con.execute("""
        SELECT p.cat, COUNT(*) AS n, ROUND(SUM(o.revenue)/100.0, 2) AS rev_dollars
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.cat ORDER BY rev_dollars DESC
    """):
        print(f"  {row}")

    print("\nTop 5 customers by spend (orders JOIN customers):")
    for row in con.execute("""
        SELECT c.name, c.plan, ROUND(SUM(o.revenue)/100.0, 2) AS spend
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        GROUP BY c.cust_id ORDER BY spend DESC LIMIT 5
    """):
        print(f"  {row}")

    con.close()


if __name__ == "__main__":
    main()
