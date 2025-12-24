"""
Test SuprSend API connection and credentials

This script verifies that:
1. SuprSend credentials are configured correctly
2. The client can be initialized
3. A test email can be sent (optional)
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_suprsend_credentials():
    """Test if SuprSend credentials are configured"""
    print("=" * 60)
    print("SuprSend Connection Test")
    print("=" * 60)
    print()

    # Check environment variables
    workspace_key = os.getenv("SUPRSEND_WORKSPACE_KEY")
    workspace_secret = os.getenv("SUPRSEND_WORKSPACE_SECRET")
    is_staging = os.getenv("IS_STAGING_ENV", "false").lower() == "true"

    print("1. Checking environment variables...")
    if workspace_key:
        print(f"   ✓ SUPRSEND_WORKSPACE_KEY: {workspace_key[:10]}...")
    else:
        print("   ✗ SUPRSEND_WORKSPACE_KEY: Not set")
        return False

    if workspace_secret:
        print(f"   ✓ SUPRSEND_WORKSPACE_SECRET: {workspace_secret[:10]}...")
    else:
        print("   ✗ SUPRSEND_WORKSPACE_SECRET: Not set")
        return False

    print(f"   ✓ IS_STAGING_ENV: {is_staging}")
    print()

    # Test SuprSend client initialization
    print("2. Initializing SuprSend client...")
    try:
        from app.infra.external.suprsend_client import SuprSendClient

        client = SuprSendClient(
            workspace_key=workspace_key,
            workspace_secret=workspace_secret,
            is_staging=is_staging
        )
        print("   ✓ SuprSend client initialized successfully")
        print()
    except ImportError as e:
        print(f"   ✗ Import error: {e}")
        print("   Run: pip install suprsend")
        return False
    except Exception as e:
        print(f"   ✗ Initialization failed: {e}")
        return False

    # Test user creation (lightweight test)
    print("3. Testing user creation API...")
    try:
        test_user_id = "test_connection_user_123"
        test_email = "test@example.com"

        response = client.create_user(
            distinct_id=test_user_id,
            email=test_email,
            name="Test Connection User"
        )

        print(f"   ✓ User creation API call successful")
        print(f"   Response: {response}")
        print()
    except Exception as e:
        print(f"   ✗ User creation failed: {e}")
        print()

    # Optional: Test email sending
    print("4. Testing email workflow (optional)...")
    print("   Note: This will only work if you have a 'transactional_email' workflow")
    print("   configured in your SuprSend dashboard.")
    print()

    send_test_email = input("   Do you want to send a test email? (y/n): ").lower().strip()

    if send_test_email == 'y':
        test_recipient = input("   Enter recipient email: ").strip()

        if test_recipient:
            try:
                response = client.send_transactional_email(
                    to_email=test_recipient,
                    subject="SuprSend Connection Test",
                    body="<h1>Success!</h1><p>Your SuprSend integration is working correctly.</p>",
                    from_name="Creator Agents Platform",
                    html=True
                )

                print(f"   ✓ Email sent successfully!")
                print(f"   Message ID: {response.get('message_id')}")
                print(f"   Status: {response.get('status')}")
                print()
            except Exception as e:
                print(f"   ✗ Email sending failed: {e}")
                print()
                print("   This is expected if you haven't configured a 'transactional_email'")
                print("   workflow in your SuprSend dashboard yet.")
                print()

    print("=" * 60)
    print("✓ Connection test completed!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Configure email workflows in SuprSend dashboard:")
    print("   https://app.suprsend.com/")
    print("2. Create a 'transactional_email' workflow for the SendEmailTool")
    print("3. Test the SendEmailTool in your agents")
    print()

    return True


if __name__ == "__main__":
    try:
        success = test_suprsend_credentials()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
