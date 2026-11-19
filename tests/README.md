# NaaVRE UI Tests

Install dependencies:

```bash
npm install
```

## Running Tests

First go to the tests' directory:

```bash
cd tests
```
end-to-end tests:
```bash
npx playwright test
```    

Use environment variables to target a deployment and credentials:
```bash
E2E_BASE_URL="https://<host>/vreapp" \
E2E_JUPYTERHUB_URL="https://<host>/vreapp/vl/openlab" \
E2E_USERNAME="<username>" \
E2E_PASSWORD="<password>" \
npx playwright test
```

For deployments with custom UI labels/selectors, you can override journey actions:
```bash
E2E_START_LAB_SELECTOR="<css-selector>" \
E2E_NEW_NOTEBOOK_SELECTOR="<css-selector>" \
E2E_CONTAINERIZE_SELECTOR="<css-selector>" \
E2E_CREATE_WORKFLOW_SELECTOR="<css-selector>" \
E2E_RUN_WORKFLOW_SELECTOR="<css-selector>" \
npx playwright test
```

Run only the end-to-end journey test:
```bash
npx playwright test -g "full user journey"
```

Optional variables for notebook run assertions:
```bash
E2E_NOTEBOOK_NAME="naavre-e2e-notebook" \
E2E_CELL_OUTPUT_PROBE="naavre-e2e-cell-ok" \
npx playwright test -g "full user journey"
```
Interactive UI mode:
```bash
npx playwright test --ui
``` 

Test only on Desktop Chrome:
```bash
  npx playwright test --project=chromium
```
Run the tests in a specific file:
```bash
npx playwright test example
```
Run the tests in debug mode:
```bash
  npx playwright test --debug
```

Auto generate tests with Codegen:
```bash
  npx playwright codegen
```


And check out the following files:
  - ./e2e/example.spec.ts - Example end-to-end test
  - ./playwright.config.ts - Playwright Test configuration

Visit https://playwright.dev/docs/intro for more information. 



## Test Coverage

The following features are covered:

- [x] Basic navigation to VRE app
- [x] Login functionality
- [x] Browse labs
- [x] Create notebook
- [x] Create containers
- [x] Build workflow
- [x] Execute workflow

## Screenshots

Test screenshots are saved to the `screenshots/` directory during test runs.

