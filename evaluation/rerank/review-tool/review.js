const PROTOCOL_VERSION = "single-expert-blind-test-retest-v1";
const STATE_VERSION = 1;
const RETEST_FRACTION = 0.1;
const EXACT_AGREEMENT_THRESHOLD = 0.85;
const WEIGHTED_KAPPA_THRESHOLD = 0.8;

const elements = Object.fromEntries(
  [
    "loading",
    "app",
    "stageLabel",
    "progressText",
    "progressBar",
    "sourceSummary",
    "sourceHash",
    "reviewWorkspace",
    "queryRail",
    "querySummary",
    "queryList",
    "queryIndex",
    "queryText",
    "candidatePlatform",
    "candidateId",
    "candidateTitle",
    "candidateExcerpt",
    "comparisonPanel",
    "firstGrade",
    "retestGrade",
    "gradeLegend",
    "uncertainLabel",
    "uncertainInput",
    "notesLabel",
    "notesInput",
    "adjudicateButton",
    "previousButton",
    "nextButton",
    "itemPosition",
    "stageActionButton",
    "stagePanel",
    "stageEyebrow",
    "stageTitle",
    "stageDescription",
    "stageMetrics",
    "stageDownloads",
    "panelActionButton",
    "importButton",
    "exportProgressButton",
    "progressFile",
    "downloadFirstButton",
    "downloadRetestButton",
    "downloadFinalButton",
    "toast",
  ].map((id) => [id, document.getElementById(id)]),
);

let reviewPackage;
let queryGroups = [];
let retestRows = [];
let state;
let toastTimer;

function emptyState(sourceHash) {
  const now = new Date().toISOString();
  return {
    state_version: STATE_VERSION,
    protocol_version: PROTOCOL_VERSION,
    source_template_sha256: sourceHash,
    stage: "first_pass",
    created_at: now,
    updated_at: now,
    first_pass_completed_at: null,
    retest_started_at: null,
    retest_completed_at: null,
    completed_at: null,
    first_pass: {},
    retest: {},
    adjudications: {},
    reliability: null,
    cursor: { query_id: null, candidate_index: 0, retest_index: 0, adjudication_index: 0 },
  };
}

