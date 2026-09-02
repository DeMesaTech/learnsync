# ACTIVITY 2: LearnSync Login Integration Demo Guide
**September 3, 2026**

---

## 📋 Activity Overview
Demonstrate how the LearnSync login form is integrated with the complete system by showing all 6 key components.

---

## 1️⃣ **FRONTEND: Login Form**
**File:** `static/index.html`

### How it works:
- **Email Input**: User enters their email address
- **Password Input**: User enters their password (masked)
- **Validation**: Form button only enabled when both fields have content (Alpine.js)
- **Styling**: Modern UI with Tailwind CSS and gradients

```html
<form id="loginForm" @submit.prevent="submitLogin">
    <input type="email" x-model="login.email" required />
    <input type="password" x-model="login.password" required />
    <button type="submit" :disabled="!login.isValid">Log In</button>
</form>
```

### Technologies Used:
- **Alpine.js** - Client-side form validation and reactivity
- **Tailwind CSS** - Responsive styling
- **HTML5** - Semantic form elements

---

## 2️⃣ **BACKEND: What Happens After Login Click**
**File:** `backend/routers/auth.py` → POST `/api/auth/login`

### Backend Flow:
1. **Receives** the login request (email + password)
2. **Validates** the request data using Pydantic models
3. **Processes** the authentication logic
4. **Returns** user data or error message

```python
@auth_router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Handles login request from frontend"""
    # Step 1: Connect to database
    # Step 2: Query user by email
    # Step 3: Verify password
    # Step 4: Return response
```

### Technologies Used:
- **FastAPI** - REST API framework
- **Pydantic** - Data validation
- **Async/await** - Non-blocking requests

---

## 3️⃣ **FRONTEND-BACKEND CONNECTION**
**File:** `static/index.html` → `submitLoginToBackend()`

### How Frontend Sends Data to Backend:

```javascript
async submitLoginToBackend() {
    const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            email: this.login.email,
            password: this.login.password
        })
    });
    
    const data = await response.json();
    // Handle success or error
}
```

### Network Details:
- **Protocol**: HTTP POST
- **Endpoint**: `http://localhost:8000/api/auth/login`
- **Content-Type**: `application/json`
- **Payload**: `{ email: string, password: string }`

### CORS Configuration:
Backend enables CORS for `localhost:3000` and `localhost:8000`

---

## 4️⃣ **DATABASE: Credential Verification**
**File:** `backend/routers/auth.py` + `static/learnsync.sql`

### Database Query Steps:

```python
# Step 1: Query user by email
cur.execute(
    'SELECT user_id, email, password, role, name FROM account WHERE email = %s',
    (request.email,)
)
user = cur.fetchone()

# Step 2: Check if user exists
if not user:
    raise HTTPException(status_code=401, detail="Invalid email or password")

# Step 3: Verify password hash
if not verify_password(request.password, user['password']):
    raise HTTPException(status_code=401, detail="Invalid email or password")
```

### Database Schema (Relevant Fields):
```sql
CREATE TABLE account (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,  -- SHA-256 hash
    role VARCHAR(50),                 -- 'student' or 'teacher'
    name VARCHAR(255)
);
```

### Security Layer:
- **Email is UNIQUE**: Only one account per email
- **Passwords are HASHED**: Never stored as plain text
- **Constant-time comparison**: Prevents timing attacks

---

## 5️⃣ **RESPONSE: Success vs. Failure**

### ✅ Successful Login Response:
```json
{
    "success": true,
    "message": "Welcome back, Juan Dela Cruz!",
    "user_id": 5,
    "role": "student",
    "name": "Juan Dela Cruz",
    "student_id": 101
}
```

**What happens:**
1. User data stored in `localStorage`
2. Frontend redirects to appropriate dashboard:
   - **Student** → `./student/dashboard.html`
   - **Teacher** → `./teacher/dashboard.html`

```javascript
// Store user info
localStorage.setItem('user_id', data.user_id);
localStorage.setItem('role', data.role);
localStorage.setItem('name', data.name);

// Redirect based on role
if (data.role === 'teacher') {
    window.location.href = './teacher/dashboard.html';
} else {
    window.location.href = './student/dashboard.html';
}
```

### ❌ Failed Login Response:
```json
{
    "detail": "Invalid email or password"
}
```

**What happens:**
- Alert shown to user
- User stays on login page
- Can retry login attempt

