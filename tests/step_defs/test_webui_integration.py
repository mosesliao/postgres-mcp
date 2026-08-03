"""End-to-end BDD steps for the Open WebUI <-> MCP integration.

Requires the full docker compose stack. Run with:

    pytest tests/ -m e2e

The @chart scenarios additionally need Ollama reachable with the analyst
model pulled; they are slow and model-dependent, so CI runs them in a
separate non-gating job.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from tests.webui_client import MCP_CONNECTION, WebUIClient, base_url

FEATURE = "../features/webui_integration.feature"

MODEL_ID = os.environ.get("E2E_MODEL_ID", "northwind-analyst")
SCREENSHOT_DIR = Path(os.environ.get("E2E_SCREENSHOT_DIR", "artifacts/screenshots"))

# Generation on a CPU-only CI runner is slow; keep this generous.
CHART_TIMEOUT_MS = int(os.environ.get("E2E_CHART_TIMEOUT", "300")) * 1000
UI_TIMEOUT_MS = 30_000

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@scenario(FEATURE, "The tool server configuration endpoint returns a valid response")
def test_tool_server_config():
    pass


@scenario(FEATURE, "Open WebUI can reach the MCP server and list its tools")
def test_mcp_reachable():
    pass


@scenario(FEATURE, "The Northwind Analyst preset carries the matplotlib system prompt")
def test_preset_system_prompt():
    pass


@scenario(FEATURE, "The admin integrations settings page renders the MCP connection")
def test_integrations_page_renders():
    pass


@pytest.mark.chart
@scenario(FEATURE, "Charts are generated from natural language prompts")
def test_charts_generated():
    """Split out so `-m "e2e and not chart"` skips the model-dependent runs."""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> dict:
    return {}


@pytest.fixture(scope="session")
def webui() -> WebUIClient:
    client = WebUIClient()
    client.wait_until_ready()
    client.sign_in_or_up()
    return client


@pytest.fixture
def screenshots() -> Path:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return SCREENSHOT_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STOP_BUTTON_SELECTORS = [
    "button[aria-label*='Stop' i]",
    "button[title*='Stop' i]",
]

CHAT_INPUT_SELECTORS = [
    "#chat-input",
    "textarea#chat-input",
    "div[contenteditable='true']",
    "textarea",
]

CHART_IMAGE_SELECTORS = [
    "img[src^='data:image/png']",
    "img[src^='data:image']",
    "img[src^='blob:']",
]


def first_visible(page, selectors, timeout=UI_TIMEOUT_MS):
    """Return the first selector that becomes visible, or None if none do.

    Open WebUI's DOM shifts between releases, so every UI step tries a few
    plausible selectors rather than pinning one and breaking on upgrade.
    """
    deadline = time.time() + timeout / 1000
    while True:
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if locator.is_visible():
                    return locator
            except Exception:  # noqa: BLE001 - element may be transiently detached
                continue
        if time.time() >= deadline:
            return None
        page.wait_for_timeout(500)


def wait_for_generation_to_settle(page, timeout=CHART_TIMEOUT_MS):
    """Wait until the assistant stops streaming.

    Detected by the stop button appearing and then disappearing. If it is never
    seen we return early and let the caller's own assertion supply the timeout.
    """
    deadline = time.time() + timeout / 1000
    saw_stop = False
    while time.time() < deadline:
        streaming = first_visible(page, STOP_BUTTON_SELECTORS, timeout=0) is not None
        if streaming:
            saw_stop = True
        elif saw_stop:
            return
        page.wait_for_timeout(1000)


def fill_chat_input(locator, prompt):
    """Open WebUI uses a textarea in some builds and contenteditable in others."""
    is_textarea = locator.evaluate("el => el.tagName.toLowerCase() === 'textarea'")
    if is_textarea:
        locator.fill(prompt)
    else:
        locator.type(prompt)


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("the Open WebUI stack is running")
def stack_running(webui):
    response = webui.session.get(webui.url("/health"), timeout=10)
    assert response.ok, f"Open WebUI health check failed: HTTP {response.status_code}"


@given("an admin account exists")
def admin_exists(webui):
    assert webui.token, "Expected an authenticated admin session"


@given("I am signed in to the browser as the admin")
def browser_signed_in(page, webui, ctx):
    url = base_url()
    page.context.add_cookies([{"name": "token", "value": webui.token, "url": url}])
    page.add_init_script(f"localStorage.setItem('token', {json.dumps(webui.token)});")

    # Record server errors so a 500 on a background XHR fails the scenario even
    # when the SPA swallows it and just spins forever.
    ctx["server_errors"] = []
    page.on(
        "response",
        lambda response: (
            ctx["server_errors"].append(f"{response.status} {response.url}")
            if response.status >= 500
            else None
        ),
    )


# ---------------------------------------------------------------------------
# When - API
# ---------------------------------------------------------------------------


@when("I request the tool server configuration")
def request_tool_servers(webui, ctx):
    ctx["response"] = webui.tool_servers()


@when("I verify the postgres-mcp tool server connection")
def verify_tool_server(webui, ctx):
    ctx["response"] = webui.verify_tool_server(MCP_CONNECTION)


@when("I request the model list")
def request_models(webui, ctx):
    ctx["response"] = webui.models()


# ---------------------------------------------------------------------------
# When - browser
# ---------------------------------------------------------------------------


@when("I open the admin integrations settings page")
def open_integrations_page(page):
    page.goto(f"{base_url()}/admin/settings/integrations", wait_until="networkidle")


@when("I start a new chat with the analyst model")
def start_chat(page):
    page.goto(f"{base_url()}/?models={MODEL_ID}", wait_until="networkidle")


@when(parsers.parse('I send the prompt "{prompt}"'))
def send_prompt(page, prompt):
    chat_input = first_visible(page, CHAT_INPUT_SELECTORS)
    assert chat_input is not None, "Could not find the chat input"
    chat_input.click()
    fill_chat_input(chat_input, prompt)
    page.keyboard.press("Enter")
    wait_for_generation_to_settle(page)


@when("I run any generated python code")
def run_generated_code(page):
    """Click Run on emitted code blocks. A no-op when auto-execution is on."""
    run_button = first_visible(
        page,
        ["button:has-text('Run')", "button[title*='Run' i]", "button[aria-label*='Run' i]"],
        timeout=15_000,
    )
    if run_button is None:
        return
    run_button.click()
    page.wait_for_timeout(2000)


# ---------------------------------------------------------------------------
# Then - API
# ---------------------------------------------------------------------------


@then(parsers.parse("the response status should be {status:d}"))
def response_status(ctx, status):
    response = ctx["response"]
    assert (
        response.status_code == status
    ), f"Expected HTTP {status}, got {response.status_code}: {response.text[:500]}"


@then(parsers.parse('the configured tool server url should be "{url}"'))
def tool_server_url(ctx, url):
    connections = ctx["response"].json()["TOOL_SERVER_CONNECTIONS"]
    urls = [connection.get("url") for connection in connections]
    assert url in urls, f"Expected {url!r} among configured tool servers, got {urls}"


@then("the verification should succeed")
def verification_succeeded(ctx):
    response = ctx["response"]
    assert response.status_code == 200, (
        "Open WebUI could not reach the MCP server "
        f"(HTTP {response.status_code}): {response.text[:500]}"
    )
    assert response.json().get("status") is True, f"Unexpected body: {response.text[:500]}"


@then(parsers.parse('the returned tool specs should include "{expected}"'))
def tool_specs_include(ctx, expected):
    specs = ctx["response"].json().get("specs", [])
    names = {spec.get("name") for spec in specs}
    missing = {name.strip() for name in expected.split(",")} - names
    assert not missing, f"Missing tools {sorted(missing)}; MCP exposed {sorted(names)}"


@then(parsers.parse('the model "{model_id}" should be offered'))
def model_offered(ctx, model_id):
    payload = ctx["response"].json()
    models = payload.get("data", payload) if isinstance(payload, dict) else payload
    available = [m.get("id") for m in models]
    assert model_id in available, f"Model {model_id!r} not offered. Available: {available}"


@when(parsers.parse('I request the "{model_id}" model definition'))
def request_model_definition(webui, ctx, model_id):
    ctx["response"] = webui.model_by_id(model_id)


@then("its system prompt should mention matplotlib")
def system_prompt_mentions_matplotlib(ctx):
    response = ctx["response"]
    assert response.status_code == 200, (
        f"Could not read the model definition (HTTP {response.status_code}): "
        f"{response.text[:300]}"
    )
    model = response.json()
    # Open WebUI applies params.system; meta.system alone is never sent to the
    # model, so assert on the field that actually reaches the request.
    system = (model.get("params") or {}).get("system", "")
    assert "matplotlib" in system.lower(), (
        f"Expected the system prompt to mention matplotlib, got: {system!r}. "
        f"Response keys: {sorted(model)}"
    )


# ---------------------------------------------------------------------------
# Then - browser
# ---------------------------------------------------------------------------


@then("no request should have failed with a server error")
def no_server_errors(ctx):
    errors = ctx.get("server_errors", [])
    assert not errors, "Server errors during page load:\n  " + "\n  ".join(errors)


@then(parsers.parse('the page should show the tool server "{name}"'))
def page_shows_tool_server(page, name):
    locator = page.get_by_text(re.compile(re.escape(name), re.IGNORECASE)).first
    locator.wait_for(state="visible", timeout=UI_TIMEOUT_MS)


@then("the conversation should contain a rendered chart image")
def conversation_contains_chart(page):
    image = first_visible(page, CHART_IMAGE_SELECTORS, timeout=CHART_TIMEOUT_MS)
    assert image is not None, "No rendered chart image appeared in the conversation"


@then(parsers.parse('I capture a screenshot named "{name}"'))
def capture_screenshot(page, screenshots, name):
    path = screenshots / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    assert path.exists() and path.stat().st_size > 0, f"Screenshot {path} was not written"