async function sha256Hex(value) {
  const bytes = typeof value === "string" ? new TextEncoder().encode(value) : value;
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function prepareOrders() {
  const queryMap = new Map();
  for (const row of reviewPackage.rows) {
    const group = queryMap.get(row.query_id) ?? { query_id: row.query_id, query: row.query, rows: [] };
    group.rows.push(row);
    queryMap.set(row.query_id, group);
  }
  const queryKeys = await Promise.all(
    [...queryMap.values()].map(async (group) => ({
      group,
      key: await sha256Hex(`${reviewPackage.source_template_sha256}:query:${group.query_id}`),
    })),
  );
  queryKeys.sort((left, right) => left.key.localeCompare(right.key));
  queryGroups = [];
  for (const { group } of queryKeys) {
    const rowKeys = await Promise.all(
      group.rows.map(async (row) => ({
        row,
        key: await sha256Hex(`${reviewPackage.source_template_sha256}:candidate:${row.blind_document_id}`),
      })),
    );
    rowKeys.sort((left, right) => left.key.localeCompare(right.key));
    queryGroups.push({ ...group, rows: rowKeys.map((item) => item.row) });
  }

  const retestKeys = await Promise.all(
    reviewPackage.rows.map(async (row) => ({
      row,
      key: await sha256Hex(`${reviewPackage.source_template_sha256}:retest:${row.blind_document_id}`),
    })),
  );
  retestKeys.sort((left, right) => left.key.localeCompare(right.key));
  const sampleCount = Math.ceil(reviewPackage.candidate_count * RETEST_FRACTION);
  retestRows = retestKeys.slice(0, sampleCount).map((item) => item.row);
}

function storageKey() {
  return `needradar-rerank-review:${PROTOCOL_VERSION}:${reviewPackage.source_template_sha256}`;
}

function decisionIsComplete(decision) {
  return decision && [0, 1, 2].includes(decision.grade);
}

function allIds() {
  return new Set(reviewPackage.rows.map((row) => row.blind_document_id));
}

function retestIds() {
  return new Set(retestRows.map((row) => row.blind_document_id));
}

function validateDecisionMap(decisions, allowedIds, allowEmptyGrade = true) {
  if (!decisions || typeof decisions !== "object" || Array.isArray(decisions)) {
    throw new Error("进度中的判断记录格式无效");
  }
  for (const [id, decision] of Object.entries(decisions)) {
    if (!allowedIds.has(id) || !decision || typeof decision !== "object") {
      throw new Error(`进度包含未知候选：${id}`);
    }
    if (decision.grade !== null && decision.grade !== undefined && ![0, 1, 2].includes(decision.grade)) {
      throw new Error(`候选 ${id} 的等级无效`);
    }
    if (!allowEmptyGrade && !decisionIsComplete(decision)) {
      throw new Error(`候选 ${id} 缺少等级`);
    }
    if (typeof (decision.notes ?? "") !== "string" || typeof (decision.uncertain ?? false) !== "boolean") {
      throw new Error(`候选 ${id} 的备注格式无效`);
    }
  }
}

function validateImportedState(candidate) {
  if (
    candidate?.state_version !== STATE_VERSION ||
    candidate?.protocol_version !== PROTOCOL_VERSION ||
    candidate?.source_template_sha256 !== reviewPackage.source_template_sha256
  ) {
    throw new Error("进度文件与当前冻结标注包不匹配");
  }
  const stages = new Set(["first_pass", "retest_ready", "retest", "adjudication", "complete"]);
  if (!stages.has(candidate.stage)) {
    throw new Error("进度阶段无效");
  }
  const ids = allIds();
  validateDecisionMap(candidate.first_pass, ids);
  validateDecisionMap(candidate.retest, retestIds());
  validateDecisionMap(candidate.adjudications, retestIds());
  if (candidate.stage !== "first_pass") {
    if (!candidate.first_pass_completed_at || completedCount(candidate.first_pass) !== reviewPackage.candidate_count) {
      throw new Error("首轮尚未完整冻结，不能进入后续阶段");
    }
  }
  if (["retest", "adjudication", "complete"].includes(candidate.stage) && !candidate.retest_started_at) {
    throw new Error("隐藏重测缺少开始时间");
  }
  if (["adjudication", "complete"].includes(candidate.stage)) {
    if (!candidate.retest_completed_at || completedCount(candidate.retest) !== retestRows.length) {
      throw new Error("隐藏重测不完整");
    }
  }
  if (candidate.stage === "complete") {
    const disagreements = disagreementIds(candidate);
    for (const id of disagreements) {
      const adjudication = candidate.adjudications[id];
      if (!decisionIsComplete(adjudication) || !(adjudication.notes ?? "").trim()) {
        throw new Error("最终进度仍有未裁决分歧");
      }
    }
  }
  return candidate;
}

function loadStoredState() {
  const raw = localStorage.getItem(storageKey());
  if (!raw) return emptyState(reviewPackage.source_template_sha256);
  try {
    return validateImportedState(JSON.parse(raw));
  } catch (error) {
    localStorage.removeItem(storageKey());
    showToast(`已忽略无效的本地进度：${error.message}`);
    return emptyState(reviewPackage.source_template_sha256);
  }
}

function persist() {
  state.updated_at = new Date().toISOString();
  localStorage.setItem(storageKey(), JSON.stringify(state));
}

function completedCount(decisions) {
  return Object.values(decisions ?? {}).filter(decisionIsComplete).length;
}

function disagreementIds(sourceState = state) {
  return retestRows
    .filter((row) => sourceState.first_pass[row.blind_document_id]?.grade !== sourceState.retest[row.blind_document_id]?.grade)
    .map((row) => row.blind_document_id);
}

function weightedKappa(firstDecisions, secondDecisions, rows) {
  const matrix = Array.from({ length: 3 }, () => [0, 0, 0]);
  for (const row of rows) {
    matrix[firstDecisions[row.blind_document_id].grade][secondDecisions[row.blind_document_id].grade] += 1;
  }
  const total = rows.length;
  const firstMarginal = matrix.map((values) => values.reduce((sum, value) => sum + value, 0));
  const secondMarginal = [0, 1, 2].map((column) => matrix.reduce((sum, values) => sum + values[column], 0));
  let observedDisagreement = 0;
  let expectedDisagreement = 0;
  for (let first = 0; first < 3; first += 1) {
    for (let second = 0; second < 3; second += 1) {
      const weight = ((first - second) / 2) ** 2;
      observedDisagreement += weight * (matrix[first][second] / total);
      expectedDisagreement += weight * ((firstMarginal[first] * secondMarginal[second]) / total ** 2);
    }
  }
  return {
    matrix,
    value: expectedDisagreement === 0 ? null : 1 - observedDisagreement / expectedDisagreement,
  };
}

function calculateReliability() {
  const agreements = retestRows.filter(
    (row) => state.first_pass[row.blind_document_id].grade === state.retest[row.blind_document_id].grade,
  ).length;
  const kappa = weightedKappa(state.first_pass, state.retest, retestRows);
  return {
    exact_agreement: agreements / retestRows.length,
    weighted_kappa: kappa.value,
    confusion_matrix: kappa.matrix,
    disagreement_count: retestRows.length - agreements,
  };
}

function queryGroupForRow(row) {
  return queryGroups.find((group) => group.query_id === row.query_id);
}

function activeCollection() {
  if (state.stage === "first_pass") {
    const group = queryGroups.find((item) => item.query_id === state.cursor.query_id) ?? queryGroups[0];
    return { rows: group.rows, index: state.cursor.candidate_index, group };
  }
  if (state.stage === "retest") {
    const row = retestRows[state.cursor.retest_index] ?? retestRows[0];
    return { rows: retestRows, index: state.cursor.retest_index, group: queryGroupForRow(row) };
  }
  const ids = disagreementIds();
  const rowsById = new Map(reviewPackage.rows.map((row) => [row.blind_document_id, row]));
  const rows = ids.map((id) => rowsById.get(id));
  const row = rows[state.cursor.adjudication_index] ?? rows[0];
  return { rows, index: state.cursor.adjudication_index, group: queryGroupForRow(row) };
}

function activeRow() {
  const collection = activeCollection();
  return collection.rows[collection.index];
}

function activeDecisionMap() {
  if (state.stage === "first_pass") return state.first_pass;
  if (state.stage === "retest") return state.retest;
  return state.adjudications;
}

function ensureCursor() {
  if (!state.cursor || typeof state.cursor !== "object") {
    state.cursor = { query_id: null, candidate_index: 0, retest_index: 0, adjudication_index: 0 };
  }
  if (!queryGroups.some((group) => group.query_id === state.cursor.query_id)) {
    state.cursor.query_id = queryGroups[0].query_id;
  }
}

function render() {
  ensureCursor();
  elements.reviewWorkspace.hidden = !["first_pass", "retest", "adjudication"].includes(state.stage);
  elements.reviewWorkspace.classList.toggle("without-query-rail", state.stage !== "first_pass");
  elements.stagePanel.hidden = !["retest_ready", "complete"].includes(state.stage);
  elements.queryRail.hidden = state.stage !== "first_pass";
  renderTopbar();
  if (!elements.reviewWorkspace.hidden) renderReview();
  if (!elements.stagePanel.hidden) renderStagePanel();
}

function renderTopbar() {
  const stageConfig = {
    first_pass: ["首轮", completedCount(state.first_pass), reviewPackage.candidate_count],
    retest_ready: ["等待重测", 0, retestRows.length],
    retest: ["隐藏重测", completedCount(state.retest), retestRows.length],
    adjudication: ["分歧裁决", completedCount(state.adjudications), disagreementIds().length],
    complete: ["已完成", reviewPackage.candidate_count, reviewPackage.candidate_count],
  }[state.stage];
  const [label, completed, total] = stageConfig;
  elements.stageLabel.textContent = label;
  elements.progressText.textContent = state.stage === "retest_ready" ? `${total} 条待重测` : `${completed} / ${total}`;
  elements.progressBar.style.width = `${total ? (completed / total) * 100 : 0}%`;
}

function renderReview() {
  const collection = activeCollection();
  const row = collection.rows[collection.index];
  if (!row) return;
  const queryPosition = queryGroups.findIndex((group) => group.query_id === row.query_id) + 1;
  elements.queryIndex.textContent = `查询 ${queryPosition} / ${queryGroups.length}`;
  elements.queryText.textContent = row.query;
  elements.candidatePlatform.textContent = row.platform || "unknown";
  elements.candidateId.textContent = row.blind_document_id;
  elements.candidateTitle.textContent = row.title || "无标题";
  elements.candidateExcerpt.textContent = row.text_excerpt;
  elements.itemPosition.textContent = `${collection.index + 1} / ${collection.rows.length}`;
  elements.previousButton.disabled = collection.index <= 0;
  elements.nextButton.disabled = collection.index >= collection.rows.length - 1;

  const decision = activeDecisionMap()[row.blind_document_id] ?? { grade: null, notes: "", uncertain: false };
  document.querySelectorAll(".grade-button").forEach((button) => {
    const selected = Number(button.dataset.grade) === decision.grade;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
  });
  elements.notesInput.value = decision.notes ?? "";
  elements.uncertainInput.checked = decision.uncertain ?? false;
  const adjudicating = state.stage === "adjudication";
  elements.comparisonPanel.hidden = !adjudicating;
  elements.comparisonPanel.style.display = adjudicating ? "grid" : "none";
  elements.uncertainLabel.hidden = adjudicating;
  elements.notesLabel.textContent = adjudicating ? "裁决理由" : "备注";
  elements.gradeLegend.textContent = adjudicating ? "最终等级" : "相关性";
  elements.adjudicateButton.hidden = !adjudicating;
  if (adjudicating) {
    elements.firstGrade.textContent = String(state.first_pass[row.blind_document_id].grade);
    elements.retestGrade.textContent = String(state.retest[row.blind_document_id].grade);
    elements.adjudicateButton.disabled = !decisionIsComplete(decision) || !(decision.notes ?? "").trim();
  }

  renderQueryList();
  renderStageAction();
}

function renderQueryList() {
  if (state.stage !== "first_pass") return;
  elements.queryList.replaceChildren();
  const completeQueries = queryGroups.filter(
    (group) => group.rows.every((row) => decisionIsComplete(state.first_pass[row.blind_document_id])),
  ).length;
  elements.querySummary.textContent = `${completeQueries} / ${queryGroups.length}`;
  queryGroups.forEach((group, index) => {
    const completed = group.rows.filter((row) => decisionIsComplete(state.first_pass[row.blind_document_id])).length;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `query-button${group.query_id === state.cursor.query_id ? " active" : ""}`;
    button.innerHTML = '<span class="query-number"></span><span class="query-title"></span><span class="query-count"></span>';
    button.querySelector(".query-number").textContent = `Q${String(index + 1).padStart(2, "0")}`;
    button.querySelector(".query-title").textContent = group.query;
    button.querySelector(".query-count").textContent = `${completed}/${group.rows.length}`;
    button.title = group.query;
    button.addEventListener("click", () => {
      state.cursor.query_id = group.query_id;
      const firstIncomplete = group.rows.findIndex((row) => !decisionIsComplete(state.first_pass[row.blind_document_id]));
      state.cursor.candidate_index = firstIncomplete >= 0 ? firstIncomplete : 0;
      persist();
      render();
    });
    elements.queryList.append(button);
  });
  elements.queryList.querySelector(".query-button.active")?.scrollIntoView({ block: "nearest" });
}

function renderStageAction() {
  if (state.stage === "first_pass") {
    const complete = completedCount(state.first_pass) === reviewPackage.candidate_count;
    elements.stageActionButton.textContent = "冻结首轮";
    elements.stageActionButton.disabled = !complete;
    elements.stageActionButton.hidden = false;
  } else if (state.stage === "retest") {
    const complete = completedCount(state.retest) === retestRows.length;
    elements.stageActionButton.textContent = "完成重测";
    elements.stageActionButton.disabled = !complete;
    elements.stageActionButton.hidden = false;
  } else {
    elements.stageActionButton.hidden = true;
  }
}

function addMetric(label, value) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = value;
  wrapper.append(term, description);
  elements.stageMetrics.append(wrapper);
}

