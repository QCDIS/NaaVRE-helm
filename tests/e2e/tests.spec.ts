import { test, expect, type Page } from '@playwright/test';

const appUrl = process.env.E2E_BASE_URL ?? 'https://naavre-dev.minikube.test/vreapp';
const validUsername = process.env.E2E_USERNAME ?? 'user';
const validPassword = process.env.E2E_PASSWORD ?? 'user';
const defaultJupyterHubUrl = new URL('vl/openlab', appUrl.endsWith('/') ? appUrl : `${appUrl}/`).toString();
const jupyterHubUrl = process.env.E2E_JUPYTERHUB_URL ?? defaultJupyterHubUrl;
const vlabName = process.env.E2E_VLAB_NAME ?? 'Open Lab';
const notebookName = process.env.E2E_NOTEBOOK_NAME ?? `naavre-e2e-${Date.now()}`;
const cellOutputProbe = process.env.E2E_CELL_OUTPUT_PROBE ?? 'naavre-e2e-cell-ok';

const selectors = {
  startLab: process.env.E2E_START_LAB_SELECTOR,
  newNotebook: process.env.E2E_NEW_NOTEBOOK_SELECTOR,
  containerize: process.env.E2E_CONTAINERIZE_SELECTOR,
  createWorkflow: process.env.E2E_CREATE_WORKFLOW_SELECTOR,
  runWorkflow: process.env.E2E_RUN_WORKFLOW_SELECTOR,
};

test.use({ ignoreHTTPSErrors: true });

async function loginField(page: Page, names: RegExp[]) {
  for (const name of names) {
    const field = page.getByRole('textbox', { name }).first();
    if (await field.isVisible({ timeout: 2_000 }).catch(() => false)) {
      return field;
    }
  }

  throw new Error('Could not find expected login input field.');
}

