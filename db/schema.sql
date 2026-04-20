CREATE TABLE IF NOT EXISTS customers (
    cust_id   INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    email     TEXT NOT NULL,
    region    TEXT NOT NULL,   -- 'North', 'South', 'East', 'West'
    plan      TEXT NOT NULL,   -- 'free', 'starter', 'pro', 'enterprise'
    joined    DATE NOT NULL,
    rep       TEXT             -- NULL if self-serve
);

CREATE TABLE IF NOT EXISTS products (
    sku       TEXT PRIMARY KEY,
    product   TEXT NOT NULL,
    cat       TEXT NOT NULL,   -- 'Software', 'Hardware', 'Services', 'Support'
    price     INTEGER NOT NULL -- list price in USD cents
);

CREATE TABLE IF NOT EXISTS orders (
    oid        INTEGER PRIMARY KEY,
    cust_id    INTEGER NOT NULL REFERENCES customers(cust_id),
    sku        TEXT    NOT NULL REFERENCES products(sku),
    dt         DATE    NOT NULL,
    qty        INTEGER NOT NULL,
    unit_price INTEGER NOT NULL,  -- actual price in USD cents (= list price, no divergence)
    discount   REAL    NOT NULL DEFAULT 0,  -- fraction 0.0–1.0
    revenue    INTEGER NOT NULL,            -- qty * unit_price * (1 - discount)
    refunded   INTEGER NOT NULL DEFAULT 0   -- 0 or 1
);