function hoursBetween(start, end) {
  if (!start || !end) return null;
  return Math.max(0, (new Date(end).getTime() - new Date(start).getTime()) / 3_600_000);
}

function renderStagePanel() {
  elements.stageMetrics.replaceChildren();
  elements.stageDownloads.hidden = true;
  elements.panelActionButton.hidden = false;
  if (state.stage === "retest_ready") {
    elements.stageEyebrow.textContent = "首轮已冻结";
    elements.stageTitle.textContent = "隐藏重测尚未开始";
    elements.stageDescription.textContent =
      "重测样本由冻结模板哈希确定。开始后不会显示首轮判断，时间间隔将写入最终证据。";
    addMetric("首轮判断", String(reviewPackage.candidate_count));
    addMetric("隐藏重测", String(retestRows.length));
    addMetric("建议间隔", "≥ 48 小时");
    elements.panelActionButton.textContent = "开始隐藏重测";
    return;
  }

  const reliability = state.reliability ?? calculateReliability();
  const delay = hoursBetween(state.first_pass_completed_at, state.retest_started_at);
  const passed = acceptancePassed(reliability);
  elements.stageEyebrow.textContent = passed ? "证据门槛通过" : "证据门槛未通过";
  elements.stageTitle.textContent = "单专家盲审已完成";
  elements.stageDescription.textContent = passed
    ? "标签可用于带有单专家证据限定的冻结质量比较。"
    : "标签和审计轨迹已保留，但质量选型必须继续保持阻塞。";
  addMetric("精确一致率", formatPercent(reliability.exact_agreement));
  addMetric("加权 kappa", reliability.weighted_kappa === null ? "不可计算" : reliability.weighted_kappa.toFixed(3));
  addMetric("重测间隔", delay === null ? "未记录" : `${delay.toFixed(1)} 小时`);
  addMetric("重测样本", String(retestRows.length));
  addMetric("已裁决分歧", String(reliability.disagreement_count));
  addMetric("证据状态", passed ? "通过" : "阻塞");
  elements.stageDownloads.hidden = false;
  elements.panelActionButton.hidden = true;
}

