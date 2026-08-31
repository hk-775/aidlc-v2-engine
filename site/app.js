"use strict";

const demo = Object.freeze({
  project: "Synthetic parser repair",
  scope: "bugfix",
  status: "completed",
  stages: [
    "reverse-engineering",
    "requirements-analysis",
    "code-generation",
    "build-and-test",
    "deployment-pipeline",
    "deployment-execution",
  ],
  artifacts: 30,
  gates: 6,
  units: 0,
  auditEvents: 66,
  auditValid: true,
});

function addMetric(container, label, value) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = String(value);
  wrapper.append(term, description);
  container.append(wrapper);
}

function renderDemo() {
  const summary = document.querySelector("#stage-summary");
  const stageList = document.querySelector("#stage-list");
  const auditSummary = document.querySelector("#audit-summary");
  if (!summary || !stageList || !auditSummary) {
    return;
  }

  summary.textContent =
    `${demo.project} completed the ${demo.scope} plan across ` +
    `${demo.stages.length} gated stages.`;
  demo.stages.forEach((stage) => {
    const item = document.createElement("li");
    item.textContent = stage;
    item.classList.add("complete");
    stageList.append(item);
  });

  addMetric(auditSummary, "Status", demo.status);
  addMetric(auditSummary, "Scope", demo.scope);
  addMetric(auditSummary, "Artifacts", demo.artifacts);
  addMetric(auditSummary, "Human gates", demo.gates);
  addMetric(auditSummary, "Units", demo.units);
  addMetric(auditSummary, "Audit events", demo.auditEvents);
  addMetric(auditSummary, "Hash chain", demo.auditValid ? "valid" : "invalid");
}

renderDemo();
