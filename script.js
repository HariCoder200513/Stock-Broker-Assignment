async function loadStocks() {
    try {
        const response = await fetch("http://127.0.0.1:5000/stocks");
        const data = await response.json();

        const table = document.getElementById("stockTable");
        table.innerHTML = "";

        data.stocks.forEach(stock => {
            table.innerHTML += `
                <tr>
                    <td>${stock.ticker}</td>
                    <td>${stock.name ?? "N/A"}</td>
                    <td>${stock.sector ?? "N/A"}</td>
                    <td>${stock.market_cap?.toLocaleString() ?? "N/A"}</td>
                </tr>
            `;
        });

        document.getElementById("loading").style.display = "none";

    } catch (error) {
        document.getElementById("loading").innerText =
            "Failed to load stock data.";
    }
}

loadStocks();
setInterval(loadStocks, 30000);