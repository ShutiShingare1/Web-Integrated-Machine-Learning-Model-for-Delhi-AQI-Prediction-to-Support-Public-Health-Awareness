let timer = 60;
let interval;

// SEND OTP
function sendOTP() {

    const email = document.getElementById("email").value;

    if (email === "") {
        alert("Enter email first");
        return;
    }

    fetch("/send_reset_otp", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            email: email
        })
    })

        .then(res => res.json())

        .then(data => {

            if (data.status === "sent") {

                document.getElementById("status").innerText = "OTP sent to your email";

                document.getElementById("emailStep").style.display = "none";

                document.getElementById("otpStep").style.display = "block";

                /* start timer */
                startTimer();

            }

            else if (data.status === "not_found") {

                document.getElementById("status").innerText = "Email not registered";

            }

        });

}



// VERIFY OTP
function verifyOTP() {

    const otp = document.getElementById("otp").value;

    fetch("/verify_reset_otp", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            otp: otp
        })

    })

        .then(res => res.json())

        .then(data => {

            if (data.status === "success") {

                document.getElementById("otpStep").style.display = "none";

                document.getElementById("passwordStep").style.display = "block";

            }

            else {

                alert("Invalid OTP");

            }

        });

}



// TIMER FUNCTION
function startTimer() {

    timer = 60;

    const resendBtn = document.getElementById("resendBtn");
    const timerText = document.getElementById("timerText");

    resendBtn.disabled = true;

    interval = setInterval(() => {

        timer--;

        timerText.innerText = "Resend OTP in " + timer + "s";

        if (timer <= 0) {

            clearInterval(interval);

            timerText.innerText = "";

            resendBtn.disabled = false;

        }

    }, 1000);

}