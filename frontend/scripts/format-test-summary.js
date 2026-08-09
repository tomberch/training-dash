#!/usr/bin/env node
/**
 * Parses Playwright JSON results and outputs a GitHub-flavored markdown table
 * for use in GitHub Actions job summaries.
 *
 * Usage: node scripts/format-test-summary.js [path-to-results.json]
 * Default: e2e-results/results.json
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const resultsPath = process.argv[2] || path.join(__dirname, '..', 'e2e-results', 'results.json');

if (!fs.existsSync(resultsPath)) {
  console.log('> No test results found at', resultsPath);
  process.exit(0);
}

const results = JSON.parse(fs.readFileSync(resultsPath, 'utf8'));

// Group tests by file/suite
const suites = new Map();

function extractSuiteName(spec) {
  // Extract from file path: e2e/journeys/J001-smoke.spec.ts -> J001-smoke
  const filePath = spec.file || '';
  const match = filePath.match(/(?:journeys|views|api)\/(.+)\.spec\.ts$/);
  if (match) {
    return match[1];
  }
  // Fallback to title
  return spec.title || 'Unknown';
}

function categorizeFile(filePath) {
  if (filePath.includes('/journeys/')) return 'Journey';
  if (filePath.includes('/views/')) return 'View';
  if (filePath.includes('/api/')) return 'API';
  return 'Other';
}

// Process all suites recursively
function processSuite(suite, filePath = '') {
  const currentFile = suite.file || filePath;
  
  for (const spec of suite.specs || []) {
    const suiteName = extractSuiteName({ file: currentFile, title: spec.title });
    
    if (!suites.has(suiteName)) {
      suites.set(suiteName, {
        name: suiteName,
        category: categorizeFile(currentFile),
        passed: 0,
        failed: 0,
        skipped: 0,
        total: 0,
      });
    }
    
    const suiteStats = suites.get(suiteName);
    
    for (const test of spec.tests || []) {
      suiteStats.total++;
      const status = test.status || (test.results?.[0]?.status) || 'unknown';
      
      if (status === 'passed' || status === 'expected') {
        suiteStats.passed++;
      } else if (status === 'failed' || status === 'unexpected') {
        suiteStats.failed++;
      } else if (status === 'skipped') {
        suiteStats.skipped++;
      }
    }
  }
  
  // Recurse into child suites
  for (const childSuite of suite.suites || []) {
    processSuite(childSuite, currentFile);
  }
}

// Process top-level suites
for (const suite of results.suites || []) {
  processSuite(suite);
}

// Calculate totals
let totalPassed = 0;
let totalFailed = 0;
let totalSkipped = 0;
let totalTests = 0;

for (const [, stats] of suites) {
  totalPassed += stats.passed;
  totalFailed += stats.failed;
  totalSkipped += stats.skipped;
  totalTests += stats.total;
}

// Sort suites: Journeys first (by J number), then Views, then API
const sortedSuites = [...suites.values()].sort((a, b) => {
  const categoryOrder = { Journey: 0, View: 1, API: 2, Other: 3 };
  const catDiff = categoryOrder[a.category] - categoryOrder[b.category];
  if (catDiff !== 0) return catDiff;
  return a.name.localeCompare(b.name);
});

// Output markdown
console.log('| Suite | Category | Tests | Status |');
console.log('|-------|----------|-------|--------|');

for (const suite of sortedSuites) {
  const status = suite.failed > 0 
    ? ':x: Failed' 
    : suite.skipped === suite.total 
      ? ':warning: Skipped'
      : ':white_check_mark: Passed';
  
  const testsDisplay = suite.failed > 0
    ? `${suite.passed}/${suite.total} (${suite.failed} failed)`
    : `${suite.passed}/${suite.total}`;
  
  console.log(`| ${suite.name} | ${suite.category} | ${testsDisplay} | ${status} |`);
}

// Summary row
console.log('|-------|----------|-------|--------|');
const overallStatus = totalFailed > 0 
  ? `:x: **${totalFailed} Failed**` 
  : ':white_check_mark: **All Passed**';
console.log(`| **Total** | | **${totalPassed}/${totalTests}** | ${overallStatus} |`);

// Additional stats
console.log('');
console.log(`Duration: ${((results.stats?.duration || 0) / 1000).toFixed(1)}s`);

if (totalFailed > 0) {
  console.log('');
  console.log('### Failed Tests');
  console.log('');
  
  // Find and list failed tests
  function findFailedTests(suite, parentTitle = '') {
    const failed = [];
    const currentTitle = parentTitle ? `${parentTitle} > ${suite.title}` : suite.title;
    
    for (const spec of suite.specs || []) {
      for (const test of spec.tests || []) {
        const status = test.status || (test.results?.[0]?.status) || 'unknown';
        if (status === 'failed' || status === 'unexpected') {
          failed.push(`- ${currentTitle} > ${spec.title}`);
        }
      }
    }
    
    for (const childSuite of suite.suites || []) {
      failed.push(...findFailedTests(childSuite, currentTitle));
    }
    
    return failed;
  }
  
  for (const suite of results.suites || []) {
    const failed = findFailedTests(suite);
    for (const test of failed) {
      console.log(test);
    }
  }
}

// Exit with error if tests failed
process.exit(totalFailed > 0 ? 1 : 0);
