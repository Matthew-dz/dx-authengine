import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import get_current_user
from app.services.ai_data_service import AIDataService
from app.services.ai_service import AIService
from app.schemas_ai import (
    AIRecommendationResponse,
    RefundContextForAI,
    AIChatRequest,
    ExecutePendingActionRequest,
    CreateRefundArgs,
    ApproveRefundArgs,
    RejectRefundArgs
)
from app.services.ai_tools import SecureAITools
from app.agent import enforcer, Subject, Resource
from app.schemas.common import StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.post("/analyze-refund/{refund_id}", response_model=StandardResponse[AIRecommendationResponse])
def analyze_refund(
    refund_id: int,
    current_user: models.Employee = Depends(get_current_user),
    ai_data_service: AIDataService = Depends(),
    ai_service: AIService = Depends()
):
    """
    API phân tích yêu cầu hoàn tiền bằng AI Assistant (Bước 4.1 & 5.1).
    - Sử dụng Depends(get_current_user) để kiểm tra quyền nhân viên.
    - Gọi AIDataService để lấy context an toàn (đã khử định danh PII).
    - Truyền context vào ai_service.analyze_refund_request.
    - Tự động ghi nhật ký vào bảng AIAuditLog.
    - Trả về kết quả bọc StandardResponse theo chuẩn Unified API.
    """
    context_data = ai_data_service.get_refund_context(refund_id)
    refund_context = RefundContextForAI(**context_data)

    recommendation = ai_service.analyze_refund_request(
        context=refund_context,
        user_id=current_user.id
    )

    return StandardResponse(
        success=True,
        message="Phân tích yêu cầu hoàn tiền thành công",
        data=recommendation
    )


@router.post("/analyze-refund-rag/{refund_id}", response_model=StandardResponse[AIRecommendationResponse])
def analyze_refund_rag(
    refund_id: int,
    current_user: models.Employee = Depends(get_current_user),
    ai_data_service: AIDataService = Depends(),
    ai_service: AIService = Depends()
):
    """
    API phân tích yêu cầu hoàn tiền kết hợp RAG (Retrieval-Augmented Generation).
    - Kiểm tra quyền nhân viên: Depends(get_current_user).
    - Lấy Context an toàn đã khử định danh: AIDataService.
    - Truy vấn tri thức liên quan từ ChromaDB: RAGService.search_knowledge.
    - Trả về khuyến nghị có trích dẫn citations từ tài liệu.
    """
    context_data = ai_data_service.get_refund_context(refund_id)
    refund_context = RefundContextForAI(**context_data)

    recommendation = ai_service.analyze_with_rag(
        context=refund_context,
        user_id=current_user.id
    )

    return StandardResponse(
        success=True,
        message="Phân tích yêu cầu hoàn tiền với RAG thành công",
        data=recommendation
    )


@router.post("/chat", response_model=StandardResponse[AIRecommendationResponse])
def chat_with_agentic_ai(
    req: AIChatRequest,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_service: AIService = Depends()
):
    """
    API trò chuyện nghiệp vụ với Agentic AI Assistant (Bước 4.3 & 4.5).
    - Tự động nhận diện ngữ cảnh người dùng và thực thi Function Calling (SecureAITools).
    - Tra cứu dữ liệu (get_order, get_refund) và chính sách RAG (search_policy).
    - Bảo vệ ngắt mạch (Circuit Breaker) chống lặp vô hạn (tối đa 3 tool calls).
    - Cơ chế Human-in-the-loop: Trả về pending_action khi người dùng yêu cầu phê duyệt/từ chối.
    """
    recommendation = ai_service.chat_with_ai(
        user_query=req.query,
        current_user=current_user,
        db=db,
        session_id=req.session_id
    )
    return StandardResponse(
        success=True,
        message="Phản hồi từ AI Assistant",
        data=recommendation
    )


@router.post("/execute-pending-action", response_model=StandardResponse[dict])
def execute_pending_action(
    req: ExecutePendingActionRequest,
    current_user: models.Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    API thực thi trực tiếp hành động chờ xác nhận (Human-in-the-loop).
    - Được gọi khi người dùng bấm nút 'Xác nhận' trên giao diện Frontend.
    - Thực thi trực tiếp dưới quyền của current_user (Casbin Enforced).
    - Không thông qua LLM nhằm đảm bảo tính tất định (deterministic) 100%.
    - Tự động ghi nhận AIAuditLog chi tiết.
    """
    tool_name = req.tool
    params = dict(req.params) if req.params else {}
    if req.action:
        tool_name = req.action.get("tool") or tool_name
        params = {**req.action, **params}

    if req.refund_id is not None:
        params["refund_id"] = req.refund_id
    if req.order_id is not None:
        params["order_id"] = req.order_id
    if req.reason is not None:
        params["reason"] = req.reason
    if req.notes is not None:
        params["notes"] = req.notes

    if not tool_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thiếu tên công cụ cần thực thi (tool)"
        )

    # GIA CỐ HUMAN-IN-THE-LOOP (HITL) - BƯỚC 4.6:
    sub = Subject(current_user.username, current_user.role)
    enforcer.load_policy()

    action_map = {
        "approve_refund": ("approve", "phê duyệt"),
        "reject_refund": ("reject", "từ chối"),
        "create_refund_request": ("create", "tạo")
    }

    if tool_name not in action_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Công cụ '{tool_name}' không được hỗ trợ trong execute-pending-action"
        )

    casbin_act, action_desc = action_map[tool_name]
    has_perm = enforcer.enforce(sub, Resource("refund"), casbin_act)
    if not has_perm:
        logger.warning(f"HITL Casbin Enforcement chặn hành động {tool_name} của user {current_user.username}")
        return StandardResponse(
            success=False,
            message=f"Thất bại: Bạn không có quyền {action_desc} yêu cầu hoàn tiền.",
            data={
                "status": "failed",
                "tool": tool_name,
                "message": f"Thất bại: Bạn không có quyền {action_desc} yêu cầu hoàn tiền.",
                "details": params
            }
        )

    tool_kit = SecureAITools(db=db, current_user=current_user, session_id=req.session_id)

    if tool_name == "approve_refund":
        ref_id = params.get("refund_id")
        if not ref_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu refund_id")
        args = ApproveRefundArgs(refund_id=int(ref_id), notes=params.get("notes"))
        res_str = tool_kit.approve_refund(args)
    elif tool_name == "reject_refund":
        ref_id = params.get("refund_id")
        if not ref_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu refund_id")
        args = RejectRefundArgs(refund_id=int(ref_id), notes=params.get("notes"))
        res_str = tool_kit.reject_refund(args)
    elif tool_name == "create_refund_request":
        ord_id = params.get("order_id")
        if not ord_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu order_id")
        args = CreateRefundArgs(
            order_id=int(ord_id),
            reason=params.get("reason", "Yêu cầu hoàn tiền"),
            amount=params.get("amount")
        )
        res_str = tool_kit.create_refund_request(args)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Công cụ '{tool_name}' không được hỗ trợ trong execute-pending-action"
        )

    is_success = res_str.startswith("Thành công")
    return StandardResponse(
        success=is_success,
        message=res_str,
        data={
            "status": "success" if is_success else "failed",
            "tool": tool_name,
            "message": res_str,
            "details": params
        }
    )