function currentDraft() {
  const row = activeRow();
  return activeDecisionMap()[row.blind_document_id] ?? { grade: null, notes: "", uncertain: false };
}

function saveDraft(updates) {
  const row = activeRow();
  if (!row) return;
  const decisions = activeDecisionMap();
  decisions[row.blind_document_id] = {
    grade: decisions[row.blind_document_id]?.grade ?? null,
    notes: decisions[row.blind_document_id]?.notes ?? "",
    uncertain: decisions[row.blind_document_id]?.uncertain ?? false,
    decided_at: decisions[row.blind_document_id]?.decided_at ?? null,
    ...updates,
  };
  persist();
}

function chooseGrade(grade) {
  if (state.stage === "adjudication") {
    saveDraft({ grade });
    renderReview();
    return;
  }
  saveDraft({ grade, decided_at: new Date().toISOString() });
  moveAfterGrade();
}

function moveAfterGrade() {
  if (state.stage === "first_pass") {
    const groupIndex = queryGroups.findIndex((group) => group.query_id === state.cursor.query_id);
    const group = queryGroups[groupIndex];
    if (state.cursor.candidate_index < group.rows.length - 1) {
      state.cursor.candidate_index += 1;
    } else {
      const nextIncomplete = queryGroups.find(
        (candidateGroup) =>
          candidateGroup.rows.some((row) => !decisionIsComplete(state.first_pass[row.blind_document_id])),
      );
      if (nextIncomplete) {
        state.cursor.query_id = nextIncomplete.query_id;
        state.cursor.candidate_index = nextIncomplete.rows.findIndex(
          (row) => !decisionIsComplete(state.first_pass[row.blind_document_id]),
        );
      }
    }
  } else if (state.cursor.retest_index < retestRows.length - 1) {
    state.cursor.retest_index += 1;
  }
  persist();
  render();
}

