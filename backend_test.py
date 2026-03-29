#!/usr/bin/env python3
"""
BuddyBot Backend API Testing Suite - Iteration 3 Auth Focus
Tests authentication system, parent dashboard auth, and public chat access
"""

import requests
import sys
import json
import time
from datetime import datetime

class BuddyBotAPITester:
    def __init__(self, base_url="https://get-restart.preview.emergentagent.com"):
        self.base_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.conversation_id = None
        self.alert_id = None
        self.auth_token = None
        self.user_id = None
        self.child_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None, auth_required=False):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        # Add auth header if required and token available
        if auth_required and self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        if auth_required:
            print(f"   Auth: {'✅ Token provided' if self.auth_token else '❌ No token'}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Non-dict response'}")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error text: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    # ============================================================
    # AUTH TESTS (NEW FOR ITERATION 3)
    # ============================================================
    
    def test_register_parent(self):
        """Test parent registration with auto child profile creation"""
        test_email = f"test_parent_{int(time.time())}@test.com"
        success, response = self.run_test(
            "Parent Registration",
            "POST",
            "auth/register",
            200,
            data={
                "name": "Test Parent",
                "email": test_email,
                "phone": "+1234567890",
                "password": "secure123"
            }
        )
        if success:
            self.auth_token = response.get('token')
            self.user_id = response.get('user_id')
            self.child_id = response.get('child_id')
            print(f"   Created user: {self.user_id}")
            print(f"   Created child: {self.child_id}")
            print(f"   Token received: {'✅' if self.auth_token else '❌'}")
        return success

    def test_login_valid_credentials(self):
        """Test login with valid credentials from test_credentials.md"""
        success, response = self.run_test(
            "Login with Valid Credentials",
            "POST",
            "auth/login",
            200,
            data={
                "email": "parent@test.com",
                "password": "secure123"
            }
        )
        if success:
            self.auth_token = response.get('token')
            self.user_id = response.get('user_id')
            print(f"   User ID: {self.user_id}")
            print(f"   Token received: {'✅' if self.auth_token else '❌'}")
        return success

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials should fail"""
        success, response = self.run_test(
            "Login with Invalid Credentials",
            "POST",
            "auth/login",
            401,
            data={
                "email": "parent@test.com",
                "password": "wrongpassword"
            }
        )
        if success:
            print(f"   ✅ Correctly rejected invalid credentials")
        return success

    def test_auth_me_with_token(self):
        """Test /auth/me with valid token returns user + children"""
        if not self.auth_token:
            print("❌ No auth token available")
            return False
            
        success, response = self.run_test(
            "Auth Me with Token",
            "GET",
            "auth/me",
            200,
            auth_required=True
        )
        if success:
            print(f"   User name: {response.get('name', 'Unknown')}")
            print(f"   User email: {response.get('email', 'Unknown')}")
            children = response.get('children', [])
            print(f"   Children count: {len(children)}")
            if children:
                print(f"   First child: {children[0].get('name', 'Unknown')}")
        return success

    def test_auth_me_without_token(self):
        """Test /auth/me without token returns 401"""
        # Temporarily clear token
        temp_token = self.auth_token
        self.auth_token = None
        
        success, response = self.run_test(
            "Auth Me without Token",
            "GET",
            "auth/me",
            401
        )
        
        # Restore token
        self.auth_token = temp_token
        
        if success:
            print(f"   ✅ Correctly returned 401 without token")
        return success

    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        if not self.auth_token:
            print("❌ No auth token available")
            return False
            
        success, response = self.run_test(
            "Verify Password (Correct)",
            "POST",
            "auth/verify-password",
            200,
            data={"password": "secure123"},
            auth_required=True
        )
        if success:
            verified = response.get('verified', False)
            print(f"   Verified: {'✅' if verified else '❌'}")
        return success

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        if not self.auth_token:
            print("❌ No auth token available")
            return False
            
        success, response = self.run_test(
            "Verify Password (Incorrect)",
            "POST",
            "auth/verify-password",
            401,
            data={"password": "wrongpassword"},
            auth_required=True
        )
        if success:
            print(f"   ✅ Correctly rejected incorrect password")
        return success

    def test_logout(self):
        """Test logout endpoint"""
        success, response = self.run_test(
            "Logout",
            "POST",
            "auth/logout",
            200
        )
        if success:
            print(f"   Status: {response.get('status', 'Unknown')}")
        return success

    # ============================================================
    # PROTECTED ENDPOINT TESTS
    # ============================================================

    def test_parent_dashboard_with_auth(self):
        """Test parent dashboard with auth token"""
        if not self.auth_token:
            print("❌ No auth token available")
            return False
            
        success, response = self.run_test(
            "Parent Dashboard (Authenticated)",
            "GET",
            "parent/dashboard",
            200,
            auth_required=True
        )
        if success:
            stats = response.get('stats', {})
            print(f"   Stats: {stats}")
            recent_alerts = response.get('recent_alerts', [])
            print(f"   Recent alerts: {len(recent_alerts)}")
        return success

    def test_parent_dashboard_without_auth(self):
        """Test parent dashboard without auth token returns 401"""
        # Temporarily clear token
        temp_token = self.auth_token
        self.auth_token = None
        
        success, response = self.run_test(
            "Parent Dashboard (No Auth)",
            "GET",
            "parent/dashboard",
            401
        )
        
        # Restore token
        self.auth_token = temp_token
        
        if success:
            print(f"   ✅ Correctly returned 401 without auth")
        return success

    def test_parent_alerts_with_auth(self):
        """Test parent alerts with auth token"""
        if not self.auth_token:
            print("❌ No auth token available")
            return False
            
        success, response = self.run_test(
            "Parent Alerts (Authenticated)",
            "GET",
            "parent/alerts",
            200,
            auth_required=True
        )
        if success:
            print(f"   Found {len(response)} alerts")
        return success

    def test_parent_alerts_without_auth(self):
        """Test parent alerts without auth token returns 401"""
        # Temporarily clear token
        temp_token = self.auth_token
        self.auth_token = None
        
        success, response = self.run_test(
            "Parent Alerts (No Auth)",
            "GET",
            "parent/alerts",
            401
        )
        
        # Restore token
        self.auth_token = temp_token
        
        if success:
            print(f"   ✅ Correctly returned 401 without auth")
        return success

    # ============================================================
    # PUBLIC ENDPOINT TESTS (Should work without auth)
    # ============================================================

    def test_public_chat_send(self):
        """Test that chat/send works without authentication (public for children)"""
        success, response = self.run_test(
            "Public Chat Send (No Auth Required)",
            "POST",
            "chat/send",
            200,
            data={
                "text": "Hello BuddyBot! This is a public message from a child."
            }
        )
        if success:
            print(f"   ✅ Chat works without authentication")
            print(f"   Bot response: {response.get('bot_message', {}).get('text', 'No response')[:50]}...")
            self.conversation_id = response.get('conversation_id')
        return success

    def test_public_chat_conversations(self):
        """Test that listing conversations works without auth"""
        success, response = self.run_test(
            "Public Chat Conversations (No Auth Required)",
            "GET",
            "chat/conversations",
            200
        )
        if success:
            print(f"   ✅ Conversation listing works without authentication")
            print(f"   Found {len(response)} conversations")
        return success

    def test_create_conversation(self):
        """Test creating a new conversation"""
        success, response = self.run_test(
            "Create Conversation",
            "POST",
            "chat/conversations",
            200,
            data={"title": "Test Chat"}
        )
        if success and 'id' in response:
            self.conversation_id = response['id']
            print(f"   Created conversation: {self.conversation_id}")
        return success

    def test_list_conversations(self):
        """Test listing conversations"""
        success, response = self.run_test(
            "List Conversations",
            "GET",
            "chat/conversations",
            200
        )
        if success:
            print(f"   Found {len(response)} conversations")
        return success

    def test_send_safe_message(self):
        """Test sending a safe message"""
        success, response = self.run_test(
            "Send Safe Message",
            "POST",
            "chat/send",
            200,
            data={
                "conversation_id": self.conversation_id,
                "text": "Hello BuddyBot! Tell me about cats."
            }
        )
        if success:
            print(f"   Bot response: {response.get('bot_message', {}).get('text', 'No response')[:50]}...")
            print(f"   Safety level: {response.get('bot_message', {}).get('safety_level', 'Unknown')}")
        return success

    def test_profanity_filter(self):
        """Test profanity filter blocking"""
        success, response = self.run_test(
            "Profanity Filter Test",
            "POST",
            "chat/send",
            200,
            data={
                "conversation_id": self.conversation_id,
                "text": "I want to kill someone"
            }
        )
        if success:
            blocked = response.get('blocked', False)
            if blocked:
                print(f"   ✅ Message correctly blocked")
                if 'alert' in response:
                    self.alert_id = response['alert']['id']
                    print(f"   Alert created: {self.alert_id}")
            else:
                print(f"   ❌ Message should have been blocked but wasn't")
                return False
        return success

def main():
    print("🤖 BuddyBot Backend API Testing Suite - Iteration 3 Auth Focus")
    print("=" * 60)
    
    tester = BuddyBotAPITester()
    
    # Test sequence - focusing on NEW auth features for iteration 3
    tests = [
        # Basic health check
        lambda: tester.run_test("API Health Check", "GET", "", 200)[0],
        
        # Auth system tests (NEW)
        tester.test_register_parent,
        tester.test_login_valid_credentials,
        tester.test_login_invalid_credentials,
        tester.test_auth_me_with_token,
        tester.test_auth_me_without_token,
        tester.test_verify_password_correct,
        tester.test_verify_password_incorrect,
        
        # Protected endpoint tests (NEW auth requirements)
        tester.test_parent_dashboard_with_auth,
        tester.test_parent_dashboard_without_auth,
        tester.test_parent_alerts_with_auth,
        tester.test_parent_alerts_without_auth,
        
        # Public endpoint tests (should work without auth)
        tester.test_public_chat_send,
        tester.test_public_chat_conversations,
        
        # Logout test
        tester.test_logout,
    ]
    
    print(f"\n🚀 Running {len(tests)} auth-focused tests...")
    
    for i, test in enumerate(tests, 1):
        try:
            print(f"\n[{i}/{len(tests)}]", end=" ")
            test()
            time.sleep(0.5)  # Small delay between tests
        except Exception as e:
            print(f"❌ Test {test.__name__ if hasattr(test, '__name__') else 'test'} failed with exception: {e}")
    
    # Results
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All auth tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())