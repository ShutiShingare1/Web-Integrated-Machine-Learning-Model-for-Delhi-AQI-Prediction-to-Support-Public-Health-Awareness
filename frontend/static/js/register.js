let timer;
let interval;

// SEND OTP
function sendOTP() {

    const email = document.getElementById("email").value;
    const status = document.getElementById("emailStatus");

    if (email === "") {
        alert("Enter email");
        return;
    }

    fetch("/send_otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email })
    })
        .then(res => res.json())
        .then(data => {

            if (data.status === "exists") {
                status.innerText = "Email already registered";
                status.style.color = "red";
            }

            else if (data.status === "sent") {

                status.innerText = "OTP sent to email";
                status.style.color = "lightgreen";

                document.getElementById("otpBox").style.display = "block";

                startTimer();
            }

        });
}


// VERIFY OTP
function verifyOTP() {

    const otp = document.getElementById("otp").value;

    if (otp === "") {
        alert("Enter OTP");
        return;
    }

    fetch("/verify_otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ otp: otp })
    })
        .then(res => res.json())
        .then(data => {

            if (data.status === "success") {

                alert("Email verified");

                document.getElementById("registerBtn").disabled = false;

                document.getElementById("otpBox").style.display = "none";

                let btn = document.getElementById("verifyBtn");
                btn.innerText = "Verified";
                btn.classList.add("verified");
                btn.disabled = true;

            }
            else {
                alert("Invalid OTP");
            }

        });
}


// TIMER FUNCTION
function startTimer() {

    clearInterval(interval);

    timer = 60;

    const resendBtn = document.getElementById("resendBtn");
    const timerText = document.getElementById("timerText");

    resendBtn.disabled = true;

    interval = setInterval(() => {

        timer--;

        timerText.innerText = "Resend OTP in " + timer + "s";

        if (timer <= 0) {

            clearInterval(interval);

            timerText.innerText = "You can resend OTP now";

            resendBtn.disabled = false;

        }

    }, 1000);

}


let selectedDiseases = [];

function toggleTag(element) {

    const value = element.innerText.toLowerCase();

    // toggle UI
    element.classList.toggle("active");

    if (selectedDiseases.includes(value)) {
        selectedDiseases = selectedDiseases.filter(d => d !== value);
    } else {
        selectedDiseases.push(value);
    }

    // Handle "None"
    if (value === "none") {
        selectedDiseases = ["none"];
        document.querySelectorAll(".tag").forEach(tag => {
            if (tag.innerText.toLowerCase() !== "none") {
                tag.classList.remove("active");
            }
        });
    } else {
        // remove "None" if others selected
        selectedDiseases = selectedDiseases.filter(d => d !== "none");
        document.querySelectorAll(".tag").forEach(tag => {
            if (tag.innerText.toLowerCase() === "none") {
                tag.classList.remove("active");
            }
        });
    }

    // set hidden input
    document.getElementById("diseaseInput").value = selectedDiseases.join(",");
}