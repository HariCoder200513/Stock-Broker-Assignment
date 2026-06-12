async function loadStocks() {
    const response = await fetch("http://127.0.0.1:5000/stocks");
    const data = await response.json();
    console.log(response.json())

    const table = document.getElementById("stockTable");
    table.innerHTML = "";

    data.forEach(stock => {
        table.innerHTML += `
            <tr>
                <td>${stock.ticker}</td>
                <td>${stock.name ?? "N/A"}</td>
                <td>${stock.sector ?? "N/A"}</td>
                <td>${stock.market_cap ?? "N/A"}</td>
            </tr>
        `;
    });
}

loadStocks();