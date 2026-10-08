import re

with open("frontend/index.html", "r", encoding="utf-8") as f:
    content = f.read()

settings_block = """        <!-- TRANG CÀI ĐẶT -->
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
        </div>"""

# Remove the block from its current location
content = content.replace(settings_block, "")

# The actual HTML in the file around line 232 has this:
# 231:             </div>
# 232:         </div>
# 233: 
# 234:     </div>
# 235: </div>
# Let's insert settings_block after page-logs

target_insertion = """            </div>
        </div>

    </div>
</div>"""

replacement_insertion = """            </div>
        </div>

""" + settings_block + """
    </div>
</div>"""

# Replace the target
if target_insertion in content:
    content = content.replace(target_insertion, replacement_insertion)
else:
    # Try another matching strategy
    target = '</div>\n</div>'
    if target in content:
        # replace the last occurrence
        parts = content.rsplit(target, 1)
        content = parts[0] + settings_block + '\n' + target + parts[1]

with open("frontend/index.html", "w", encoding="utf-8") as f:
    f.write(content)
