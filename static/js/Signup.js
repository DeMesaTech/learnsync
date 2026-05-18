document.addEventListener('DOMContentLoaded', () => {
  // Select elements
  const form = document.getElementById('signupForm');
  const submitBtn = document.getElementById('signupSubmitBtn');

  const firstName = document.getElementById('signupFirstName');
  const middleName = document.getElementById('signupMiddleName');
  const lastName = document.getElementById('signupLastName');
  const email = document.getElementById('signupEmail');
  const idNumber = document.getElementById('signupIDnumber');
  const password = document.getElementById('signupPassword');
  const confirmPassword = document.getElementById('signupConfirmPassword');

  // Regular expressions
  const nameRegex = /^[A-Za-z\s'-]+$/;
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const idNumberRegex = /^[A-Z][a-z]-\d{2}-\d-\d{3}$/;
  const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$/;

  // ============================================
  // SMOOTH VALIDATION HANDLING
  // ============================================

  let typingTimer;
  form.addEventListener('input', delayedValidate);
  form.addEventListener('blur', validateAll, true);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    validateForm();
  });

  function delayedValidate() {
    clearTimeout(typingTimer);
    typingTimer = setTimeout(validateAll, 400);
  }

  function validateAll() {
    const isValid =
      validateFirstName() &&
      validateMiddleName() &&
      validateLastName() &&
      validateEmail() &&
      validateIDnumber() &&
      validatePassword() &&
      validateConfirmPassword();

    submitBtn.disabled = !isValid;
  }

  function validateFirstName() {
    const value = firstName.value.trim();
    const error = document.getElementById('signupFirstNameError');

    if (value === '') {
      showError(firstName, error, 'First name is required.');
      return false;
    }
    if (!nameRegex.test(value)) {
      showError(firstName, error, 'Only letters and spaces are allowed.');
      return false;
    }
    showValid(firstName, error, 'Looks good!');
    return true;
  }

  function validateMiddleName() {
    const value = middleName.value.trim();
    const error = document.getElementById('signupMiddleNameError');

    if (value === '') {
      showError(middleName, error, 'Middle name is required.');
      return false;
    }
    if (!nameRegex.test(value)) {
      showError(middleName, error, 'Only letters and spaces are allowed.');
      return false;
    }
    showValid(middleName, error, 'Looks good!');
    return true;
  }

  function validateLastName() {
    const value = lastName.value.trim();
    const error = document.getElementById('signupLastNameError');

    if (value === '') {
      showError(lastName, error, 'Last name is required.');
      return false;
    }
    if (!nameRegex.test(value)) {
      showError(lastName, error, 'Only letters and spaces are allowed.');
      return false;
    }
    showValid(lastName, error, 'Looks good!');
    return true;
  }

  function validateEmail() {
    const value = email.value.trim();
    const error = document.getElementById('signupEmailError');

    if (value === '') {
      showError(email, error, 'Email address is required.');
      return false;
    }
    if (!emailRegex.test(value)) {
      showError(email, error, 'Enter a valid email (e.g. name@domain.com).');
      return false;
    }
    showValid(email, error, 'Valid email address!');
    return true;
  }

  function validateIDnumber() {
    const value = idNumber.value.trim();
    const error = document.getElementById('signupIDnumberError');

    if (value === '') {
      showError(idNumber, error, 'ID number is required.');
      return false;
    }
    if (!idNumberRegex.test(value)) {
      showError(idNumber, error, 'ID format must be like Xx-00-0-000.');
      return false;
    }
    showValid(idNumber, error, 'Valid ID number!');
    return true;
  }

  function validatePassword() {
    const value = password.value.trim();
    const error = document.getElementById('signupPasswordError');

    if (value === '') {
      showError(password, error, 'Password is required.');
      return false;
    }

    let message = '';
    if (value.length < 8) message += 'At least 8 characters. ';
    if (!/[A-Z]/.test(value)) message += 'Add an uppercase letter. ';
    if (!/[a-z]/.test(value)) message += 'Add a lowercase letter. ';
    if (!/\d/.test(value)) message += 'Add a number. ';
    if (!/[\W_]/.test(value)) message += 'Add a special character. ';

    if (message !== '') {
      showError(password, error, message.trim());
      return false;
    }

    if (!passwordRegex.test(value)) {
      showError(password, error, 'Must contain uppercase, lowercase, number, and symbol.');
      return false;
    }

    showValid(password, error, 'Strong password!');
    return true;
  }

  function validateConfirmPassword() {
    const value = confirmPassword.value.trim();
    const error = document.getElementById('signupConfirmPasswordError');

    if (value === '') {
      showError(confirmPassword, error, 'Please confirm your password.');
      return false;
    }
    if (value !== password.value.trim()) {
      showError(confirmPassword, error, 'Passwords do not match.');
      return false;
    }
    showValid(confirmPassword, error, 'Passwords match!');
    return true;
  }

  function showError(input, errorElement, message) {
    input.classList.add('invalid');
    input.classList.remove('valid');
    errorElement.textContent = message;
    errorElement.classList.remove('valid-msg');
  }

  function showValid(input, errorElement, message) {
    input.classList.add('valid');
    input.classList.remove('invalid');
    errorElement.textContent = message;
    errorElement.classList.add('valid-msg');
  }

  function validateForm() {
    if (
      validateFirstName() &&
      validateMiddleName() &&
      validateLastName() &&
      validateEmail() &&
      validateIDnumber() &&
      validatePassword() &&
      validateConfirmPassword()
    ) {
      alert('Registration Successful!');
      form.reset();

      document.querySelectorAll('#signupForm input').forEach(input => {
        input.classList.remove('valid', 'invalid');
      });
      document.querySelectorAll('#signupForm .error').forEach(msg => (msg.textContent = ''));

      submitBtn.disabled = true;
      return false;
    }
    return false;
  }
});