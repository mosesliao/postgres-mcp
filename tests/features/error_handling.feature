Feature: Graceful error handling
  As a user of the MCP server
  I want meaningful errors when something goes wrong
  So that I can understand and fix the problem

  Background:
    Given the MCP server is initialised

  # --- Missing DATABASE_URL ---

  Scenario: Query fails clearly when DATABASE_URL is not set
    Given the DATABASE_URL environment variable is not set
    When I call query with "SELECT 1"
    Then it should raise a RuntimeError
    And the error message should contain "DATABASE_URL environment variable is not set"

  # --- Database unreachable ---

  Scenario: Query fails clearly when the database is unreachable
    Given the database is unreachable
    When I call query with "SELECT 1"
    Then it should raise a database connection error

  Scenario: list_tables fails clearly when the database is unreachable
    Given the database is unreachable
    When I call list_tables
    Then it should raise a database connection error

  # --- Unknown table ---

  Scenario: describe_table raises an error for a table that does not exist
    Given the database is connected
    When I call describe_table with "nonexistent_table"
    Then it should raise a ValueError
    And the error message should contain "not found in public schema"

  # --- Malformed SQL ---

  Scenario: Malformed SQL raises a database error
    Given the database is connected
    When I call query with "SELECT * FROM"
    Then it should raise a database syntax error

  # --- Result limits ---

  Scenario: sample_table limit is capped at 100 rows
    Given the database is connected
    When I call sample_table with "orders" and limit 9999
    Then the SQL executed should use a limit of 100

  Scenario: sample_table limit is at least 1 row
    Given the database is connected
    When I call sample_table with "orders" and limit 0
    Then the SQL executed should use a limit of 1

  Scenario: query results are capped at 500 rows
    Given the database returns more than 500 rows
    When I call query with "SELECT * FROM orders"
    Then the result should contain at most 500 rows

  # --- Empty results ---

  Scenario: query returns an empty list when no rows match
    Given the database is connected
    When I call query with "SELECT * FROM orders WHERE order_id = -1"
    Then the result should be an empty list

  # --- Connection cleanup ---

  Scenario: Database connection is closed after a successful query
    Given the database is connected
    When I call query with "SELECT 1"
    Then the connection should be closed afterwards

  Scenario: Database connection is closed even when a query raises an error
    Given the database is connected
    When I call query with "SELECT * FROM"
    Then the connection should be closed afterwards
