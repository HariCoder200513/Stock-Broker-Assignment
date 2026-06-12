// Relative URL — works on both localhost and deployed environments (Render, etc.)
const DEFAULT_API_URL = "/stocks";
const AUTO_REFRESH_MS = 30000;

const state = {
    stocks: [],
    filteredStocks: [],
    loading: false,
    timerId: null,
    currentPage: 1,
    itemsPerPage: 50
};

function getApiUrl() {
    const override = new URLSearchParams(window.location.search).get("api");
    return override || window.API_BASE_URL || DEFAULT_API_URL;
}

function formatMarketCap(value) {
    if (typeof value !== "number") {
        return "N/A";
    }

    if (value >= 1_000_000_000_000) {
        return `${(value / 1_000_000_000_000).toFixed(2)}T`;
    }

    if (value >= 1_000_000_000) {
        return `${(value / 1_000_000_000).toFixed(2)}B`;
    }

    if (value >= 1_000_000) {
        return `${(value / 1_000_000).toFixed(2)}M`;
    }

    return value.toLocaleString();
}

function setStatus(message, tone = "info") {
    const statusText = document.getElementById("statusText");
    statusText.textContent = message;
    statusText.dataset.tone = tone;
}

function setLoading(isLoading) {
    state.loading = isLoading;
    document.getElementById("refreshButton").disabled = isLoading;
}

function getFilters() {
    return {
        search: document.getElementById("searchInput").value.trim().toLowerCase(),
        sector: document.getElementById("sectorFilter").value,
        sortBy: document.getElementById("sortSelect").value
    };
}

function applyFilters() {
    const { search, sector, sortBy } = getFilters();

    const filtered = state.stocks.filter(stock => {
        const matchesSearch =
            !search ||
            stock.ticker.toLowerCase().includes(search) ||
            (stock.name ?? "").toLowerCase().includes(search) ||
            (stock.sector ?? "").toLowerCase().includes(search);

        const matchesSector = !sector || stock.sector === sector;
        return matchesSearch && matchesSector;
    });

    filtered.sort((left, right) => {
        if (sortBy === "market_cap") {
            return (right.market_cap ?? 0) - (left.market_cap ?? 0);
        }

        return String(left[sortBy] ?? "").localeCompare(
            String(right[sortBy] ?? "")
        );
    });

    state.filteredStocks = filtered;
    state.currentPage = 1; // Reset to page 1 on filter change
    renderTable();
}

function populateSectorFilter() {
    const select = document.getElementById("sectorFilter");
    const current = select.value;
    const sectors = [...new Set(state.stocks.map(stock => stock.sector).filter(Boolean))].sort();

    select.innerHTML = '<option value="">All sectors</option>';

    sectors.forEach(sector => {
        const option = document.createElement("option");
        option.value = sector;
        option.textContent = sector;
        select.appendChild(option);
    });

    if (sectors.includes(current)) {
        select.value = current;
    }
}

function renderTable() {
    const table = document.getElementById("stockTable");
    const emptyState = document.getElementById("emptyState");

    table.innerHTML = "";

    if (state.filteredStocks.length === 0) {
        emptyState.classList.remove("hidden");
        updatePaginationControls(0);
        return;
    }

    emptyState.classList.add("hidden");

    const totalPages = Math.ceil(state.filteredStocks.length / state.itemsPerPage);
    if (state.currentPage > totalPages) state.currentPage = totalPages;
    if (state.currentPage < 1) state.currentPage = 1;

    const start = (state.currentPage - 1) * state.itemsPerPage;
    const end = start + state.itemsPerPage;
    const pageItems = state.filteredStocks.slice(start, end);

    const rows = pageItems.map(stock => {
        let statusBadge = "";
        if (stock.status === "success") {
            statusBadge = stock.retries > 0 
                ? `<span class="badge warning">Retried (${stock.retries})</span>` 
                : '<span class="badge success">OK</span>';
        } else {
            statusBadge = `<span class="badge error" title="${stock.message || ''}">Failed</span>`;
        }

        return `
            <tr>
                <td class="mono">${stock.ticker}</td>
                <td>${stock.name ?? "N/A"}</td>
                <td>${stock.sector ?? "N/A"}</td>
                <td class="mono">${formatMarketCap(stock.market_cap)}</td>
                <td>${statusBadge}</td>
            </tr>
        `;
    });

    table.innerHTML = rows.join("");
    updatePaginationControls(totalPages);
}

function updatePaginationControls(totalPages) {
    const prevBtn = document.getElementById("prevPageButton");
    const nextBtn = document.getElementById("nextPageButton");
    const indicator = document.getElementById("pageIndicator");

    prevBtn.disabled = state.currentPage <= 1;
    nextBtn.disabled = state.currentPage >= totalPages || totalPages === 0;
    indicator.textContent = `Page ${totalPages > 0 ? state.currentPage : 0} of ${totalPages}`;
}

function updateSummary(data) {
    document.getElementById("requestedCount").textContent = data.requested ?? "-";
    document.getElementById("returnedCount").textContent = data.returned ?? "-";
    document.getElementById("failedCount").textContent = data.failed ?? "-";
    document.getElementById("retriesCount").textContent = data.total_retries ?? "-";
    document.getElementById("loadTime").textContent =
        typeof data.time_taken_seconds === "number"
            ? `${data.time_taken_seconds.toFixed(2)}s`
            : "-";

    document.getElementById("persistedAt").textContent = data.persisted_at
        ? `Snapshot saved ${new Date(data.persisted_at).toLocaleString()}`
        : "";
}

async function loadStocks() {
    if (state.loading) {
        return;
    }

    setLoading(true);
    setStatus("Loading stock data...");

    try {
        const response = await fetch(getApiUrl(), {
            headers: {
                Accept: "application/json"
            }
        });

        if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
        }

        const data = await response.json();

        state.stocks = Array.isArray(data.stocks) ? data.stocks : [];
        populateSectorFilter();
        updateSummary(data);
        applyFilters();

        setStatus(
            `Loaded ${data.returned ?? state.stocks.length} of ${data.requested ?? state.stocks.length} stocks.`,
            "success"
        );
    } catch (error) {
        state.stocks = [];
        state.filteredStocks = [];
        renderTable();
        setStatus(`Failed to load stock data: ${error.message}`, "error");
    } finally {
        setLoading(false);
    }
}

function setupControls() {
    document.getElementById("refreshButton").addEventListener("click", loadStocks);
    document.getElementById("searchInput").addEventListener("input", applyFilters);
    document.getElementById("sectorFilter").addEventListener("change", applyFilters);
    document.getElementById("sortSelect").addEventListener("change", applyFilters);

    document.getElementById("prevPageButton").addEventListener("click", () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            renderTable();
        }
    });

    document.getElementById("nextPageButton").addEventListener("click", () => {
        const totalPages = Math.ceil(state.filteredStocks.length / state.itemsPerPage);
        if (state.currentPage < totalPages) {
            state.currentPage++;
            renderTable();
        }
    });

    const autoRefreshToggle = document.getElementById("autoRefreshToggle");
    autoRefreshToggle.addEventListener("change", event => {
        if (state.timerId) {
            clearInterval(state.timerId);
            state.timerId = null;
        }

        if (event.target.checked) {
            state.timerId = setInterval(loadStocks, AUTO_REFRESH_MS);
        }
    });
}

setupControls();
loadStocks();
state.timerId = setInterval(loadStocks, AUTO_REFRESH_MS);
