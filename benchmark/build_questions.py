"""
build_questions.py — validates all 100 ground-truth questions against the seeded DB
and writes benchmark/questions.json.

Schema (opaque names):
  customers : cust_id, name, email, region, plan, joined, rep
  products  : sku, product, cat, price  (cents)
  orders    : oid, cust_id, sku, dt, qty, unit_price, discount, revenue, refunded
"""
import json, sqlite3, sys
from pathlib import Path

BASE    = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "orders.db"
OUT     = Path(__file__).parent / "questions.json"

# ---------------------------------------------------------------------------
# 25 Single-table questions  (s01–s25)
# ---------------------------------------------------------------------------
SINGLE = [
    ("s01", "How many customers are there in each region?",
     "SELECT region, COUNT(*) AS customer_count FROM customers GROUP BY region ORDER BY customer_count DESC"),

    ("s02", "What is the breakdown of customers by plan type?",
     "SELECT plan, COUNT(*) AS customer_count FROM customers GROUP BY plan ORDER BY customer_count DESC"),

    ("s03", "How many customers signed up in 2024?",
     "SELECT COUNT(*) AS customers_2024 FROM customers WHERE joined >= '2024-01-01' AND joined < '2025-01-01'"),

    ("s04", "Which sales rep manages the most customers?",
     "SELECT rep, COUNT(*) AS customer_count FROM customers WHERE rep IS NOT NULL GROUP BY rep ORDER BY customer_count DESC LIMIT 1"),

    ("s05", "How many customers have no sales rep?",
     "SELECT COUNT(*) AS self_serve_count FROM customers WHERE rep IS NULL"),

    ("s06", "What is the most common plan in the West region?",
     "SELECT plan, COUNT(*) AS cnt FROM customers WHERE region = 'West' GROUP BY plan ORDER BY cnt DESC LIMIT 1"),

    ("s07", "How many customers signed up each month in 2023?",
     "SELECT strftime('%Y-%m', joined) AS month, COUNT(*) AS customer_count FROM customers WHERE joined >= '2023-01-01' AND joined < '2024-01-01' GROUP BY month ORDER BY month"),

    ("s08", "Which region has the most enterprise customers?",
     "SELECT region, COUNT(*) AS enterprise_count FROM customers WHERE plan = 'enterprise' GROUP BY region ORDER BY enterprise_count DESC LIMIT 1"),

    ("s09", "How many products are in each category?",
     "SELECT cat, COUNT(*) AS product_count FROM products GROUP BY cat ORDER BY product_count DESC"),

    ("s10", "What is the average list price in dollars by product category?",
     "SELECT cat, ROUND(AVG(price) / 100.0, 2) AS avg_price_dollars FROM products GROUP BY cat ORDER BY avg_price_dollars DESC"),

    ("s11", "Which product has the highest list price?",
     "SELECT sku, product, ROUND(price / 100.0, 2) AS price_dollars FROM products ORDER BY price DESC LIMIT 1"),

    ("s12", "How many products have a list price above $200?",
     "SELECT COUNT(*) AS expensive_product_count FROM products WHERE price > 20000"),

    ("s13", "What is the cheapest product in each category?",
     """SELECT p.cat, p.product, ROUND(p.price / 100.0, 2) AS price_dollars
        FROM products p
        JOIN (SELECT cat, MIN(price) AS min_price FROM products GROUP BY cat) m
          ON p.cat = m.cat AND p.price = m.min_price
        ORDER BY p.cat"""),

    ("s14", "How many orders were placed in 2024?",
     "SELECT COUNT(*) AS orders_2024 FROM orders WHERE dt >= '2024-01-01' AND dt < '2025-01-01'"),

    ("s15", "What is the total revenue across all orders in dollars?",
     "SELECT ROUND(SUM(revenue) / 100.0, 2) AS total_revenue_dollars FROM orders"),

    ("s16", "What is the overall refund rate as a percentage?",
     "SELECT ROUND(100.0 * SUM(refunded) / COUNT(*), 2) AS refund_rate_pct FROM orders"),

    ("s17", "What is the total revenue by month in 2024 in dollars?",
     """SELECT strftime('%Y-%m', dt) AS month, ROUND(SUM(revenue) / 100.0, 2) AS revenue_dollars
        FROM orders WHERE dt >= '2024-01-01' AND dt < '2025-01-01'
        GROUP BY month ORDER BY month"""),

    ("s18", "How many orders included a discount?",
     "SELECT COUNT(*) AS discounted_order_count FROM orders WHERE discount > 0"),

    ("s19", "What is the average discount percentage on discounted orders?",
     "SELECT ROUND(AVG(discount) * 100, 2) AS avg_discount_pct FROM orders WHERE discount > 0"),

    ("s20", "What is the distribution of order quantities?",
     "SELECT qty, COUNT(*) AS order_count FROM orders GROUP BY qty ORDER BY qty"),

    ("s21", "How many orders were placed each year?",
     "SELECT strftime('%Y', dt) AS year, COUNT(*) AS order_count FROM orders GROUP BY year ORDER BY year"),

    ("s22", "What is the highest revenue from a single order in dollars?",
     "SELECT ROUND(MAX(revenue) / 100.0, 2) AS max_order_revenue_dollars FROM orders"),

    ("s23", "What is the total number of units sold across all orders?",
     "SELECT SUM(qty) AS total_units_sold FROM orders"),

    ("s24", "How many orders were refunded in each quarter of 2024?",
     """SELECT 'Q' || CAST((CAST(strftime('%m', dt) AS INTEGER) + 2) / 3 AS TEXT) AS quarter,
               COUNT(*) AS refunded_count
        FROM orders WHERE dt >= '2024-01-01' AND dt < '2025-01-01' AND refunded = 1
        GROUP BY quarter ORDER BY quarter"""),

    ("s25", "What is the average revenue per order in dollars?",
     "SELECT ROUND(AVG(revenue) / 100.0, 2) AS avg_order_revenue_dollars FROM orders"),
]

