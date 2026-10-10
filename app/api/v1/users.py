from fastapi import APIRouter, Depends
from app import models
from app.security import get_current_user
from app.schemas.employee import EmployeeProfileResponse
from app.schemas.common import StandardResponse

router = APIRouter(prefix="/api/v1/users", tags=["Users"])
legacy_router = APIRouter(prefix="/api/v1", tags=["Users"])


@router.get("/me", response_model=StandardResponse[EmployeeProfileResponse])
@legacy_router.get("/me", response_model=StandardResponse[EmployeeProfileResponse], include_in_schema=False)
def get_user_profile(current_user: models.Employee = Depends(get_current_user)):
    """
    API Định danh người dùng chuẩn hóa (Bước 5.4 - Unified Experience).
    - Trả về thông tin đầy đủ gồm avatar, full_name, role để hiển thị đồng nhất trên Header.
    - Đảm bảo định dạng StandardResponse[EmployeeProfileResponse].
    """
    profile_data = EmployeeProfileResponse.model_validate(current_user, from_attributes=True)
    return StandardResponse(
        success=True,
        message="Lấy thông tin định danh thành công",
        data=profile_data
    )
