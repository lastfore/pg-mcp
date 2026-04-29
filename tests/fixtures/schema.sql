-- Test schema for PostgreSQL MCP Server integration tests
-- This script creates sample tables for testing

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    quantity INTEGER DEFAULT 0,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Order items table
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL
);

-- Insert sample data
INSERT INTO users (username, email) VALUES
    ('alice', 'alice@example.com'),
    ('bob', 'bob@example.com'),
    ('charlie', 'charlie@example.com');

INSERT INTO products (sku, name, price, quantity, category) VALUES
    ('SKU001', 'Laptop', 999.99, 50, 'Electronics'),
    ('SKU002', 'Mouse', 29.99, 200, 'Electronics'),
    ('SKU003', 'Keyboard', 79.99, 150, 'Electronics'),
    ('SKU004', 'Monitor', 299.99, 75, 'Electronics'),
    ('SKU005', 'Desk Chair', 199.99, 30, 'Furniture');

INSERT INTO orders (user_id, total_amount, status) VALUES
    (1, 1029.98, 'completed'),
    (1, 29.99, 'completed'),
    (2, 379.98, 'pending'),
    (3, 199.99, 'completed');

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    (1, 1, 1, 999.99),  -- Alice: 1 laptop
    (1, 2, 1, 29.99),   -- Alice: 1 mouse
    (2, 2, 1, 29.99),   -- Alice: 1 mouse
    (3, 2, 1, 29.99),   -- Bob: 1 mouse
    (3, 4, 1, 299.99),  -- Bob: 1 monitor
    (4, 5, 1, 199.99);  -- Charlie: 1 chair

-- Create a sensitive table for security testing
CREATE TABLE IF NOT EXISTS sensitive_data (
    id SERIAL PRIMARY KEY,
    ssn VARCHAR(11) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    api_key VARCHAR(100) NOT NULL
);

INSERT INTO sensitive_data (ssn, password_hash, api_key) VALUES
    ('123-45-6789', 'hash1', 'key1'),
    ('987-65-4321', 'hash2', 'key2');
