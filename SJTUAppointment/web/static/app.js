const state = {
  venues: [],
  streamStarted: false,
  pollTimer: null,
  activeTaskPollTimer: null,
};

const defaultTitle = document.title;

function setButtonDisabled(selector, disabled) {
  const node = document.querySelector(selector);
  if (!node) {
    return;
  }
  node.disabled = disabled;
}

function stopActiveTaskPolling() {
  if (state.activeTaskPollTimer) {
    clearInterval(state.activeTaskPollTimer);
    state.activeTaskPollTimer = null;
  }
}

function startActiveTaskPolling() {
  if (state.activeTaskPollTimer) {
    return;
  }
  state.activeTaskPollTimer = setInterval(() => {
    refreshStatus().catch(() => {});
  }, 1000);
}

function renderControls(status) {
  const busyStates = new Set(["starting", "running", "stopping"]);
  const isBusy = busyStates.has(status.state);
  setButtonDisabled("#start-task", isBusy);
  setButtonDisabled("#test-login", isBusy);
  setButtonDisabled("#test-email", isBusy);
  setButtonDisabled("#stop-task", !isBusy);
  if (isBusy) {
    startActiveTaskPolling();
  } else {
    stopActiveTaskPolling();
  }
}

function setFeedback(message, tone = "success") {
  const node = document.querySelector("#feedback");
  node.hidden = !message;
  node.className = `feedback is-${tone}`;
  node.textContent = message;
}

function renderSuccessBanner(status) {
  const banner = document.querySelector("#success-banner");
  const success = status.state === "success";
  banner.hidden = !success;
  document.body.classList.toggle("is-success", success);
  document.title = success ? "抢票成功 | SJTU Appointment Console" : defaultTitle;
  if (success) {
    setFeedback("抢票成功，请尽快前往平台确认并支付。", "success");
  }
}

function parseCsvNumbers(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number(item))
    .filter((item) => !Number.isNaN(item));
}

function collectConfig() {
  return {
    account: {
      username: document.querySelector("#username").value.trim(),
      password: document.querySelector("#password").value,
    },
    task: {
      venue: document.querySelector("#venue").value,
      venue_item: document.querySelector("#venue-item").value,
      target_date: document.querySelector("#target-date").value,
      times: parseCsvNumbers(document.querySelector("#times").value),
      headless: document.querySelector("#headless").checked,
      pre_poll_ms: Number(document.querySelector("#pre-poll").value || 1000),
      post_poll_ms: Number(document.querySelector("#post-poll").value || 500),
    },
    notification: {
      enabled: document.querySelector("#notification-enabled").checked,
      smtp_host: document.querySelector("#smtp-host").value.trim(),
      smtp_port: Number(document.querySelector("#smtp-port").value || 465),
      use_ssl: document.querySelector("#smtp-ssl").value === "true",
      sender: document.querySelector("#smtp-sender").value.trim(),
      password: document.querySelector("#smtp-password").value,
      receiver: document.querySelector("#smtp-receiver").value.trim(),
    },
  };
}

function updateVenueItems(selectedVenue, selectedItem = "") {
  const venueItemSelect = document.querySelector("#venue-item");
  const venue = state.venues.find((entry) => entry.name === selectedVenue);
  venueItemSelect.innerHTML = "";
  (venue?.items || []).forEach((item) => {
    const option = document.createElement("option");
    option.value = item;
    option.textContent = item;
    if (item === selectedItem) {
      option.selected = true;
    }
    venueItemSelect.appendChild(option);
  });
}

