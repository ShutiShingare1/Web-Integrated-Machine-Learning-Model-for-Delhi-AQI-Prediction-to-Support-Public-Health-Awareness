// Toggle dropdown menu
function toggleMenu() {

    const menu = document.getElementById("userDropdown");

    menu.classList.toggle("show");

}


// Close dropdown when clicking outside
window.onclick = function (event) {

    if (!event.target.closest(".user-menu")) {

        const dropdown = document.getElementById("userDropdown");

        if (dropdown) {
            dropdown.classList.remove("show");
        }

    }

}


function showDisease(type) {

    // hide all
    document.querySelectorAll(".disease").forEach(card => {
        card.classList.remove("active");
    });

    // show selected
    document.getElementById(type).classList.add("active");

    // active tab
    document.querySelectorAll(".tab").forEach(btn => {
        btn.classList.remove("active");
    });

    event.target.classList.add("active");
}


// ================= GLOBAL =================
let chart;
let currentDate = new Date();
let aqiData = {};
let lastGraphData = [];


// ================= INIT =================
document.addEventListener("DOMContentLoaded", () => {

    const dateInput = document.getElementById("datePicker");
    const modeSelect = document.getElementById("mode");

    // ===== SET TODAY DATE =====
    const today = new Date().toISOString().split("T")[0];
    dateInput.value = today;
    dateInput.max = today;

    // ===== EVENTS =====
    modeSelect.addEventListener("change", fetchGraphData);
    dateInput.addEventListener("change", fetchGraphData);

    // ===== INITIAL LOAD =====
    fetchGraphData();
    loadCalendarData();   // 🔥 FIX: was missing

    // ===== AUTO UPDATE GRAPH =====
    setInterval(fetchGraphData, 10000);
});


// ================= GRAPH =================
async function fetchGraphData() {
    const mode = document.getElementById("mode").value;
    const date = document.getElementById("datePicker").value;

    let url = `/aqi-data?mode=${mode}`;
    if (mode === "day") {
        url += `&date=${date}`;
    }

    try {
        const res = await fetch(url);
        const data = await res.json();

        console.log("DATA:", data);

        let labels = [];
        let values = [];

        if (mode === "day") {

            // ✅ ALWAYS 24 HOURS
            let hours = Array(24).fill(null);

            data.forEach(item => {
                let hour = parseInt(item[0]);
                let value = Number(item[1]);

                if (!isNaN(hour) && !isNaN(value)) {
                    hours[hour] = value;
                }
            });

            // Labels
            labels = Array.from({ length: 24 }, (_, i) =>
                i === 0 ? "12 AM" :
                    i < 12 ? `${i} AM` :
                        i === 12 ? "12 PM" :
                            `${i - 12} PM`
            );

            values = hours;

        } else {
            // WEEK MODE
            labels = data.map(item => item[0]);
            values = data.map(item => Number(item[1]));
        }

        // ✅ Better comparison (fix redraw issue)
        if (JSON.stringify(values) === JSON.stringify(lastGraphData)) {
            return;
        }
        lastGraphData = [...values];

        updateChart(labels, values);

    } catch (err) {
        console.error("Error fetching graph data:", err);
    }
}


// ================= CHART =================
function updateChart(labels, values) {
    const ctx = document.getElementById("aqiChart").getContext("2d");

    if (!chart) {
        chart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "AQI",
                    data: values,
                    backgroundColor: "rgba(29, 53, 87, 0.7)",
                    borderColor: "#1d3557",
                    borderWidth: 1,
                    borderRadius: 6   // 🔥 nicer bars
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: "#1d3557"
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: "#1d3557"
                        }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: "#1d3557"
                        }
                    }
                }
            }
        });
    } else {
        chart.data.labels = labels;
        chart.data.datasets[0].data = values;
        chart.update();
    }
}


// ================= CALENDAR =================
async function loadCalendarData() {
    const year = currentDate.getFullYear();

    try {
        const res = await fetch(`/aqi-calendar?year=${year}`);
        aqiData = await res.json();

        renderCalendar();

    } catch (err) {
        console.error("Error loading calendar:", err);
    }
}


function renderCalendar() {
    const calendar = document.getElementById("calendar");
    calendar.innerHTML = "";

    const today = new Date();
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    const monthName = currentDate.toLocaleString('default', { month: 'long' });
    document.getElementById("monthYear").innerText = `${monthName} ${year}`;

    const nextBtn = document.querySelector(".calendar-nav button:last-child");

    if (
        year === today.getFullYear() &&
        month === today.getMonth()
    ) {
        nextBtn.disabled = true;
        nextBtn.style.opacity = "0.4";
    } else {
        nextBtn.disabled = false;
        nextBtn.style.opacity = "1";
    }

    const daysDiv = document.createElement("div");
    daysDiv.classList.add("days");

    let daysInMonth = new Date(year, month + 1, 0).getDate();

    for (let day = 1; day <= daysInMonth; day++) {

        let dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        let aqi = aqiData[dateStr];

        const dayBox = document.createElement("div");
        dayBox.classList.add("day");

        if (
            year === today.getFullYear() &&
            month === today.getMonth() &&
            day > today.getDate()
        ) {
            dayBox.style.opacity = "0.3";
            dayBox.innerHTML = `<span>${day}</span><b>-</b>`;
        }
        else if (aqi) {
            dayBox.classList.add(getAQIColor(aqi));
            dayBox.innerHTML = `<span>${day}</span><b>${Math.round(aqi)}</b>`;
        }
        else {
            dayBox.innerHTML = `<span>${day}</span><b>-</b>`;
        }

        daysDiv.appendChild(dayBox);
    }

    calendar.appendChild(daysDiv);
}


// ================= MONTH CHANGE =================
function changeMonth(step) {
    const today = new Date();

    let newDate = new Date(currentDate);
    newDate.setMonth(newDate.getMonth() + step);

    if (
        newDate.getFullYear() > today.getFullYear() ||
        (newDate.getFullYear() === today.getFullYear() &&
            newDate.getMonth() > today.getMonth())
    ) {
        return;
    }

    currentDate = newDate;
    loadCalendarData();
}


// ================= AQI COLOR =================
function getAQIColor(aqi) {
    if (aqi <= 50) return "good";
    if (aqi <= 100) return "moderate";
    if (aqi <= 200) return "poor";
    if (aqi <= 300) return "unhealthy";
    if (aqi <= 400) return "severe";
    return "hazardous";
}