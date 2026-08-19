const elements = {
  total: document.querySelector("#totalMetric"),
  open: document.querySelector("#openMetric"),
  overdue: document.querySelector("#overdueMetric"),
  resolution: document.querySelector("#resolutionMetric"),
  categoryBreakdown: document.querySelector("#categoryBreakdown"),
  statusBreakdown: document.querySelector("#statusBreakdown"),
  ticketRows: document.querySelector("#ticketRows"),
  ticketCount: document.querySelector("#ticketCount"),
  query: document.querySelector("#queryFilter"),
  status: document.querySelector("#statusFilter"),
  priority: document.querySelector("#priorityFilter"),
  newTicketButton: document.querySelector("#newTicketButton"),
  dialog: document.querySelector("#ticketDialog"),
  closeDialogButton: document.querySelector("#closeDialogButton"),
  cancelTicketButton: document.querySelector("#cancelTicketButton"),
  ticketForm: document.querySelector("#ticketForm"),
  formMessage: document.querySelector("#formMessage"),
};

const escapeHtml = (value) =>
  String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);

function renderBreakdown(container, items) {
  container.innerHTML = items
    .map(({ category, status, count }) => `<span>${escapeHtml(category || status).toLowerCase()} <b>${count}</b></span>`)
    .join("");
}

async function loadMetrics() {
  const response = await fetch("/api/metrics");
  const metrics = await response.json();
  elements.total.textContent = metrics.total;
  elements.open.textContent = metrics.open;
  elements.overdue.textContent = metrics.overdue;
  elements.resolution.textContent = `${metrics.average_resolution_hours}h`;
  renderBreakdown(elements.categoryBreakdown, metrics.by_category);
  renderBreakdown(elements.statusBreakdown, metrics.by_status);
}

function badge(value, type) {
  return `<span class="badge ${type}-${value.toLowerCase().replaceAll(" ", "-")}">${escapeHtml(value).toLowerCase()}</span>`;
}

function renderTickets(tickets) {
  elements.ticketCount.textContent = `${tickets.length} ticket${tickets.length === 1 ? "" : "s"}`;
  elements.ticketRows.innerHTML = tickets.map((ticket) => `
    <tr title="${escapeHtml(ticket.description)}">
      <td><strong>${escapeHtml(ticket.title)}</strong><small>${escapeHtml(ticket.requester)}</small></td>
      <td>${escapeHtml(ticket.category).toLowerCase()}</td>
      <td>${badge(ticket.priority, "priority")}</td>
      <td>${badge(ticket.status, "status")}</td>
      <td>${escapeHtml(ticket.assigned_to).toLowerCase()}</td>
      <td>${new Date(ticket.due_at.replace(" ", "T")).toLocaleDateString()}</td>
    </tr>`).join("");
}

async function loadTickets() {
  const params = new URLSearchParams();
  if (elements.query.value.trim()) params.set("query", elements.query.value.trim());
  if (elements.status.value) params.set("status", elements.status.value);
  if (elements.priority.value) params.set("priority", elements.priority.value);
  const response = await fetch(`/api/tickets?${params.toString()}`);
  const { tickets } = await response.json();
  renderTickets(tickets);
}

let searchTimer;
elements.query.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadTickets, 180);
});
elements.status.addEventListener("change", loadTickets);
elements.priority.addEventListener("change", loadTickets);

function closeTicketDialog() {
  elements.dialog.close();
  elements.formMessage.textContent = "";
}

elements.newTicketButton.addEventListener("click", () => elements.dialog.showModal());
elements.closeDialogButton.addEventListener("click", closeTicketDialog);
elements.cancelTicketButton.addEventListener("click", closeTicketDialog);
elements.dialog.addEventListener("click", (event) => {
  if (event.target === elements.dialog) closeTicketDialog();
});

elements.ticketForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = elements.ticketForm.querySelector('[type="submit"]');
  submitButton.disabled = true;
  elements.formMessage.textContent = "adding it…";

  try {
    const payload = Object.fromEntries(new FormData(elements.ticketForm));
    const response = await fetch("/api/tickets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "could not add that ticket");

    elements.ticketForm.reset();
    closeTicketDialog();
    await Promise.all([loadMetrics(), loadTickets()]);
  } catch (error) {
    elements.formMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

Promise.all([loadMetrics(), loadTickets()]).catch((error) => {
  console.error(error);
  elements.ticketRows.innerHTML = '<tr><td colspan="6">Unable to load dashboard data.</td></tr>';
});