# ---------------------------------------------------------------------------
# 25 Two-join questions  (j01–j25)
# ---------------------------------------------------------------------------
TWO_JOIN = [
    ("j01", "What is the total revenue by customer region in dollars?",
     """SELECT c.region, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        GROUP BY c.region ORDER BY revenue_dollars DESC"""),

    ("j02", "What is the average order value by plan type in dollars?",
     """SELECT c.plan, ROUND(AVG(o.revenue) / 100.0, 2) AS avg_order_value_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        GROUP BY c.plan ORDER BY avg_order_value_dollars DESC"""),

    ("j03", "Which plan type has the highest refund rate?",
     """SELECT c.plan, ROUND(100.0 * SUM(o.refunded) / COUNT(*), 2) AS refund_rate_pct
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        GROUP BY c.plan ORDER BY refund_rate_pct DESC LIMIT 1"""),

    ("j04", "Who are the top 5 customers by total spend in dollars?",
     """SELECT c.name, c.plan, ROUND(SUM(o.revenue) / 100.0, 2) AS total_spend_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        GROUP BY c.cust_id ORDER BY total_spend_dollars DESC LIMIT 5"""),

    ("j05", "How many orders did each sales rep close?",
     """SELECT c.rep, COUNT(*) AS order_count
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        WHERE c.rep IS NOT NULL GROUP BY c.rep ORDER BY order_count DESC"""),

    ("j06", "What is the total revenue from enterprise plan customers in dollars?",
     """SELECT ROUND(SUM(o.revenue) / 100.0, 2) AS enterprise_revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        WHERE c.plan = 'enterprise'"""),

    ("j07", "What is the average discount percentage by plan type?",
     """SELECT c.plan, ROUND(AVG(o.discount) * 100, 2) AS avg_discount_pct
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        GROUP BY c.plan ORDER BY avg_discount_pct DESC"""),

    ("j08", "How many customers from each region have placed more than 3 orders?",
     """SELECT c.region, COUNT(*) AS customer_count
        FROM customers c
        WHERE c.cust_id IN (SELECT cust_id FROM orders GROUP BY cust_id HAVING COUNT(*) > 3)
        GROUP BY c.region ORDER BY customer_count DESC"""),

    ("j09", "What is the total revenue from self-serve versus rep-assisted orders in dollars?",
     """SELECT CASE WHEN c.rep IS NULL THEN 'Self-serve' ELSE 'Rep-assisted' END AS order_type,
               ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        GROUP BY order_type ORDER BY order_type"""),

    ("j10", "Which region has the highest refund rate?",
     """SELECT c.region, ROUND(100.0 * SUM(o.refunded) / COUNT(*), 2) AS refund_rate_pct
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        GROUP BY c.region ORDER BY refund_rate_pct DESC LIMIT 1"""),

    ("j11", "What is the total revenue from customers who signed up in 2023 in dollars?",
     """SELECT ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        WHERE c.joined >= '2023-01-01' AND c.joined < '2024-01-01'"""),

    ("j12", "How many orders were placed by customers in each region in 2024?",
     """SELECT c.region, COUNT(*) AS order_count
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        WHERE o.dt >= '2024-01-01' AND o.dt < '2025-01-01'
        GROUP BY c.region ORDER BY order_count DESC"""),

    ("j13", "Which sales rep has the highest average order value in dollars?",
     """SELECT c.rep, ROUND(AVG(o.revenue) / 100.0, 2) AS avg_order_value_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        WHERE c.rep IS NOT NULL GROUP BY c.rep ORDER BY avg_order_value_dollars DESC LIMIT 1"""),

    ("j14", "What is the total revenue by product category in dollars?",
     """SELECT p.cat, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.cat ORDER BY revenue_dollars DESC"""),

    ("j15", "Which product has generated the most total revenue in dollars?",
     """SELECT p.product, ROUND(SUM(o.revenue) / 100.0, 2) AS total_revenue_dollars
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.sku ORDER BY total_revenue_dollars DESC LIMIT 1"""),

    ("j16", "What is the refund rate by product category?",
     """SELECT p.cat, ROUND(100.0 * SUM(o.refunded) / COUNT(*), 2) AS refund_rate_pct
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.cat ORDER BY refund_rate_pct DESC"""),

    ("j17", "What are the top 5 products by number of orders?",
     """SELECT p.product, COUNT(*) AS order_count
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.sku ORDER BY order_count DESC LIMIT 5"""),

    ("j18", "How many total units of each product category have been sold?",
     """SELECT p.cat, SUM(o.qty) AS total_units
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.cat ORDER BY total_units DESC"""),

    ("j19", "What is the average revenue per order by product category in dollars?",
     """SELECT p.cat, ROUND(AVG(o.revenue) / 100.0, 2) AS avg_revenue_dollars
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.cat ORDER BY avg_revenue_dollars DESC"""),

    ("j20", "What is the total revenue from Software products in 2024 in dollars?",
     """SELECT ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN products p ON o.sku = p.sku
        WHERE p.cat = 'Software' AND o.dt >= '2024-01-01' AND o.dt < '2025-01-01'"""),

    ("j21", "What is the average discount percentage by product category?",
     """SELECT p.cat, ROUND(AVG(o.discount) * 100, 2) AS avg_discount_pct
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.cat ORDER BY avg_discount_pct DESC"""),

    ("j22", "Which product category has the highest average order quantity?",
     """SELECT p.cat, ROUND(AVG(o.qty), 2) AS avg_qty
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.cat ORDER BY avg_qty DESC LIMIT 1"""),

    ("j23", "What is the most ordered product?",
     """SELECT p.product, COUNT(*) AS order_count
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.sku ORDER BY order_count DESC LIMIT 1"""),

    ("j24", "What is the total revenue from Hardware products ordered after 2023 in dollars?",
     """SELECT ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN products p ON o.sku = p.sku
        WHERE p.cat = 'Hardware' AND o.dt >= '2024-01-01'"""),

    ("j25", "How many distinct customers have ordered from each product category?",
     """SELECT p.cat, COUNT(DISTINCT o.cust_id) AS customer_count
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.cat ORDER BY customer_count DESC"""),
]

