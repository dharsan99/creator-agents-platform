"""
Send a test email via SuprSend to verify end-to-end functionality
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def send_test_email():
    """Send a test email via SuprSend"""
    print("=" * 60)
    print("SuprSend End-to-End Email Test")
    print("=" * 60)
    print()

    # Get credentials
    workspace_key = os.getenv("SUPRSEND_WORKSPACE_KEY")
    workspace_secret = os.getenv("SUPRSEND_WORKSPACE_SECRET")
    is_staging = os.getenv("IS_STAGING_ENV", "false").lower() == "true"

    # Initialize client
    print("1. Initializing SuprSend client...")
    try:
        from app.infra.external.suprsend_client import SuprSendClient

        client = SuprSendClient(
            workspace_key=workspace_key,
            workspace_secret=workspace_secret,
            is_staging=is_staging
        )
        print("   ✓ Client initialized")
        print()
    except Exception as e:
        print(f"   ✗ Failed to initialize client: {e}")
        return False

    # Test recipient
    recipient_email = "dharsantkumar1999@gmail.com"

    print(f"2. Sending test email to: {recipient_email}")
    print()

    # Create test email content
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    subject = "🎉 SuprSend Integration Test - Creator Agents Platform"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }}
            .content {{
                background: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 10px 10px;
            }}
            .success {{
                background: #d4edda;
                border: 1px solid #c3e6cb;
                color: #155724;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .info-box {{
                background: white;
                padding: 20px;
                border-radius: 5px;
                margin: 20px 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .footer {{
                text-align: center;
                color: #666;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
            }}
            code {{
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: monospace;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎉 Success!</h1>
            <p>Your SuprSend integration is working perfectly</p>
        </div>

        <div class="content">
            <div class="success">
                <strong>✓ Email Delivery Confirmed</strong><br>
                Your Creator Agents Platform is now connected to SuprSend!
            </div>

            <div class="info-box">
                <h2>✨ What This Means</h2>
                <p>Your platform can now:</p>
                <ul>
                    <li>📧 Send transactional emails to users</li>
                    <li>💬 Send WhatsApp messages (if configured)</li>
                    <li>📱 Send SMS notifications (if configured)</li>
                    <li>🔔 Trigger multi-channel workflows</li>
                </ul>
            </div>

            <div class="info-box">
                <h2>📊 Test Details</h2>
                <p><strong>Timestamp:</strong> {timestamp}</p>
                <p><strong>Environment:</strong> {'Staging' if is_staging else 'Production'}</p>
                <p><strong>Workspace:</strong> {workspace_key[:10]}...</p>
                <p><strong>Recipient:</strong> {recipient_email}</p>
            </div>

            <div class="info-box">
                <h2>🚀 Next Steps</h2>
                <ol>
                    <li>Configure your SuprSend workflows in the <a href="https://app.suprsend.com/">SuprSend Dashboard</a></li>
                    <li>Set up email templates for your agents</li>
                    <li>Test the <code>SendEmailTool</code> in your agent workflows</li>
                    <li>Configure WhatsApp and SMS channels if needed</li>
                </ol>
            </div>

            <div class="footer">
                <p>
                    <strong>Creator Agents Platform</strong><br>
                    Powered by SuprSend
                </p>
                <p style="font-size: 12px; color: #999;">
                    This is an automated test email from your Creator Agents Platform
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    # Send email
    try:
        print("   → Calling SuprSend API...")
        response = client.send_transactional_email(
            to_email=recipient_email,
            subject=subject,
            body=html_body,
            from_name="Creator Agents Platform",
            from_email="noreply@creatoragents.ai",
            html=True
        )

        print("   ✓ Email sent successfully!")
        print()
        print("   Response Details:")
        print(f"   - Success: {response.get('success')}")
        print(f"   - Message ID: {response.get('message_id')}")
        print(f"   - Status: {response.get('status')}")
        print(f"   - Sent At: {response.get('sent_at')}")
        print()
        print("=" * 60)
        print("✓ End-to-End Test Completed Successfully!")
        print("=" * 60)
        print()
        print("📧 Check your inbox at: dharsantkumar1999@gmail.com")
        print()
        print("⚠️  Note: If you don't see the email:")
        print("   1. Check your spam/junk folder")
        print("   2. Verify email workflows are configured in SuprSend")
        print("   3. Check SuprSend dashboard for delivery logs")
        print()

        return True

    except Exception as e:
        print(f"   ✗ Failed to send email: {e}")
        print()
        print("   Common issues:")
        print("   1. Email workflow 'transactional_email' not configured in SuprSend")
        print("   2. Email channel not verified in SuprSend dashboard")
        print("   3. Workspace credentials invalid")
        print()
        print("   Visit https://app.suprsend.com/ to configure workflows")
        return False


if __name__ == "__main__":
    try:
        success = send_test_email()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
