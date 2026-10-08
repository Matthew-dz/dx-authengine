import re

with open("frontend/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update the sidebar link
content = content.replace(
    '<a href="#"><i class="fas fa-cog me-2"></i> Cài đặt</a>',
    '<a href="#" id="nav-settings"><i class="fas fa-cog me-2"></i> Cài đặt</a>'
)

# 2. Add page-settings HTML
page_settings_html = """
        <!-- TRANG CÀI ĐẶT -->
        <div id="page-settings" class="d-none">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3 class="h4 mb-0 text-gray-800 fw-bold">Cài đặt Hệ thống</h3>
            </div>
            
            <div class="card card-custom shadow-sm border-0 mb-4">
                <div class="card-header bg-white border-0 pt-4 pb-0">
                    <h5 class="card-title fw-bold text-primary">Cấu hình Chính sách Hoàn tiền (ABAC)</h5>
                </div>
                <div class="card-body p-4">
                    <form id="policySettingsForm">
                        <div class="mb-3">
                            <label for="salesRefundLimit" class="form-label fw-bold">Giới hạn ngày duyệt của Sales</label>
                            <div class="input-group" style="max-width: 300px;">
                                <input type="number" class="form-control" id="salesRefundLimit" required min="1">
                                <span class="input-group-text">ngày</span>
                            </div>
                            <div class="form-text">Số ngày tối đa kể từ ngày mua mà nhân viên Sales được phép tự động hoàn tiền.</div>
                        </div>
                        <button type="submit" class="btn btn-primary fw-bold px-4" id="btnSaveSettings">
                            <i class="fas fa-save me-2"></i> Lưu Cập Nhật
                        </button>
                    </form>
                </div>
            </div>
        </div>
"""

# Insert right before </div></div> <!-- End Main Content -->
# Wait, let's just insert it before <!-- Modal Employee -->
content = content.replace("<!-- Modal Employee -->", page_settings_html + "\n\n<!-- Modal Employee -->")

# 3. Add JS navigation logic
nav_vars = """    const navOrders = document.getElementById('nav-orders');
    const navLogs = document.getElementById('nav-logs');
    const navEmployees = document.getElementById('nav-employees');"""

nav_vars_new = """    const navOrders = document.getElementById('nav-orders');
    const navLogs = document.getElementById('nav-logs');
    const navEmployees = document.getElementById('nav-employees');
    const navSettings = document.getElementById('nav-settings');"""
content = content.replace(nav_vars, nav_vars_new)


page_vars = """    const pageOrders = document.getElementById('page-orders');
    const pageLogs = document.getElementById('page-logs');
    const pageEmployees = document.getElementById('page-employees');"""
    
page_vars_new = """    const pageOrders = document.getElementById('page-orders');
    const pageLogs = document.getElementById('page-logs');
    const pageEmployees = document.getElementById('page-employees');
    const pageSettings = document.getElementById('page-settings');"""
content = content.replace(page_vars, page_vars_new)


reset_navs = """    function resetNavs() {
        navOrders.classList.remove('active');
        navLogs.classList.remove('active');
        if (navEmployees) navEmployees.classList.remove('active');
        pageOrders.classList.add('d-none');
        pageLogs.classList.add('d-none');
        if (pageEmployees) pageEmployees.classList.add('d-none');
    }"""
    
reset_navs_new = """    function resetNavs() {
        navOrders.classList.remove('active');
        navLogs.classList.remove('active');
        if (navEmployees) navEmployees.classList.remove('active');
        if (navSettings) navSettings.classList.remove('active');
        pageOrders.classList.add('d-none');
        pageLogs.classList.add('d-none');
        if (pageEmployees) pageEmployees.classList.add('d-none');
        if (pageSettings) pageSettings.classList.add('d-none');
    }"""
content = content.replace(reset_navs, reset_navs_new)


switch_tab = """        } else if (tabId === 'nav-logs') {
            navLogs.classList.add('active');
            pageLogs.classList.remove('d-none');
        } else if (tabId === 'nav-employees' && navEmployees) {"""

switch_tab_new = """        } else if (tabId === 'nav-logs') {
            navLogs.classList.add('active');
            pageLogs.classList.remove('d-none');
        } else if (tabId === 'nav-settings' && navSettings) {
            navSettings.classList.add('active');
            pageSettings.classList.remove('d-none');
            loadSettings();
        } else if (tabId === 'nav-employees' && navEmployees) {"""
content = content.replace(switch_tab, switch_tab_new)


nav_listeners = """    if (navEmployees) {
        navEmployees.addEventListener('click', (e) => {
            e.preventDefault();
            switchTab('nav-employees');
        });
    }"""

nav_listeners_new = """    if (navEmployees) {
        navEmployees.addEventListener('click', (e) => {
            e.preventDefault();
            switchTab('nav-employees');
        });
    }
    
    if (navSettings) {
        navSettings.addEventListener('click', (e) => {
            e.preventDefault();
            switchTab('nav-settings');
        });
    }
    
    // --- SETTINGS LOGIC ---
    async function loadSettings() {
        try {
            const res = await fetch('http://127.0.0.1:8000/api/v1/settings/policy');
            if (res.ok) {
                const data = await res.json();
                document.getElementById('salesRefundLimit').value = data.limit;
            }
        } catch (e) {
            console.error(e);
        }
    }
    
    document.getElementById('policySettingsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const limitVal = document.getElementById('salesRefundLimit').value;
        const btnSave = document.getElementById('btnSaveSettings');
        btnSave.disabled = true;
        btnSave.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Đang lưu...';
        
        try {
            const res = await fetch('http://127.0.0.1:8000/api/v1/settings/policy', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_limit: parseInt(limitVal) })
            });
            
            if (res.ok) {
                Swal.fire({
                    icon: 'success', title: 'Cập nhật chính sách thành công!', toast: true,
                    position: 'top-end', showConfirmButton: false, timer: 2000
                });
            } else {
                Swal.fire('Lỗi', 'Không thể cập nhật chính sách', 'error');
            }
        } catch (e) {
            Swal.fire('Lỗi', 'Lỗi kết nối Backend', 'error');
        } finally {
            btnSave.disabled = false;
            btnSave.innerHTML = '<i class="fas fa-save me-2"></i> Lưu Cập Nhật';
        }
    });
"""
content = content.replace(nav_listeners, nav_listeners_new)

with open("frontend/index.html", "w", encoding="utf-8") as f:
    f.write(content)