# ---------------------------------------------------------------------------
# 25 Three-join questions  (t01–t25)
# ---------------------------------------------------------------------------
THREE_JOIN = [
    ("t01", "What is the total revenue by customer region and product category in dollars?",
     """SELECT c.region, p.cat, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY c.region, p.cat ORDER BY c.region, revenue_dollars DESC"""),

    ("t02", "Which sales rep generates the most revenue from Software products in dollars?",
     """SELECT c.rep, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.rep IS NOT NULL AND p.cat = 'Software'
        GROUP BY c.rep ORDER BY revenue_dollars DESC LIMIT 1"""),

    ("t03", "What is the refund rate by plan type and product category?",
     """SELECT c.plan, p.cat, ROUND(100.0 * SUM(o.refunded) / COUNT(*), 2) AS refund_rate_pct
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY c.plan, p.cat ORDER BY c.plan, refund_rate_pct DESC"""),

    ("t04", "Who are the top 5 customers by spend on Hardware products in dollars?",
     """SELECT c.name, c.plan, ROUND(SUM(o.revenue) / 100.0, 2) AS hardware_spend_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE p.cat = 'Hardware'
        GROUP BY c.cust_id ORDER BY hardware_spend_dollars DESC LIMIT 5"""),

    ("t05", "What is the average order value by region and product category in dollars?",
     """SELECT c.region, p.cat, ROUND(AVG(o.revenue) / 100.0, 2) AS avg_order_value_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY c.region, p.cat ORDER BY c.region, avg_order_value_dollars DESC"""),

    ("t06", "What is the total revenue from enterprise customers on Hardware products in dollars?",
     """SELECT ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.plan = 'enterprise' AND p.cat = 'Hardware'"""),

    ("t07", "How does revenue from self-serve versus rep-assisted orders break down by product category in dollars?",
     """SELECT p.cat,
               CASE WHEN c.rep IS NULL THEN 'Self-serve' ELSE 'Rep-assisted' END AS order_type,
               ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY p.cat, order_type ORDER BY p.cat, order_type"""),

    ("t08", "What is the total revenue by plan type and product category in dollars?",
     """SELECT c.plan, p.cat, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY c.plan, p.cat ORDER BY c.plan, revenue_dollars DESC"""),

    ("t09", "Which product category is most ordered by free plan customers?",
     """SELECT p.cat, COUNT(*) AS order_count
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.plan = 'free' GROUP BY p.cat ORDER BY order_count DESC LIMIT 1"""),

    ("t10", "What is the total revenue from pro and enterprise customers on Software products in 2024 in dollars?",
     """SELECT ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.plan IN ('pro', 'enterprise') AND p.cat = 'Software'
          AND o.dt >= '2024-01-01' AND o.dt < '2025-01-01'"""),

    ("t11", "What is the total number of units sold by product category and customer region?",
     """SELECT p.cat, c.region, SUM(o.qty) AS total_units
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY p.cat, c.region ORDER BY p.cat, total_units DESC"""),

    ("t12", "What is the average discount given to enterprise customers by product category?",
     """SELECT p.cat, ROUND(AVG(o.discount) * 100, 2) AS avg_discount_pct
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.plan = 'enterprise' GROUP BY p.cat ORDER BY avg_discount_pct DESC"""),

    ("t13", "Which region has the highest revenue from Software products in dollars?",
     """SELECT c.region, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE p.cat = 'Software' GROUP BY c.region ORDER BY revenue_dollars DESC LIMIT 1"""),

    ("t14", "Which sales rep has closed the most orders for enterprise customers buying Hardware?",
     """SELECT c.rep, COUNT(*) AS order_count
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.plan = 'enterprise' AND p.cat = 'Hardware' AND c.rep IS NOT NULL
        GROUP BY c.rep ORDER BY order_count DESC LIMIT 1"""),

    ("t15", "What is the average order value for starter plan customers buying Software in dollars?",
     """SELECT ROUND(AVG(o.revenue) / 100.0, 2) AS avg_order_value_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.plan = 'starter' AND p.cat = 'Software'"""),

    ("t16", "What is the total revenue from customers in the South region who ordered Hardware in dollars?",
     """SELECT ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.region = 'South' AND p.cat = 'Hardware'"""),

    ("t17", "Which plan type spends the most on Support products in dollars?",
     """SELECT c.plan, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE p.cat = 'Support' GROUP BY c.plan ORDER BY revenue_dollars DESC LIMIT 1"""),

    ("t18", "How many orders from pro plan customers for Software products included a discount?",
     """SELECT COUNT(*) AS discounted_order_count
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.plan = 'pro' AND p.cat = 'Software' AND o.discount > 0"""),

    ("t19", "What is the revenue contribution of each product category in the East region in dollars?",
     """SELECT p.cat, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.region = 'East' GROUP BY p.cat ORDER BY revenue_dollars DESC"""),

    ("t20", "Which sales rep has the highest refund rate for Software products?",
     """SELECT c.rep, ROUND(100.0 * SUM(o.refunded) / COUNT(*), 2) AS refund_rate_pct
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.rep IS NOT NULL AND p.cat = 'Software'
        GROUP BY c.rep ORDER BY refund_rate_pct DESC LIMIT 1"""),

    ("t21", "What is the total revenue from non-refunded orders by region and category in dollars?",
     """SELECT c.region, p.cat, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE o.refunded = 0
        GROUP BY c.region, p.cat ORDER BY c.region, revenue_dollars DESC"""),

    ("t22", "How many distinct customers from each plan type have ordered Services products?",
     """SELECT c.plan, COUNT(DISTINCT o.cust_id) AS customer_count
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE p.cat = 'Services' GROUP BY c.plan ORDER BY customer_count DESC"""),

    ("t23", "What is the average quantity per order by product category for enterprise customers?",
     """SELECT p.cat, ROUND(AVG(o.qty), 2) AS avg_qty
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.plan = 'enterprise' GROUP BY p.cat ORDER BY avg_qty DESC"""),

    ("t24", "What is the total discount amount given by product category and region in dollars?",
     """SELECT p.cat, c.region,
               ROUND(SUM(o.qty * o.unit_price * o.discount) / 100.0, 2) AS total_discount_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY p.cat, c.region ORDER BY p.cat, total_discount_dollars DESC"""),

    ("t25", "Which region and product category combination has the highest average order value in dollars?",
     """SELECT c.region, p.cat, ROUND(AVG(o.revenue) / 100.0, 2) AS avg_order_value_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY c.region, p.cat ORDER BY avg_order_value_dollars DESC LIMIT 1"""),
]

