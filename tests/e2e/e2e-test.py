import json
import os
import re
import uuid
from urllib.parse import parse_qs, quote, urlsplit

import pytest
from playwright.sync_api import Page, expect

APP_URL = os.getenv("E2E_BASE_URL", "https://naavre-dev.minikube.test/vreapp")
JUPYTER_WORKSPACE_URL = os.getenv(
    "E2E_WORKSPACE_URL",
    "https://naavre-dev.minikube.test/jupyter/user/user/lab/workspaces/openlab",
)
USERNAME = os.getenv("E2E_USERNAME", "user")
PASSWORD = os.getenv("E2E_PASSWORD", "user")

notebook_code = {
    'cell1': "# input-list\n\nstr_list = ['a', 'b', 'c', 'd', 'e',"
             " 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', "
             "'p','q']",
    'cell2': "# str-parallel-processing\n\nnew_lines = []\n"
             "for line in str_list:\n    line += '_processed'"
             "\n    print(line)\n    new_lines.append(line)",
    'cell3': "# assert-new-lines\n"
             "\nassert new_lines == ['a_processed', 'b_processed', "
             "'c_processed','d_processed', 'e_processed', 'f_processed',"
                     "'g_processed', 'h_processed', 'i_processed',"
                     "'j_processed', 'k_processed', 'l_processed',"
                     "'m_processed', 'n_processed', 'o_processed',"
                     "'p_processed', 'q_processed']"}

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
    workspace_page.get_by_role("menuitem", name="File", exact=True).click()
    workspace_page.get_by_role("menuitem", name="New Launcher").click()
    workspace_page.locator('.jp-LauncherCard[data-category="Notebook"]').get_by_title(
        "Python [conda env:vanilla]", exact=True
    ).click()
    expect(workspace_page.get_by_role("textbox").first).to_be_visible()
    return workspace_page


def test_user_can_sign_in_to_open_lab(authenticated_page: Page) -> None:
    expect(authenticated_page.get_by_role("button", name="Start Virtual Lab")).to_be_visible()

@pytest.fixture
def created_notebook(notebook_page: Page) -> str:
    cell = notebook_page.get_by_role("textbox").first
    cell.fill(notebook_code['cell1'])
    cell.press("ControlOrMeta+s")

    notebook_name = f"notebook-{uuid.uuid4().hex}.ipynb"
    filename = notebook_page.get_by_role("textbox", name="File name")
    filename.fill(notebook_name)
    filename.press("Enter")
    expect(cell.locator(".cm-line")).to_have_text(
        notebook_code['cell1'].split("\n"))

    # Create a new cell and add notebook_code['cell2'] to it
    cell.click()
    notebook_page.get_by_role("feed", name="Cells").get_by_role("button",
                                                                name="Insert a cell below (B)").click()
    new_cell = notebook_page.get_by_role("textbox").last
    new_cell.fill(notebook_code['cell2'])
    new_cell.press("ControlOrMeta+s")
    expect(new_cell.locator(".cm-line")).to_have_text(
        notebook_code['cell2'].split("\n"))

    # Create a new cell and add notebook_code['cell3'] to it
    new_cell.click()
    notebook_page.get_by_role("feed", name="Cells").get_by_role("button",
                                                                name="Insert a cell below (B)").click()
    new_cell = notebook_page.get_by_role("textbox").last
    new_cell.fill(notebook_code['cell3'])
    new_cell.press("ControlOrMeta+s")
    expect(new_cell.locator(".cm-line")).to_have_text(
        notebook_code['cell3'].split("\n"))
    return notebook_name


def test_user_can_create_new_notebook(notebook_page: Page, created_notebook: str) -> None:
    expect(notebook_page.get_by_role("tab", name=created_notebook)).to_be_visible()


