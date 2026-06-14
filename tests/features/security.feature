Feature: Read-only database security
  As a system administrator
  I want the MCP server to enforce read-only access at all levels
  So that no client can mutate the Northwind database

  Background:
    Given the MCP server is initialised

  # --- SQL keyword enforcement ---

  Scenario Outline: Write SQL statements are rejected by the query tool
    When I call query with "<sql>"
    Then it should raise a ValueError
    And the error message should contain "Only SELECT / WITH queries are permitted"

    Examples:
      | sql                                              |
      | INSERT INTO products (product_name) VALUES ('x') |
      | UPDATE products SET unit_price = 0               |
      | DELETE FROM products WHERE product_id = 1        |
      | DROP TABLE products                              |
      | TRUNCATE TABLE products                          |
      | ALTER TABLE products ADD COLUMN foo TEXT         |
      | CREATE TABLE hacked (id INT)                     |

  Scenario: Leading whitespace does not bypass the keyword check
    When I call query with "   \n  DELETE FROM orders"
    Then it should raise a ValueError
    And the error message should contain "Only SELECT / WITH queries are permitted"

  Scenario: A semicolon prefix does not bypass the keyword check
    When I call query with "; DROP TABLE orders"
    Then it should raise a ValueError
    And the error message should contain "Only SELECT / WITH queries are permitted"

  Scenario: A valid SELECT query is accepted
    When I call query with "SELECT 1"
    Then it should not raise an error

  Scenario: A valid WITH (CTE) query is accepted
    When I call query with "WITH cte AS (SELECT 1 AS n) SELECT n FROM cte"
    Then it should not raise an error

  # --- CTE write-smuggling ---

  Scenario: A write operation hidden inside a CTE is rejected by the database session
    Given the database session is read-only
    When I execute "WITH d AS (DELETE FROM orders RETURNING *) SELECT * FROM d" directly on the connection
    Then the database should raise a read-only transaction error

  # --- Identifier injection ---

  Scenario Outline: Malicious table names are rejected before reaching the database
    When I call describe_table with "<table_name>"
    Then it should raise a ValueError
    And the error message should contain "Invalid identifier"

    Examples:
      | table_name                  |
      | orders; DROP TABLE orders-- |
      | 1_invalid                   |
      | orders UNION SELECT 1--     |
      | ""                          |
      | orders'--                   |

  Scenario Outline: Malicious table names are rejected in sample_table
    When I call sample_table with "<table_name>"
    Then it should raise a ValueError
    And the error message should contain "Invalid identifier"

    Examples:
      | table_name                  |
      | orders; DROP TABLE orders-- |
      | products'--                 |

  # --- PostgreSQL session-level enforcement ---

  Scenario: The database connection is opened in read-only mode
    Given a real database connection is established
    Then the session should have the read-only flag set to true

  Scenario: A direct INSERT on a read-only session is rejected by PostgreSQL
    Given the database session is read-only
    When I execute "INSERT INTO products (product_name) VALUES ('hacked')" directly on the connection
    Then the database should raise a read-only transaction error