---

## 6️⃣ **SECURITY: Password Protection**

### How Passwords Are Secured:

#### Hashing (Backend: `backend/utils.py`)
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password before storing in database"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password during login"""
    return pwd_context.verify(plain_password, hashed_password)
```

### Security Features:
1. **Bcrypt Hashing**: Password converted to irreversible hash
2. **Salting**: Each hash includes unique salt (built into bcrypt)
3. **No Plain Text**: Passwords never stored or logged
4. **Constant-time Comparison**: Prevents timing-based attacks
5. **HTTPS Ready**: Application can enforce encrypted connections
6. **Database Isolation**: Only account table has password data

### Example:
- **User Input**: `MyPassword123`
- **Stored in DB**: `$2b$12$EIx3...` (irreversible hash)
- **During Login**: Hash is compared, not the plain password

---

## 🚀 How to Run the Demo

### Prerequisites:
1. PostgreSQL running with database set up
2. Python dependencies installed

### Steps:

**1. Start the Backend:**
```bash
cd backend
python -m uvicorn main:app --reload
```
Backend runs at: `http://localhost:8000`

**2. Open Frontend:**
- Open `static/index.html` in browser
- Or run a simple server: `python -m http.server 8080`
- Frontend accessible at: `http://localhost:8080`

**3. Test Login:**
- Use test credentials from database
- Example: `student@gmvcc.edu.ph` / `password123`

### Browser DevTools Tips:
- **Network Tab**: See POST request to `/api/auth/login`
- **Console**: Check for errors
- **Application Tab**: View localStorage after login

---

## 📊 System Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      USER ENTERS CREDENTIALS                │
│                   (Email + Password in Form)                 │
└────────────────────────────┬────────────────────────────────┘
                             │ (User clicks "Log In")
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              FRONTEND: Validates Form Fields                │
│                  (Alpine.js Validation)                      │
└────────────────────────────┬────────────────────────────────┘
                             │ (If valid)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│        SEND: POST /api/auth/login with JSON body           │
│            { email: "...", password: "..." }                │
└────────────────────────────┬────────────────────────────────┘
                             │ (Over HTTP)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                 BACKEND: Receive Request                    │
│              (FastAPI validates with Pydantic)              │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│            DATABASE: Query by Email                        │
│      SELECT * FROM account WHERE email = ?                 │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
           User NOT Found      User Found
                    │                 │
                    ▼                 ▼
           Return Error        Verify Password
           (401 Unauthorized)   (Compare Hashes)
                    │                 │
                    │        ┌────────┴────────┐
                    │        │                 │
                    │   Password Valid   Password Invalid
                    │        │                 │
                    └───┬────┘                 │
                        │                      │
                        ▼                      ▼
                    ✅ SUCCESS          ❌ FAILURE
                  Return User Data     Return Error
                        │                      │
                        └──────┬───────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────┐
        │  FRONTEND: Receive Response (JSON)       │
        │  { success: true, user_id: 5, role: ... │
        └──────────────────────────────────────────┘
                        │
                ┌───────┴───────┐
                │               │
         Store in           Redirect to
        localStorage      Dashboard
                │               │
                └───────┬───────┘
                        │
                        ▼
        ┌──────────────────────────────────┐
        │    USER LOGGED IN & REDIRECT    │
        │   to /student or /teacher       │
        └──────────────────────────────────┘
```

---

## 💡 Key Points to Emphasize During Demo

1. **Frontend Validation**: Form is responsive to user input
2. **Network Request**: Show POST request in DevTools Network tab
3. **Database Lookup**: Explain email query and hash verification
4. **Security**: Demonstrate that password is never shown in transit or database
5. **Role-Based Routing**: Show redirection to different dashboards
6. **Error Handling**: Test with invalid credentials to show error response

---

## 📝 Rubric Alignment

| Criteria | How We Meet It |
|----------|---|
| **Frontend Login Form** | ✅ Complete, functional form with email/password fields |
| **Frontend-Backend Connection** | ✅ Fetch POST to `/api/auth/login` with proper headers |
| **Database Integration** | ✅ Query account table, verify credentials |
| **System Functionality** | ✅ Success/failure responses, role-based redirect |
| **Explanation & Presentation** | ✅ All 6 components documented with flow diagram |
| **Security** | ✅ Passwords hashed with bcrypt, not stored plaintext |