def test_user_can_run_notebook(notebook_page: Page, created_notebook: str) -> None:
    tab = notebook_page.get_by_role("tab", name=created_notebook)
    expect(tab).not_to_have_class(re.compile(r"\bjp-mod-dirty\b"))
    tab.click(button="middle")
    expect(tab).to_have_count(0)
    file_browser = notebook_page.get_by_role("region", name="File Browser Section")
    if not file_browser.is_visible():
        notebook_page.get_by_role("tab", name=re.compile("File Browser")).click()
    file_browser.locator("span").filter(has_text=created_notebook).first.dblclick()
    last_cell = notebook_page.get_by_role("textbox").nth(2)
    last_cell.fill(notebook_code['cell3'] + "\nprint('notebook execution complete')")
    last_cell.press("ControlOrMeta+s")
    notebook_page.get_by_role("menuitem", name="Run", exact=True).click()
    notebook_page.get_by_role("menuitem", name="Restart Kernel and Run All Cells").click()
    notebook_page.get_by_role("button", name="Confirm Kernel Restart").click()

    cells = notebook_page.get_by_role("feed", name="Cells").locator(".jp-Cell")
    expect(cells).to_have_count(3)
    expect(cells.nth(2).locator(".jp-OutputArea-output")).to_contain_text(
        "notebook execution complete", timeout=120_000
    )
    expect(cells.nth(1).locator(".jp-OutputArea-output")).to_contain_text("q_processed")
    expect(notebook_page.locator(".jp-RenderedError")).to_have_count(0)


def analyze_cell(page: Page, index: int) -> dict:
    page.get_by_role("feed", name="Cells").get_by_role("textbox").nth(index).click()
    with page.expect_response(
        lambda response: (
            "naavre-communicator/external-service" in response.url
            and response.request.post_data_json["query"]["url"].endswith("/extract_cell")
        ),
        timeout=120_000,
    ) as response_info:
        page.get_by_role("button", name="Analyze cell").click()
    response = response_info.value
    assert response.ok
    result = response.json()
    assert result["status_code"] == 200, result["content"]
    cell = json.loads(result["content"])
    expect(page.locator("#combo-box-demo")).to_be_visible(timeout=120_000)
    return cell


def open_containerizer(page: Page) -> None:
    page.get_by_role("tab", name="NaaVRE containerizer").get_by_role("img").click()
    expect(page.get_by_role("button", name="Analyze cell")).to_be_visible()


def test_user_can_analyze_notebook_cells(notebook_page: Page, created_notebook: str) -> None:
    open_containerizer(notebook_page)
    expected_variables = (
        ("outputs", "str_list"),
        ("inputs", "str_list"),
        ("inputs", "new_lines"),
    )
    for index, (category, variable) in enumerate(expected_variables):
        cell = analyze_cell(notebook_page, index)
        assert variable in {item["name"] for item in cell[category]}


def containerize_cell(page: Page, index: int) -> None:
    cell = analyze_cell(page, index)
    page.locator("#combo-box-demo").click()
    page.get_by_role("option", name="python", exact=True).click()
    page.get_by_role("button", name="Containerize", exact=True).click()
    expect(page.get_by_text(
        re.compile(
            rf"^(Containerized {re.escape(cell['title'])}|"
            rf"Cell {re.escape(cell['title'])} is already containerized)$"
        )
    )).to_be_visible(timeout=600_000)


def test_user_can_containerize_notebook_cells(notebook_page: Page, created_notebook: str) -> None:
    open_containerizer(notebook_page)
    for index in range(3):
        containerize_cell(notebook_page, index)


