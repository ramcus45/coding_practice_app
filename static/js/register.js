
document.addEventListener('DOMContentLoaded', function () {
  const usernameInput = document.getElementById('username');
  const passwordInput = document.getElementById('password');
  const usernameFeedback = document.getElementById('usernameFeedback');
  const passwordFeedback = document.getElementById('passwordFeedback');
  const form = document.querySelector('form');

  // Username availability check
  usernameInput.addEventListener('blur', () => {
    const username = usernameInput.value.trim();
    if (username.length > 0) {
      fetch('/check_username', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `username=${encodeURIComponent(username)}`
      })
      .then(res => res.json())
      .then(data => {
        if (data.taken) {
          usernameFeedback.textContent = "Username is already taken.";
          usernameFeedback.classList.remove("d-none");
        } else {
          usernameFeedback.classList.add("d-none");
        }
      });
    }
  });

  // Password validation
  passwordInput.addEventListener('input', () => {
    const password = passwordInput.value;
    if (password.length < 6 || !/\d/.test(password)) {
      passwordFeedback.textContent = "Password must be at least 6 characters and contain a number.";
      passwordFeedback.classList.remove("d-none");
    } else {
      passwordFeedback.classList.add("d-none");
    }
  });

  // Prevent form submit if validations fail
  form.addEventListener('submit', (e) => {
    let issues = [];
  
    if (!usernameFeedback.classList.contains('d-none')) {
      issues.push("The username is already taken.");
    }
    if (!passwordFeedback.classList.contains('d-none')) {
      issues.push("The password is too weak.");
    }
  
    if (issues.length > 0) {
      e.preventDefault();
  
      const modalMessage = document.getElementById("modalMessage");
      modalMessage.innerHTML = issues.map(issue => `<li>${issue}</li>`).join("");
      const warningModal = new bootstrap.Modal(document.getElementById('warningModal'));
      warningModal.show();
    }
  });
  
});