function move(delta) {
  const collection = activeCollection();
  const next = Math.max(0, Math.min(collection.rows.length - 1, collection.index + delta));
  if (state.stage === "first_pass") state.cursor.candidate_index = next;
  if (state.stage === "retest") state.cursor.retest_index = next;
  if (state.stage === "adjudication") state.cursor.adjudication_index = next;
  persist();
  render();
}

function freezeFirstPass() {
  if (completedCount(state.first_pass) !== reviewPackage.candidate_count) return;
  if (!window.confirm("冻结后首轮判断将作为重测基准，确认继续？")) return;
  state.first_pass_completed_at = new Date().toISOString();
  state.stage = "retest_ready";
  persist();
  render();
}

function startRetest() {
  state.retest_started_at = new Date().toISOString();
  state.stage = "retest";
  state.cursor.retest_index = 0;
  persist();
  render();
}

function finishRetest() {
  if (completedCount(state.retest) !== retestRows.length) return;
  state.retest_completed_at = new Date().toISOString();
  state.reliability = calculateReliability();
  if (state.reliability.disagreement_count === 0) {
    state.completed_at = new Date().toISOString();
    state.stage = "complete";
  } else {
    state.stage = "adjudication";
    state.cursor.adjudication_index = 0;
  }
  persist();
  render();
}

