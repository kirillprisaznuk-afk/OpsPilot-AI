"""Check the restricted workflow connection and policy without exposing credentials."""

from app.workflow import policy
from app.workflow.common import transaction


def main():
    with transaction("read") as db:
        policy.current(db)
    print("Workflow: restricted database connection ready")


if __name__ == "__main__":
    main()
