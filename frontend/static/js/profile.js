// Enable edit mode
document.getElementById("editBtn").addEventListener("click", function () {

    // Enable dropdown
    document.getElementById("ageGroup").disabled = false;

    // Enable checkboxes
    let checkboxes = document.querySelectorAll("input[type='checkbox']");
    checkboxes.forEach(cb => cb.disabled = false);

    // Show Save button
    document.getElementById("saveBtn").style.display = "block";

    // Optional: hide edit button
    this.style.display = "none";
});


// Optional UX improvement: handle "None" selection
let diseaseCheckboxes = document.querySelectorAll("input[name='diseases']");

diseaseCheckboxes.forEach(cb => {
    cb.addEventListener("change", function () {

        if (this.value === "None" && this.checked) {
            diseaseCheckboxes.forEach(other => {
                if (other.value !== "None") other.checked = false;
            });
        }

        if (this.value !== "None" && this.checked) {
            document.querySelector("input[value='None']").checked = false;
        }
    });
});