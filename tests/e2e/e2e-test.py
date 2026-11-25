from time import sleep

from playwright.sync_api import Page, expect
import uuid


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

notebook_code = {'cell1': "print('Hello, World!')",
                 'cell2': "print('This is a test notebook.')",
                 'cell3': "print('Goodbye, World!')"}

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "ignore_https_errors": True,
        "record_video_dir": "tests/e2e/videos/",
    }


@pytest.fixture
def authenticated_page(page: Page) -> Page:
    page.goto(APP_URL)
    page.get_by_role("link", name="NaaVRE Open Lab").click()
    page.get_by_role("link", name="Login", exact=True).click()
    page.get_by_role("textbox", name="Username or email").fill(USERNAME)
    page.get_by_role("textbox", name="Password").fill(PASSWORD)
    page.get_by_role("textbox", name="Password").press("Enter")
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
    workspace_page.get_by_title("Python [conda env:vanilla]").first.click()
    expect(workspace_page.get_by_role("textbox").first).to_be_visible()
    return workspace_page


def test_user_can_sign_in_to_open_lab(authenticated_page: Page) -> None:
    expect(authenticated_page.get_by_role("button", name="Start Virtual Lab")).to_be_visible()

def test_user_can_create_new_notebook(notebook_page: Page) -> None:
    cell = notebook_page.get_by_role("textbox").first
    cell.fill(notebook_code['cell1'])
    cell.press("ControlOrMeta+s")

    filename = notebook_page.get_by_role("textbox", name="File name")
    filename.fill(f"notebook-{uuid.uuid4().hex}.ipynb")
    filename.press("Enter")

    expect(cell).to_contain_text(notebook_code['cell1'])