function saveAdjudication() {
  const draft = currentDraft();
  if (!decisionIsComplete(draft) || !(draft.notes ?? "").trim()) {
    showToast("裁决等级和理由均为必填");
    return;
  }
  saveDraft({ decided_at: new Date().toISOString(), uncertain: false });
  const ids = disagreementIds();
  const currentIndex = state.cursor.adjudication_index;
  if (currentIndex < ids.length - 1) {
    state.cursor.adjudication_index += 1;
  } else if (ids.every((id) => decisionIsComplete(state.adjudications[id]) && state.adjudications[id].notes.trim())) {
    state.completed_at = new Date().toISOString();
    state.stage = "complete";
  }
  persist();
  render();
}

function acceptancePassed(reliability) {
  return (
    reliability.exact_agreement >= EXACT_AGREEMENT_THRESHOLD &&
    reliability.weighted_kappa !== null &&
    reliability.weighted_kappa >= WEIGHTED_KAPPA_THRESHOLD &&
    disagreementIds().every(
      (id) => decisionIsComplete(state.adjudications[id]) && (state.adjudications[id].notes ?? "").trim(),
    )
  );
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function decisionNotes(decision, prefix = "") {
  const parts = [];
  if (decision?.uncertain) parts.push("[uncertain]");
  if (prefix) parts.push(prefix);
  if ((decision?.notes ?? "").trim()) parts.push(decision.notes.trim());
  return parts.join(" ");
}

function serializeRows(rows, decisionForRow) {
  const fields = [
    "query_id",
    "query",
    "split",
    "blind_document_id",
    "platform",
    "title",
    "text_excerpt",
    "relevance_grade",
    "notes",
  ];
  const lines = [fields.join(",")];
  for (const row of rows) {
    const decision = decisionForRow(row);
    const record = { ...row, relevance_grade: decision.grade, notes: decision.notes };
    lines.push(fields.map((field) => csvCell(record[field])).join(","));
  }
  return `${lines.join("\r\n")}\r\n`;
}

function firstPassCsv() {
  return serializeRows(reviewPackage.rows, (row) => {
    const decision = state.first_pass[row.blind_document_id];
    return { ...decision, notes: decisionNotes(decision) };
  });
}

function retestCsv() {
  return serializeRows(retestRows, (row) => {
    const decision = state.retest[row.blind_document_id];
    return { ...decision, notes: decisionNotes(decision) };
  });
}

function finalCsv() {
  return serializeRows(reviewPackage.rows, (row) => {
    const id = row.blind_document_id;
    const first = state.first_pass[id];
    const retest = state.retest[id];
    const adjudication = state.adjudications[id];
    if (retest && first.grade !== retest.grade) {
      return { ...adjudication, notes: decisionNotes(adjudication, "[self-adjudicated]") };
    }
    return { ...first, notes: decisionNotes(first) };
  });
}

async function finalManifest(csvText, firstCsvText, retestCsvText) {
  const reliability = state.reliability ?? calculateReliability();
  const labelsHash = await sha256Hex(new TextEncoder().encode(csvText));
  const firstPassHash = await sha256Hex(new TextEncoder().encode(firstCsvText));
  const retestHash = await sha256Hex(new TextEncoder().encode(retestCsvText));
  const delay = hoursBetween(state.first_pass_completed_at, state.retest_started_at);
  return {
    schema_version: 2,
    labels_path: "labels-adjudicated.csv",
    labels_sha256: labelsHash,
    first_pass_path: "reviewer-single.csv",
    first_pass_sha256: firstPassHash,
    retest_path: "reviewer-retest.csv",
    retest_sha256: retestHash,
    source_template_sha256: reviewPackage.source_template_sha256,
    protocol_version: PROTOCOL_VERSION,
    review_method: "single_expert_blind_test_retest",
    reviewer_count: 1,
    independent_review: false,
    system_blinded: true,
    adjudicated: true,
    all_disagreements_adjudicated: disagreementIds().every(
      (id) => decisionIsComplete(state.adjudications[id]) && state.adjudications[id].notes.trim(),
    ),
    candidate_count: reviewPackage.candidate_count,
    retest_fraction: RETEST_FRACTION,
    retest_sample_count: retestRows.length,
    retest_delay_hours: delay,
    exact_agreement: reliability.exact_agreement,
    weighted_kappa: reliability.weighted_kappa,
    disagreement_count: reliability.disagreement_count,
    acceptance: {
      exact_agreement_minimum: EXACT_AGREEMENT_THRESHOLD,
      weighted_kappa_minimum: WEIGHTED_KAPPA_THRESHOLD,
      passed: acceptancePassed(reliability),
    },
    first_pass_completed_at: state.first_pass_completed_at,
    retest_started_at: state.retest_started_at,
    retest_completed_at: state.retest_completed_at,
    completed_at: state.completed_at,
  };
}

function download(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportProgress() {
  download("rerank-review-progress.json", `${JSON.stringify(state, null, 2)}\n`, "application/json;charset=utf-8");
  showToast("进度文件已导出");
}

async function importProgress(file) {
  const candidate = validateImportedState(JSON.parse(await file.text()));
  state = candidate;
  persist();
  render();
  showToast("进度已恢复");
}

async function downloadFinal() {
  const csv = finalCsv();
  const first = firstPassCsv();
  const retest = retestCsv();
  const manifest = await finalManifest(csv, first, retest);
  download("reviewer-single.csv", first, "text/csv;charset=utf-8");
  download("reviewer-retest.csv", retest, "text/csv;charset=utf-8");
  download("labels-adjudicated.csv", csv, "text/csv;charset=utf-8");
  download(
    "labels-adjudicated.manifest.json",
    `${JSON.stringify(manifest, null, 2)}\n`,
    "application/json;charset=utf-8",
  );
  showToast("完整证据包已导出");
}

function formatPercent(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function showToast(message) {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.hidden = false;
  toastTimer = setTimeout(() => {
    elements.toast.hidden = true;
  }, 3200);
}

function bindEvents() {
  document.querySelectorAll(".grade-button").forEach((button) => {
    button.addEventListener("click", () => chooseGrade(Number(button.dataset.grade)));
  });
  elements.notesInput.addEventListener("input", () => {
    saveDraft({ notes: elements.notesInput.value });
    if (state.stage === "adjudication") {
      elements.adjudicateButton.disabled = !decisionIsComplete(currentDraft()) || !elements.notesInput.value.trim();
    }
  });
  elements.uncertainInput.addEventListener("change", () => saveDraft({ uncertain: elements.uncertainInput.checked }));
  elements.previousButton.addEventListener("click", () => move(-1));
  elements.nextButton.addEventListener("click", () => move(1));
  elements.adjudicateButton.addEventListener("click", saveAdjudication);
  elements.stageActionButton.addEventListener("click", () => {
    if (state.stage === "first_pass") freezeFirstPass();
    if (state.stage === "retest") finishRetest();
  });
  elements.panelActionButton.addEventListener("click", startRetest);
  elements.exportProgressButton.addEventListener("click", exportProgress);
  elements.importButton.addEventListener("click", () => elements.progressFile.click());
  elements.progressFile.addEventListener("change", async () => {
    const [file] = elements.progressFile.files;
    if (!file) return;
    try {
      await importProgress(file);
    } catch (error) {
      showToast(`无法导入：${error.message}`);
    } finally {
      elements.progressFile.value = "";
    }
  });
  elements.downloadFirstButton.addEventListener("click", () =>
    download("reviewer-single.csv", firstPassCsv(), "text/csv;charset=utf-8"),
  );
  elements.downloadRetestButton.addEventListener("click", () =>
    download("reviewer-retest.csv", retestCsv(), "text/csv;charset=utf-8"),
  );
  elements.downloadFinalButton.addEventListener("click", downloadFinal);
  document.addEventListener("keydown", (event) => {
    if (elements.reviewWorkspace.hidden || event.metaKey || event.ctrlKey || event.altKey) return;
    if (["TEXTAREA", "INPUT"].includes(document.activeElement?.tagName)) return;
    if (["0", "1", "2"].includes(event.key)) chooseGrade(Number(event.key));
    if (event.key === "ArrowLeft") move(-1);
    if (event.key === "ArrowRight") move(1);
    if (event.key.toLowerCase() === "u" && state.stage !== "adjudication") {
      elements.uncertainInput.checked = !elements.uncertainInput.checked;
      saveDraft({ uncertain: elements.uncertainInput.checked });
      renderReview();
    }
  });
}

async function initialize() {
  try {
    const response = await fetch("/api/package", { cache: "no-store" });
    if (!response.ok) throw new Error(`标注包请求失败：HTTP ${response.status}`);
    reviewPackage = await response.json();
    if (
      reviewPackage.protocol_version !== PROTOCOL_VERSION ||
      !Array.isArray(reviewPackage.rows) ||
      reviewPackage.rows.length !== reviewPackage.candidate_count
    ) {
      throw new Error("冻结标注包结构无效");
    }
    await prepareOrders();
    state = loadStoredState();
    ensureCursor();
    elements.sourceSummary.textContent = `${reviewPackage.query_count} 个查询 · ${reviewPackage.candidate_count} 个候选 · 本地只读`;
    elements.sourceHash.textContent = reviewPackage.source_template_sha256;
    bindEvents();
    elements.loading.hidden = true;
    elements.app.hidden = false;
    render();
  } catch (error) {
    elements.loading.textContent = `无法启动盲审工具：${error.message}`;
  }
}

initialize();
