Feature: Open WebUI admin integration
  As someone setting up the project from a clean checkout
  I want the MCP tool server wired into Open WebUI automatically
  So that the admin integrations page works and models can chart Northwind data

  Background:
    Given the Open WebUI stack is running
    And an admin account exists

  # --- Admin integration configuration ---

  Scenario: The tool server configuration endpoint returns a valid response
    When I request the tool server configuration
    Then the response status should be 200
    And the configured tool server url should be "http://mcp:8000/mcp"

  Scenario: Open WebUI can reach the MCP server and list its tools
    When I verify the postgres-mcp tool server connection
    Then the verification should succeed
    And the returned tool specs should include "list_tables, describe_table, sample_table, query, get_schema"

  Scenario: The Northwind Analyst preset carries the matplotlib system prompt
    When I request the model list
    Then the model "northwind-analyst" should be offered
    When I request the "northwind-analyst" model definition
    Then its system prompt should mention matplotlib

  # --- Rendered admin UI ---

  Scenario: The admin integrations settings page renders the MCP connection
    Given I am signed in to the browser as the admin
    When I open the admin integrations settings page
    Then no request should have failed with a server error
    And the page should show the tool server "postgres-mcp"
    And I capture a screenshot named "admin-integrations"

  # --- Chart generation (depends on a live model; see @chart in the README) ---

  @chart
  Scenario Outline: Charts are generated from natural language prompts
    Given I am signed in to the browser as the admin
    When I start a new chat with the analyst model
    And I send the prompt "<prompt>"
    And I run any generated python code
    Then the conversation should contain a rendered chart image
    And I capture a screenshot named "<screenshot>"

    Examples:
      | prompt                                                        | screenshot     |
      | Chart total revenue by product category as a bar chart        | chart-revenue  |
      | Chart the top 10 countries by number of orders as a bar chart | chart-orders   |