function fillForm(config, venues) {
  state.venues = venues;
  const venueSelect = document.querySelector("#venue");
  venueSelect.innerHTML = "";
  venues.forEach((venue) => {
    const option = document.createElement("option");
    option.value = venue.name;
    option.textContent = venue.name;
    venueSelect.appendChild(option);
  });

  document.querySelector("#username").value = config.account.username || "";
  document.querySelector("#password").value = config.account.password || "";
  document.querySelector("#headless").checked = Boolean(config.task.headless);
  document.querySelector("#target-date").value = config.task.target_date || "";
  document.querySelector("#times").value = (config.task.times || []).join(",");
  document.querySelector("#pre-poll").value = config.task.pre_poll_ms ?? 1000;
  document.querySelector("#post-poll").value = config.task.post_poll_ms ?? 500;
  document.querySelector("#notification-enabled").checked = Boolean(config.notification.enabled);
  document.querySelector("#smtp-host").value = config.notification.smtp_host || "";
  document.querySelector("#smtp-port").value = config.notification.smtp_port ?? 465;
  document.querySelector("#smtp-ssl").value = String(config.notification.use_ssl ?? true);
  document.querySelector("#smtp-sender").value = config.notification.sender || "";
  document.querySelector("#smtp-password").value = config.notification.password || "";
  document.querySelector("#smtp-receiver").value = config.notification.receiver || "";

  const selectedVenue = config.task.venue || venues[0]?.name || "";
  venueSelect.value = selectedVenue;
  updateVenueItems(selectedVenue, config.task.venue_item);
}

function renderStatus(status) {
  const statusBox = document.querySelector(".status-box");
  statusBox.classList.remove("is-success", "is-error");
  if (status.state === "success") {
    statusBox.classList.add("is-success");
  } else if (status.state === "error") {
    statusBox.classList.add("is-error");
  }
  document.querySelector("#status-message").textContent = status.message || "Ready";
  document.querySelector("#status-meta").textContent = `状态: ${status.state} | 尝试次数: ${status.attempts ?? 0}`;
  renderSuccessBanner(status);
  renderControls(status);
}

function renderLogs(logs) {
  const container = document.querySelector("#logs");
  if (!logs.length) {
    container.innerHTML = '<div class="log-line">暂无日志</div>';
    return;
  }
  container.innerHTML = logs
    .map((entry) => `<div class="log-line"><span class="log-time">${entry.time}</span>${entry.message}</div>`)
    .join("");
  container.scrollTop = container.scrollHeight;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || data.error || "请求失败");
  }
  return data;
}

async function refreshStatus() {
  const payload = await fetchJson("/api/status");
  renderStatus(payload.status);
  renderLogs(payload.logs);
}

function startPolling() {
  if (state.pollTimer) {
    return;
  }
  state.pollTimer = setInterval(() => {
    refreshStatus().catch(() => {});
  }, 3000);
}

function startStream() {
  if (state.streamStarted || !window.EventSource) {
    startPolling();
    return;
  }

  const stream = new EventSource("/api/stream");
  state.streamStarted = true;

  stream.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    renderStatus(payload.status);
    renderLogs(payload.logs);
  };

  stream.onerror = () => {
    stream.close();
    state.streamStarted = false;
    startPolling();
    setTimeout(startStream, 3000);
  };
}

async function bootstrap() {
  const payload = await fetchJson("/api/bootstrap");
  fillForm(payload.config, payload.venues);
  renderStatus(payload.status);
  renderLogs(payload.logs);
}

async function invokeAction(url) {
  const payload = await fetchJson(url, {
    method: "POST",
    body: JSON.stringify(collectConfig()),
  });
  if (payload.message) {
    setFeedback(payload.message);
  }
  await refreshStatus();
}

async function runAction(action) {
  try {
    await action();
  } catch (error) {
    setFeedback(error.message || "请求失败", "error");
  }
}

document.querySelector("#venue").addEventListener("change", (event) => {
  updateVenueItems(event.target.value);
});

document.querySelector("#test-login").addEventListener("click", () =>
  runAction(async () => {
    await invokeAction("/api/test-login");
  })
);

document.querySelector("#test-email").addEventListener("click", () =>
  runAction(async () => {
    await invokeAction("/api/test-email");
  })
);

document.querySelector("#start-task").addEventListener("click", () =>
  runAction(async () => {
    startActiveTaskPolling();
    await invokeAction("/api/start");
    await refreshStatus();
  })
);

document.querySelector("#stop-task").addEventListener("click", () =>
  runAction(async () => {
    await invokeAction("/api/stop");
    await refreshStatus();
  })
);

document.querySelector("#refresh-status").addEventListener("click", () =>
  runAction(async () => {
    await refreshStatus();
    setFeedback("状态已刷新");
  })
);

runAction(bootstrap);
startStream();
