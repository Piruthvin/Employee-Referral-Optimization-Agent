import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const outputDir = path.resolve(__dirname, '../docs/ui_redesign_screenshots');
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

const PORT = 5174;
const BASE_URL = `http://localhost:${PORT}`;

const mockCandidateReferrals = [
  {
    candidate_id: 'cand-001',
    full_name: 'Sarah Connor',
    email: 'sarah.connor@example.com',
    candidate_status: 'Associated',
    approval_status: 'Approved',
    referred_by: 'Piruthvin (Staff Engineer)',
    referred_date: '2026-09-20',
    referral_score: 94,
    current_job_title: 'Senior Distributed Systems Engineer',
    current_employer: 'Cyberdyne Systems',
    experience_in_years: 7,
    skill_set: 'Python, FastAPI, Kafka, Distributed Systems, Kubernetes',
    best_match: {
      job_title: 'Senior Backend Engineer (Python/FastAPI)',
      match_percent: 94,
    },
  },
  {
    candidate_id: 'cand-002',
    full_name: 'David Lightman',
    email: 'david.lightman@example.com',
    candidate_status: 'Under Review',
    approval_status: 'Pending',
    referred_by: 'Piruthvin (Staff Engineer)',
    referred_date: '2026-09-25',
    referral_score: 88,
    current_job_title: 'Full Stack Web Architect',
    current_employer: 'NORAD Solutions',
    experience_in_years: 4,
    skill_set: 'React, TypeScript, Node.js, GraphQL, Tailwind CSS',
    best_match: {
      job_title: 'Full Stack Engineer (React/TypeScript)',
      match_percent: 88,
    },
  },
  {
    candidate_id: 'cand-003',
    full_name: 'Miles Dyson',
    email: 'miles.dyson@example.com',
    candidate_status: 'Interviewing',
    approval_status: 'Approved',
    referred_by: 'Piruthvin (Staff Engineer)',
    referred_date: '2026-09-18',
    referral_score: 97,
    current_job_title: 'Principal AI Researcher',
    current_employer: 'Cyberdyne Systems Research',
    experience_in_years: 10,
    skill_set: 'PyTorch, Transformers, LLMs, Neural Networks, Python',
    best_match: {
      job_title: 'Lead AI/ML Systems Architect',
      match_percent: 97,
    },
  },
];

const mockRecruiterReferrals = [
  {
    candidate_id: 'cand-101',
    full_name: 'Alex Rivera',
    email: 'alex.rivera@example.com',
    candidate_status: 'Submitted',
    approval_status: 'Approved',
    referred_by: 'Piruthvin (Staff Engineer)',
    referred_date: '2026-09-27',
    referral_score: 92,
    current_job_title: 'Senior Staff Software Engineer',
    current_employer: 'CloudScale Infrastructure Labs',
    experience_in_years: 8,
    skill_set: 'Python, FastAPI, PostgreSQL, Docker, Kafka, AWS',
    best_match: {
      job_title: 'Senior Backend Engineer (Python/FastAPI)',
      match_percent: 92,
    },
  },
  {
    candidate_id: 'cand-102',
    full_name: 'Elena Rostova',
    email: 'elena.rostova@example.com',
    candidate_status: 'Under Review',
    approval_status: 'Pending',
    referred_by: 'Marcus Chen (Tech Lead)',
    referred_date: '2026-09-26',
    referral_score: 96,
    current_job_title: 'Lead AI Systems Architect',
    current_employer: 'AeroDynamics AI',
    experience_in_years: 9,
    skill_set: 'PyTorch, LLMs, CUDA, Distributed Training, Python',
    best_match: {
      job_title: 'Lead AI/ML Systems Architect',
      match_percent: 96,
    },
  },
  {
    candidate_id: 'cand-103',
    full_name: 'Jordan Hayes',
    email: 'jordan.hayes@example.com',
    candidate_status: 'Submitted',
    approval_status: 'Pending',
    referred_by: 'Sarah Jenkins (DevRel)',
    referred_date: '2026-09-28',
    referral_score: 85,
    current_job_title: 'Senior Frontend Engineer',
    current_employer: 'HyperText Digital',
    experience_in_years: 5,
    skill_set: 'React, TypeScript, Next.js, Redux, Tailwind',
    best_match: {
      job_title: 'Full Stack Engineer (React/TypeScript)',
      match_percent: 85,
    },
  },
  {
    candidate_id: 'cand-104',
    full_name: 'Maya Patel',
    email: 'maya.patel@example.com',
    candidate_status: 'Interview Scheduled',
    approval_status: 'Approved',
    referred_by: 'Piruthvin (Staff Engineer)',
    referred_date: '2026-09-21',
    referral_score: 91,
    current_job_title: 'Cloud DevOps Architect',
    current_employer: 'SaaS Platformics',
    experience_in_years: 6,
    skill_set: 'Kubernetes, Terraform, AWS, Python, CI/CD',
    best_match: {
      job_title: 'Senior Cloud Platform Engineer',
      match_percent: 91,
    },
  },
];