# ---------------------------------------------------------------------------
# 25 Complex questions  (c01–c25)
# ---------------------------------------------------------------------------
COMPLEX = [
    ("c01", "For each region, which product category generates the highest revenue?",
     """SELECT region, cat, revenue_dollars FROM (
            SELECT c.region, p.cat, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars,
                   RANK() OVER (PARTITION BY c.region ORDER BY SUM(o.revenue) DESC) AS rnk
            FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
            GROUP BY c.region, p.cat
        ) WHERE rnk = 1 ORDER BY region"""),

    ("c02", "Which customers have a total spend above the average customer spend?",
     """SELECT c.name, c.plan, ROUND(SUM(o.revenue) / 100.0, 2) AS total_spend_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        GROUP BY c.cust_id
        HAVING SUM(o.revenue) > (
            SELECT AVG(cust_rev) FROM (SELECT SUM(revenue) AS cust_rev FROM orders GROUP BY cust_id)
        )
        ORDER BY total_spend_dollars DESC"""),

    ("c03", "Which products have a refund rate higher than the overall average?",
     """SELECT p.product, ROUND(100.0 * SUM(o.refunded) / COUNT(*), 2) AS refund_rate_pct
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.sku
        HAVING (100.0 * SUM(o.refunded) / COUNT(*)) > (
            SELECT 100.0 * SUM(refunded) / COUNT(*) FROM orders
        )
        ORDER BY refund_rate_pct DESC"""),

    ("c04", "For each sales rep, what percentage of their revenue comes from Software products?",
     """SELECT c.rep,
               ROUND(100.0 * SUM(CASE WHEN p.cat = 'Software' THEN o.revenue ELSE 0 END) / SUM(o.revenue), 2) AS software_revenue_pct
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        WHERE c.rep IS NOT NULL GROUP BY c.rep ORDER BY software_revenue_pct DESC"""),

    ("c05", "What is the cumulative revenue by month in 2024 in dollars?",
     """SELECT month, monthly_revenue_dollars,
               ROUND(SUM(monthly_revenue_dollars) OVER (ORDER BY month), 2) AS cumulative_revenue_dollars
        FROM (
            SELECT strftime('%Y-%m', dt) AS month, ROUND(SUM(revenue) / 100.0, 2) AS monthly_revenue_dollars
            FROM orders WHERE dt >= '2024-01-01' AND dt < '2025-01-01' GROUP BY month
        ) ORDER BY month"""),

    ("c06", "For each plan type, rank the product categories by total revenue.",
     """SELECT plan, cat, revenue_dollars,
               RANK() OVER (PARTITION BY plan ORDER BY revenue_dollars DESC) AS revenue_rank
        FROM (
            SELECT c.plan, p.cat, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
            FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
            GROUP BY c.plan, p.cat
        ) ORDER BY plan, revenue_rank"""),

    ("c07", "Which customers have placed orders in every product category?",
     """SELECT c.name, c.plan
        FROM customers c
        WHERE (
            SELECT COUNT(DISTINCT p.cat)
            FROM orders o JOIN products p ON o.sku = p.sku
            WHERE o.cust_id = c.cust_id
        ) = (SELECT COUNT(DISTINCT cat) FROM products)
        ORDER BY c.name"""),

    ("c08", "For each product category, which month in 2024 had the highest revenue?",
     """SELECT cat, month, revenue_dollars FROM (
            SELECT p.cat, strftime('%Y-%m', o.dt) AS month,
                   ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars,
                   RANK() OVER (PARTITION BY p.cat ORDER BY SUM(o.revenue) DESC) AS rnk
            FROM orders o JOIN products p ON o.sku = p.sku
            WHERE o.dt >= '2024-01-01' AND o.dt < '2025-01-01'
            GROUP BY p.cat, month
        ) WHERE rnk = 1 ORDER BY cat"""),

    ("c09", "Which customers placed their first order within 30 days of signing up?",
     """SELECT c.name, c.plan, c.joined, MIN(o.dt) AS first_order_date
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id
        GROUP BY c.cust_id
        HAVING julianday(MIN(o.dt)) - julianday(c.joined) <= 30
        ORDER BY c.name"""),

    ("c10", "What is the total revenue from repeat customers versus first-time buyers in dollars?",
     """SELECT CASE WHEN order_count > 1 THEN 'Repeat' ELSE 'First-time' END AS customer_type,
               ROUND(SUM(total_revenue) / 100.0, 2) AS revenue_dollars
        FROM (
            SELECT cust_id, COUNT(*) AS order_count, SUM(revenue) AS total_revenue
            FROM orders GROUP BY cust_id
        ) GROUP BY customer_type ORDER BY customer_type"""),

    ("c11", "For each region, which sales rep has generated the most revenue?",
     """SELECT region, rep, revenue_dollars FROM (
            SELECT c.region, c.rep, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars,
                   RANK() OVER (PARTITION BY c.region ORDER BY SUM(o.revenue) DESC) AS rnk
            FROM orders o JOIN customers c ON o.cust_id = c.cust_id
            WHERE c.rep IS NOT NULL GROUP BY c.region, c.rep
        ) WHERE rnk = 1 ORDER BY region"""),

    ("c12", "Which customers have only ever ordered from a single product category?",
     """SELECT c.name, c.plan, MAX(p.cat) AS only_category
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY c.cust_id HAVING COUNT(DISTINCT p.cat) = 1
        ORDER BY c.name"""),

    ("c13", "For each product category, what percentage of its revenue came from discounted orders?",
     """SELECT p.cat,
               ROUND(100.0 * SUM(CASE WHEN o.discount > 0 THEN o.revenue ELSE 0 END) / SUM(o.revenue), 2) AS discounted_revenue_pct
        FROM orders o JOIN products p ON o.sku = p.sku
        GROUP BY p.cat ORDER BY discounted_revenue_pct DESC"""),

    ("c14", "Which plan type had the largest increase in order count from 2023 to 2024?",
     """SELECT plan, orders_2024 - orders_2023 AS order_count_increase FROM (
            SELECT c.plan,
                SUM(CASE WHEN o.dt >= '2023-01-01' AND o.dt < '2024-01-01' THEN 1 ELSE 0 END) AS orders_2023,
                SUM(CASE WHEN o.dt >= '2024-01-01' AND o.dt < '2025-01-01' THEN 1 ELSE 0 END) AS orders_2024
            FROM orders o JOIN customers c ON o.cust_id = c.cust_id GROUP BY c.plan
        ) ORDER BY order_count_increase DESC LIMIT 1"""),

    ("c15", "Who is the top spending customer in each region?",
     """SELECT region, name, plan, total_spend_dollars FROM (
            SELECT c.region, c.name, c.plan,
                   ROUND(SUM(o.revenue) / 100.0, 2) AS total_spend_dollars,
                   RANK() OVER (PARTITION BY c.region ORDER BY SUM(o.revenue) DESC) AS rnk
            FROM orders o JOIN customers c ON o.cust_id = c.cust_id
            GROUP BY c.region, c.cust_id
        ) WHERE rnk = 1 ORDER BY region"""),

    ("c16", "What is the average number of days between a customer's signup date and their first order?",
     """SELECT ROUND(AVG(days_to_first_order), 1) AS avg_days_to_first_order FROM (
            SELECT julianday(MIN(o.dt)) - julianday(c.joined) AS days_to_first_order
            FROM orders o JOIN customers c ON o.cust_id = c.cust_id GROUP BY c.cust_id
        )"""),

    ("c17", "Which products have been ordered by customers from all four regions?",
     """SELECT p.product
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY p.sku HAVING COUNT(DISTINCT c.region) = 4
        ORDER BY p.product"""),

    ("c18", "What percentage of customers have placed more than one order?",
     """SELECT ROUND(100.0 * SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_customer_pct
        FROM (SELECT cust_id, COUNT(*) AS order_count FROM orders GROUP BY cust_id)"""),

    ("c19", "What is the total revenue by quarter and product category in 2024 in dollars?",
     """SELECT p.cat,
               'Q' || CAST((CAST(strftime('%m', o.dt) AS INTEGER) + 2) / 3 AS TEXT) AS quarter,
               ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN products p ON o.sku = p.sku
        WHERE o.dt >= '2024-01-01' AND o.dt < '2025-01-01'
        GROUP BY p.cat, quarter ORDER BY p.cat, quarter"""),

    ("c20", "Which product category has the highest proportion of enterprise customer orders?",
     """SELECT p.cat,
               ROUND(100.0 * SUM(CASE WHEN c.plan = 'enterprise' THEN 1 ELSE 0 END) / COUNT(*), 2) AS enterprise_order_pct
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY p.cat ORDER BY enterprise_order_pct DESC LIMIT 1"""),

    ("c21", "Which customers have an average order value above the average for their plan type?",
     """SELECT c.name, c.plan, ROUND(AVG(o.revenue) / 100.0, 2) AS avg_order_value_dollars
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id GROUP BY c.cust_id
        HAVING AVG(o.revenue) > (
            SELECT AVG(o2.revenue) FROM orders o2 JOIN customers c2 ON o2.cust_id = c2.cust_id
            WHERE c2.plan = c.plan
        )
        ORDER BY avg_order_value_dollars DESC"""),

    ("c22", "Which month in 2024 had the highest revenue from non-refunded Hardware orders?",
     """SELECT strftime('%Y-%m', o.dt) AS month, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars
        FROM orders o JOIN products p ON o.sku = p.sku
        WHERE o.dt >= '2024-01-01' AND o.dt < '2025-01-01' AND o.refunded = 0 AND p.cat = 'Hardware'
        GROUP BY month ORDER BY revenue_dollars DESC LIMIT 1"""),

    ("c23", "For each sales rep, what is their best-performing product category by revenue?",
     """SELECT rep, cat, revenue_dollars FROM (
            SELECT c.rep, p.cat, ROUND(SUM(o.revenue) / 100.0, 2) AS revenue_dollars,
                   RANK() OVER (PARTITION BY c.rep ORDER BY SUM(o.revenue) DESC) AS rnk
            FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
            WHERE c.rep IS NOT NULL GROUP BY c.rep, p.cat
        ) WHERE rnk = 1 ORDER BY rep"""),

    ("c24", "For each product, what proportion of its orders came from enterprise customers?",
     """SELECT p.product,
               ROUND(100.0 * SUM(CASE WHEN c.plan = 'enterprise' THEN 1 ELSE 0 END) / COUNT(*), 2) AS enterprise_order_pct
        FROM orders o JOIN customers c ON o.cust_id = c.cust_id JOIN products p ON o.sku = p.sku
        GROUP BY p.sku ORDER BY enterprise_order_pct DESC"""),

    ("c25", "What is the average number of product categories ordered per customer, by plan type?",
     """SELECT c.plan, ROUND(AVG(cat_count), 2) AS avg_categories_per_customer
        FROM (
            SELECT o.cust_id, COUNT(DISTINCT p.cat) AS cat_count
            FROM orders o JOIN products p ON o.sku = p.sku GROUP BY o.cust_id
        ) sub JOIN customers c ON sub.cust_id = c.cust_id
        GROUP BY c.plan ORDER BY avg_categories_per_customer DESC"""),
]

