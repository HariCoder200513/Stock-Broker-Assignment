const DEFAULT_API_URL = "http://127.0.0.1:5000/stocks";
const AUTO_REFRESH_MS = 30000;

const state = {
    stocks: [],
    filteredStocks: [],
    loading: false,
    timerId: null
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
        return;
    }

    emptyState.classList.add("hidden");

    const rows = state.filteredStocks.map(stock => `
        <tr>
            <td class="mono">${stock.ticker}</td>
            <td>${stock.name ?? "N/A"}</td>
            <td>${stock.sector ?? "N/A"}</td>
            <td class="mono">${formatMarketCap(stock.market_cap)}</td>
        </tr>
    `);

    table.innerHTML = rows.join("");
}

function updateSummary(data) {
    document.getElementById("requestedCount").textContent = data.requested ?? "-";
    document.getElementById("returnedCount").textContent = data.returned ?? "-";
    document.getElementById("failedCount").textContent = data.failed ?? "-";
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
