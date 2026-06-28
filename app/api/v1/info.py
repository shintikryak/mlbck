from fastapi import APIRouter

router = APIRouter()


@router.get(
    "",
    summary="Get project information",
    description="Returns implemented Mailback MVP features for demonstration purposes.",
)
async def get_project_info():
    return {
        "name": "Mailback",
        "version": "1.0.0",
        "type": "Backend platform for mailbox aggregation",
        "features": [
            "Unified REST API",
            "OpenAPI and Swagger UI",
            "Fake mailbox connector",
            "Real IMAP synchronization",
            "Real SMTP sending",
            "Incoming attachments synchronization",
            "Outgoing attachments sending",
            "Attachment storage in MinIO",
            "PostgreSQL metadata storage",
            "Full-text message search",
            "Message pagination",
            "Local read/star/delete/restore actions",
            "Encrypted mailbox credentials",
            "Idempotent synchronization",
            "Integration tests with pytest",
        ],
    }