# ---------------------------------------------------------------------------
# Validate and assemble
# ---------------------------------------------------------------------------

TIER_MAP = {
    "single_table": SINGLE,
    "two_join":     TWO_JOIN,
    "three_join":   THREE_JOIN,
    "complex":      COMPLEX,
}

def validate_and_build():
    con = sqlite3.connect(DB_PATH)
    questions = []
    errors = []

    for tier, items in TIER_MAP.items():
        for qid, question, sql in items:
            try:
                rows = con.execute(sql).fetchall()
                result_type = "scalar" if (len(rows) == 1 and len(rows[0]) == 1) else "rows"
                questions.append({
                    "id": qid,
                    "tier": tier,
                    "question": question,
                    "ground_truth_sql": sql.strip(),
                    "result_type": result_type,
                })
            except Exception as e:
                errors.append((qid, str(e), sql[:80]))

    con.close()

    if errors:
        print(f"\n{len(errors)} ERRORS:")
        for qid, err, sql in errors:
            print(f"  {qid}: {err}")
            print(f"    {sql}")
        sys.exit(1)

    payload = {
        "tiers": {
            "single_table":  {"label": "Single-table", "question_ids": [q["id"] for q in questions if q["tier"] == "single_table"]},
            "two_join":      {"label": "Two-join",     "question_ids": [q["id"] for q in questions if q["tier"] == "two_join"]},
            "three_join":    {"label": "Three-join",   "question_ids": [q["id"] for q in questions if q["tier"] == "three_join"]},
            "complex":       {"label": "Complex",      "question_ids": [q["id"] for q in questions if q["tier"] == "complex"]},
        },
        "questions": questions,
    }

    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Written {len(questions)} questions to {OUT}")
    for tier, items in TIER_MAP.items():
        print(f"  {tier}: {len(items)} questions")

if __name__ == "__main__":
    validate_and_build()
