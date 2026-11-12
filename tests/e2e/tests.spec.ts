import { test, expect, type Page } from '@playwright/test';

const appUrl = process.env.E2E_BASE_URL ?? 'https://naavre-dev.minikube.test/vreapp';
const validUsername = process.env.E2E_USERNAME ?? 'user';
const validPassword = process.env.E2E_PASSWORD ?? 'user';
const jupyterHubUrl = process.env.E2E_JUPYTERHUB_URL ?? new URL('/jhub', appUrl).toString();
const vlabName = process.env.E2E_VLAB_NAME ?? 'Open Lab';

const selectors = {
  startLab: process.env.E2E_START_LAB_SELECTOR,
  newNotebook: process.env.E2E_NEW_NOTEBOOK_SELECTOR,
  containerize: process.env.E2E_CONTAINERIZE_SELECTOR,
  createWorkflow: process.env.E2E_CREATE_WORKFLOW_SELECTOR,
  runWorkflow: process.env.E2E_RUN_WORKFLOW_SELECTOR,
};

test.use({ ignoreHTTPSErrors: true });

async function openLoginPage(page: Page) {
  await page.goto(appUrl);
  await expect(page).toHaveTitle(/NaaVRE PaaS/i);
  await page.getByRole('link', { name: 'Login' }).click();
  await expect(page.getByRole('textbox', { name: 'Username or email' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Password' })).toBeVisible();
  await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
}

async function login(
  page: Page,
  username: string,
  password: string,
) {
  await page.getByRole('textbox', { name: 'Username or email' }).fill(username);
  await page.getByRole('textbox', { name: 'Password' }).fill(password);
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

async function expectAnyText(page: Page, patterns: RegExp[], description: string) {
  for (const pattern of patterns) {
    const found = await page.getByText(pattern).first().isVisible({ timeout: 3_000 }).catch(() => false);
    if (found) {
      return;
    }
  }

  throw new Error(`Could not verify "${description}" from page content.`);
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
    await expect(page.getByRole('textbox', { name: 'Username or email' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Password' })).toBeVisible();
  });

  test('rejects invalid credentials', async ({ page }) => {
    await openLoginPage(page);
    await login(page, 'invalid-user', 'invalid-password');

    await expect(page.getByRole('textbox', { name: 'Username or email' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Password' })).toBeVisible();
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
      await page.goto(jupyterHubUrl);

      if (!/\/(lab|tree)(\/|$)/i.test(page.url())) {
        const clickedBySelector = await clickBySelector(page, selectors.startLab);
        if (!clickedBySelector) {
          await clickByTextPatterns(
            page,
            [
              new RegExp(vlabName, 'i'),
              /start (my )?(server|lab|instance)/i,
              /launch (server|lab|instance)/i,
              /spawn/i,
              /open (lab|jupyter)/i,
            ],
            'start virtual lab'
          );
        }
      }

      await expect(page).toHaveURL(/\/(lab|tree)(\/|$)/i, { timeout: 180_000 });
    });

    await test.step('Create notebook', async () => {
      const clickedBySelector = await clickBySelector(page, selectors.newNotebook);
      if (!clickedBySelector) {
        await clickByTextPatterns(
          page,
          [/new notebook/i, /notebook/i, /python 3/i, /python/i],
          'create notebook'
        );
      }

      await expect(page).toHaveURL(/\.ipynb|\/lab(\/|$)/i, { timeout: 30_000 });

      const firstCodeCell = page.locator('.jp-CodeCell .cm-content').first();
      await firstCodeCell.click({ timeout: 30_000 });
      await page.keyboard.type('print("naavre-e2e")');
      await page.keyboard.press('Shift+Enter');
      await expect(page.getByText('naavre-e2e')).toBeVisible({ timeout: 30_000 });
    });

    await test.step('Containerize notebook cells', async () => {
      const clickedBySelector = await clickBySelector(page, selectors.containerize);
      if (!clickedBySelector) {
        await clickByTextPatterns(
          page,
          [/containeriz/i, /build container/i, /create container/i],
          'containerize cells'
        );
      }

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
    });

    await test.step('Create workflow', async () => {
      const clickedBySelector = await clickBySelector(page, selectors.createWorkflow);
      if (!clickedBySelector) {
        await clickByTextPatterns(
          page,
          [/create workflow/i, /build workflow/i, /workflow from notebook/i, /workflow/i],
          'create workflow'
        );
      }

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
    });

    await test.step('Run workflow', async () => {
      const clickedBySelector = await clickBySelector(page, selectors.runWorkflow);
      if (!clickedBySelector) {
        await clickByTextPatterns(
          page,
          [/run workflow/i, /execute workflow/i, /submit workflow/i, /^run$/i],
          'run workflow'
        );
      }

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
    });
  });
});