const mockCandidateDetail = {
  candidate_id: 'cand-101',
  full_name: 'Alex Rivera',
  email: 'alex.rivera@example.com',
  phone: '+1 (555) 901-2345',
  candidate_status: 'Associated',
  referred_by: 'Piruthvin (Staff Engineer)',
  referred_date: 'Sep 27, 2026',
  approval_status: 'Approved',
  referral_score: 92,
  identity_mismatch: false,
  parsed_profile: {
    headline: 'Senior Distributed Systems & Python Backend Specialist',
    current_job_title: 'Senior Staff Software Engineer',
    current_employer: 'CloudScale Infrastructure Labs',
    total_experience_years: 8,
    summary: 'Senior systems engineer with 8+ years architecting high-throughput distributed microservices in Python, FastAPI, Go, and Kafka. Led cloud-native modernization saving $1.2M annually while maintaining 99.99% uptime.',
    links: {
      linkedin: 'https://linkedin.com/in/alex-rivera-sample',
      github: 'https://github.com/alex-rivera-sample',
    },
    experience: [
      {
        job_title: 'Senior Staff Software Engineer',
        company: 'CloudScale Infrastructure Labs',
        start_date: 'Jan 2022',
        end_date: 'Present',
        is_current: true,
        description: 'Architected async event streaming pipelines processing 120k req/sec with FastAPI and Kafka. Mentored 9 mid-level engineers and spearheaded security compliance.',
      },
      {
        job_title: 'Senior Python Engineer',
        company: 'Nexus Data Technologies',
        start_date: 'Mar 2018',
        end_date: 'Dec 2021',
        is_current: false,
        description: 'Engineered multi-tenant REST APIs and distributed background workers using Redis and PostgreSQL with strict p99 sub-30ms latencies.',
      },
    ],
    education: [
      {
        degree: 'B.S. in Computer Science & Engineering',
        institution: 'University of California, Berkeley',
        field_of_study: 'Distributed Systems & Algorithms',
        grade: 'Magna Cum Laude (3.88 GPA)',
      },
    ],
    skills: ['Python', 'FastAPI', 'PostgreSQL', 'Docker', 'Kubernetes', 'Apache Kafka', 'Redis', 'AWS', 'System Design', 'CI/CD Pipelines'],
  },
  best_match: {
    job_id: 'job-1',
    job_title: 'Senior Backend Engineer (Python/FastAPI)',
    match_percent: 92,
    matched_skills: ['Python', 'FastAPI', 'PostgreSQL', 'Docker', 'System Design', 'AWS'],
    missing_skills: ['GraphQL', 'Terraform'],
  },
};

