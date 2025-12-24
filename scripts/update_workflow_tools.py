#!/usr/bin/env python3
"""
Update workflow to include send_email tool in available_tools
"""

import sys
from uuid import UUID
from sqlmodel import Session, select
from app.infra.db.connection import engine
from app.domain.workflow.models import Workflow

def main():
    workflow_id = UUID("21b7b58a-8f2f-4ecf-b524-3e72a1faccd9")

    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)

        if not workflow:
            print(f"❌ Workflow not found: {workflow_id}")
            sys.exit(1)

        print(f"📋 Current available_tools: {workflow.available_tools}")

        # Add send_email if not already present
        if "send_email" not in workflow.available_tools:
            # Create new list to trigger SQLModel change detection
            new_tools = list(workflow.available_tools)
            new_tools.append("send_email")
            workflow.available_tools = new_tools

            session.add(workflow)
            session.commit()
            session.refresh(workflow)
            print(f"✅ Updated available_tools: {workflow.available_tools}")
        else:
            print(f"✅ send_email already in available_tools")

        print(f"\n📊 Workflow Details:")
        print(f"   ID: {workflow.id}")
        print(f"   Purpose: {workflow.purpose}")
        print(f"   Available Tools: {workflow.available_tools}")

if __name__ == "__main__":
    main()
