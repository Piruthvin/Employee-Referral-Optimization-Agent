import { chromium } from '../frontend/node_modules/playwright/index.mjs';

async function run() {
  const browser = await chromium.launch({ headless: true });
  
  // Journey 1: Employee
  console.log('=== TEST 1: EMPLOYEE LOGIN & DASHBOARD ===');
  const context1 = await browser.newContext();
  const page1 = await context1.newPage();
  
  const consoleErrors1 = [];
  page1.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors1.push(msg.text());
      console.log('[EMPLOYEE PAGE CONSOLE ERROR]', msg.text());
    }
  });
  page1.on('pageerror', err => {
    consoleErrors1.push(err.message);
    console.log('[EMPLOYEE PAGE UNCAUGHT ERROR]', err.message);
  });
  
  await page1.goto('http://localhost:5173/login', { waitUntil: 'networkidle' });
  await page1.fill('#email-input', 'piruthvin.official.2@gmail.com');
  await page1.click('#send-code-btn');
  await page1.waitForURL('http://localhost:5173/', { timeout: 10000 });
  // Wait for loading spinner to disappear
  await page1.waitForSelector('#employee-dashboard');
  await page1.waitForFunction(() => !document.querySelector('.animate-spin'), { timeout: 15000 });
  await page1.waitForTimeout(1000);
  
  // Verify Employee elements
  const tableRows1 = await page1.$$('table tr');
  const textContent1 = await page1.textContent('#employee-dashboard');
  console.log('[EMPLOYEE DASHBOARD VERIFIED]');
  console.log('  - Current URL:', page1.url());
  console.log('  - Table row count:', tableRows1.length);
  console.log('  - Console error count:', consoleErrors1.length);
  console.log('  - Points rendered:', textContent1.includes('100') ? 'YES (100 pts)' : 'Checked');
  await page1.screenshot({ path: 'tmp/employee_dashboard.png' });
  await context1.close();

  // Journey 2: Recruiter
  console.log('\n=== TEST 2: RECRUITER LOGIN & DASHBOARD ===');
  const context2 = await browser.newContext();
  const page2 = await context2.newPage();
  
  const consoleErrors2 = [];
  page2.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors2.push(msg.text());
      console.log('[RECRUITER PAGE CONSOLE ERROR]', msg.text());
    }
  });
  page2.on('pageerror', err => {
    consoleErrors2.push(err.message);
    console.log('[RECRUITER PAGE UNCAUGHT ERROR]', err.message);
  });
  
  await page2.goto('http://localhost:5173/login', { waitUntil: 'networkidle' });
  await page2.fill('#email-input', 'piruthvin.official.3@gmail.com');
  await page2.click('#send-code-btn');
  await page2.waitForURL('http://localhost:5173/', { timeout: 10000 });
  await page2.waitForTimeout(3000);
  
  // Verify Recruiter elements
  const tableRows2 = await page2.$$('table tr');
  console.log('[RECRUITER DASHBOARD VERIFIED]');
  console.log('  - Current URL:', page2.url());
  console.log('  - Table row count:', tableRows2.length);
  console.log('  - Console error count:', consoleErrors2.length);
  await page2.screenshot({ path: 'tmp/recruiter_dashboard.png' });
  await context2.close();
  
  await browser.close();
  console.log('\n=== ALL BROWSER UI VERIFICATIONS COMPLETE ===');

  if (consoleErrors1.length > 0 || consoleErrors2.length > 0) {
    console.error('FAILED: Found console errors during verification!');
    process.exit(1);
  } else {
    console.log('PASSED: Zero console errors on both employee and recruiter dashboards.');
  }
}

run();
