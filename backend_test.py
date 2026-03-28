#!/usr/bin/env python3
"""
BuddyBot Backend API Testing Suite
Tests all chat, parent dashboard, and safety features
"""

import requests
import sys
import json
import time
from datetime import datetime

class BuddyBotAPITester:
    def __init__(self, base_url="https://problem-breakdown-2.preview.emergentagent.com"):
        self.base_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.conversation_id = None
        self.alert_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
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

    def test_health_check(self):
        """Test basic API health"""
        success, response = self.run_test(
            "API Health Check",
            "GET", 
            "",
            200
        )
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

    def test_restricted_topic_detection(self):
        """Test restricted topic detection"""
        success, response = self.run_test(
            "Restricted Topic Detection",
            "POST",
            "chat/send",
            200,
            data={
                "conversation_id": self.conversation_id,
                "text": "Can you tell me about violence and fighting?"
            }
        )
        if success:
            print(f"   Bot response: {response.get('bot_message', {}).get('text', 'No response')[:50]}...")
            print(f"   Safety level: {response.get('bot_message', {}).get('safety_level', 'Unknown')}")
        return success

    def test_get_conversation(self):
        """Test getting conversation details"""
        if not self.conversation_id:
            print("❌ No conversation ID available")
            return False
            
        success, response = self.run_test(
            "Get Conversation Details",
            "GET",
            f"chat/conversations/{self.conversation_id}",
            200
        )
        if success:
            messages = response.get('messages', [])
            print(f"   Found {len(messages)} messages in conversation")
        return success

    def test_parent_dashboard(self):
        """Test parent dashboard stats"""
        success, response = self.run_test(
            "Parent Dashboard Stats",
            "GET",
            "parent/dashboard",
            200
        )
        if success:
            stats = response.get('stats', {})
            print(f"   Stats: {stats}")
            recent_alerts = response.get('recent_alerts', [])
            print(f"   Recent alerts: {len(recent_alerts)}")
        return success

    def test_parent_alerts(self):
        """Test getting parent alerts"""
        success, response = self.run_test(
            "Parent Alerts List",
            "GET",
            "parent/alerts",
            200
        )
        if success:
            print(f"   Found {len(response)} alerts")
            if response and not self.alert_id:
                self.alert_id = response[0].get('id')
        return success

    def test_parent_conversations(self):
        """Test parent conversations list"""
        success, response = self.run_test(
            "Parent Conversations List",
            "GET",
            "parent/conversations",
            200
        )
        if success:
            print(f"   Found {len(response)} conversations")
        return success

    def test_parent_conversation_detail(self):
        """Test parent conversation detail view"""
        if not self.conversation_id:
            print("❌ No conversation ID available")
            return False
            
        success, response = self.run_test(
            "Parent Conversation Detail",
            "GET",
            f"parent/conversations/{self.conversation_id}",
            200
        )
        if success:
            messages = response.get('messages', [])
            alerts = response.get('alerts', [])
            print(f"   Messages: {len(messages)}, Alerts: {len(alerts)}")
        return success

    def test_resolve_alert(self):
        """Test resolving an alert"""
        if not self.alert_id:
            print("❌ No alert ID available")
            return False
            
        success, response = self.run_test(
            "Resolve Alert",
            "PUT",
            f"parent/alerts/{self.alert_id}/resolve",
            200
        )
        if success:
            print(f"   Alert {self.alert_id} resolved")
        return success

    def test_new_conversation_creation(self):
        """Test creating conversation via chat send without conversation_id"""
        success, response = self.run_test(
            "Auto-Create Conversation",
            "POST",
            "chat/send",
            200,
            data={
                "text": "This should create a new conversation"
            }
        )
        if success:
            new_conv_id = response.get('conversation_id')
            print(f"   Auto-created conversation: {new_conv_id}")
        return success

def main():
    print("🤖 BuddyBot Backend API Testing Suite")
    print("=" * 50)
    
    tester = BuddyBotAPITester()
    
    # Test sequence
    tests = [
        tester.test_health_check,
        tester.test_create_conversation,
        tester.test_list_conversations,
        tester.test_send_safe_message,
        tester.test_profanity_filter,
        tester.test_restricted_topic_detection,
        tester.test_get_conversation,
        tester.test_parent_dashboard,
        tester.test_parent_alerts,
        tester.test_parent_conversations,
        tester.test_parent_conversation_detail,
        tester.test_resolve_alert,
        tester.test_new_conversation_creation,
    ]
    
    print(f"\n🚀 Running {len(tests)} tests...")
    
    for test in tests:
        try:
            test()
            time.sleep(0.5)  # Small delay between tests
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    # Results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())