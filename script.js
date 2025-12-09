const form = document.getElementById("contactForm");

form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const userData = {
        name: document.getElementById("name").value,
        email: document.getElementById("email").value,
        message: document.getElementById("message").value
    };

    const res = await fetch("https://portfolio-backend-rgbj.onrender.com/contact", {

        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(userData)
    });

    const result = await res.json();
    document.getElementById("responseMsg").innerText = result.message;
});
