# ACTIVITY 2: Pre-Presentation Checklist

## ✅ System Setup Verification

### Database Setup
- [ ] PostgreSQL is running
- [ ] Database `school_management_system` exists
- [ ] `account` table has test data (test@gmvcc.edu.ph)
- [ ] Passwords are properly hashed

**Verify with:**
```bash
psql -U postgres -d school_management_system
SELECT email, role, name FROM account LIMIT 5;
```

---

### Backend Verification
- [ ] All dependencies installed: `pip install -r backend/requirements.txt`
- [ ] `backend/main.py` has correct DB password
- [ ] No syntax errors in:
  - `backend/main.py`
  - `backend/routers/auth.py`
  - `backend/models.py`
  - `backend/utils.py`

**Test Backend:**
```bash
cd backend
python -m uvicorn main:app --reload
# Should see: Uvicorn running on http://127.0.0.1:8000
```

---

### Frontend Verification
- [ ] `static/index.html` loads without errors
- [ ] Login form displays correctly
- [ ] Email and password fields respond to input
- [ ] "Log In" button enables/disables based on form validation

**Test Frontend:**
```bash
# Option 1: Simple HTTP server
cd static
python -m http.server 8000

# Option 2: Open file directly
# Open static/index.html in browser
```

---

## 🔐 Test Login Scenarios

### Scenario 1: Successful Login
- [ ] Use valid credentials: `student@gmvcc.edu.ph` / `password`
- [ ] Should see: "Welcome back, [Name]!"
- [ ] Should redirect to student dashboard
- [ ] Check browser DevTools → Application → localStorage for:
  - `user_id`
  - `role`
  - `name`
  - `student_id`

### Scenario 2: Invalid Email
- [ ] Enter: `nonexistent@gmvcc.edu.ph`
- [ ] Should show: "Invalid email or password"
- [ ] Should NOT redirect
- [ ] User stays on login form

### Scenario 3: Invalid Password
- [ ] Enter correct email with wrong password
- [ ] Should show: "Invalid email or password"
- [ ] Should NOT redirect
- [ ] User stays on login form

### Scenario 4: Backend Offline
- [ ] Stop backend server
- [ ] Try to login
- [ ] Should show: "Network error. Please check if the backend is running."

---

## 📱 DevTools Testing (For Presentation)

### Network Tab
- [ ] Open DevTools (F12)
- [ ] Go to Network tab
- [ ] Enter login credentials
- [ ] Click "Log In"
- [ ] See POST request to `http://localhost:8000/api/auth/login`
- [ ] Check:
  - **Request Headers**: Content-Type: application/json
  - **Request Body**: JSON with email and password
  - **Response Status**: 200 (success) or 401 (failure)
  - **Response Body**: User data or error message

### Console Tab
- [ ] Check for any JavaScript errors
- [ ] No CORS errors should appear

### Application Tab
- [ ] Verify localStorage contains user data after successful login

---

## 🎬 Demo Presentation Order

### Part 1: Frontend (2 minutes)
1. Show login form
2. Explain email/password fields
3. Show form validation (button disables when empty)
4. Explain styling (Tailwind CSS, Alpine.js)

### Part 2: Frontend-Backend Connection (2 minutes)
1. Open DevTools Network tab
2. Enter test credentials
3. Click "Log In"
4. Show POST request in Network tab
5. Highlight request headers and body

### Part 3: Backend Processing (2 minutes)
1. Show backend code running in terminal
2. Explain the login endpoint logic
3. Point out password verification step
4. Show response being sent back

### Part 4: Database Query (2 minutes)
1. Open database in pgAdmin or psql
2. Show account table
3. Explain the query that finds the user by email
4. Highlight password hash (not plaintext)
5. Explain email is UNIQUE

### Part 5: Response Handling (2 minutes)
1. Show DevTools Response tab with returned JSON
2. Explain success vs. failure responses
3. Show localStorage being populated
4. Demonstrate redirect to dashboard
5. Explain role-based routing (student vs. teacher)

### Part 6: Security (2 minutes)
1. Show `utils.py` password hashing functions
2. Explain bcrypt algorithm
3. Show example hash (irreversible)
4. Explain salt (built into bcrypt)
5. Emphasize: passwords never sent plaintext, never logged

---

## 🚨 Troubleshooting

### "Network error. Please check if the backend is running."
- Verify backend is running: `python -m uvicorn main:app --reload`
- Check backend is on `http://localhost:8000`
- Check CORS is enabled in `backend/main.py`

### "401 Invalid email or password"
- Verify test user exists in database
- Check password hash matches
- Test credentials: Check `account` table

### CORS Errors
- Verify `backend/main.py` has:
  ```python
  allow_origins=["http://localhost:3000", "http://localhost:8000", "http://localhost:8080"]
  ```

### Form won't submit
- Check browser console for JavaScript errors
- Verify Alpine.js is loaded from CDN
- Check email and password fields are not empty

### Can't see DevTools Network requests
- F12 to open DevTools
- Click Network tab BEFORE making request
- Clear existing requests
- Then test login

---

## ✨ Pro Tips for Presentation

1. **Record a demo video** in advance as backup
2. **Test with two browser windows**:
   - One showing frontend (login form)
   - One showing DevTools (Network requests)
3. **Have test credentials written down** for quick login
4. **Practice the timing** - aim for ~12 minutes total
5. **Explain error cases** - shows comprehensive system
6. **Show the database directly** - proves persistence
7. **Use browser zoom** to make text visible to audience

---

## 📊 Grading Expectations

| Criteria | Points | Your Status |
|----------|--------|------------|
| Frontend Login Form | 10 | ✅ Complete, functional form |
| Frontend-Backend Connection | 10 | ✅ Fetch POST working |
| Database Integration | 10 | ✅ Query & verification working |
| System Functionality | 10 | ✅ Login/redirect working |
| Explanation & Presentation | 10 | ⏳ [Practice based on guide] |
| **TOTAL** | **50** | **~40-45** (if tech works) |

---

## 📞 Last Minute Issues?

Run this quick test:
```bash
# Terminal 1: Start Backend
cd backend
python -m uvicorn main:app --reload

# Terminal 2: Check database
psql -U postgres -d school_management_system -c "SELECT COUNT(*) FROM account;"

# Terminal 3: Test API directly with curl
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student@gmvcc.edu.ph","password":"password"}'
```

If all three work, you're ready! ✅
