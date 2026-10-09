import re

with open("frontend/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update page-orders header and remove the row
page_orders_old = """        <!-- TRANG QUẢN LÝ ĐƠN HÀNG -->
        <div id="page-orders">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3 class="h4 mb-0 text-gray-800 fw-bold">Trạm Xử Lý Hoàn Tiền</h3>
                <button class="btn btn-sm btn-outline-secondary" onclick="loadOrders()"><i class="fas fa-sync-alt me-1"></i> Làm mới dữ liệu</button>
            </div>
            
            <div class="row mb-3">
                <div class="col-md-4">
                    <div class="card card-custom h-100 mb-0 shadow-sm border-0">
                        <div class="card-body text-center p-3">
                            <h6 class="fw-bold text-secondary mb-2" style="font-size: 0.9rem;">Tỷ lệ Quyết định Hoàn tiền</h6>
                            <div style="height: 120px; display: flex; justify-content: center;">
                                <canvas id="refundChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-8">
                    <div class="card card-custom h-100 mb-0 shadow-sm border-0 bg-primary text-white d-flex justify-content-center align-items-center text-center p-3" style="background: linear-gradient(135deg, #0d6efd, #0dcaf0);">
                        <div>
                            <h4 class="fw-bold mb-1"><i class="fas fa-robot me-2"></i> AI-Powered DX-OS</h4>
                            <p class="mb-0" style="font-size: 0.95rem;">Ứng dụng quản lý giao dịch với ABAC & AI Automation</p>
                        </div>
                    </div>
                </div>
            </div>"""

page_orders_new = """        <!-- TRANG QUẢN LÝ ĐƠN HÀNG -->
        <div id="page-orders">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3 class="h4 mb-0 text-gray-800 fw-bold">Quản lý Đơn hàng</h3>
                <button class="btn btn-sm btn-outline-secondary" onclick="loadOrders()"><i class="fas fa-sync-alt me-1"></i> Làm mới dữ liệu</button>
            </div>"""

# 2. Update page-logs to insert the row
page_logs_old = """        <!-- TRANG LỊCH SỬ HỆ THỐNG -->
        <div id="page-logs" class="d-none">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3 class="h4 mb-0 text-gray-800 fw-bold">Lịch sử Hệ thống</h3>
                <button class="btn btn-success fw-bold shadow-sm" onclick="exportCSV()"><i class="fas fa-file-csv me-1"></i> Xuất CSV</button>
            </div>"""

page_logs_new = """        <!-- TRANG LỊCH SỬ HỆ THỐNG -->
        <div id="page-logs" class="d-none">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3 class="h4 mb-0 text-gray-800 fw-bold">Lịch sử Hệ thống</h3>
                <button class="btn btn-success fw-bold shadow-sm" onclick="exportCSV()"><i class="fas fa-file-csv me-1"></i> Xuất CSV</button>
            </div>
            
            <div class="row mb-3">
                <div class="col-md-4">
                    <div class="card card-custom h-100 mb-0 shadow-sm border-0">
                        <div class="card-body text-center p-3">
                            <h6 class="fw-bold text-secondary mb-2" style="font-size: 0.9rem;">Tỷ lệ Quyết định Hoàn tiền</h6>
                            <div style="height: 120px; display: flex; justify-content: center;">
                                <canvas id="refundChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-8">
                    <div class="card card-custom h-100 mb-0 shadow-sm border-0 bg-primary text-white d-flex justify-content-center align-items-center text-center p-3" style="background: linear-gradient(135deg, #0d6efd, #0dcaf0);">
                        <div>
                            <h4 class="fw-bold mb-1"><i class="fas fa-robot me-2"></i> AI-Powered DX-OS</h4>
                            <p class="mb-0" style="font-size: 0.95rem;">Ứng dụng quản lý giao dịch với ABAC & AI Automation</p>
                        </div>
                    </div>
                </div>
            </div>"""

content = content.replace(page_orders_old, page_orders_new)
content = content.replace(page_logs_old, page_logs_new)

with open("frontend/index.html", "w", encoding="utf-8") as f:
    f.write(content)
