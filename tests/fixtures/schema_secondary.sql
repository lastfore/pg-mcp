-- Secondary test schema for multi-database testing
-- This represents a different database (e.g., analytics or inventory)

-- Inventory table
CREATE TABLE IF NOT EXISTS inventory (
    id SERIAL PRIMARY KEY,
    warehouse_location VARCHAR(50) NOT NULL,
    item_sku VARCHAR(50) NOT NULL,
    stock_level INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Warehouse locations table
CREATE TABLE IF NOT EXISTS warehouses (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) NOT NULL UNIQUE,
    city VARCHAR(50) NOT NULL,
    country VARCHAR(50) NOT NULL
);

-- Sales summary table
CREATE TABLE IF NOT EXISTS sales_summary (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    product_category VARCHAR(50) NOT NULL,
    total_sales DECIMAL(12, 2) NOT NULL,
    units_sold INTEGER NOT NULL
);

-- Insert sample data
INSERT INTO warehouses (code, city, country) VALUES
    ('NYC01', 'New York', 'USA'),
    ('LAX01', 'Los Angeles', 'USA'),
    ('LON01', 'London', 'UK'),
    ('TKY01', 'Tokyo', 'Japan');

INSERT INTO inventory (warehouse_location, item_sku, stock_level) VALUES
    ('NYC01', 'SKU001', 100),
    ('NYC01', 'SKU002', 500),
    ('LAX01', 'SKU001', 75),
    ('LAX01', 'SKU003', 300),
    ('LON01', 'SKU004', 150),
    ('TKY01', 'SKU005', 80);

INSERT INTO sales_summary (date, product_category, total_sales, units_sold) VALUES
    ('2024-01-01', 'Electronics', 15000.00, 50),
    ('2024-01-01', 'Furniture', 5000.00, 10),
    ('2024-01-02', 'Electronics', 18000.00, 60),
    ('2024-01-02', 'Furniture', 3000.00, 6);
