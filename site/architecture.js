"use strict";

const scenarios = Object.freeze({
  lifecycle: Object.freeze({
    eyebrow: "Plan composition",
    title: "Intent becomes an exact 33-stage execute/skip plan",
    summary:
      "The engine combines intent, workspace classification, scope defaults, depth, and test strategy before activating the first planned stage.",
    steps: Object.freeze([
      Object.freeze({
        title: "Capture intent",
        lane: "Interface",
        copy:
          "A human supplies a project description and greenfield or brownfield workspace classification.",
      }),
      Object.freeze({
        title: "Resolve scope",
        lane: "Scope router",
        copy:
          "An explicit scope is accepted directly. Automatic routing fails for ambiguous multi-scope vocabulary instead of guessing.",
      }),
      Object.freeze({
        title: "Load exact grid",
        lane: "Pinned catalog",
        copy:
          "One of 11 core scope presets selects execute or skip for all 33 stages plus independent depth, test-strategy, skeleton, and review-cap defaults.",
      }),
      Object.freeze({
        title: "Complete initialization",
        lane: "Initialization",
        copy:
          "Workspace Scaffold, Workspace Detection, and State Initialization complete atomically in the first state.",
      }),
      Object.freeze({
        title: "Activate cursor",
        lane: "Workflow service",
        copy:
          "The first executable non-initialization stage becomes active; all skipped and pending decisions remain explicit.",
      }),
      Object.freeze({
        title: "Allow bounded change",
        lane: "Human authority",
        copy:
          "Only a human can later change depth, tests, navigation, or pending ahead-of-cursor composition.",
      }),
    ]),
  }),
  governance: Object.freeze({
    eyebrow: "Stage-gate flow",
    title: "Declared work becomes a reviewed, human-governed decision",
    summary:
      "Each active context records canonical evidence, advisory checks, bounded reviewer outcomes, and a fresh human decision.",
    steps: Object.freeze([
      Object.freeze({
        title: "Answer questions",
        lane: "Guide / Edit / Chat",
        copy:
          "All three interaction modes converge on canonical recorded answers for the active stage and Unit.",
      }),
      Object.freeze({
        title: "Register outputs",
        lane: "Stage producer",
        copy:
          "Only declared artifact names are accepted, with a SHA-256 digest, safe relative locator, and producing context.",
      }),
      Object.freeze({
        title: "Verify inputs",
        lane: "Deterministic guard",
        copy:
          "Required upstream artifacts are enforced only when their producing stages execute in the live plan.",
      }),
      Object.freeze({
        title: "Record checks",
        lane: "Sensors + reviewers",
        copy:
          "Advisory sensors are recorded and configured reviewers return READY or NOT-READY for at most two iterations.",
      }),
      Object.freeze({
        title: "Open gate",
        lane: "Requester",
        copy:
          "The requester can open a gate only after output, input, workspace-change, reviewer, and strict-sensor guards pass.",
      }),
      Object.freeze({
        title: "Human decision",
        lane: "Authority boundary",
        copy:
          "A distinct human approves or rejects. Three revisions permit human accept-as-is without bypassing artifact guards.",
      }),
    ]),
  }),
  construction: Object.freeze({
    eyebrow: "Stage-major Unit flow",
    title: "Each Construction stage spans every Unit before one gate",
    summary:
      "The default stage-major walk settles one stage across dependency-ready Units, then gates the aggregate before moving on.",
    steps: Object.freeze([
      Object.freeze({
        title: "Generate Units",
        lane: "Inception",
        copy:
          "Units of Work declare kind, order, and dependencies. Scopes without a Unit DAG follow a stage-level zero-Unit path.",
      }),
      Object.freeze({
        title: "Run per-Unit stages",
        lane: "Construction",
        copy:
          "Functional Design through Code Generation execute stage-major: the active stage settles across every Unit before the next stage starts.",
      }),
      Object.freeze({
        title: "Gate the first stage",
        lane: "Human gate",
        copy:
          "After every Unit settles the first in-scope Construction stage, one aggregate walking-skeleton gate opens.",
      }),
      Object.freeze({
        title: "Choose once",
        lane: "Human authority",
        copy:
          "After that first stage gate, a human selects gated or autonomous execution once for the remaining Construction stages.",
      }),
      Object.freeze({
        title: "Run later stages",
        lane: "Bounded autonomy",
        copy:
          "Autonomous mode skips later Construction completion gates, while evidence, reviewer, dependency, and policy guards remain active.",
      }),
      Object.freeze({
        title: "Halt on failure",
        lane: "Recovery boundary",
        copy:
          "Any Unit failure blocks ordinary progress until a human retries, skips an eligible non-skeleton Unit, or aborts.",
      }),
      Object.freeze({
        title: "Run global checks",
        lane: "Construction",
        copy:
          "Build and Test and CI Pipeline execute once after the planned Unit set, not once per Unit.",
      }),
    ]),
  }),
  persistence: Object.freeze({
    eyebrow: "Persistence flow",
    title: "Every mutation is recoverable and hash-linked",
    summary:
      "A project lock, complete-chain verification, prepared transaction, exclusive event append, and atomic state replacement form one local commit.",
    steps: Object.freeze([
      Object.freeze({
        title: "Acquire project lock",
        lane: "Repository",
        copy:
          "A POSIX advisory lock serializes initialization, verified reads, recovery, and mutation within the supported local boundary.",
      }),
      Object.freeze({
        title: "Recover pending pair",
        lane: "Repository",
        copy:
          "If a valid prepared transaction exists, the repository completes that exact event and state pair before continuing.",
      }),
      Object.freeze({
        title: "Verify current history",
        lane: "Audit",
        copy:
          "The full event directory is checked for sequence, filenames, hashes, project identity, event count, and final state digest.",
      }),
      Object.freeze({
        title: "Mutate a copy",
        lane: "Application service",
        copy:
          "Workflow logic runs against a deep copy, so a failed validation or authority check writes no durable change.",
      }),
      Object.freeze({
        title: "Prepare next pair",
        lane: "Repository",
        copy:
          "The canonical next event and state snapshot are atomically written to the pending transaction file.",
      }),
      Object.freeze({
        title: "Append and replace",
        lane: "Repository",
        copy:
          "The event file is created exclusively and flushed before state.json is atomically replaced and the directory is flushed.",
      }),
      Object.freeze({
        title: "Remove pending marker",
        lane: "Repository",
        copy:
          "The completed pending file is removed only after the event and state are durable, making retry idempotent.",
      }),
    ]),
  }),
});