function setupMockRoutes(page, currentRole = 'employee') {
  return page.route('**/*', async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (url.includes('/api/v1/auth/login/request') && method === 'POST') {
      const body = JSON.parse(route.request().postData() || '{}');
      if (body.email?.includes('emailonly')) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            auth_mode: 'email_only',
            challenge_token: 'valid-session-jwt-token',
            access_token: 'valid-session-jwt-token',
            role: 'employee',
            email: body.email,
            name: 'Piruthvin (Staff Engineer)',
            zoho_user_id: 'zoho-emp-001',
            message: 'Development direct login successful.',
            user: {
              email: body.email,
              role: 'employee',
              name: 'Piruthvin (Staff Engineer)',
              zoho_user_id: 'zoho-emp-001',
            },
          }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          auth_mode: 'otp',
          challenge_token: 'valid-challenge-token-hmac',
          message: '6-digit verification code sent to your email. Valid for 10 minutes.',
        }),
      });
    }

    if (url.includes('/api/v1/auth/login/verify') && method === 'POST') {
      const body = JSON.parse(route.request().postData() || '{}');
      if (body.otp === '000000') {
        return route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Invalid or expired verification code.' }),
        });
      }
      const isRec = currentRole === 'recruiter';
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          access_token: 'valid-session-jwt-token',
          token_type: 'bearer',
          role: isRec ? 'recruiter' : 'employee',
          email: isRec ? 'piruthvin.official.3@gmail.com' : 'piruthvin.official.2@gmail.com',
          name: isRec ? 'Piruthvin (Senior Recruiter)' : 'Piruthvin (Staff Engineer)',
          zoho_user_id: isRec ? 'zoho-rec-002' : 'zoho-emp-001',
          user: {
            email: isRec ? 'piruthvin.official.3@gmail.com' : 'piruthvin.official.2@gmail.com',
            role: isRec ? 'recruiter' : 'employee',
            name: isRec ? 'Piruthvin (Senior Recruiter)' : 'Piruthvin (Staff Engineer)',
            zoho_user_id: isRec ? 'zoho-rec-002' : 'zoho-emp-001',
          },
        }),
      });
    }

    if (url.includes('/api/v1/employees/points') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          employee_email: 'piruthvin.official.2@gmail.com',
          total_referrals: 5,
          approved_referrals: 3,
          points: 350,
        }),
      });
    }

    if (url.includes('/api/v1/referral/list') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(currentRole === 'recruiter' ? mockRecruiterReferrals : mockCandidateReferrals),
      });
    }

    if (url.includes('/api/v1/referral/submit') && method === 'POST') {
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          candidate_id: 'zoho-cand-8991',
          message: 'Candidate referral submitted successfully to Zoho Recruit.',
          referral_score: 95,
        }),
      });
    }

    if (url.includes('/api/v1/analytics/dashboard') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_referrals: 142,
          pending_approval: 18,
          approved_referrals: 98,
          rejected_referrals: 26,
          interviews_scheduled: 45,
          overall_conversion_rate: 69.0,
          avg_approval_time_days: 1.8,
        }),
      });
    }

    if (url.includes('/api/v1/analytics/conversion') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          funnel_stages: [
            { stage: 'Referred', count: 142, conversion_from_previous: 100 },
            { stage: 'Screened', count: 112, conversion_from_previous: 78.9 },
            { stage: 'Approved', count: 98, conversion_from_previous: 87.5 },
            { stage: 'Interviewed', count: 45, conversion_from_previous: 45.9 },
            { stage: 'Offered', count: 28, conversion_from_previous: 62.2 },
            { stage: 'Hired', count: 24, conversion_from_previous: 85.7 },
          ],
        }),
      });
    }

    if (url.includes('/api/v1/analytics/pending') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          overdue_referrals: [
            {
              candidate_id: 'cand-103',
              candidate_name: 'Jordan Hayes',
              referred_by: 'Sarah Jenkins (DevRel)',
              referred_date: '2026-09-22',
              days_pending: 7,
              referral_score: 85,
            },
          ],
        }),
      });
    }

    if (url.includes('/api/v1/approvals/cand-101') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockCandidateDetail),
      });
    }

    if (url.includes('/api/v1/interview/schedule') && method === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          meeting_id: 'teams-mtg-98765',
          meeting_url: 'https://teams.microsoft.com/l/meetup-join/19%3ameeting_fake/0',
        }),
      });
    }

    return route.continue();
  });
}

