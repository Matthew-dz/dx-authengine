import re

with open("frontend/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# Modify JS navigation to save state
old_nav_js = """    navOrders.addEventListener('click', (e) => {
        e.preventDefault();
        resetNavs();
        navOrders.classList.add('active');
        pageOrders.classList.remove('d-none');
    });

    navLogs.addEventListener('click', (e) => {
        e.preventDefault();
        resetNavs();
        navLogs.classList.add('active');
        pageLogs.classList.remove('d-none');
    });

    if (navEmployees) {
        navEmployees.addEventListener('click', (e) => {
            e.preventDefault();
            resetNavs();
            navEmployees.classList.add('active');
            pageEmployees.classList.remove('d-none');
            loadEmployees(); 
        });
    }"""

new_nav_js = """    function switchTab(tabId) {
        resetNavs();
        if (tabId === 'nav-orders') {
            navOrders.classList.add('active');
            pageOrders.classList.remove('d-none');
        } else if (tabId === 'nav-logs') {
            navLogs.classList.add('active');
            pageLogs.classList.remove('d-none');
        } else if (tabId === 'nav-employees' && navEmployees) {
            navEmployees.classList.add('active');
            pageEmployees.classList.remove('d-none');
            loadEmployees();
        }
        localStorage.setItem('activeTab', tabId);
    }

    navOrders.addEventListener('click', (e) => {
        e.preventDefault();
        switchTab('nav-orders');
    });

    navLogs.addEventListener('click', (e) => {
        e.preventDefault();
        switchTab('nav-logs');
    });

    if (navEmployees) {
        navEmployees.addEventListener('click', (e) => {
            e.preventDefault();
            switchTab('nav-employees');
        });
    }
"""

content = content.replace(old_nav_js, new_nav_js)

# Modify initialization of the page to read the activeTab
init_js_old = """    function checkLoginState() {
        const userStr = localStorage.getItem('currentUser');
        if (userStr) {
            const userObj = JSON.parse(userStr);
            document.getElementById('login-view').classList.add('d-none');
            document.getElementById('dashboard-view').classList.remove('d-none');
            
            document.getElementById('nav-user-name').innerText = userObj.name;
            document.getElementById('nav-user-role').innerText = userObj.role;

            // Ẩn hiện phần Roles theo quyền Admin
            const navEmployeesElement = document.getElementById('nav-employees');
            if (userObj.role.toLowerCase().includes('admin')) {
                navEmployeesElement.style.display = 'block';
            } else {
                navEmployeesElement.style.display = 'none';
            }
            
            loadOrders();
        } else {
            document.getElementById('login-view').classList.remove('d-none');
            document.getElementById('dashboard-view').classList.add('d-none');
        }
    }"""

init_js_new = """    function checkLoginState() {
        const userStr = localStorage.getItem('currentUser');
        if (userStr) {
            const userObj = JSON.parse(userStr);
            document.getElementById('login-view').classList.add('d-none');
            document.getElementById('dashboard-view').classList.remove('d-none');
            
            document.getElementById('nav-user-name').innerText = userObj.name;
            document.getElementById('nav-user-role').innerText = userObj.role;

            // Ẩn hiện phần Roles theo quyền Admin
            const navEmployeesElement = document.getElementById('nav-employees');
            if (userObj.role.toLowerCase().includes('admin')) {
                navEmployeesElement.style.display = 'block';
            } else {
                navEmployeesElement.style.display = 'none';
            }
            
            // Phục hồi tab đang xem
            const activeTab = localStorage.getItem('activeTab') || 'nav-orders';
            if (activeTab === 'nav-employees' && !userObj.role.toLowerCase().includes('admin')) {
                switchTab('nav-orders');
            } else {
                switchTab(activeTab);
            }
            
            loadOrders();
        } else {
            document.getElementById('login-view').classList.remove('d-none');
            document.getElementById('dashboard-view').classList.add('d-none');
        }
    }"""

content = content.replace(init_js_old, init_js_new)

with open("frontend/index.html", "w", encoding="utf-8") as f:
    f.write(content)
