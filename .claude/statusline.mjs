/**
 * Claude Flow V3 Development Statusline
 * Displays V3 development metrics, swarm coordination, performance, and security status
 */

import { readFileSync } from 'fs';
import { join } from 'path';
import { execSync } from 'child_process';

/**
 * Safely read JSON file
 */
function readJSON(path, fallback = {}) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return fallback;
  }
}

/**
 * Format percentage
 */
function formatPercent(value) {
  return `${Math.round(value)}%`;
}

/**
 * Get git branch
 */
function getGitBranch() {
  try {
    return execSync('git branch --show-current 2>/dev/null', { encoding: 'utf8' }).trim();
  } catch {
    return 'unknown';
  }
}

/**
 * Calculate intelligence score from learning patterns
 */
function calculateIntelligence(learning) {
  const { routing, patterns, sessions } = learning;
  const routingScore = (routing?.accuracy || 0) * 30;
  const patternScore = Math.min((patterns?.shortTerm || 0) + (patterns?.longTerm || 0), 50) * 0.5;
  const sessionScore = Math.min((sessions?.total || 0), 20);
  return Math.round(routingScore + patternScore + sessionScore);
}

/**
 * Calculate performance speedup estimate
 */
function calculateSpeedup(swarm, learning) {
  const baseSpeedup = 1.0;
  const agentBonus = (swarm.activeAgents / swarm.maxAgents) * 3.0;
  const learningBonus = ((learning.routing?.accuracy || 0) / 100) * 3.47;
  return (baseSpeedup + agentBonus + learningBonus).toFixed(2);
}

/**
 * Main statusline export
 */
export default function statusline(context) {
  const baseDir = process.env.PWD || process.cwd();

  // Read metric files
  const v3Progress = readJSON(join(baseDir, '.claude-flow/metrics/v3-progress.json'));
  const swarmActivity = readJSON(join(baseDir, '.claude-flow/metrics/swarm-activity.json'));
  const learning = readJSON(join(baseDir, '.claude-flow/metrics/learning.json'));
  const auditStatus = readJSON(join(baseDir, '.claude-flow/security/audit-status.json'));

  const parts = [];

  // 1. Claude Flow V3 project header
  parts.push('\u{1F916} CF-V3');

  // 2. Git branch
  const branch = getGitBranch();
  if (branch && branch !== 'master' && branch !== 'main') {
    parts.push(`\u{1F333}${branch}`);
  }

  // 3. V3 domain implementation progress (5 domains)
  const domainProgress = v3Progress.domains?.completed || 0;
  const totalDomains = v3Progress.domains?.total || 5;
  parts.push(`D:${domainProgress}/${totalDomains}`);

  // 4. DDD architecture progress
  if (v3Progress.ddd?.progress > 0) {
    parts.push(`DDD:${formatPercent(v3Progress.ddd.progress)}`);
  }

  // 5. 15-agent swarm coordination status
  const activeAgents = swarmActivity.swarm?.agent_count || 0;
  const maxAgents = v3Progress.swarm?.maxAgents || 15;
  const swarmIcon = swarmActivity.swarm?.active ? '\u{1F41D}' : '\u{1F4A4}';
  parts.push(`${swarmIcon}${activeAgents}/${maxAgents}`);

  // 6. Performance metrics (current speedup vs 2.49x-7.47x target)
  const speedup = calculateSpeedup(v3Progress.swarm || {}, learning);
  const speedupIcon = parseFloat(speedup) >= 2.49 ? '\u{1F680}' : '\u{1F6A6}';
  parts.push(`${speedupIcon}${speedup}x`);

  // 7. Security audit status (CVEs fixed out of 3 critical)
  const cvesFixed = auditStatus.cvesFixed || 0;
  const totalCves = auditStatus.totalCves || 3;
  const securityIcon = cvesFixed === totalCves ? '\u{1F512}' : '\u{1F6A8}';
  parts.push(`${securityIcon}${cvesFixed}/${totalCves}`);

  // 8. Integration status with agentic-flow@alpha
  if (swarmActivity.integration?.agentic_flow_active) {
    parts.push('\u{1F517}AF');
  }

  // 9. Intelligence score (0-100)
  const intelligence = calculateIntelligence(learning);
  if (intelligence > 0) {
    const iqIcon = intelligence >= 70 ? '\u{1F9E0}' : intelligence >= 40 ? '\u{1F4A1}' : '\u{1F331}';
    parts.push(`${iqIcon}${intelligence}`);
  }

  // 10. Learning patterns
  const patternsLearned = v3Progress.learning?.patternsLearned || 0;
  if (patternsLearned > 0) {
    parts.push(`\u{1F4DA}${patternsLearned}`);
  }

  // 11. Context window usage
  if (context.context_window?.used_percentage !== null && context.context_window?.used_percentage !== undefined) {
    const usedPct = context.context_window.used_percentage;
    const ctxIcon = usedPct >= 80 ? '\u{1F534}' : usedPct >= 50 ? '\u{1F7E1}' : '\u{1F7E2}';
    parts.push(`${ctxIcon}${formatPercent(usedPct)}`);
  }

  // 12. Model (shortened)
  if (context.model?.display_name) {
    const model = context.model.display_name
      .replace('Claude ', '')
      .replace(' Sonnet', 'S')
      .replace(' Opus', 'O')
      .replace(' Haiku', 'H')
      .replace('3.5', '3.5')
      .replace('4.5', '4.5');
    parts.push(model);
  }

  return parts.join(' | ');
}
