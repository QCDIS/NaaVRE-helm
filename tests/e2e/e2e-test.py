import os

import pytest
from playwright.sync_api import Page, expect


APP_URL = os.getenv("E2E_BASE_URL", "https://naavre-dev.minikube.test/vreapp")
JUPYTER_WORKSPACE_URL = os.getenv(
    "E2E_WORKSPACE_URL",
    "https://naavre-dev.minikube.test/jupyter/user/user/lab/workspaces/openlab",
)
USERNAME = os.getenv("E2E_USERNAME", "user")
PASSWORD = os.getenv("E2E_PASSWORD", "user")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "ignore_https_errors": True}

@pytest.fixture
def authenticated_page(page: Page) -> Page:
    page.goto(APP_URL)
    page.get_by_role("link", name="NaaVRE Open Lab").click()
    page.get_by_role("link", name="Login to see details").click()
    page.get_by_role("textbox", name="Username or email").fill(USERNAME)
    page.get_by_role("textbox", name="Password").fill(PASSWORD)
    page.get_by_role("button", name="Sign In").click()
    expect(page.get_by_role("button", name="Start Virtual Lab")).to_be_visible()
    return page


@pytest.fixture
def workspace_page(authenticated_page: Page) -> Page:
    with authenticated_page.expect_popup() as popup:
        authenticated_page.get_by_role("button", name="Start Virtual Lab").click()

    workspace = popup.value
    workspace.goto(JUPYTER_WORKSPACE_URL)
    return workspace


@pytest.fixture
def notebook_page(workspace_page: Page) -> Page:
    workspace_page.locator(".jp-LauncherCard-icon").first.click()
    expect(workspace_page.get_by_role("textbox").first).to_be_visible()
    return workspace_page


def test_user_can_sign_in_to_open_lab(authenticated_page: Page) -> None:
    expect(authenticated_page.get_by_role("button", name="Start Virtual Lab")).to_be_visible()


def test_user_can_start_virtual_lab(workspace_page: Page) -> None:
    expect(workspace_page).to_have_url(JUPYTER_WORKSPACE_URL)


def test_user_can_edit_and_save_notebook(notebook_page: Page) -> None:
    code = (
        "str_list = ['a', 'b', 'c', 'd']\n"
        "new_lines = [line + '_proc' for line in str_list]\n"
        "assert new_lines == ['a_proc', 'b_proc', 'c_proc', 'd_proc']"
    )
    cell = notebook_page.get_by_role("textbox").first
    cell.fill(code)
    cell.press("ControlOrMeta+s")

    expect(cell).to_contain_text("new_lines")


def test_user_can_run_notebook_cell(notebook_page: Page) -> None:
    notebook_page.get_by_role("textbox").first.fill(
        "str_list = ['a', 'b', 'c', 'd']\n"
        "new_lines = [line + '_proc' for line in str_list]\n"
        "print(new_lines)"
    )
    notebook_page.get_by_role("button", name="Run this cell and advance (").click()

    expect(
        notebook_page.get_by_text("['a_proc', 'b_proc', 'c_proc', 'd_proc']")
    ).to_be_visible()


def test_user_can_containerize_notebook_cell(notebook_page: Page) -> None:
    notebook_page.get_by_role("textbox").first.fill("print('containerize me')")
    notebook_page.get_by_role("button", name="Analyze cell").click()
    notebook_page.locator("#combo-box-demo").click()
    notebook_page.get_by_role("option", name="python").click()
    notebook_page.get_by_role("button", name="Containerize").click()
