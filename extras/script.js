// ============================================
// Registration Form Validation Script
// Developed by: Mohammad Hasssan De Mesa & Krisscel Merenciano
// Subject: IT ELEC 3
// ============================================

// Select elements
const form = document.getElementById('registrationForm');
const submitBtn = document.getElementById('submitBtn');

const fullname = document.getElementById('fullname');
const email = document.getElementById('email');
const mobile = document.getElementById('mobile');
const password = document.getElementById('password');
const confirmPassword = document.getElementById('confirmPassword');

// Regular expressions
const nameRegex = /^[A-Za-z\s'-]+$/;
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const mobileRegex = /^09\d{9}$/;
const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$/;

// ============================================
// SMOOTH VALIDATION HANDLING
// ============================================

// Waits for typing to stop before validating
let typingTimer;
form.addEventListener('input', delayedValidate);
form.addEventListener('blur', validateAll, true);

function delayedValidate() {
  clearTimeout(typingTimer);
  typingTimer = setTimeout(validateAll, 400); // wait 0.4s after last key press
}

function validateAll() {
  const isValid =
    validateName() &&
    validateEmail() &&
    validateMobile() &&
    validatePassword() &&
    validateConfirmPassword();

  submitBtn.disabled = !isValid;
  submitBtn.classList.toggle('active', isValid);
}

// ============================================
// FIELD VALIDATION FUNCTIONS
// ============================================

function validateName() {
  const value = fullname.value.trim();
  const error = document.getElementById('fullnameError');

  if (value === '') {
    showError(fullname, error, 'Full name is required.');
    return false;
  }
  if (!nameRegex.test(value)) {
    showError(fullname, error, 'Only letters and spaces are allowed.');
    return false;
  }
  showValid(fullname, error, 'Looks good!');
  return true;
}

function validateEmail() {
  const value = email.value.trim();
  const error = document.getElementById('emailError');

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

function validateMobile() {
  const value = mobile.value.trim();
  const error = document.getElementById('mobileError');

  if (value === '') {
    showError(mobile, error, 'Mobile number is required.');
    return false;
  }
  
  // Check for any non-numeric characters
  if (/[^\d]/.test(value)) {
    showError(mobile, error, 'Only numbers are allowed.');
    return false;
  }

  // Check for correct format (09 prefix and exactly 11 digits)
  if (!mobileRegex.test(value)) {
    showError(mobile, error, 'Must start with 09 and contain exactly 11 digits.');
    return false;
  }

  showValid(mobile, error, 'Valid mobile number!');
  return true;
}

function validatePassword() {
  const value = password.value.trim();
  const error = document.getElementById('passwordError');

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
  const error = document.getElementById('confirmPasswordError');

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

// ============================================
// HELPER FUNCTIONS
// ============================================
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

// ============================================
// FINAL SUBMIT FUNCTION
// ============================================
function validateForm() {
  if (
    validateName() &&
    validateEmail() &&
    validateMobile() &&
    validatePassword() &&
    validateConfirmPassword()
  ) {
    alert("Registration Successful!");
    form.reset();

    document.querySelectorAll('input').forEach(input => {
      input.classList.remove('valid', 'invalid');
    });
    document.querySelectorAll('.error').forEach(msg => (msg.textContent = ''));

    submitBtn.disabled = true;
    submitBtn.classList.remove('active');
    return false;
  }
  return false;
}