const scenarioButtons = Array.from(
  document.querySelectorAll("[data-scenario]"),
);
const scenarioEyebrow = document.querySelector("#scenario-eyebrow");
const scenarioTitle = document.querySelector("#scenario-title");
const scenarioSummary = document.querySelector("#scenario-summary");
const stepList = document.querySelector("#architecture-steps");
const stepPosition = document.querySelector("#step-position");
const stepTitle = document.querySelector("#step-title");
const stepCopy = document.querySelector("#step-copy");
const previousButton = document.querySelector("#previous-step");
const playButton = document.querySelector("#play-flow");
const nextButton = document.querySelector("#next-step");

let activeScenario = "lifecycle";
let activeStep = 0;
let timerId = null;

function stopPlayback() {
  if (timerId !== null) {
    window.clearInterval(timerId);
    timerId = null;
  }
  if (playButton) {
    playButton.textContent = "Play";
    playButton.setAttribute("aria-pressed", "false");
  }
}

function selectStep(index) {
  const scenario = scenarios[activeScenario];
  activeStep = Math.max(0, Math.min(index, scenario.steps.length - 1));
  render();
}

function createStepButton(step, index) {
  const item = document.createElement("li");
  const button = document.createElement("button");
  const number = document.createElement("span");
  const label = document.createElement("strong");
  const lane = document.createElement("small");

  button.type = "button";
  button.className = "architecture-step";
  number.textContent = String(index + 1);
  label.textContent = step.title;
  lane.textContent = step.lane;
  button.append(number, label, lane);
  button.addEventListener("click", () => {
    stopPlayback();
    selectStep(index);
  });

  if (index < activeStep) {
    button.classList.add("complete");
  }
  if (index === activeStep) {
    button.classList.add("active");
    button.setAttribute("aria-current", "step");
  }

  item.append(button);
  return item;
}

function render() {
  const scenario = scenarios[activeScenario];
  const step = scenario.steps[activeStep];
  if (
    !scenarioEyebrow ||
    !scenarioTitle ||
    !scenarioSummary ||
    !stepList ||
    !stepPosition ||
    !stepTitle ||
    !stepCopy ||
    !previousButton ||
    !nextButton
  ) {
    return;
  }

  scenarioEyebrow.textContent = scenario.eyebrow;
  scenarioTitle.textContent = scenario.title;
  scenarioSummary.textContent = scenario.summary;
  stepList.replaceChildren(
    ...scenario.steps.map((candidate, index) =>
      createStepButton(candidate, index),
    ),
  );
  stepPosition.textContent =
    `Step ${activeStep + 1} of ${scenario.steps.length} · ${step.lane}`;
  stepTitle.textContent = step.title;
  stepCopy.textContent = step.copy;
  previousButton.disabled = activeStep === 0;
  nextButton.disabled = activeStep === scenario.steps.length - 1;
}

function chooseScenario(name) {
  if (!Object.hasOwn(scenarios, name)) {
    return;
  }
  stopPlayback();
  activeScenario = name;
  activeStep = 0;
  scenarioButtons.forEach((button) => {
    const selected = button.dataset.scenario === name;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", String(selected));
  });
  render();
}

scenarioButtons.forEach((button) => {
  button.addEventListener("click", () => {
    chooseScenario(button.dataset.scenario || "");
  });
});

if (previousButton) {
  previousButton.addEventListener("click", () => {
    stopPlayback();
    selectStep(activeStep - 1);
  });
}

if (nextButton) {
  nextButton.addEventListener("click", () => {
    stopPlayback();
    selectStep(activeStep + 1);
  });
}

if (playButton) {
  const reducedMotion =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion) {
    playButton.disabled = true;
    playButton.textContent = "Auto-play off";
  } else {
    playButton.addEventListener("click", () => {
      if (timerId !== null) {
        stopPlayback();
        return;
      }
      playButton.textContent = "Pause";
      playButton.setAttribute("aria-pressed", "true");
      timerId = window.setInterval(() => {
        const lastIndex = scenarios[activeScenario].steps.length - 1;
        if (activeStep >= lastIndex) {
          stopPlayback();
          return;
        }
        activeStep += 1;
        render();
      }, 1400);
    });
  }
}

render();
