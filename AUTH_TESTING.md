# AUTH_TESTING.md

## Authentication Flow Test Cases

### 1. Register
- **Test Case ID**: TC_REG_01
- **Description**: Verify the user can register with valid credentials.
- **Steps**:
  1. Navigate to the registration page.
  2. Enter valid user details (name, email, password).
  3. Submit the registration form.
- **Expected Result**: User should be redirected to the login page with a success message.

- **Test Case ID**: TC_REG_02
- **Description**: Verify that registration fails with an existing email.
- **Expected Result**: User should receive an error message about the email being taken.

### 2. Login
- **Test Case ID**: TC_LOGIN_01
- **Description**: Verify the user can login with valid credentials.
- **Steps**:
  1. Go to the login page.
  2. Enter valid email and password.
  3. Click login.
- **Expected Result**: User should be redirected to their dashboard.

- **Test Case ID**: TC_LOGIN_02
- **Description**: Verify login fails with invalid credentials.
- **Expected Result**: User should receive an error message.

### 3. Forgot Password
- **Test Case ID**: TC_FORGOT_PASSWORD_01
- **Description**: Verify the user can request a password reset link.
- **Steps**:
  1. Click on ‘Forgot Password’. 
  2. Enter the registered email.
  3. Submit the request.
- **Expected Result**: User receives a password reset link via email.

### 4. Reset Password
- **Test Case ID**: TC_RESET_PASSWORD_01
- **Description**: Verify the user can reset password with a valid link.
- **Expected Result**: User should be prompted to enter a new password.

### 5. Admin Login
- **Test Case ID**: TC_ADMIN_LOGIN_01
- **Description**: Verify admin can login using admin credentials.
- **Expected Result**: Admin is redirected to the admin dashboard.

### 6. Role Redirects
- **Test Case ID**: TC_ROLE_REDIRECT_01
- **Description**: Verify users are redirected based on roles.
- **Expected Result**: Users are redirected to their respective dashboards based on roles.

### 7. Rate Limiting
- **Test Case ID**: TC_RATE_LIMITING_01
- **Description**: Verify that excessive login attempts are blocked.
- **Expected Result**: User receives a rate limit error after multiple failed attempts.

### 8. Lockout Testing
- **Test Case ID**: TC_LOCKOUT_TESTING_01
- **Description**: Verify account is locked after too many failed login attempts.
- **Expected Result**: Account is temporarily locked and user receives a notification.

---

**Note**: Ensure to conduct these tests in a controlled environment to verify security mechanisms are in place for the authentication flow. 
