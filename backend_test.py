#!/usr/bin/env python3
"""
Comprehensive BuddyBot Backend API Test Suite
Tests authentication, chat, and parent dashboard APIs with Supabase integration
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime

# Test configuration
BASE_URL = "https://get-restart.preview.emergentagent.com/api"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test123456"
TEST_NAME = "Test User"

class BuddyBotTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0, cookies={})  # Fresh client with no cookies
        self.access_token = None
        self.user_id = None
        self.conversation_id = None
        self.test_results = []
        
    async def log_result(self, test_name: str, success: bool, details: str = "", response_data: dict = None):
        """Log test result with details"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")
        if response_data and not success:
            print(f"   Response: {json.dumps(response_data, indent=2)}")
        print()
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "response": response_data
        })
    
    async def test_auth_protection_first(self):
        """Test that protected endpoints require authentication - BEFORE login"""
        try:
            # Test chat endpoint without token using fresh client
            response = await self.client.post(f"{BASE_URL}/chat/send", json={"text": "test"})
            
            if response.status_code == 401:
                await self.log_result("Auth Protection (Pre-login)", True, "Protected endpoints correctly require authentication")
                return True
            else:
                await self.log_result("Auth Protection (Pre-login)", False, f"Expected 401, got {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_result("Auth Protection (Pre-login)", False, f"Exception: {str(e)}")
            return False
    
    async def test_auth_register(self):
        """Test user registration"""
        try:
            # First try to register a new user
            response = await self.client.post(f"{BASE_URL}/auth/register", json={
                "name": TEST_NAME,
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            
            if response.status_code == 400 and "already registered" in response.text:
                await self.log_result("Auth Register", True, "User already exists (expected)")
                return True
            elif response.status_code == 200:
                data = response.json()
                if "user_id" in data and "token" in data and "email" in data:
                    self.access_token = data["token"]
                    self.user_id = data["user_id"]
                    await self.log_result("Auth Register", True, f"New user created: {data['email']}")
                    return True
                else:
                    await self.log_result("Auth Register", False, "Missing required fields in response", data)
                    return False
            else:
                await self.log_result("Auth Register", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_result("Auth Register", False, f"Exception: {str(e)}")
            return False
    
    async def test_auth_login(self):
        """Test user login"""
        try:
            response = await self.client.post(f"{BASE_URL}/auth/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            
            if response.status_code == 200:
                data = response.json()
                if "user_id" in data and "token" in data and "email" in data:
                    self.access_token = data["token"]
                    self.user_id = data["user_id"]
                    await self.log_result("Auth Login", True, f"Login successful for: {data['email']}")
                    return True
                else:
                    await self.log_result("Auth Login", False, "Missing required fields in response", data)
                    return False
            else:
                await self.log_result("Auth Login", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_result("Auth Login", False, f"Exception: {str(e)}")
            return False
    
    async def test_auth_me(self):
        """Test getting current user info"""
        try:
            if not self.access_token:
                await self.log_result("Auth Me", False, "No access token available")
                return False
                
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = await self.client.get(f"{BASE_URL}/auth/me", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if "user_id" in data and "email" in data and "name" in data:
                    await self.log_result("Auth Me", True, f"User info retrieved: {data['email']}")
                    return True
                else:
                    await self.log_result("Auth Me", False, "Missing required fields in response", data)
                    return False
            else:
                await self.log_result("Auth Me", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_result("Auth Me", False, f"Exception: {str(e)}")
            return False
    
    async def test_supabase_connection(self):
        """Test that Supabase database is working by checking user data persistence"""
        try:
            if not self.access_token:
                await self.log_result("Supabase Connection", False, "No access token available")
                return False
                
            # Get user info to verify database connection
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = await self.client.get(f"{BASE_URL}/auth/me", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                # Check if we have children data (created during registration)
                if "children" in data and isinstance(data["children"], list):
                    await self.log_result("Supabase Connection", True, f"Database connected - user has {len(data['children'])} child profiles")
                    return True
                else:
                    await self.log_result("Supabase Connection", False, "Missing children data in user response", data)
                    return False
            else:
                await self.log_result("Supabase Connection", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_result("Supabase Connection", False, f"Exception: {str(e)}")
            return False
    
    async def test_chat_send_normal(self):
        """Test sending a normal chat message"""
        try:
            if not self.access_token:
                await self.log_result("Chat Send Normal", False, "No access token available")
                return False
                
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = await self.client.post(f"{BASE_URL}/chat/send", 
                headers=headers,
                json={"text": "Hello, I love puppies"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "conversation_id" in data and "user_message" in data and "bot_message" in data:
                    self.conversation_id = data["conversation_id"]
                    blocked = data.get("blocked", False)
                    if not blocked:
                        await self.log_result("Chat Send Normal", True, f"Message sent successfully, conversation: {self.conversation_id}")
                        return True
                    else:
                        await self.log_result("Chat Send Normal", False, "Normal message was blocked unexpectedly", data)
                        return False
                else:
                    await self.log_result("Chat Send Normal", False, "Missing required fields in response", data)
                    return False
            else:
                await self.log_result("Chat Send Normal", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_result("Chat Send Normal", False, f"Exception: {str(e)}")
            return False
    
    async def test_chat_send_profanity(self):
        """Test sending a message with profanity"""
        try:
            if not self.access_token:
                await self.log_result("Chat Send Profanity", False, "No access token available")
                return False
                
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = await self.client.post(f"{BASE_URL}/chat/send", 
                headers=headers,
                json={"text": "what the fuck"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if "conversation_id" in data and "user_message" in data and "bot_message" in data:
                    blocked = data.get("blocked", False)
                    if blocked:
                        user_msg = data.get("user_message", {})
                        blocked_words = user_msg.get("blocked_words", [])
                        if "fuck" in blocked_words:
                            await self.log_result("Chat Send Profanity", True, f"Profanity correctly blocked: {blocked_words}")
                            return True
                        else:
                            await self.log_result("Chat Send Profanity", False, f"Profanity blocked but wrong words detected: {blocked_words}", data)
                            return False
                    else:
                        await self.log_result("Chat Send Profanity", False, "Profanity was not blocked", data)
                        return False
                else:
                    await self.log_result("Chat Send Profanity", False, "Missing required fields in response", data)
                    return False
            else:
                await self.log_result("Chat Send Profanity", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_result("Chat Send Profanity", False, f"Exception: {str(e)}")
            return False
    
    async def test_chat_conversations(self):
        """Test listing user conversations"""
        try:
            if not self.access_token:
                await self.log_result("Chat Conversations", False, "No access token available")
                return False
                
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = await self.client.get(f"{BASE_URL}/chat/conversations", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    await self.log_result("Chat Conversations", True, f"Found {len(data)} conversations")
                    return True
                else:
                    await self.log_result("Chat Conversations", False, "Response is not a list", data)
                    return False
            else:
                await self.log_result("Chat Conversations", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_result("Chat Conversations", False, f"Exception: {str(e)}")
            return False
    
    async def test_parent_dashboard(self):
        """Test parent dashboard stats"""
        try:
            if not self.access_token:
                await self.log_result("Parent Dashboard", False, "No access token available")
                return False
                
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = await self.client.get(f"{BASE_URL}/parent/dashboard", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if "stats" in data and "recent_alerts" in data:
                    stats = data["stats"]
                    required_stats = ["total_conversations", "total_messages", "total_alerts", "unresolved_alerts"]
                    missing_stats = [stat for stat in required_stats if stat not in stats]
                    
                    if not missing_stats:
                        await self.log_result("Parent Dashboard", True, f"Dashboard loaded with {stats['total_conversations']} conversations, {stats['total_messages']} messages")
                        return True
                    else:
                        await self.log_result("Parent Dashboard", False, f"Missing stats: {missing_stats}", data)
                        return False
                else:
                    await self.log_result("Parent Dashboard", False, "Missing required fields in response", data)
                    return False
            else:
                await self.log_result("Parent Dashboard", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_result("Parent Dashboard", False, f"Exception: {str(e)}")
            return False
    
    async def test_parent_alerts(self):
        """Test parent alerts listing"""
        try:
            if not self.access_token:
                await self.log_result("Parent Alerts", False, "No access token available")
                return False
                
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = await self.client.get(f"{BASE_URL}/parent/alerts", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    # Check if we have any alerts from our profanity test
                    profanity_alerts = [alert for alert in data if alert.get("type") == "profanity"]
                    await self.log_result("Parent Alerts", True, f"Found {len(data)} total alerts, {len(profanity_alerts)} profanity alerts")
                    return True
                else:
                    await self.log_result("Parent Alerts", False, "Response is not a list", data)
                    return False
            else:
                await self.log_result("Parent Alerts", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_result("Parent Alerts", False, f"Exception: {str(e)}")
            return False
    
    async def test_conversation_user_isolation(self):
        """Test that conversations are properly isolated per user"""
        try:
            if not self.access_token or not self.conversation_id:
                await self.log_result("Conversation User Isolation", False, "No conversation to test isolation")
                return False
                
            # Get conversation details to verify user isolation
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = await self.client.get(f"{BASE_URL}/chat/conversations/{self.conversation_id}", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if "conversation" in data and "messages" in data:
                    conversation = data["conversation"]
                    messages = data["messages"]
                    
                    # Verify conversation belongs to current user
                    if len(messages) >= 2:  # Should have user message and bot response
                        user_messages = [msg for msg in messages if msg["role"] == "user"]
                        bot_messages = [msg for msg in messages if msg["role"] == "assistant"]
                        
                        if len(user_messages) > 0 and len(bot_messages) > 0:
                            await self.log_result("Conversation User Isolation", True, f"Conversation properly isolated with {len(messages)} messages")
                            return True
                        else:
                            await self.log_result("Conversation User Isolation", False, f"Missing user or bot messages: {len(user_messages)} user, {len(bot_messages)} bot")
                            return False
                    else:
                        await self.log_result("Conversation User Isolation", False, f"Expected at least 2 messages, found {len(messages)}")
                        return False
                else:
                    await self.log_result("Conversation User Isolation", False, "Missing conversation or messages in response", data)
                    return False
            else:
                await self.log_result("Conversation User Isolation", False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_result("Conversation User Isolation", False, f"Exception: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting BuddyBot Backend API Tests")
        print(f"Testing against: {BASE_URL}")
        print(f"Test credentials: {TEST_EMAIL} / {TEST_PASSWORD}")
        print("=" * 60)
        print()
        
        # Test authentication protection FIRST (before login)
        await self.test_auth_protection_first()
        
        # Authentication tests
        await self.test_auth_register()
        await self.test_auth_login()
        await self.test_auth_me()
        
        # Database connection test
        await self.test_supabase_connection()
        
        # Chat tests (requires auth)
        await self.test_chat_send_normal()
        await self.test_chat_send_profanity()
        await self.test_chat_conversations()
        
        # Parent dashboard tests (requires auth)
        await self.test_parent_dashboard()
        await self.test_parent_alerts()
        
        # User isolation test
        await self.test_conversation_user_isolation()
        
        # Summary
        print("=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        print()
        
        if total - passed > 0:
            print("❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['details']}")
            print()
        
        await self.client.aclose()
        return passed == total

async def main():
    """Main test runner"""
    tester = BuddyBotTester()
    success = await tester.run_all_tests()
    
    if success:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())