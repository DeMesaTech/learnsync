document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('loginForm');
  const submitBtn = document.getElementById('loginBtn');

  const email = document.getElementById('loginEmail');
  const password = document.getElementById('loginPassword');

  const emailError = document.getElementById('loginEmailError');
  const passwordError = document.getElementById('loginPasswordError');

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  submitBtn.disabled = true;

  form.addEventListener('input', () => {
    const isValid = validateEmail() && validatePassword();
    submitBtn.disabled = !isValid;
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (validateEmail() && validatePassword()) {
      clearErrors();
      window.location.href = 'dashboard.html';
    }
  });

  function validateEmail() {
    const value = email.value.trim();
    if (!value) {
      setError(emailError, 'Email address is required.');
      return false;
    }
    if (!emailRegex.test(value)) {
      setError(emailError, 'Enter a valid email address.');
      return false;
    }
    clearError(emailError);
    return true;
  }

  function validatePassword() {
    const value = password.value.trim();
    if (!value) {
      setError(passwordError, 'Password is required.');
      return false;
    }
    if (value.length < 6) {
      setError(passwordError, 'Password must be at least 6 characters.');
      return false;
    }
    clearError(passwordError);
    return true;
  }

  function setError(element, message) {
    element.textContent = message;
    element.classList.remove('valid-msg');
  }

  function clearError(element) {
    element.textContent = '';
    element.classList.add('valid-msg');
  }

  function clearErrors() {
    clearError(emailError);
    clearError(passwordError);
  }
});