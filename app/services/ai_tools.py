import json
import time
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app import models
from app.agent import enforcer, Subject, Resource
from app.schemas_ai import (
    RecentOrderForAI,
    RefundContextForAI,
    CreateRefundArgs,
    ApproveRefundArgs,
    RejectRefundArgs
)
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class SecureAITools:
    """
    Tập hợp Data Tools có nhận thức bảo mật (Context-Aware Tools).
    Bắt buộc nhận vào db Session và current_user (Employee) để thực thi kiểm soát truy cập (Casbin)
    và ghi vết kiểm toán (AIAuditLog).
    """
    def __init__(self, db: Session, current_user: models.Employee, session_id: Optional[str] = None):
        if db is None or current_user is None:
            raise ValueError("SecureAITools bắt buộc phải được khởi tạo với db Session và current_user!")
        self.db = db
        self.current_user = current_user
        self.session_id = session_id

    def _record_tool_audit(
        self,
        tool_name: str,
        input_context: Any,
        output_result: Any,
        action_status: str,
        execution_time: float,
        context_snapshot: Optional[Any] = None
    ):
        """Hàm dùng chung để ghi bản ghi AIAuditLog với đầy đủ metadata bảo mật, context_snapshot và hiệu năng."""
        try:
            ctx = dict(input_context) if isinstance(input_context, dict) else {"raw": str(input_context)}
            if "tool_name" not in ctx:
                ctx["tool_name"] = tool_name
            snapshot = context_snapshot if context_snapshot is not None else ctx
            audit = models.AIAuditLog(
                user_id=self.current_user.id,
                ai_session_id=self.session_id,
                tool_name=tool_name,
                action_type="tool_call",
                action_status=action_status,
                input_context=ctx,
                output_result=output_result if isinstance(output_result, (dict, list)) else {"result": str(output_result)},
                context_snapshot=snapshot if isinstance(snapshot, (dict, list)) else {"snapshot": str(snapshot)},
                execution_time=round(execution_time, 4)
            )
            self.db.add(audit)
            self.db.commit()
        except Exception as e:
            logger.error(f"Lỗi ghi AIAuditLog cho tool {tool_name}: {e}")
            self.db.rollback()

    def get_order(self, order_id: int) -> str:
        """
        Tra cứu thông tin chi tiết đơn hàng theo order_id.
        Kiểm tra quyền hạn Casbin của nhân viên và khử định danh dữ liệu nhạy cảm.
        """
        start_time = time.time()
        # Bước 1: Check quyền Casbin của current_user đối với resource order
        sub = Subject(self.current_user.username, self.current_user.role)
        enforcer.load_policy()
        has_perm = enforcer.enforce(sub, Resource("order"), "read")
        if not has_perm:
            logger.warning(f"Người dùng {self.current_user.username} không có quyền đọc order #{order_id}")
            err_msg = "Lỗi: Bạn không có quyền truy cập đơn hàng này."
            self._record_tool_audit(
                tool_name="get_order",
                input_context={"order_id": order_id, "resource_id": order_id},
                output_result={"error": err_msg},
                action_status="FAILED",
                execution_time=time.time() - start_time
            )
            return err_msg

        # Bước 2: Gọi DB lấy dữ liệu và ép kiểu qua Pydantic Schema để làm sạch PII
        order = self.db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            not_found_msg = f"Lỗi: Không tìm thấy đơn hàng #{order_id}."
            self._record_tool_audit(
                tool_name="get_order",
                input_context={"order_id": order_id, "resource_id": order_id},
                output_result={"error": not_found_msg},
                action_status="FAILED",
                execution_time=time.time() - start_time
            )
            return not_found_msg

        cleaned_order = RecentOrderForAI(
            order_id=order.id,
            product_name=order.product_name,
            price=float(order.price) if order.price is not None else 0.0,
            order_date=order.order_date,
            status=order.status or "UNKNOWN"
        )
        order_dict = cleaned_order.model_dump(mode="json")

        # Bước 3: Ghi AIAuditLog
        self._record_tool_audit(
            tool_name="get_order",
            input_context={"order_id": order_id, "resource_id": order_id},
            output_result=order_dict,
            action_status="SUCCESS",
            execution_time=time.time() - start_time,
            context_snapshot={"order_data": order_dict}
        )

        return json.dumps(order_dict, ensure_ascii=False)

    def get_refund(self, refund_id: int) -> str:
        """
        Tra cứu thông tin chi tiết yêu cầu hoàn tiền theo refund_id.
        Kiểm tra quyền hạn Casbin của nhân viên và khử định danh dữ liệu nhạy cảm.
        """
        start_time = time.time()
        # Bước 1: Check quyền Casbin của current_user đối với resource refund
        sub = Subject(self.current_user.username, self.current_user.role)
        enforcer.load_policy()
        has_perm = enforcer.enforce(sub, Resource("refund"), "read")
        if not has_perm:
            logger.warning(f"Người dùng {self.current_user.username} không có quyền đọc refund #{refund_id}")
            err_msg = "Lỗi: Bạn không có quyền truy cập yêu cầu hoàn tiền này."
            self._record_tool_audit(
                tool_name="get_refund",
                input_context={"refund_id": refund_id, "resource_id": refund_id},
                output_result={"error": err_msg},
                action_status="FAILED",
                execution_time=time.time() - start_time
            )
            return err_msg

        # Bước 2: Gọi DB lấy dữ liệu và ép kiểu qua Pydantic Schema để làm sạch PII
        refund = self.db.query(models.RefundRequest).filter(models.RefundRequest.id == refund_id).first()
        if not refund:
            not_found_msg = f"Lỗi: Không tìm thấy yêu cầu hoàn tiền #{refund_id}."
            self._record_tool_audit(
                tool_name="get_refund",
                input_context={"refund_id": refund_id, "resource_id": refund_id},
                output_result={"error": not_found_msg},
                action_status="FAILED",
                execution_time=time.time() - start_time
            )
            return not_found_msg

        status_val = refund.status.value if hasattr(refund.status, "value") else str(refund.status)
        amount_val = refund.amount
        if amount_val is None and refund.order:
            amount_val = refund.order.price

        cleaned_refund = RefundContextForAI(
            refund_id=refund.id,
            order_id=refund.order_id,
            amount=amount_val,
            status=status_val,
            reason=refund.reason,
            created_at=refund.created_at
        )
        refund_dict = cleaned_refund.model_dump(mode="json")

        # Bước 3: Ghi AIAuditLog
        self._record_tool_audit(
            tool_name="get_refund",
            input_context={"refund_id": refund_id, "resource_id": refund_id},
            output_result=refund_dict,
            action_status="SUCCESS",
            execution_time=time.time() - start_time,
            context_snapshot={"refund_data": refund_dict}
        )

        return json.dumps(refund_dict, ensure_ascii=False)

    def search_policy(self, query: str) -> str:
        """
        Tra cứu các quy định, chính sách và cẩm nang vận hành hoàn tiền từ kho tri thức (RAG).
        """
        start_time = time.time()
        rag_service = RAGService()
        try:
            hits = rag_service.search_knowledge(query=query, top_k=3)
        except Exception as e:
            logger.error(f"Lỗi khi tìm kiếm chính sách RAG: {e}")
            hits = []

        if not hits:
            result_str = "Không tìm thấy tài liệu quy định nào phù hợp với từ khóa tìm kiếm."
        else:
            formatted_chunks = []
            for hit in hits:
                meta = hit.get("metadata", {})
                title = meta.get("title", meta.get("filename", "Quy định"))
                filename = meta.get("filename", "")
                header = meta.get("header", "")
                content = hit.get("content", "")
                formatted_chunks.append(f"[{title} ({filename}) | Phần: {header}]:\n{content}")
            result_str = "\n\n".join(formatted_chunks)

        self._record_tool_audit(
            tool_name="search_policy",
            input_context={"query": query},
            output_result={
                "hits_count": len(hits),
                "sources": [h.get("metadata", {}).get("filename") for h in hits]
            },
            action_status="SUCCESS",
            execution_time=time.time() - start_time,
            context_snapshot={"query": query, "retrieved_policy_chunks": hits}
        )

        return result_str

    # ======================= WRITE-TOOLS (BƯỚC 4.5) =======================

    def create_refund_request(self, args: CreateRefundArgs) -> str:
        """
        Tạo yêu cầu hoàn tiền mới cho đơn hàng (Write-Tool).
        Được bọc lót Pydantic schema CreateRefundArgs và xử lý lỗi không dùng raise.
        """
        start_time = time.time()
        try:
            if isinstance(args, dict):
                args = CreateRefundArgs(**args)
            elif not isinstance(args, CreateRefundArgs):
                return "Thất bại: Tham số đầu vào không đúng định dạng CreateRefundArgs."

            input_dict = args.model_dump(mode="json")

            # 1. Kiểm tra phân quyền Casbin
            sub = Subject(self.current_user.username, self.current_user.role)
            enforcer.load_policy()
            has_perm = enforcer.enforce(sub, Resource("refund"), "create")
            if not has_perm:
                err_msg = "Thất bại: Bạn không có quyền tạo yêu cầu hoàn tiền."
                self._record_tool_audit(
                    tool_name="create_refund_request",
                    input_context=input_dict,
                    output_result={"error": err_msg},
                    action_status="FAILED",
                    execution_time=time.time() - start_time
                )
                return err_msg

            # 2. Kiểm tra nghiệp vụ: Đơn hàng có tồn tại không
            order = self.db.query(models.Order).filter(models.Order.id == args.order_id).first()
            if not order:
                err_msg = f"Thất bại: Không tìm thấy đơn hàng #{args.order_id}."
                self._record_tool_audit(
                    tool_name="create_refund_request",
                    input_context=input_dict,
                    output_result={"error": err_msg},
                    action_status="FAILED",
                    execution_time=time.time() - start_time
                )
                return err_msg

            # 3. Kiểm tra nghiệp vụ: Trùng lặp yêu cầu đang chờ xử lý
            existing = self.db.query(models.RefundRequest).filter(
                models.RefundRequest.order_id == args.order_id,
                models.RefundRequest.status.in_([models.RefundState.PENDING, models.RefundState.PROCESSING])
            ).first()
            if existing:
                err_msg = f"Thất bại: Đơn hàng #{args.order_id} đã có yêu cầu hoàn tiền #{existing.id} đang chờ xử lý."
                self._record_tool_audit(
                    tool_name="create_refund_request",
                    input_context=input_dict,
                    output_result={"error": err_msg},
                    action_status="FAILED",
                    execution_time=time.time() - start_time
                )
                return err_msg

            refund_amount = args.amount if args.amount is not None else order.price
            new_refund = models.RefundRequest(
                order_id=args.order_id,
                employee_id=self.current_user.id,
                reason=args.reason,
                amount=refund_amount,
                status=models.RefundState.PENDING
            )
            self.db.add(new_refund)
            self.db.commit()
            self.db.refresh(new_refund)

            success_msg = f"Thành công: Đã tạo yêu cầu hoàn tiền #{new_refund.id} cho đơn hàng #{args.order_id}."
            self._record_tool_audit(
                tool_name="create_refund_request",
                input_context=input_dict,
                output_result={"message": success_msg, "refund_id": new_refund.id},
                action_status="SUCCESS",
                execution_time=time.time() - start_time,
                context_snapshot={"order_id": args.order_id, "reason": args.reason, "amount": refund_amount, "new_refund_id": new_refund.id}
            )
            return success_msg

        except Exception as e:
            self.db.rollback()
            logger.error(f"Lỗi ngoại lệ khi tạo yêu cầu hoàn tiền: {e}")
            err_msg = f"Thất bại: Lỗi hệ thống khi tạo yêu cầu hoàn tiền ({str(e)})."
            self._record_tool_audit(
                tool_name="create_refund_request",
                input_context=args.model_dump(mode="json") if isinstance(args, CreateRefundArgs) else {"raw": str(args)},
                output_result={"error": err_msg},
                action_status="FAILED",
                execution_time=time.time() - start_time,
                context_snapshot={"error": str(e)}
            )
            return err_msg

    def approve_refund(self, args: ApproveRefundArgs) -> str:
        """
        Phê duyệt yêu cầu hoàn tiền (Write-Tool / Hành động nhạy cảm).
        Kiểm tra quyền hạn Casbin (admin, manager), trạng thái hợp lệ, cập nhật trạng thái đơn hàng.
        """
        start_time = time.time()
        try:
            if isinstance(args, dict):
                args = ApproveRefundArgs(**args)
            elif not isinstance(args, ApproveRefundArgs):
                return "Thất bại: Tham số đầu vào không đúng định dạng ApproveRefundArgs."

            input_dict = args.model_dump(mode="json")

            # 1. Kiểm tra quyền Casbin (approve)
            sub = Subject(self.current_user.username, self.current_user.role)
            enforcer.load_policy()
            has_perm = enforcer.enforce(sub, Resource("refund"), "approve")
            if not has_perm:
                err_msg = "Thất bại: Bạn không có quyền phê duyệt yêu cầu hoàn tiền."
                self._record_tool_audit(
                    tool_name="approve_refund",
                    input_context=input_dict,
                    output_result={"error": err_msg},
                    action_status="FAILED",
                    execution_time=time.time() - start_time,
                    context_snapshot={"denied_user": self.current_user.username, "refund_id": args.refund_id}
                )
                return err_msg

            # 2. Tìm yêu cầu hoàn tiền
            refund = self.db.query(models.RefundRequest).filter(models.RefundRequest.id == args.refund_id).first()
            if not refund:
                err_msg = f"Thất bại: Không tìm thấy yêu cầu hoàn tiền #{args.refund_id}."
                self._record_tool_audit(
                    tool_name="approve_refund",
                    input_context=input_dict,
                    output_result={"error": err_msg},
                    action_status="FAILED",
                    execution_time=time.time() - start_time
                )
                return err_msg

            # 3. Kiểm tra Business Rules (Trạng thái phải là PENDING hoặc PROCESSING)
            current_status = refund.status.value if hasattr(refund.status, "value") else str(refund.status)
            if current_status not in ["PENDING", "PROCESSING"]:
                err_msg = f"Thất bại: Yêu cầu hoàn tiền #{args.refund_id} đang ở trạng thái {current_status}, không thể phê duyệt."
                self._record_tool_audit(
                    tool_name="approve_refund",
                    input_context=input_dict,
                    output_result={"error": err_msg},
                    action_status="FAILED",
                    execution_time=time.time() - start_time,
                    context_snapshot={"current_status": current_status, "refund_id": args.refund_id}
                )
                return err_msg

            # 4. Thực thi cập nhật
            refund.status = models.RefundState.APPROVED
            if refund.order:
                refund.order.status = "REFUNDED"
            if args.notes:
                refund.notes = args.notes

            # Ghi vết vào audit_logs chung
            audit_entry = models.AuditLog(
                order_id=refund.order_id,
                employee_username=self.current_user.username,
                decision="ALLOW",
                reason=args.notes or "Phê duyệt thông qua AI Assistant Human-in-the-loop"
            )
            self.db.add(audit_entry)
            self.db.commit()

            success_msg = "Thành công: Đã cập nhật trạng thái."
            self._record_tool_audit(
                tool_name="approve_refund",
                input_context=input_dict,
                output_result={"message": success_msg, "refund_id": args.refund_id, "new_status": "APPROVED"},
                action_status="SUCCESS",
                execution_time=time.time() - start_time,
                context_snapshot={"refund_id": args.refund_id, "order_id": refund.order_id, "new_status": "APPROVED", "notes": args.notes}
            )
            return success_msg

        except Exception as e:
            self.db.rollback()
            logger.error(f"Lỗi ngoại lệ khi phê duyệt hoàn tiền: {e}")
            err_msg = f"Thất bại: Lỗi hệ thống khi phê duyệt ({str(e)})."
            self._record_tool_audit(
                tool_name="approve_refund",
                input_context=args.model_dump(mode="json") if isinstance(args, ApproveRefundArgs) else {"raw": str(args)},
                output_result={"error": err_msg},
                action_status="FAILED",
                execution_time=time.time() - start_time,
                context_snapshot={"error": str(e)}
            )
            return err_msg

    def reject_refund(self, args: RejectRefundArgs) -> str:
        """
        Từ chối yêu cầu hoàn tiền (Write-Tool / Hành động nhạy cảm).
        Kiểm tra quyền hạn Casbin (admin, manager), trạng thái hợp lệ.
        """
        start_time = time.time()
        try:
            if isinstance(args, dict):
                args = RejectRefundArgs(**args)
            elif not isinstance(args, RejectRefundArgs):
                return "Thất bại: Tham số đầu vào không đúng định dạng RejectRefundArgs."

            input_dict = args.model_dump(mode="json")

            # 1. Kiểm tra quyền Casbin (reject)
            sub = Subject(self.current_user.username, self.current_user.role)
            enforcer.load_policy()
            has_perm = enforcer.enforce(sub, Resource("refund"), "reject")
            if not has_perm:
                err_msg = "Thất bại: Bạn không có quyền từ chối yêu cầu hoàn tiền."
                self._record_tool_audit(
                    tool_name="reject_refund",
                    input_context=input_dict,
                    output_result={"error": err_msg},
                    action_status="FAILED",
                    execution_time=time.time() - start_time,
                    context_snapshot={"denied_user": self.current_user.username, "refund_id": args.refund_id}
                )
                return err_msg

            # 2. Tìm yêu cầu hoàn tiền
            refund = self.db.query(models.RefundRequest).filter(models.RefundRequest.id == args.refund_id).first()
            if not refund:
                err_msg = f"Thất bại: Không tìm thấy yêu cầu hoàn tiền #{args.refund_id}."
                self._record_tool_audit(
                    tool_name="reject_refund",
                    input_context=input_dict,
                    output_result={"error": err_msg},
                    action_status="FAILED",
                    execution_time=time.time() - start_time
                )
                return err_msg

            # 3. Kiểm tra trạng thái
            current_status = refund.status.value if hasattr(refund.status, "value") else str(refund.status)
            if current_status not in ["PENDING", "PROCESSING"]:
                err_msg = f"Thất bại: Yêu cầu hoàn tiền #{args.refund_id} đang ở trạng thái {current_status}, không thể từ chối."
                self._record_tool_audit(
                    tool_name="reject_refund",
                    input_context=input_dict,
                    output_result={"error": err_msg},
                    action_status="FAILED",
                    execution_time=time.time() - start_time,
                    context_snapshot={"current_status": current_status, "refund_id": args.refund_id}
                )
                return err_msg

            # 4. Thực thi cập nhật
            refund.status = models.RefundState.REJECTED
            if args.notes:
                refund.notes = args.notes

            audit_entry = models.AuditLog(
                order_id=refund.order_id,
                employee_username=self.current_user.username,
                decision="DENY",
                reason=args.notes or "Từ chối thông qua AI Assistant Human-in-the-loop"
            )
            self.db.add(audit_entry)
            self.db.commit()

            success_msg = "Thành công: Đã cập nhật trạng thái."
            self._record_tool_audit(
                tool_name="reject_refund",
                input_context=input_dict,
                output_result={"message": success_msg, "refund_id": args.refund_id, "new_status": "REJECTED"},
                action_status="SUCCESS",
                execution_time=time.time() - start_time,
                context_snapshot={"refund_id": args.refund_id, "order_id": refund.order_id, "new_status": "REJECTED", "notes": args.notes}
            )
            return success_msg

        except Exception as e:
            self.db.rollback()
            logger.error(f"Lỗi ngoại lệ khi từ chối hoàn tiền: {e}")
            err_msg = f"Thất bại: Lỗi hệ thống khi từ chối ({str(e)})."
            self._record_tool_audit(
                tool_name="reject_refund",
                input_context=args.model_dump(mode="json") if isinstance(args, RejectRefundArgs) else {"raw": str(args)},
                output_result={"error": err_msg},
                action_status="FAILED",
                execution_time=time.time() - start_time
            )
            return err_msg
