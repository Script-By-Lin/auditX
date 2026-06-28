"""Run demo: python -m auditx"""

from auditx.core import AuditAction, BusinessModule
from auditx import RequestContext, audit


def main() -> None:
    RequestContext.set(
        user="admin",
        user_role="manager",
        company_id="CO-001",
        branch_id="BR-YGN",
        ip="192.168.1.10",
    )

    print("auditX demo — writing logs to ./logs/\n")

    audit.log_security("User login successful", action=AuditAction.LOGIN, user="admin", success=True)

    audit.log_transaction(
        "Sales invoice posted",
        module=BusinessModule.SALES,
        action=AuditAction.POST,
        reference_no="SI-2026-0042",
        amount=1_250_000,
        entity_type="sales_invoice",
        entity_id="inv-42",
        party="Golden Trading Co.",
    )

    audit.log_inventory(
        "Stock issued for sales order",
        action=AuditAction.TRANSFER,
        product_id="SKU-1001",
        product_name="LED Panel 24W",
        quantity=50,
        warehouse_id="WH-MAIN",
        reference_no="SI-2026-0042",
    )

    audit.log_service(
        "Service job completed",
        action=AuditAction.UPDATE,
        job_id="SVC-889",
        customer_id="CUST-220",
        technician="U Kyaw",
        service_type="AC Maintenance",
        status_label="completed",
        amount=85_000,
    )

    audit.log_change(
        "Customer credit limit updated",
        module=BusinessModule.CRM,
        action=AuditAction.UPDATE,
        entity_type="customer",
        entity_id="CUST-220",
        old_values={"credit_limit": 500_000},
        new_values={"credit_limit": 1_000_000},
    )

    for _ in range(7):
        audit.log_security(
            "Failed login attempt",
            action=AuditAction.LOGIN,
            user="attacker",
            ip="192.168.1.50",
            success=False,
        )

    print("\nDone. Check logs/audit.jsonl and logs/security.jsonl")


if __name__ == "__main__":
    main()
