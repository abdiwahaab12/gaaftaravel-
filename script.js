document.addEventListener('DOMContentLoaded', function() {
    const closeBtn = document.getElementById('closeFormBox');
    const formBox = document.getElementById('formBox');
    if (closeBtn && formBox) {
        closeBtn.addEventListener('click', function() {
            formBox.classList.remove('active');
        });
    }
});

function showLoginForm() {
    const formBox = document.getElementById('formBox');
    const loginContainer = document.getElementById('login');
    const registerContainer = document.getElementById('register');
    formBox.classList.add('active');
    loginContainer.style.display = 'block';
    registerContainer.style.display = 'none';
}

function showRegisterForm() {
    const formBox = document.getElementById('formBox');
    const loginContainer = document.getElementById('login');
    const registerContainer = document.getElementById('register');
    formBox.classList.add('active');
    loginContainer.style.display = 'none';
    registerContainer.style.display = 'block';
}

// Helper function to get auth headers
function getAuthHeaders() {
    const token = localStorage.getItem('token');
    return {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
    };
}

// Connect Register Form to Flask backend
async function handleRegister(event) {
    event.preventDefault();
    const form = event.target;
    const username = form.username.value;
    const email = form.email.value;
    const password = form.password.value;
    const confirmPassword = form.confirmPassword.value;
    if (password !== confirmPassword) {
        alert('Passwords do not match!');
        return;
    }
    try {
        const res = await fetch('http://127.0.0.1:5000/api/signup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, email, password})
        });
        const data = await res.json();
        if (res.ok) {
            alert('Sign Up successful!');
            showLoginForm();
        } else {
            alert(data.error || 'Sign Up failed');
        }
    } catch (err) {
        alert('Network error. Please try again.');
    }
}

// Connect Login Form to Flask backend
async function handleLogin(event) {
    event.preventDefault();
    const form = event.target;
    const identifier = form.identifier.value;
    const password = form.password.value;
    // Try as email first, fallback to username if needed
    let email = identifier;
    let username = '';
    if (!identifier.includes('@')) {
        username = identifier;
        email = '';
    }
    try {
        const res = await fetch('http://127.0.0.1:5000/api/signin', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include', // Important: Include cookies
            body: JSON.stringify(email ? {email, password} : {username, password})
        });
        const data = await res.json();
        if (res.ok && data.token) {
            localStorage.setItem('token', data.token);
            localStorage.setItem('userData', JSON.stringify({
                username: data.user,
                email: email,
                role: data.role
            }));
            // Redirect to dashboard
            window.location.href = '/admin/dashboard';
        } else {
            alert(data.error || 'Sign In failed');
        }
    } catch (err) {
        alert('Network error. Please try again.');
    }
}

function openAuthModal(tab = 'signin') {
    document.getElementById('modalOverlay').style.display = 'block';
    document.getElementById('authModal').style.display = 'block';
    showAuthTab(tab);
}

function closeAuthModal() {
    document.getElementById('modalOverlay').style.display = 'none';
    document.getElementById('authModal').style.display = 'none';
}

document.getElementById('closeAuthModal').onclick = closeAuthModal;
document.getElementById('modalOverlay').onclick = closeAuthModal;

function showAuthTab(tab) {
    document.getElementById('signinForm').style.display = (tab === 'signin') ? 'flex' : 'none';
    document.getElementById('signupForm').style.display = (tab === 'signup') ? 'flex' : 'none';
    document.getElementById('tabSignIn').classList.toggle('active', tab === 'signin');
    document.getElementById('tabSignUp').classList.toggle('active', tab === 'signup');
}

// Navbar buttons
document.querySelector('.btn-signin').onclick = () => openAuthModal('signin');
document.querySelector('.btn-signup').onclick = () => openAuthModal('signup');

// Sign Up logic (connect to backend)
document.getElementById('signupForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const username = document.getElementById('signupUsername').value;
    const email = document.getElementById('signupEmail').value;
    const password = document.getElementById('signupPassword').value;
    const confirmPassword = document.getElementById('signupConfirmPassword').value;
    if (password !== confirmPassword) {
        alert('Passwords do not match!');
        return;
    }
    if (!document.getElementById('termsCheck').checked) {
        alert('You must agree to the Terms & Conditions.');
        return;
    }
    try {
        const first_name = document.getElementById('signupFirstName').value;
        const last_name = document.getElementById('signupLastName').value;
        const res = await fetch('http://127.0.0.1:5000/api/signup', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, email, password, first_name, last_name})
        });
        const data = await res.json();
        if (res.ok) {
            alert('Sign Up successful!');
            showAuthTab('signin');
        } else {
            alert(data.error || 'Sign Up failed');
        }
    } catch (err) {
        alert('Network error. Please try again.');
    }
});

// Sign In logic (connect to backend)
document.getElementById('signinForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const email = document.getElementById('signinEmail').value;
    const password = document.getElementById('signinPassword').value;
    try {
        const res = await fetch('http://127.0.0.1:5000/api/signin', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include', // Important: Include cookies
            body: JSON.stringify({email, password})
        });
        const data = await res.json();
        if (res.ok && data.token) {
            localStorage.setItem('token', data.token);
            localStorage.setItem('userData', JSON.stringify({
                username: data.user,
                email: email,
                role: data.role
            }));
            // Redirect to dashboard
            window.location.href = '/admin/dashboard';
        } else {
            alert(data.error || 'Sign In failed');
        }
    } catch (err) {
        alert('Network error. Please try again.');
    }
});

// Forgot Password Modal Logic
function openForgotModal() {
    document.getElementById('forgotModalOverlay').style.display = 'block';
    document.getElementById('forgotModal').style.display = 'block';
}
function closeForgotModal() {
    document.getElementById('forgotModalOverlay').style.display = 'none';
    document.getElementById('forgotModal').style.display = 'none';
}
document.getElementById('closeForgotModal').onclick = closeForgotModal;
document.getElementById('forgotModalOverlay').onclick = closeForgotModal;
document.getElementById('forgotForm').addEventListener('submit', function(e) {
    e.preventDefault();
    alert('If this email exists, a reset link will be sent.');
    closeForgotModal();
});