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

    def test_extension_packets(self):
        """Test receiving browsing packets from extension"""
        test_packets = [
            {
                "id": "test-packet-1",
                "timestamp": datetime.now().isoformat(),
                "device_id": "dev-test-123",
                "tab_type": "normal",
                "url": "https://www.google.com/search?q=how+to+study",
                "domain": "google.com",
                "title": "Google Search",
                "packet_type": "search_query",
                "search_query": "how to study",
                "search_engine": "Google"
            },
            {
                "id": "test-packet-2", 
                "timestamp": datetime.now().isoformat(),
                "device_id": "dev-test-123",
                "tab_type": "incognito",
                "url": "https://www.google.com/search?q=how+to+fight+at+school",
                "domain": "google.com",
                "title": "Google Search",
                "packet_type": "search_query",
                "search_query": "how to fight at school",
                "search_engine": "Google"
            }
        ]
        
        success, response = self.run_test(
            "Extension Packets Submission",
            "POST",
            "extension/packets",
            200,
            data={
                "device_id": "dev-test-123",
                "packets": test_packets
            }
        )
        if success:
            print(f"   Received: {response.get('received', 0)} packets")
            print(f"   Alerts created: {response.get('alerts_created', 0)}")
        return success

    def test_extension_status(self):
        """Test getting extension status for device"""
        success, response = self.run_test(
            "Extension Device Status",
            "GET",
            "extension/status/dev-test-123",
            200
        )
        if success:
            print(f"   Device: {response.get('device_id')}")
            print(f"   Total packets: {response.get('total_packets', 0)}")
            print(f"   Total alerts: {response.get('total_alerts', 0)}")
        return success

    def test_browsing_stats(self):
        """Test browsing statistics endpoint"""
        success, response = self.run_test(
            "Browsing Statistics",
            "GET",
            "parent/browsing/stats",
            200
        )
        if success:
            print(f"   Total packets: {response.get('total_packets', 0)}")
            print(f"   Search count: {response.get('search_count', 0)}")
            print(f"   Visit count: {response.get('visit_count', 0)}")
            print(f"   Incognito count: {response.get('incognito_count', 0)}")
            print(f"   Flagged searches: {response.get('flagged_searches', 0)}")
            print(f"   Browsing alerts: {response.get('browsing_alerts', 0)}")
        return success

    def test_browsing_searches(self):
        """Test browsing searches endpoint"""
        success, response = self.run_test(
            "Browsing Searches",
            "GET",
            "parent/browsing/searches",
            200,
            params={"limit": 20}
        )
        if success:
            print(f"   Found {len(response)} search queries")
            if response:
                flagged_count = sum(1 for s in response if s.get('profanity_flagged') or s.get('restricted_topics'))
                print(f"   Flagged searches: {flagged_count}")
        return success

    def test_browsing_visits(self):
        """Test browsing visits endpoint"""
        success, response = self.run_test(
            "Browsing Visits",
            "GET",
            "parent/browsing/visits",
            200,
            params={"limit": 20}
        )
        if success:
            print(f"   Found {len(response)} URL visits")
        return success

    def test_browsing_analysis(self):
        """Test AI browsing pattern analysis"""
        success, response = self.run_test(
            "Browsing Pattern Analysis",
            "GET",
            "parent/browsing/analysis",
            200,
            params={"device_id": "dev-test-123"}
        )
        if success:
            print(f"   Safety level: {response.get('safety_level', 'Unknown')}")
            print(f"   Analysis: {response.get('analysis', 'No analysis')[:100]}...")
            print(f"   Total searches analyzed: {response.get('total_searches', 0)}")
            print(f"   Flagged searches: {len(response.get('flagged_searches', []))}")
        return success

    def test_enhanced_chat_with_browsing_context(self):
        """Test chat with browsing context enhancement"""
        success, response = self.run_test(
            "Chat with Browsing Context",
            "POST",
            "chat/send",
            200,
            data={
                "text": "I've been looking up some things online",
                "device_id": "dev-test-123"
            }
        )
        if success:
            print(f"   Bot response: {response.get('bot_message', {}).get('text', 'No response')[:50]}...")
            print(f"   Safety level: {response.get('bot_message', {}).get('safety_level', 'Unknown')}")
            # Check if AI thought mentions browsing context
            thought = response.get('bot_message', {}).get('thought', '')
            if 'browsing' in thought.lower() or 'search' in thought.lower():
                print(f"   ✅ AI thought includes browsing context")
            else:
                print(f"   ⚠️  AI thought may not include browsing context")
        return success

def main():
    print("🤖 BuddyBot Backend API Testing Suite")
    print("=" * 50)
    
    tester = BuddyBotAPITester()
    
    # Test sequence - focusing on NEW extension features for iteration 2
    tests = [
        tester.test_health_check,
        # Extension endpoints (NEW)
        tester.test_extension_packets,
        tester.test_extension_status,
        tester.test_browsing_stats,
        tester.test_browsing_searches,
        tester.test_browsing_visits,
        tester.test_browsing_analysis,
        tester.test_enhanced_chat_with_browsing_context,
        # Updated parent dashboard (should now include browsing stats)
        tester.test_parent_dashboard,
        # Quick verification that existing features still work
        tester.test_create_conversation,
        tester.test_send_safe_message,
        tester.test_profanity_filter,
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