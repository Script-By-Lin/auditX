"""
Basic auditX usage examples for an ERP trading & service app.

Run after install:
    pip install auditX
    python examples/basic_usage.py
"""

from auditx import (
    AuditAction,
    AuditLogger,
    BusinessModule,
    RequestContext,
    audit,
    configure,
    create_logger,
)


def example_default_singleton() -> None:
    """Use the built-in `audit` singleton (logs go to ./logs/)."""
    RequestContext.set(
        user="admin",
        user_role="manager",
        company_id="CO-001",
        branch_id="BR-YGN",
        ip="10.0.0.5",
    )

    audit.log_security("User logged in", action=AuditAction.LOGIN, user="admin", success=True)

    audit.log_transaction(
        "Purchase order approved",
        module=BusinessModule.PURCHASE,
        action=AuditAction.APPROVE,
        reference_no="PO-2026-0100",
        amount=3_500_000,
        entity_type="purchase_order",
        entity_id="po-100",
        party="Shwe Supply Ltd.",
    )


def example_custom_logger() -> None:
    """Create a dedicated logger for a microservice or tenant."""
    tenant_logger = create_logger(log_dir="logs/tenant-acme", console=False)

    tenant_logger.log(
        "Monthly report exported",
        module=BusinessModule.REPORTING.value,
        action=AuditAction.EXPORT.value,
        user="report_bot",
        metadata={"format": "xlsx", "rows": 1240},
    )


def example_configure_global() -> None:
    """Reconfigure the global singleton once at app startup."""
    configure(log_dir="/var/log/my-erp", console=False)

    audit.info("ERP application started", env="production", version="1.0.0")


def example_field_change_audit() -> None:
    """Track before/after values for compliance."""
    audit.log_change(
        "Product selling price updated",
        module=BusinessModule.INVENTORY,
        action=AuditAction.UPDATE,
        entity_type="product",
        entity_id="SKU-1001",
        reference_no="PRICE-2026-001",
        old_values={"price": 45_000, "currency": "MMK"},
        new_values={"price": 48_000, "currency": "MMK"},
    )


def example_service_workflow() -> None:
    """Service department job lifecycle."""
    audit.log_service(
        "Technician assigned to job",
        action=AuditAction.UPDATE,
        job_id="SVC-1024",
        customer_id="CUST-550",
        technician="Ma Hla",
        service_type="Generator Repair",
        status_label="in_progress",
    )


def example_custom_logging_format() -> None:
    """Demonstrate logging_custom with custom fields and messages."""
    # Using default values from RequestContext
    RequestContext.set(user="manager_user", ip="192.168.1.15")
    audit.logging_custom("Application initialization completed", level="info")

    # Overriding user and method explicitly
    audit.logging_custom(
        "User modified custom system setting",
        level="warning",
        user="sys_admin",
        method="POST"
    )

    # Passing custom keyword arguments
    audit.logging_custom(
        "Tenant status updated",
        level="info",
        user="billing_service",
        isActive="Not at all"
    )


if __name__ == "__main__":
    print("=== auditX basic usage ===\n")
    example_default_singleton()
    example_custom_logger()
    example_field_change_audit()
    example_service_workflow()
    
    print("\n=== Custom Format Logging ===")
    example_custom_logging_format()
    
    print("\nLogs written to ./logs/ — open audit.jsonl to inspect structured entries.")

