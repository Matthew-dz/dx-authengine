import re

with open("frontend/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# Replace sidebar nav-roles
content = content.replace(
    '<a href="#" id="nav-roles"><i class="fas fa-user-shield me-2"></i> Cài đặt Role (RBAC)</a>',
    '<a href="#" id="nav-employees"><i class="fas fa-users me-2"></i> Quản lý Nhân sự</a>'
)
content = content.replace(
    '<a href="#"><i class="fas fa-users me-2"></i> Quản lý User</a>\n',
    ''
)

# Replace admin check in checkLoginState
old_admin_check = """            const navRolesElement = document.getElementById('nav-roles');
            if (userObj.username.toLowerCase() === 'admin') {
                navRolesElement.style.display = 'block';
            } else {
                navRolesElement.style.display = 'none';
            }"""
new_admin_check = """            const navEmployeesElement = document.getElementById('nav-employees');
            if (userObj.role.toLowerCase().includes('admin')) {
                navEmployeesElement.style.display = 'block';
            } else {
                navEmployeesElement.style.display = 'none';
            }"""
content = content.replace(old_admin_check, new_admin_check)

# Replace TRANG CÀI ĐẶT ROLE HTML
old_page_roles = """        <!-- TRANG CÀI ĐẶT ROLE (DYNAMIC RBAC) -->
        <div id="page-roles" class="d-none">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3 class="h4 mb-0 text-gray-800 fw-bold">Quản trị Phân quyền Động (Dynamic RBAC)</h3>
            </div>
            
            <div class="card card-custom">
                <div class="card-header bg-white border-0 pt-4 pb-0">
                    <h5 class="card-title fw-bold">Luân chuyển nhân sự</h5>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th>Tài khoản</th>
                                    <th>Vai trò hiện tại</th>
                                    <th>Thao tác</th>
                                </tr>
                            </thead>
                            <tbody id="rolesTableBody">
                                <tr><td colspan="3" class="text-center text-muted">Đang tải dữ liệu...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>"""
new_page_employees = """        <!-- TRANG QUẢN LÝ NHÂN SỰ -->
        <div id="page-employees" class="d-none">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3 class="h4 mb-0 text-gray-800 fw-bold">Quản trị Nhân sự & Phân quyền</h3>
                <button class="btn btn-primary fw-bold shadow-sm" onclick="openEmployeeModal()"><i class="fas fa-plus me-1"></i> Thêm nhân viên</button>
            </div>
            
            <div class="card card-custom">
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th>Mã NV</th>
                                    <th>Họ tên</th>
                                    <th>Chức vụ</th>
                                    <th>Quê quán</th>
                                    <th>SĐT</th>
                                    <th>CCCD</th>
                                    <th>Vai trò</th>
                                    <th>Thao tác</th>
                                </tr>
                            </thead>
                            <tbody id="employeesTableBody">
                                <tr><td colspan="8" class="text-center text-muted">Đang tải dữ liệu...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>"""
content = content.replace(old_page_roles, new_page_employees)

# Add Modal
modal_html = """
<!-- Modal Employee -->
<div class="modal fade" id="employeeModal" tabindex="-1">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header bg-light">
        <h5 class="modal-title fw-bold" id="employeeModalTitle">Thêm nhân viên mới</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body p-4">
        <form id="employeeForm">
            <input type="hidden" id="empId">
            <div class="row mb-3">
                <div class="col-md-6">
                    <label class="form-label">Tài khoản đăng nhập</label>
                    <input type="text" class="form-control" id="empUsername" required>
                </div>
                <div class="col-md-6">
                    <label class="form-label">Mật khẩu</label>
                    <input type="text" class="form-control" id="empPassword" required>
                </div>
            </div>
            <div class="row mb-3">
                <div class="col-md-6">
                    <label class="form-label">Họ tên</label>
                    <input type="text" class="form-control" id="empFullName" required>
                </div>
                <div class="col-md-6">
                    <label class="form-label">Chức vụ</label>
                    <input type="text" class="form-control" id="empPosition" required>
                </div>
            </div>
            <div class="row mb-3">
                <div class="col-md-4">
                    <label class="form-label">Ngày vào làm</label>
                    <input type="date" class="form-control" id="empHireDate" required>
                </div>
                <div class="col-md-4">
                    <label class="form-label">Số điện thoại</label>
                    <input type="text" class="form-control" id="empPhone" required>
                </div>
                <div class="col-md-4">
                    <label class="form-label">CCCD</label>
                    <input type="text" class="form-control" id="empCCCD" required>
                </div>
            </div>
            <div class="row mb-3">
                <div class="col-md-6">
                    <label class="form-label">Địa chỉ</label>
                    <input type="text" class="form-control" id="empAddress" required>
                </div>
                <div class="col-md-6">
                    <label class="form-label">Quê quán</label>
                    <input type="text" class="form-control" id="empHometown" required>
                </div>
            </div>
            <div class="mb-3">
                <label class="form-label">Vai trò (Role - Casbin)</label>
                <select class="form-select" id="empRole" required>
                    <option value="admin">Admin (Toàn quyền)</option>
                    <option value="staff_sales">Sales (Quyền giới hạn)</option>
                    <option value="warehouse">Warehouse (Không quyền)</option>
                </select>
            </div>
            <div class="text-end mt-4">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Hủy</button>
                <button type="submit" class="btn btn-primary" id="btnSaveEmployee">Lưu lại</button>
            </div>
        </form>
      </div>
    </div>
  </div>
</div>
"""
content = content.replace("<!-- Modal Hoàn Tiền -->", modal_html + "\n<!-- Modal Hoàn Tiền -->")

# Replace nav javascript
old_nav_js = """    const navOrders = document.getElementById('nav-orders');
    const navLogs = document.getElementById('nav-logs');
    const navRoles = document.getElementById('nav-roles');
    
    const pageOrders = document.getElementById('page-orders');
    const pageLogs = document.getElementById('page-logs');
    const pageRoles = document.getElementById('page-roles');

    function resetNavs() {
        navOrders.classList.remove('active');
        navLogs.classList.remove('active');
        navRoles.classList.remove('active');
        pageOrders.classList.add('d-none');
        pageLogs.classList.add('d-none');
        pageRoles.classList.add('d-none');
    }

    navOrders.addEventListener('click', (e) => {
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

    navRoles.addEventListener('click', (e) => {
        e.preventDefault();
        resetNavs();
        navRoles.classList.add('active');
        pageRoles.classList.remove('d-none');
        loadRoles(); // Tải danh sách role
    });"""

new_nav_js = """    const navOrders = document.getElementById('nav-orders');
    const navLogs = document.getElementById('nav-logs');
    const navEmployees = document.getElementById('nav-employees');
    
    const pageOrders = document.getElementById('page-orders');
    const pageLogs = document.getElementById('page-logs');
    const pageEmployees = document.getElementById('page-employees');

    function resetNavs() {
        navOrders.classList.remove('active');
        navLogs.classList.remove('active');
        if (navEmployees) navEmployees.classList.remove('active');
        pageOrders.classList.add('d-none');
        pageLogs.classList.add('d-none');
        if (pageEmployees) pageEmployees.classList.add('d-none');
    }

    navOrders.addEventListener('click', (e) => {
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
content = content.replace(old_nav_js, new_nav_js)

# Remove old loadRoles and updateRole
import re
content = re.sub(r'// --- QUẢN LÝ ROLES DYNAMIC \(RBAC\) ---.*?(?=// --- CHART.JS)', '', content, flags=re.DOTALL)

# Insert Employee JS
employee_js = """    // --- QUẢN LÝ NHÂN SỰ ---
    const employeeModal = new bootstrap.Modal(document.getElementById('employeeModal'));
    
    window.openEmployeeModal = function(empStr = null) {
        if (empStr) {
            const emp = JSON.parse(decodeURIComponent(empStr));
            document.getElementById('employeeModalTitle').innerText = 'Cập nhật Nhân viên & Phân quyền';
            document.getElementById('empId').value = emp.id;
            document.getElementById('empUsername').value = emp.username;
            document.getElementById('empUsername').disabled = true;
            document.getElementById('empPassword').value = emp.password; 
            document.getElementById('empPassword').disabled = true;
            document.getElementById('empFullName').value = emp.full_name;
            document.getElementById('empPosition').value = emp.position;
            document.getElementById('empHireDate').value = emp.hire_date;
            document.getElementById('empPhone').value = emp.phone;
            document.getElementById('empCCCD').value = emp.cccd;
            document.getElementById('empAddress').value = emp.address;
            document.getElementById('empHometown').value = emp.hometown;
            document.getElementById('empRole').value = emp.role;
        } else {
            document.getElementById('employeeModalTitle').innerText = 'Thêm nhân viên mới';
            document.getElementById('employeeForm').reset();
            document.getElementById('empId').value = '';
            document.getElementById('empUsername').disabled = false;
            document.getElementById('empPassword').disabled = false;
        }
        employeeModal.show();
    }
    
    async function loadEmployees() {
        const tbody = document.getElementById('employeesTableBody');
        tbody.innerHTML = '<tr><td colspan="8" class="text-center">Đang tải...</td></tr>';
        try {
            const res = await fetch('http://127.0.0.1:8000/api/v1/employees');
            const data = await res.json();
            tbody.innerHTML = '';
            data.forEach(emp => {
                const tr = document.createElement('tr');
                const empData = encodeURIComponent(JSON.stringify(emp));
                tr.innerHTML = `
                    <td class="fw-bold">#${emp.id}</td>
                    <td><div class="fw-bold">${emp.full_name}</div><small class="text-muted">@${emp.username}</small></td>
                    <td>${emp.position}</td>
                    <td>${emp.hometown}</td>
                    <td>${emp.phone}</td>
                    <td>${emp.cccd}</td>
                    <td><span class="badge bg-primary">${emp.role}</span></td>
                    <td>
                        <button class="btn btn-sm btn-info text-white me-1" onclick="openEmployeeModal('${empData}')">
                            <i class="fas fa-edit"></i> Sửa
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteEmployee(${emp.id})">
                            <i class="fas fa-trash"></i> Xóa
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">Lỗi kết nối Backend</td></tr>';
        }
    }
    
    document.getElementById('employeeForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('btnSaveEmployee');
        btn.disabled = true;
        const empId = document.getElementById('empId').value;
        const payload = {
            username: document.getElementById('empUsername').value,
            password: document.getElementById('empPassword').value,
            full_name: document.getElementById('empFullName').value,
            position: document.getElementById('empPosition').value,
            hire_date: document.getElementById('empHireDate').value,
            phone: document.getElementById('empPhone').value,
            cccd: document.getElementById('empCCCD').value,
            address: document.getElementById('empAddress').value,
            hometown: document.getElementById('empHometown').value,
            role: document.getElementById('empRole').value,
        };
        
        try {
            const url = empId ? `http://127.0.0.1:8000/api/v1/employees/${empId}` : 'http://127.0.0.1:8000/api/v1/employees';
            const method = empId ? 'PUT' : 'POST';
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                Swal.fire({ icon: 'success', title: 'Thành công!', toast: true, position: 'top-end', showConfirmButton: false, timer: 2000 });
                employeeModal.hide();
                loadEmployees();
            } else {
                const err = await res.json();
                Swal.fire('Lỗi', err.detail || 'Có lỗi xảy ra', 'error');
            }
        } catch (e) {
            Swal.fire('Lỗi', 'Không thể kết nối đến Backend', 'error');
        } finally {
            btn.disabled = false;
        }
    });
    
    window.deleteEmployee = async function(id) {
        if (!confirm('Bạn có chắc chắn muốn xóa nhân viên này?')) return;
        try {
            const res = await fetch(`http://127.0.0.1:8000/api/v1/employees/${id}`, { method: 'DELETE' });
            if (res.ok) {
                Swal.fire({ icon: 'success', title: 'Đã xóa!', toast: true, position: 'top-end', showConfirmButton: false, timer: 2000 });
                loadEmployees();
            }
        } catch (e) {
            Swal.fire('Lỗi', 'Không thể xóa', 'error');
        }
    }

    // --- CHART.JS"""
content = content.replace("// --- CHART.JS", employee_js)

with open("frontend/index.html", "w", encoding="utf-8") as f:
    f.write(content)
