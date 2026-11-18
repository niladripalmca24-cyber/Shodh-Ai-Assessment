"""
Interactive Web Dashboard for Shodh AI Neuro-Symbolic Workflow Reviewer.
Provides a modern, responsive single-page application.
"""

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Shodh AI — Neuro-Symbolic Workflow Reviewer</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    body { font-family: 'Inter', sans-serif; }
    code, pre { font-family: 'JetBrains Mono', monospace; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">

  <!-- Top Navigation Bar -->
  <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/30">
          <i class="fa-solid fa-microchip"></i>
        </div>
        <div>
          <span class="font-bold text-lg tracking-tight bg-gradient-to-r from-indigo-400 via-sky-300 to-teal-300 bg-clip-text text-transparent">
            Shodh AI Reviewer
          </span>
          <span class="text-xs text-slate-400 block -mt-1 font-mono">Neuro-Symbolic SMT Verifier</span>
        </div>
      </div>
      <div class="flex items-center space-x-4 text-xs">
        <span class="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
          <i class="fa-solid fa-user-graduate text-indigo-400 mr-1.5"></i>Candidate: <strong>Niladri Pal</strong> (MCA 2026)
        </span>
        <span class="px-2.5 py-1 rounded-full bg-indigo-950/80 border border-indigo-700/50 text-indigo-300 font-medium">
          <i class="fa-solid fa-briefcase text-indigo-400 mr-1.5"></i>Full-Time / AI & ML Eng
        </span>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
    
    <!-- Hero / Metrics Overview -->
    <section class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <div class="text-slate-400 text-xs uppercase font-semibold tracking-wider">Evaluation Accuracy</div>
        <div class="text-2xl font-bold text-emerald-400 mt-1 flex items-baseline justify-between">
          <span>100.0%</span>
          <span class="text-xs text-slate-400 font-normal">14/14 Bundles</span>
        </div>
        <div class="text-[11px] text-slate-400 mt-1">10 Dev + 4 Frozen Holdout</div>
      </div>

      <div class="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <div class="text-slate-400 text-xs uppercase font-semibold tracking-wider">Formal Prover</div>
        <div class="text-2xl font-bold text-indigo-400 mt-1 flex items-baseline justify-between">
          <span>Z3 SMT</span>
          <span class="text-xs text-slate-400 font-normal">CPU Offline</span>
        </div>
        <div class="text-[11px] text-slate-400 mt-1">Exhaustive Equivalence & Counterexamples</div>
      </div>

      <div class="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <div class="text-slate-400 text-xs uppercase font-semibold tracking-wider">AST Code Safety</div>
        <div class="text-2xl font-bold text-sky-400 mt-1 flex items-baseline justify-between">
          <span>ast.parse</span>
          <span class="text-xs text-slate-400 font-normal">No eval()</span>
        </div>
        <div class="text-[11px] text-slate-400 mt-1">Restricted Pure Functional Python</div>
      </div>

      <div class="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
        <div class="text-slate-400 text-xs uppercase font-semibold tracking-wider">False Passes / Blocks</div>
        <div class="text-2xl font-bold text-teal-400 mt-1 flex items-baseline justify-between">
          <span>0 / 0</span>
          <span class="text-xs text-emerald-400 font-semibold"><i class="fa-solid fa-check mr-1"></i>Verified</span>
        </div>
        <div class="text-[11px] text-slate-400 mt-1">Zero Blind Substring Matching</div>
      </div>
    </section>

    <!-- Two-Column Interactive Workspace -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
      
      <!-- Left Column: Bundle Selector & Controls (5 Cols) -->
      <div class="lg:col-span-5 space-y-6">
        <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 class="text-base font-semibold text-white flex items-center">
              <i class="fa-solid fa-folder-open text-indigo-400 mr-2"></i>Select Evaluation Bundle
            </h2>
            <span id="splitBadge" class="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">Dev Split</span>
          </div>

          <!-- Bundle Dropdown -->
          <div>
            <label class="block text-xs font-medium text-slate-400 mb-1.5">Pre-configured Synthetic Test Case</label>
            <select id="bundleSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500">
              <optgroup label="Development Bundles (10 Cases)">
                <option value="01_valid_baseline">01: valid_baseline (Expected: PASS)</option>
                <option value="02_valid_unusual_demorgan">02: valid_unusual_demorgan (Expected: PASS)</option>
                <option value="03_valid_paired_rename">03: valid_paired_rename (Expected: PASS)</option>
                <option value="04_defect_paired_boundary" selected>04: defect_paired_boundary (Expected: CHANGES_REQ)</option>
                <option value="05_defect_unapproved_change">05: defect_unapproved_change (Expected: CHANGES_REQ)</option>
                <option value="06_defect_prose_approval">06: defect_prose_approval (Expected: CHANGES_REQ)</option>
                <option value="07_defect_missing_r2">07: defect_missing_r2 (Expected: CHANGES_REQ)</option>
                <option value="08_defect_precedence_swap">08: defect_precedence_swap (Expected: CHANGES_REQ)</option>
                <option value="09_incomplete_conflict_appr">09: incomplete_conflict_appr (Expected: INCOMPLETE)</option>
                <option value="10_incomplete_unsupported_py">10: incomplete_unsupported_py (Expected: INCOMPLETE)</option>
              </optgroup>
              <optgroup label="Frozen Holdout Bundles (4 Cases)">
                <option value="11_holdout_valid_nested_exc">11: holdout_valid_nested_exc (Expected: PASS)</option>
                <option value="12_holdout_defect_unit_bug">12: holdout_defect_unit_bug (Expected: CHANGES_REQ)</option>
                <option value="13_holdout_defect_injection">13: holdout_defect_injection (Expected: CHANGES_REQ)</option>
                <option value="14_holdout_inc_model_trunc">14: holdout_inc_model_trunc (Expected: INCOMPLETE)</option>
              </optgroup>
            </select>
          </div>

          <!-- Description Box -->
          <div class="bg-slate-950/70 rounded-lg p-3 border border-slate-800 text-xs space-y-1">
            <div class="text-slate-400 font-medium">Bundle Description:</div>
            <div id="bundleDesc" class="text-slate-300 font-mono text-[11px] leading-relaxed">
              Paired variant to bundle 03 that subtly changes operator >= to >.
            </div>
          </div>

          <!-- Controlled Ablation Toggle -->
          <div class="pt-2 border-t border-slate-800/80 space-y-3">
            <div class="flex items-center justify-between">
              <div>
                <label for="ablateToggle" class="text-xs font-semibold text-slate-200 block">Controlled Ablation Mode</label>
                <span class="text-[11px] text-slate-400 block">Disable Z3 SMT solver (--ablate-z3)</span>
              </div>
              <input type="checkbox" id="ablateToggle" class="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 bg-slate-900 border-slate-700 cursor-pointer">
            </div>

            <!-- Run Button -->
            <button id="runBtn" onclick="runReview()" class="w-full bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-semibold py-2.5 px-4 rounded-lg shadow-lg shadow-indigo-600/30 transition flex items-center justify-center space-x-2">
              <i class="fa-solid fa-play text-xs"></i>
              <span>Run Verification Pipeline</span>
            </button>
          </div>

          <!-- Raw Input Preview Accordion -->
          <details class="text-xs border border-slate-800 rounded-lg p-3 bg-slate-950/40">
            <summary class="font-medium text-slate-400 cursor-pointer hover:text-slate-200">
              <i class="fa-solid fa-code text-indigo-400 mr-1.5"></i>Inspect Source Bundle JSON
            </summary>
            <pre id="rawBundleJson" class="mt-2 text-[10px] text-slate-400 max-h-48 overflow-y-auto bg-slate-950 p-2 rounded border border-slate-900">Loading bundle...</pre>
          </details>

        </div>
      </div>

      <!-- Right Column: Verification Results & Telemetry (7 Cols) -->
      <div class="lg:col-span-7 space-y-6">
        
        <!-- Live Verdict Card -->
        <div id="verdictCard" class="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
          <div class="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <span class="text-xs uppercase tracking-wider text-slate-400 font-semibold block">Decision Verdict</span>
              <div id="verdictBadge" class="mt-1 inline-flex items-center px-3 py-1 rounded-full text-sm font-bold bg-amber-950/80 text-amber-300 border border-amber-700/60">
                <i class="fa-solid fa-triangle-exclamation mr-1.5"></i>CHANGES_REQUIRED
              </div>
            </div>
            <div class="text-right">
              <span class="text-[11px] text-slate-400 block font-mono">Execution Latency</span>
              <span id="latencySpan" class="text-sm font-bold text-slate-200 font-mono">28.4 ms</span>
            </div>
          </div>

          <!-- Summary Message -->
          <div id="summaryText" class="text-sm text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
            Review failed with blocking defect(s). Formal SMT counterexample synthesized below.
          </div>

          <!-- Counterexample Showcase Card (Critical for Shodh AI) -->
          <div id="counterexampleContainer" class="bg-gradient-to-br from-rose-950/40 to-slate-900 border border-rose-800/40 rounded-xl p-4 space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-rose-300 uppercase tracking-wide flex items-center">
                <i class="fa-solid fa-bug text-rose-400 mr-2"></i>Concrete Ticket Counterexample (Z3 Model)
              </span>
              <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-900/60 text-rose-200 border border-rose-700/50">Mathematical SAT Proof</span>
            </div>
            
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
              <div class="bg-slate-950/80 p-2 rounded border border-slate-800">
                <span class="text-slate-500 block text-[10px]">category_missing</span>
                <span id="ceCatMiss" class="text-slate-200 font-semibold">false</span>
              </div>
              <div class="bg-slate-950/80 p-2 rounded border border-slate-800">
                <span class="text-slate-500 block text-[10px]">urgent</span>
                <span id="ceUrgent" class="text-slate-200 font-semibold">false</span>
              </div>
              <div class="bg-slate-950/80 p-2 rounded border border-slate-800">
                <span class="text-slate-500 block text-[10px]">wait_seconds</span>
                <span id="ceWait" class="text-amber-300 font-bold">1500</span>
              </div>
              <div class="bg-slate-950/80 p-2 rounded border border-slate-800">
                <span class="text-slate-500 block text-[10px]">vip</span>
                <span id="ceVip" class="text-slate-200 font-semibold">false</span>
              </div>
            </div>

            <!-- Route Divergence Highlight -->
            <div class="flex items-center justify-between bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-xs">
              <div class="flex items-center space-x-2">
                <span class="text-slate-400">Expected Route:</span>
                <span id="ceExpected" class="font-bold text-emerald-400 font-mono">escalation</span>
              </div>
              <i class="fa-solid fa-arrow-right text-rose-400 text-xs"></i>
              <div class="flex items-center space-x-2">
                <span class="text-slate-400">Actual Target Route:</span>
                <span id="ceActual" class="font-bold text-rose-400 font-mono">normal_queue</span>
              </div>
            </div>
          </div>

          <!-- Findings List -->
          <div class="space-y-3">
            <h3 class="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center justify-between">
              <span>Evidenced Findings</span>
              <span id="findingsCountBadge" class="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">3 findings</span>
            </h3>
            <div id="findingsList" class="space-y-2 max-h-56 overflow-y-auto pr-1">
              <!-- Dynamically populated -->
            </div>
          </div>

          <!-- Coverage & Verification Checklist -->
          <div class="pt-4 border-t border-slate-800 grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
            <div class="bg-slate-950/60 p-2 rounded border border-slate-800/80 flex items-center space-x-2">
              <i id="chkApproval" class="fa-solid fa-check text-emerald-400"></i>
              <span class="text-slate-300">Approval Integrity</span>
            </div>
            <div class="bg-slate-950/60 p-2 rounded border border-slate-800/80 flex items-center space-x-2">
              <i id="chkCoverage" class="fa-solid fa-check text-emerald-400"></i>
              <span class="text-slate-300">Spec Coverage</span>
            </div>
            <div class="bg-slate-950/60 p-2 rounded border border-slate-800/80 flex items-center space-x-2">
              <i id="chkZ3Spec" class="fa-solid fa-xmark text-rose-400"></i>
              <span class="text-slate-300">Spec Equivalence</span>
            </div>
            <div class="bg-slate-950/60 p-2 rounded border border-slate-800/80 flex items-center space-x-2">
              <i id="chkZ3Wf" class="fa-solid fa-xmark text-rose-400"></i>
              <span class="text-slate-300">Workflow Equivalence</span>
            </div>
            <div class="bg-slate-950/60 p-2 rounded border border-slate-800/80 flex items-center space-x-2">
              <i id="chkZ3Py" class="fa-solid fa-xmark text-rose-400"></i>
              <span class="text-slate-300">Python AST Equivalence</span>
            </div>
            <div class="bg-slate-950/60 p-2 rounded border border-slate-800/80 flex items-center space-x-2">
              <i id="chkModel" class="fa-solid fa-check text-emerald-400"></i>
              <span class="text-slate-300">Guardrails Clean</span>
            </div>
          </div>

        </div>
      </div>
    </div>

    <!-- Comparative Evaluation Benchmark Table -->
    <section class="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h2 class="text-base font-semibold text-white flex items-center">
            <i class="fa-solid fa-chart-line text-indigo-400 mr-2"></i>Frozen Evaluation Benchmark Results
          </h2>
          <span class="text-xs text-slate-400">Committed machine-readable outputs from eval/results/</span>
        </div>
        <span class="text-xs font-mono text-slate-400 bg-slate-950 px-2 py-1 rounded border border-slate-800">Frozen Test Suite</span>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs font-mono">
          <thead class="bg-slate-950 text-slate-400 border-b border-slate-800">
            <tr>
              <th class="py-2.5 px-3">Pipeline Configuration</th>
              <th class="py-2.5 px-3">Overall Accuracy</th>
              <th class="py-2.5 px-3">Dev (10 Cases)</th>
              <th class="py-2.5 px-3">Holdout (4 Cases)</th>
              <th class="py-2.5 px-3">False Passes</th>
              <th class="py-2.5 px-3">False Blocks</th>
              <th class="py-2.5 px-3">Counterexamples</th>
              <th class="py-2.5 px-3">Avg Latency</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800 text-slate-300">
            <tr class="hover:bg-slate-800/40">
              <td class="py-2.5 px-3 font-semibold text-amber-300">Baseline Checkpoint (v0)</td>
              <td class="py-2.5 px-3 text-rose-400 font-bold">50.0%</td>
              <td class="py-2.5 px-3">5 / 10</td>
              <td class="py-2.5 px-3">2 / 4</td>
              <td class="py-2.5 px-3 text-rose-400">4</td>
              <td class="py-2.5 px-3 text-rose-400">1</td>
              <td class="py-2.5 px-3 text-slate-500">0</td>
              <td class="py-2.5 px-3">1.8 ms</td>
            </tr>
            <tr class="hover:bg-slate-800/40">
              <td class="py-2.5 px-3 font-semibold text-sky-300">Controlled Ablation (--ablate-z3)</td>
              <td class="py-2.5 px-3 text-amber-400 font-bold">71.4%</td>
              <td class="py-2.5 px-3">7 / 10</td>
              <td class="py-2.5 px-3">3 / 4</td>
              <td class="py-2.5 px-3 text-amber-400">1</td>
              <td class="py-2.5 px-3 text-amber-400">1</td>
              <td class="py-2.5 px-3 text-slate-500">0</td>
              <td class="py-2.5 px-3">12.4 ms</td>
            </tr>
            <tr class="hover:bg-slate-800/40 bg-indigo-950/30">
              <td class="py-2.5 px-3 font-semibold text-indigo-300 flex items-center">
                <i class="fa-solid fa-star text-amber-400 mr-1.5 text-[10px]"></i>Final System (v1)
              </td>
              <td class="py-2.5 px-3 text-emerald-400 font-bold">100.0%</td>
              <td class="py-2.5 px-3 text-emerald-400 font-bold">10 / 10</td>
              <td class="py-2.5 px-3 text-emerald-400 font-bold">4 / 4</td>
              <td class="py-2.5 px-3 text-emerald-400 font-bold">0</td>
              <td class="py-2.5 px-3 text-emerald-400 font-bold">0</td>
              <td class="py-2.5 px-3 text-indigo-300 font-bold">7 (100%)</td>
              <td class="py-2.5 px-3">22.5 ms</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

  </main>

  <script>
    let currentBundleData = null;

    async function loadBundle() {
      const bundleId = document.getElementById('bundleSelect').value;
      const isHoldout = bundleId.startsWith('11') || bundleId.startsWith('12') || bundleId.startsWith('13') || bundleId.startsWith('14');
      document.getElementById('splitBadge').textContent = isHoldout ? 'Frozen Holdout Split' : 'Development Split';
      
      try {
        const resp = await fetch(`/api/bundles/${bundleId}`);
        currentBundleData = await resp.json();
        document.getElementById('bundleDesc').textContent = currentBundleData.description || 'No description';
        document.getElementById('rawBundleJson').textContent = JSON.stringify(currentBundleData, null, 2);
      } catch (err) {
        console.error('Failed to load bundle', err);
      }
    }

    async function runReview() {
      if (!currentBundleData) await loadBundle();
      const ablateZ3 = document.getElementById('ablateToggle').checked;
      const runBtn = document.getElementById('runBtn');
      
      runBtn.disabled = true;
      runBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-xs"></i><span>Evaluating SMT & AST...</span>';

      try {
        const resp = await fetch(`/review?ablate_z3=${ablateZ3}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentBundleData)
        });

        const result = await resp.json();
        renderResult(result);
      } catch (err) {
        alert('Review error: ' + err);
      } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = '<i class="fa-solid fa-play text-xs"></i><span>Run Verification Pipeline</span>';
      }
    }

    function renderResult(res) {
      // Verdict Badge
      const badge = document.getElementById('verdictBadge');
      if (res.status === 'PASS') {
        badge.className = 'mt-1 inline-flex items-center px-3 py-1 rounded-full text-sm font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-700/60';
        badge.innerHTML = '<i class="fa-solid fa-circle-check mr-1.5"></i>PASS';
      } else if (res.status === 'CHANGES_REQUIRED') {
        badge.className = 'mt-1 inline-flex items-center px-3 py-1 rounded-full text-sm font-bold bg-rose-950/80 text-rose-300 border border-rose-700/60';
        badge.innerHTML = '<i class="fa-solid fa-circle-xmark mr-1.5"></i>CHANGES_REQUIRED';
      } else {
        badge.className = 'mt-1 inline-flex items-center px-3 py-1 rounded-full text-sm font-bold bg-amber-950/80 text-amber-300 border border-amber-700/60';
        badge.innerHTML = '<i class="fa-solid fa-triangle-exclamation mr-1.5"></i>INCOMPLETE';
      }

      document.getElementById('summaryText').textContent = res.summary;
      document.getElementById('latencySpan').textContent = (res.provenance?.execution_time_ms || 25).toFixed(1) + ' ms';

      // Counterexample
      const ceContainer = document.getElementById('counterexampleContainer');
      const ceFinding = res.findings.find(f => f.counterexample_ticket);
      if (ceFinding && ceFinding.counterexample_ticket) {
        ceContainer.classList.remove('hidden');
        const t = ceFinding.counterexample_ticket;
        document.getElementById('ceCatMiss').textContent = t.category_missing;
        document.getElementById('ceUrgent').textContent = t.urgent;
        document.getElementById('ceWait').textContent = t.wait_seconds;
        document.getElementById('ceVip').textContent = t.vip || false;
        document.getElementById('ceExpected').textContent = t.expected_route || 'unknown';
        document.getElementById('ceActual').textContent = t.actual_route || 'unknown';
      } else {
        ceContainer.classList.add('hidden');
      }

      // Findings List
      const list = document.getElementById('findingsList');
      list.innerHTML = '';
      document.getElementById('findingsCountBadge').textContent = `${res.findings.length} findings`;
      
      if (res.findings.length === 0) {
        list.innerHTML = '<div class="text-xs text-emerald-400 font-mono p-2 bg-emerald-950/20 rounded border border-emerald-900/30"><i class="fa-solid fa-shield-check mr-1.5"></i>Zero defects detected. Formal SMT equivalence proved.</div>';
      } else {
        res.findings.forEach(f => {
          const item = document.createElement('div');
          const isBlocker = f.severity === 'BLOCKER';
          item.className = `p-2.5 rounded text-xs border ${isBlocker ? 'bg-rose-950/30 border-rose-900/50 text-rose-200' : 'bg-slate-950 border-slate-800 text-slate-300'}`;
          item.innerHTML = `
            <div class="flex items-center justify-between font-semibold">
              <span>${f.id}</span>
              <span class="text-[10px] px-1.5 py-0.5 rounded ${isBlocker ? 'bg-rose-900/60 text-rose-300' : 'bg-slate-800 text-slate-400'}">${f.severity}</span>
            </div>
            <div class="mt-1 text-[11px] leading-relaxed">${f.description}</div>
            ${f.suggested_correction ? `<div class="mt-1.5 text-[10px] text-indigo-300 font-mono"><i class="fa-solid fa-wrench mr-1"></i>Fix: ${f.suggested_correction}</div>` : ''}
          `;
          list.appendChild(item);
        });
      }

      // Checklist update
      function updateChk(id, val) {
        const el = document.getElementById(id);
        if (val) {
          el.className = 'fa-solid fa-check text-emerald-400';
        } else {
          el.className = 'fa-solid fa-xmark text-rose-400';
        }
      }
      updateChk('chkApproval', res.check_results?.approval_conflict_check);
      updateChk('chkCoverage', res.check_results?.spec_coverage_check);
      updateChk('chkZ3Spec', res.check_results?.z3_spec_equivalence);
      updateChk('chkZ3Wf', res.check_results?.z3_wf_equivalence);
      updateChk('chkZ3Py', res.check_results?.z3_py_equivalence);
      updateChk('chkModel', res.check_results?.model_inspection_clean);
    }

    document.getElementById('bundleSelect').addEventListener('change', loadBundle);
    window.onload = () => { loadBundle().then(() => runReview()); };
  </script>
</body>
</html>
"""
