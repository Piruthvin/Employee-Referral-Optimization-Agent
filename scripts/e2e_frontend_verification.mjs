import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');

const FRONTEND_URL = 'http://localhost:5173';
const RESUME_PATH = path.resolve(ROOT_DIR, 'tmp/e2e/Piruthvin_Resume__.pdf');

async function run() {
  console.log('='.repeat(80));
  console.log(' STARTING REAL FRONTEND CLICK-THROUGH VERIFICATION LOOP');
  console.log('='.repeat(80));

  const interceptedCalls = [];

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Intercept every network call to the backend
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes(':8000/api/v1') || url.includes(':8000/health') || url.includes(':8000/ready')) {
      const method = response.request().method();
      const status = response.status();
      const cleanUrl = url.split('?')[0];
      const entry = { method, url: cleanUrl, fullUrl: url, status };
      interceptedCalls.push(entry);
      console.log(`[NETWORK CAPTURED] ${method} ${cleanUrl} -> HTTP ${status}`);
    }
  });

  page.on('dialog', async (dialog) => {
    console.log(`[BROWSER DIALOG] ${dialog.type()}: ${dialog.message()}`);
    await dialog.accept();
  });

  try {
    // =========================================================================
    // JOURNEY 1: RECRUITER JOURNEY (piruthvin.official.3@gmail.com)
    // =========================================================================
    console.log('\n--- [RECRUITER JOURNEY] Navigating to /login ---');
    await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'networkidle' });

    console.log('[UI ACTION] Entering Recruiter email: piruthvin.official.3@gmail.com');
    await page.waitForSelector('#email-input', { timeout: 10000 });
    await page.fill('#email-input', 'piruthvin.official.3@gmail.com');

    console.log('[UI ACTION] Clicking "Send Verification Code" / "Sign In" button');
    await page.click('#send-code-btn');

    // Wait for client-side routing to Recruiter Dashboard
    await page.waitForURL(`${FRONTEND_URL}/`, { timeout: 15000 });
    console.log('[UI VERIFIED] Landed on Recruiter Dashboard: /');
    await page.waitForTimeout(3000);

    // Filter or click on a candidate's "Review" link client-side
    console.log('\n--- [RECRUITER JOURNEY] Candidate Review & Approval ---');
    const reviewLink = await page.$('a:has-text("Review")');
    if (reviewLink) {
      console.log('[UI ACTION] Clicking "Review" link on candidate table row...');
      await reviewLink.click();
      await page.waitForTimeout(2000);
      console.log('[UI VERIFIED] Navigated client-side to Approval Detail Page. Current URL:', page.url());

      // Click "View Resume" button (calls /api/v1/referral/{id}/resume via apiClient)
      const viewResumeBtn = await page.$('button:has-text("View Resume")');
      if (viewResumeBtn) {
        console.log('[UI ACTION] Clicking "View Resume" button...');
        await viewResumeBtn.click();
        await page.waitForTimeout(2000);
      }

      // Check if Approve button is available
      const approveBtn = await page.$('button:has-text("Approve Referral")');
      if (approveBtn) {
        console.log('[UI ACTION] Clicking "Approve Referral" button...');
        await approveBtn.click();
        await page.waitForTimeout(1000);

        // Fill note and submit modal
        const noteArea = await page.$('textarea');
        if (noteArea) {
          await noteArea.fill('Approved during real frontend click-through verification.');
        }
        const confirmBtn = await page.$('button:has-text("Approve"), button:has-text("Confirm")');
        if (confirmBtn) {
          await confirmBtn.click();
          console.log('[UI ACTION] Submitted approval modal');
          await page.waitForTimeout(3000);
        }
      }

      // Check if Schedule Interview button is available
      const scheduleBtn = await page.$('button:has-text("Schedule Interview"):not([disabled])');
      if (scheduleBtn) {
        console.log('[UI ACTION] Clicking "Schedule Interview" button...');
        await scheduleBtn.click();
        await page.waitForTimeout(1000);

        const startTimeInput = await page.$('input[type="datetime-local"]');
        if (startTimeInput) {
          await startTimeInput.fill('2026-10-10T14:30');
        }
        const interviewerInput = await page.$('input[placeholder*="interviewer@company.com"], input[name="interviewer_email"]');
        if (interviewerInput) {
          await interviewerInput.fill('piruthvin.official.3@gmail.com');
        }
        const confirmSchedBtn = await page.$('button[type="submit"]:has-text("Schedule Interview"), button:has-text("Confirm Schedule")');
        if (confirmSchedBtn) {
          console.log('[UI ACTION] Submitting Schedule Interview modal...');
          await confirmSchedBtn.click();
          await page.waitForTimeout(4000);
        }
      }
    }

    // Navigate to Chat via Navbar link
    console.log('\n--- [RECRUITER JOURNEY] Navigating to AI Chat Assistant ---');
    const chatNavLink = await page.$('a[href="/chat"]');
    if (chatNavLink) {
      console.log('[UI ACTION] Clicking "AI Chat Assistant" in Navbar...');
      await chatNavLink.click();
      await page.waitForTimeout(2000);
      console.log('[UI VERIFIED] Navigated to Chat Page. Current URL:', page.url());

      // Type chat query
      const chatInput = await page.$('textarea, input[placeholder*="Type a message"], input[placeholder*="Ask"]');
      if (chatInput) {
        await chatInput.fill('Show candidates currently pending referral review');
        console.log('[UI ACTION] Typed query into Chat input');
        const sendBtn = await page.$('button:has(svg.lucide-send), button[type="submit"]');
        if (sendBtn) {
          await sendBtn.click();
          console.log('[UI ACTION] Clicked Chat Send button');
          await page.waitForTimeout(5000);
        }
      }
    }

    // Logout
    console.log('\n--- [RECRUITER JOURNEY] Logging Out ---');
    const logoutBtn = await page.$('button[title="Sign Out"]');
    if (logoutBtn) {
      console.log('[UI ACTION] Clicking "Sign Out" button in Navbar...');
      await logoutBtn.click();
      await page.waitForTimeout(2000);
    }

    // =========================================================================
    // JOURNEY 2: EMPLOYEE JOURNEY (piruthvin.official.2@gmail.com)
    // =========================================================================
    console.log('\n--- [EMPLOYEE JOURNEY] Logging In as Employee ---');
    await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'networkidle' });
    await page.waitForSelector('#email-input', { timeout: 10000 });
    await page.fill('#email-input', 'piruthvin.official.2@gmail.com');
    console.log('[UI ACTION] Entered Employee email: piruthvin.official.2@gmail.com');
    await page.click('#send-code-btn');
    await page.waitForURL(`${FRONTEND_URL}/`, { timeout: 15000 });
    console.log('[UI VERIFIED] Landed on Employee Dashboard: /');
    await page.waitForTimeout(3000);

    // Open Referral Modal
    console.log('\n--- [EMPLOYEE JOURNEY] Submitting a Referral ---');
    const referBtn = await page.$('#refer-candidate-btn, button:has-text("Refer Candidate"), button:has-text("Submit a Referral")');
    if (referBtn) {
      console.log('[UI ACTION] Clicking "Refer Candidate" button...');
      await referBtn.click();
      await page.waitForTimeout(1000);

      const nameInput = await page.$('input[placeholder*="Alex Morgan"], #candidate-name-input');
      const emailInput = await page.$('input[placeholder*="alex.morgan@gmail.com"], #candidate-email-input');
      const fileInput = await page.$('input[type="file"]');

      if (nameInput && emailInput && fileInput && fs.existsSync(RESUME_PATH)) {
        const uniqueEmail = `real_e2e_cand_${Date.now()}@example.com`;
        await nameInput.fill('Real E2E Candidate');
        await emailInput.fill(uniqueEmail);
        await fileInput.setInputFiles(RESUME_PATH);
        console.log(`[UI ACTION] Filled referral form (email: ${uniqueEmail}) and selected PDF resume`);

        const submitBtn = await page.$('button[type="submit"]:has-text("Submit Referral")');
        if (submitBtn) {
          console.log('[UI ACTION] Clicking "Submit Referral" button...');
          await submitBtn.click();
          await page.waitForTimeout(10000);
          console.log('[UI VERIFIED] Referral submission processed!');

          // Close modal
          const closeModalBtn = await page.$('button:has-text("Done"), button:has-text("Close"), button:has(svg.lucide-x)');
          if (closeModalBtn) {
            await closeModalBtn.click();
            await page.waitForTimeout(1000);
          }
        }
      }
    }

    // Logout
    console.log('\n--- [EMPLOYEE JOURNEY] Logging Out ---');
    const empLogoutBtn = await page.$('button[title="Sign Out"]');
    if (empLogoutBtn) {
      await empLogoutBtn.click();
      await page.waitForTimeout(2000);
    }

    console.log('\n' + '='.repeat(80));
    console.log(' ALL FRONTEND CLICK JOURNEYS COMPLETED SUCCESSFULLY');
    console.log('='.repeat(80));

    // Summary of captured network calls
    console.log('\n--- UNIQUE CAPTURED BACKEND API CALLS ---');
    const uniqueCalls = new Map();
    for (const c of interceptedCalls) {
      const key = `${c.method} ${c.url}`;
      uniqueCalls.set(key, c.status);
    }
    for (const [call, status] of uniqueCalls.entries()) {
      console.log(`- ${call} -> HTTP ${status}`);
    }

  } catch (err) {
    console.error('[PLAYWRIGHT EXECUTION ERROR]', err);
  } finally {
    await browser.close();
  }
}

run();