def test_user_can_compose_and_submit_workflow(notebook_page: Page, created_notebook: str) -> None:
    page = notebook_page
    open_containerizer(page)
    for index in range(3):
        containerize_cell(page, index)

    page.set_viewport_size({"width": 2400, "height": 1000})
    page.get_by_role("menuitem", name="File", exact=True).click()
    page.get_by_role("menuitem", name="New Launcher").click()
    page.get_by_text("Experiment Manager", exact=True).click()

    editor = page.get_by_role("region", name="notebook content")
    canvas = editor.locator("div[tabindex='0'][config]")
    catalog_search = editor.get_by_role("textbox")
    for title, x, y in (
        ("input-list", 400, 260),
        ("Splitter", 720, 260),
        ("str-parallel-processing", 1040, 260),
        ("Merger", 1409, 254),
        ("assert-new-lines", 1686, 262),
    ):
        if title not in ("Splitter", "Merger"):
            with page.expect_response(
                lambda response: (
                    "naavre-communicator/external-service" in response.url
                    and "/workflow-cells/" in response.request.post_data_json["query"]["url"]
                    and parse_qs(urlsplit(
                        response.request.post_data_json["query"]["url"]
                    ).query).get("search") == [title]
                ),
                timeout=60_000,
            ) as search_info:
                catalog_search.fill(title)
            assert search_info.value.ok
            search_result = search_info.value.json()
            assert search_result["status_code"] == 200, search_result["content"]
        component = editor.locator('[draggable="true"]').filter(
            has=page.locator(f'[aria-label="{title}"]')
        )
        if title not in ("Splitter", "Merger"):
            component = component.filter(has=page.get_by_label("me", exact=True))
            component = component.filter(has=page.get_by_label("build succeeded"))
        component.first.drag_to(canvas, target_position={"x": x, "y": y})
        expect(canvas.locator(".react-draggable").filter(
            has=page.get_by_label(title, exact=True)
        )).to_have_count(1)

    nodes = canvas.locator(".react-draggable")
    input_node = nodes.filter(has=page.get_by_label("input-list", exact=True))
    splitter = nodes.filter(has=page.get_by_label("Splitter", exact=True))
    processing = nodes.filter(has=page.get_by_label("str-parallel-processing", exact=True))
    merger = nodes.filter(has=page.get_by_label("Merger", exact=True))
    assertion = nodes.filter(has=page.get_by_label("assert-new-lines", exact=True))
    input_node.locator('[data-port-id="str_list"] [aria-label="str_list"] > div:last-child').drag_to(
        splitter.locator('[data-port-id="splitter_source"] [aria-label="splitter_source"] > div')
    )
    splitter.locator('[data-port-id="splitter_target"] [aria-label="splitter_target"] > div').drag_to(
        processing.locator('[data-port-id="str_list"] [aria-label="str_list"] > div:first-child')
    )
    processing.locator('[data-port-id="new_lines"] [aria-label="new_lines"] > div:last-child').drag_to(
        merger.locator('[data-port-id="merger_source"] [aria-label="merger_source"] > div')
    )
    merger.locator('[data-port-id="merger_target"] [aria-label="merger_target"] > div').drag_to(
        assertion.locator('[data-port-id="new_lines"] [aria-label="new_lines"] > div:first-child')
    )

    workflow_name = f"workflow-{uuid.uuid4().hex}.naavrewf"
    editor.press("ControlOrMeta+s")
    page.get_by_role("textbox", name="File name").fill(workflow_name)
    with page.expect_response(
        lambda response: "/api/contents/" in response.url and response.request.method == "PATCH"
    ) as rename_info:
        page.get_by_role("button", name="Rename").click()
    rename_response = rename_info.value
    assert rename_response.ok
    saved_path = rename_response.json()["path"]
    contents_url = (
        rename_response.url.split("/api/contents/", 1)[0]
        + "/api/contents/" + quote(saved_path, safe="/")
    )
    saved_response = page.request.get(contents_url)
    assert saved_response.ok
    chart = json.loads(saved_response.json()["content"])["chart"]
    assert len(chart["nodes"]) == 5
    node_ids = {}
    for node_id, node in chart["nodes"].items():
        cell = node["properties"]["cell"]
        title = cell["title"]
        if cell.get("owner"):
            title = title.removesuffix(f"-{cell['owner']}")
        node_ids[title] = node_id
    assert set(node_ids) == {
        "input-list", "Splitter", "str-parallel-processing", "Merger", "assert-new-lines"
    }
    expected_nodes = {
        "input-list": ("workflow-cell", {"str_list": "right"}, (400, 260)),
        "Splitter": ("splitter", {"splitter_source": "left", "splitter_target": "right"}, (720, 260)),
        "str-parallel-processing": ("workflow-cell", {"str_list": "left", "new_lines": "right"}, (1040, 260)),
        "Merger": ("merger", {"merger_source": "left", "merger_target": "right"}, (1409, 254)),
        "assert-new-lines": ("workflow-cell", {"new_lines": "left"}, (1686, 262)),
    }
    for title, (node_type, ports, position) in expected_nodes.items():
        node = chart["nodes"][node_ids[title]]
        assert node["type"] == node_type
        assert {name: port["type"] for name, port in node["ports"].items()} == ports
        assert node["position"]["x"] == pytest.approx(position[0], abs=3)
        assert node["position"]["y"] == pytest.approx(position[1], abs=3)
    assert chart["properties"]["params"] == []
    links = {
        (link["from"]["nodeId"], link["from"]["portId"],
         link["to"]["nodeId"], link["to"]["portId"])
        for link in chart["links"].values()
    }
    assert links == {
        (node_ids["input-list"], "str_list", node_ids["Splitter"], "splitter_source"),
        (node_ids["Splitter"], "splitter_target", node_ids["str-parallel-processing"], "str_list"),
        (node_ids["str-parallel-processing"], "new_lines", node_ids["Merger"], "merger_source"),
        (node_ids["Merger"], "merger_target", node_ids["assert-new-lines"], "new_lines"),
    }

    page.get_by_role("button", name="Run", exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("Run Workflow")).to_be_visible()
    with page.expect_response(
        lambda response: (
            "naavre-communicator/external-service" in response.url
            and response.request.post_data_json["query"]["url"].endswith("/submit")
        ),
        timeout=120_000,
    ) as submit_info:
        dialog.get_by_role("button", name="Run", exact=True).click()
    submit_response = submit_info.value
    assert submit_response.ok
    submitted_chart = submit_response.request.post_data_json["query"]["data"]["naavrewf2"]
    assert set(submitted_chart["nodes"]) == set(chart["nodes"])
    assert submitted_chart["links"] == chart["links"]
    result = submit_response.json()
    assert result["status_code"] == 200, result["content"]
    run_url = json.loads(result["content"])["run_url"]
    expect(dialog.get_by_text("Workflow submitted")).to_be_visible()
    link = dialog.get_by_role("link", name="Show in workflow engine")
    expect(link).to_have_attribute("href", run_url)
    with page.expect_popup() as workflow_popup:
        link.click()
    workflow_page = workflow_popup.value
    workflow_name = run_url.rstrip("/").rsplit("/", 1)[-1]
    details = workflow_page.get_by_text(re.compile(r"^workflow details$", re.I))
    login = workflow_page.get_by_role("button", name=re.compile("Login", re.I)).first
    graph_node = workflow_page.locator("svg .node-label").first
    expect(login.or_(graph_node)).to_be_visible(timeout=60_000)
    if login.is_visible():
        login.click()
        continue_button = workflow_page.get_by_text("Continue", exact=True)
        workflow_link = workflow_page.get_by_role("link", name=re.compile(re.escape(workflow_name)))
        expect(continue_button.or_(workflow_link).or_(details)).to_be_visible(timeout=60_000)
        if continue_button.is_visible():
            continue_button.click()
        if not details.is_visible():
            workflow_link.click()
    expect(details).to_be_visible(timeout=60_000)
    expect(workflow_page).to_have_url(re.compile(rf"^{re.escape(run_url)}(?:[?#]|$)"))