async function run() {
  console.log('Starting Vite server on port', PORT);
  const viteProcess = spawn('npx', ['vite', '--port', String(PORT)], {
    cwd: path.resolve(__dirname, '../frontend'),
    shell: true,
    stdio: 'ignore',
  });

  // Give server 3.5 seconds to start
  await new Promise((resolve) => setTimeout(resolve, 3500));

  const browser = await chromium.launch({ headless: true });

  const viewports = [
    { name: 'desktop', width: 1440, height: 900 },
    { name: 'mobile', width: 390, height: 844 },
  ];

  for (const vp of viewports) {
    console.log(`\n========================================`);
    console.log(`Capturing for Viewport: ${vp.name} (${vp.width}x${vp.height})`);
    console.log(`========================================`);

    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 2,
    });
    const page = await context.newPage();
    await setupMockRoutes(page, 'employee');

    // 1. Login Screen
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector('#email-input');
    await page.screenshot({ path: path.join(outputDir, `01_login_${vp.name}.png`), fullPage: true });
    console.log(`✓ 01_login_${vp.name}.png`);

    // Color verification
    if (vp.name === 'desktop') {
      const sendBtn = page.locator('#send-code-btn');
      const bg = await sendBtn.evaluate((el) => window.getComputedStyle(el).backgroundColor);
      console.log('  [Color Check] Primary button background:', bg); // rgb(185, 28, 28)
    }

    // 2. OTP Screen
    await page.fill('#email-input', 'piruthvin.official.2@gmail.com');
    await page.click('#send-code-btn');
    await page.waitForSelector('#otp-input');
    await page.screenshot({ path: path.join(outputDir, `02_otp_screen_${vp.name}.png`), fullPage: true });
    console.log(`✓ 02_otp_screen_${vp.name}.png`);

    // 3. OTP Error State
    await page.fill('#otp-input', '000000');
    await page.click('#verify-signin-btn');
    await page.waitForSelector('#login-error-banner');
    await page.screenshot({ path: path.join(outputDir, `03_otp_error_${vp.name}.png`), fullPage: true });
    console.log(`✓ 03_otp_error_${vp.name}.png`);

    // 4. OTP Success State (Email-only direct login path)
    await page.goto(`${BASE_URL}/login`);
    await page.fill('#email-input', 'piruthvin.emailonly@gmail.com');
    await page.click('#send-code-btn');
    await page.waitForURL(`${BASE_URL}/`, { timeout: 8000 });
    await page.waitForSelector('#employee-dashboard');
    await page.screenshot({ path: path.join(outputDir, `04_otp_success_${vp.name}.png`), fullPage: true });
    console.log(`✓ 04_otp_success_${vp.name}.png`);

    // 5. Employee Dashboard
    await page.screenshot({ path: path.join(outputDir, `05_employee_dashboard_${vp.name}.png`), fullPage: true });
    console.log(`✓ 05_employee_dashboard_${vp.name}.png`);

    // 6. Referral Form - Empty Modal
    const referBtn = page.locator('#refer-candidate-btn').first();
    await referBtn.click();
    await page.waitForSelector('#referral-form');
    await page.screenshot({ path: path.join(outputDir, `06_referral_form_empty_${vp.name}.png`), fullPage: false });
    console.log(`✓ 06_referral_form_empty_${vp.name}.png`);

    // 7. Referral Form - Filled
    await page.fill('#candidate-name-input', 'Marcus Vance');
    await page.fill('#candidate-email-input', 'marcus.vance@example.com');
    await page.screenshot({ path: path.join(outputDir, `07_referral_form_filled_${vp.name}.png`), fullPage: false });
    console.log(`✓ 07_referral_form_filled_${vp.name}.png`);

    // 8. Referral Form - Error State (Missing required resume file)
    await page.click('#referral-submit-btn');
    await page.waitForSelector('#referral-error-banner');
    await page.screenshot({ path: path.join(outputDir, `08_referral_form_error_${vp.name}.png`), fullPage: false });
    console.log(`✓ 08_referral_form_error_${vp.name}.png`);

    // 9. Referral Form - Success State
    const dummyPdf = path.resolve(__dirname, 'dummy_resume.pdf');
    if (!fs.existsSync(dummyPdf)) {
      fs.writeFileSync(dummyPdf, '%PDF-1.4 sample resume');
    }
    await page.locator('#candidate-resume-file').setInputFiles(dummyPdf);
    await page.click('#referral-submit-btn');
    await page.waitForSelector('#referral-done-btn');
    await page.screenshot({ path: path.join(outputDir, `09_referral_form_success_${vp.name}.png`), fullPage: false });
    console.log(`✓ 09_referral_form_success_${vp.name}.png`);
    await page.click('#referral-done-btn');

    // 10. My Referrals List Section
    const tableHeader = page.locator('#referrals-table-header, table').first();
    await tableHeader.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(outputDir, `10_my_referrals_list_${vp.name}.png`), fullPage: false });
    console.log(`✓ 10_my_referrals_list_${vp.name}.png`);

    // 11. Chat Page (Client-side route transition preserving in-memory JWT)
    await page.evaluate(() => {
      window.history.pushState(null, '', '/chat');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await page.waitForSelector('text=Referral Companion AI');
    await page.screenshot({ path: path.join(outputDir, `11_chat_${vp.name}.png`), fullPage: true });
    console.log(`✓ 11_chat_${vp.name}.png`);

    await context.close();

    // Now Recruiter Context
    const recContext = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 2,
    });
    const recPage = await recContext.newPage();
    await setupMockRoutes(recPage, 'recruiter');

    // Log in as recruiter
    await recPage.goto(`${BASE_URL}/login`);
    await recPage.fill('#email-input', 'piruthvin.official.3@gmail.com');
    await recPage.click('#send-code-btn');
    await recPage.waitForSelector('#otp-input');
    await recPage.fill('#otp-input', '123456');
    await recPage.click('#verify-signin-btn');
    await recPage.waitForURL(`${BASE_URL}/`, { timeout: 8000 });
    await recPage.waitForSelector('#recruiter-dashboard');

    // 12. Recruiter Dashboard & KPIs
    await recPage.screenshot({ path: path.join(outputDir, `12_recruiter_dashboard_${vp.name}.png`), fullPage: true });
    console.log(`✓ 12_recruiter_dashboard_${vp.name}.png`);

    // 13. Pending Approvals List Tab
    const pendingTab = recPage.locator('button:has-text("Pending Review")').first();
    await pendingTab.click();
    await recPage.screenshot({ path: path.join(outputDir, `13_pending_approvals_list_${vp.name}.png`), fullPage: false });
    console.log(`✓ 13_pending_approvals_list_${vp.name}.png`);

    // 14. Approval Detail Page (Client-side route transition preserving recruiter JWT)
    await recPage.evaluate(() => {
      window.history.pushState(null, '', '/approvals/cand-101');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await recPage.waitForSelector('text=Alex Rivera');
    await recPage.screenshot({ path: path.join(outputDir, `14_approval_detail_page_${vp.name}.png`), fullPage: true });
    console.log(`✓ 14_approval_detail_page_${vp.name}.png`);

    // 15. Schedule Interview Modal
    const schedBtn = recPage.locator('button:has-text("Schedule Interview")').first();
    await schedBtn.click();
    await recPage.waitForSelector('text=Schedule Microsoft Teams Interview');
    await recPage.screenshot({ path: path.join(outputDir, `15_schedule_interview_modal_${vp.name}.png`), fullPage: false });
    console.log(`✓ 15_schedule_interview_modal_${vp.name}.png`);

    await recContext.close();
  }

  await browser.close();
  viteProcess.kill();
  console.log('\n======================================================');
  console.log('All 30 screenshots generated successfully in:');
  console.log(outputDir);
  console.log('======================================================');
}

run().catch((err) => {
  console.error('Fatal screenshot error:', err);
  process.exit(1);
});