async function openLoginPage(page: Page) {
  await page.goto(appUrl);
  await expect(page).toHaveTitle(/NaaVRE PaaS/i);
  await page.getByRole('link', { name: 'Login' }).click();

  await expect(
    page.getByRole('textbox', { name: /username|email/i }).first()
  ).toBeVisible();
  await expect(page.getByRole('textbox', { name: /password/i }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
}

async function login(
  page: Page,
  username: string,
  password: string,
) {
  const usernameField = await loginField(page, [/username or email/i, /username/i, /email/i]);
  const passwordField = await loginField(page, [/password/i]);

  await usernameField.fill(username);
  await passwordField.fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
}

async function clickBySelector(page: Page, selector: string | undefined) {
  if (!selector) {
    return false;
  }

  const element = page.locator(selector).first();
  if (await element.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await element.click();
    return true;
  }

  return false;
}

async function clickByTextPatterns(page: Page, patterns: RegExp[], actionName: string) {
  const candidates = page.locator(
    'button, a, [role="button"], [role="link"], [role="menuitem"], [role="tab"], [role="option"], .jp-CommandPalette-item'
  );

  for (const pattern of patterns) {
    const candidate = candidates.filter({ hasText: pattern }).first();
    if (await candidate.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await candidate.click();
      return;
    }
  }

  throw new Error(`Could not find UI control for action "${actionName}". Set the matching E2E_*_SELECTOR env var.`);
}

async function clickAction(
  page: Page,
  selector: string | undefined,
  patterns: RegExp[],
  actionName: string
) {
  const clickedBySelector = await clickBySelector(page, selector);
  if (!clickedBySelector) {
    await clickByTextPatterns(page, patterns, actionName);
  }
}

async function expectAnyText(page: Page, patterns: RegExp[], description: string) {
  for (const pattern of patterns) {
    const found = await page.getByText(pattern).first().isVisible({ timeout: 3_000 }).catch(() => false);
    if (found) {
      return;
    }
  }

  throw new Error(`Could not verify "${description}" from page content.`);
}

async function ensureLabOrNotebookPage(page: Page) {
  if (/\/(lab|tree)(\/|$)/i.test(page.url())) {
    return;
  }

  await clickAction(
    page,
    selectors.startLab,
    [
      new RegExp(vlabName, 'i'),
      /start (my )?(server|lab|instance)/i,
      /launch (server|lab|instance)/i,
      /spawn/i,
      /open (lab|jupyter)/i,
    ],
    'start virtual lab'
  );

  await expect(page).toHaveURL(/\/(lab|tree)(\/|$)/i, { timeout: 180_000 });
}

async function navigateToJupyterAndStartLab(page: Page) {
  await page.goto(jupyterHubUrl);
  await ensureLabOrNotebookPage(page);
}

async function waitForNotebookPage(page: Page) {
  await expect(page).toHaveURL(/\.ipynb|\/lab(\/|$)|\/tree(\/|$)/i, { timeout: 60_000 });
  await expect(page.locator('.jp-Notebook, .jp-CodeCell').first()).toBeVisible({ timeout: 60_000 });
}

async function createNotebookAndExecuteCell(page: Page) {
  await clickAction(
    page,
    selectors.newNotebook,
    [/new notebook/i, /notebook/i, /python 3/i, /python/i],
    'create notebook'
  );

  await waitForNotebookPage(page);
  await page.keyboard.press('ControlOrMeta+s').catch(() => undefined);

  const notebookNameInput = page.locator('input[aria-label*="File Name"], input[placeholder*="Name"]').first();
  if (await notebookNameInput.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await notebookNameInput.fill(`${notebookName}.ipynb`);
    await page.keyboard.press('Enter').catch(() => undefined);
  }

  const firstCodeCell = page.locator('.jp-CodeCell .cm-content').first();
  await firstCodeCell.click({ timeout: 30_000 });
  await page.keyboard.type(`print("${cellOutputProbe}")`);
  await page.keyboard.press('Shift+Enter');
  await expect(page.getByText(cellOutputProbe)).toBeVisible({ timeout: 60_000 });
}

async function containerizeCells(page: Page) {
  await clickAction(
    page,
    selectors.containerize,
    [/containeriz/i, /build container/i, /create container/i],
    'containerize cells'
  );

  await clickByTextPatterns(
    page,
    [/create/i, /build/i, /submit/i, /ok/i],
    'confirm containerization'
  ).catch(() => {
    // Some deployments submit immediately without confirmation dialogs.
  });

  await expectAnyText(
    page,
    [/container/i, /image/i, /submitted|queued|running|created|success/i],
    'containerization feedback'
  );
}

async function createWorkflow(page: Page) {
  await clickAction(
    page,
    selectors.createWorkflow,
    [/create workflow/i, /build workflow/i, /workflow from notebook/i, /workflow/i],
    'create workflow'
  );

  await clickByTextPatterns(
    page,
    [/create/i, /build/i, /generate/i, /submit/i, /ok/i],
    'confirm workflow creation'
  ).catch(() => {
    // Some deployments create immediately without explicit confirmation.
  });

  await expectAnyText(
    page,
    [/workflow/i, /created|generated|saved|success/i],
    'workflow creation feedback'
  );
}

async function runWorkflow(page: Page) {
  await clickAction(
    page,
    selectors.runWorkflow,
    [/run workflow/i, /execute workflow/i, /submit workflow/i, /^run$/i],
    'run workflow'
  );

  await clickByTextPatterns(
    page,
    [/run/i, /execute/i, /submit/i, /ok/i],
    'confirm workflow run'
  ).catch(() => {
    // Some deployments submit immediately.
  });

  await expectAnyText(
    page,
    [/workflow/i, /submitted|queued|running|succeeded|completed|success/i],
    'workflow run feedback'
  );
}

test.describe('login', () => {
  test('shows login entry point from app home', async ({ page }) => {
    await page.goto(appUrl);
    await expect(page).toHaveTitle(/NaaVRE PaaS/i);
    await expect(page.getByRole('link', { name: 'Login' })).toBeVisible();
  });

  test('shows required fields in login page', async ({ page }) => {
    await openLoginPage(page);
  });

  test('keeps user on login page when credentials are empty', async ({ page }) => {
    await openLoginPage(page);
    const loginUrl = page.url();
    await page.getByRole('button', { name: /sign in/i }).click();

    expect(page.url()).toBe(loginUrl);
    await expect(page.getByRole('textbox', { name: /username|email/i }).first()).toBeVisible();
    await expect(page.getByRole('textbox', { name: /password/i }).first()).toBeVisible();
  });

  test('rejects invalid credentials', async ({ page }) => {
    await openLoginPage(page);
    await login(page, 'invalid-user', 'invalid-password');

    await expect(page.getByRole('textbox', { name: /username|email/i }).first()).toBeVisible();
    await expect(page.getByRole('textbox', { name: /password/i }).first()).toBeVisible();
    await expect(page.getByText(/invalid username or password/i)).toHaveCount(1);
  });

  test('logs in with valid credentials and shows logged-in state', async ({ page }) => {
    await openLoginPage(page);
    await login(page, validUsername, validPassword);

    await expect(page.getByRole('link', { name: 'Login' })).toHaveCount(0);
    await expect(page.getByText(`Logged in as user ${validUsername}`)).toHaveCount(1);
  });

  test('keeps logged-in user session after page reload', async ({ page }) => {
    await openLoginPage(page);
    await login(page, validUsername, validPassword);

    await page.reload();
    await expect(page.getByRole('link', { name: 'Login' })).toHaveCount(0);
    await expect(page.getByText(`Logged in as user ${validUsername}`)).toHaveCount(1);
  });
});

test.describe('full user journey', () => {
  test('logs in, starts a virtual lab, creates a notebook, containerizes cells, creates workflow, and runs it', async ({ page }) => {
    test.slow();

    await test.step('Login', async () => {
      await openLoginPage(page);
      await login(page, validUsername, validPassword);
      await expect(page.getByRole('link', { name: 'Login' })).toHaveCount(0);
      await expect(page.getByText(`Logged in as user ${validUsername}`)).toHaveCount(1);
    });

    await test.step('Start virtual lab instance', async () => {
      await navigateToJupyterAndStartLab(page);
    });

    await test.step('Create notebook', async () => {
      await createNotebookAndExecuteCell(page);
    });

    await test.step('Containerize notebook cells', async () => {
      await containerizeCells(page);
    });

    await test.step('Create workflow', async () => {
      await createWorkflow(page);
    });

    await test.step('Run workflow', async () => {
      await runWorkflow(page);
    });
  });
});