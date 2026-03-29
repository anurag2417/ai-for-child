#!/usr/bin/env python3
"""
Backend Test Suite for BuddyBot Fuzzy Keyword Filtering System
Tests the /api/chat/send endpoint for comprehensive profanity filtering
"""

import asyncio
import httpx
import json
import os
from datetime import datetime
from typing import Dict, List, Any

# Get backend URL from frontend .env file
BACKEND_URL = "https://get-restart.preview.emergentagent.com/api"

class BuddyBotTester:
    def __init__(self):
        self.base_url = BACKEND_URL
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_results = []
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def log_test(self, test_name: str, passed: bool, details: str = "", expected: Any = None, actual: Any = None):
        """Log test results"""
        result = {
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        if expected is not None:
            result["expected"] = expected
        if actual is not None:
            result["actual"] = actual
        self.test_results.append(result)
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
        if not passed and expected is not None and actual is not None:
            print(f"    Expected: {expected}")
            print(f"    Actual: {actual}")
        print()

    async def test_chat_send_endpoint(self, message: str, test_name: str, should_be_blocked: bool, expected_categories: List[str] = None, expected_words: List[str] = None):
        """Test the /api/chat/send endpoint with a specific message"""
        try:
            payload = {"text": message}
            response = await self.client.post(f"{self.base_url}/chat/send", json=payload)
            
            if response.status_code != 200:
                self.log_test(test_name, False, f"HTTP {response.status_code}: {response.text}")
                return None
                
            data = response.json()
            
            # Check if message was blocked as expected
            is_blocked = data.get("blocked", False)
            if is_blocked != should_be_blocked:
                self.log_test(test_name, False, 
                    f"Expected blocked={should_be_blocked}, got blocked={is_blocked}",
                    should_be_blocked, is_blocked)
                return data
            
            if should_be_blocked:
                # Verify alert was created
                alert = data.get("alert")
                if not alert:
                    self.log_test(test_name, False, "Expected alert to be created but none found")
                    return data
                
                # Check matched words
                user_message = data.get("user_message", {})
                matched_words = user_message.get("blocked_words", [])
                
                if expected_words:
                    # Check if any expected words were matched
                    found_expected = any(word.lower() in [w.lower() for w in matched_words] for word in expected_words)
                    if not found_expected:
                        self.log_test(test_name, False, 
                            f"Expected words {expected_words} not found in matched words {matched_words}")
                        return data
                
                # Check categories if specified
                if expected_categories:
                    alert_categories = alert.get("categories", {})
                    found_categories = list(alert_categories.keys())
                    
                    category_match = any(cat in found_categories for cat in expected_categories)
                    if not category_match:
                        self.log_test(test_name, False, 
                            f"Expected categories {expected_categories} not found in {found_categories}")
                        return data
                
                # Check bot response contains friendly redirect
                bot_message = data.get("bot_message", {})
                bot_text = bot_message.get("text", "").lower()
                
                friendly_indicators = ["kind", "friendly", "fun", "talk about", "instead", "favorite"]
                has_friendly_redirect = any(indicator in bot_text for indicator in friendly_indicators)
                
                if not has_friendly_redirect:
                    self.log_test(test_name, False, 
                        f"Bot response doesn't contain friendly redirect: '{bot_text}'")
                    return data
                
                self.log_test(test_name, True, 
                    f"Blocked correctly. Matched: {matched_words}, Categories: {list(alert.get('categories', {}).keys())}")
            else:
                # Message should not be blocked
                bot_message = data.get("bot_message", {})
                if not bot_message:
                    self.log_test(test_name, False, "Expected bot response but none found")
                    return data
                    
                self.log_test(test_name, True, "Message allowed correctly")
            
            return data
            
        except Exception as e:
            self.log_test(test_name, False, f"Exception: {str(e)}")
            return None

    async def run_comprehensive_tests(self):
        """Run all fuzzy keyword filtering tests"""
        print("🚀 Starting BuddyBot Fuzzy Keyword Filtering Tests")
        print("=" * 60)
        
        # Test 1: Exact profanity match
        await self.test_chat_send_endpoint(
            "fuck you", 
            "Exact profanity match", 
            should_be_blocked=True,
            expected_categories=["profanity"],
            expected_words=["fuck"]
        )
        
        # Test 2: Misspelling with extra characters
        await self.test_chat_send_endpoint(
            "fuuck this", 
            "Misspelling - extra characters", 
            should_be_blocked=True,
            expected_categories=["profanity"],
            expected_words=["fuck"]
        )
        
        # Test 3: Misspelling - shitt
        await self.test_chat_send_endpoint(
            "shitt", 
            "Misspelling - shitt", 
            should_be_blocked=True,
            expected_categories=["profanity"],
            expected_words=["shit"]
        )
        
        # Test 4: Leetspeak - sh1t
        await self.test_chat_send_endpoint(
            "sh1t", 
            "Leetspeak - sh1t", 
            should_be_blocked=True,
            expected_categories=["profanity"],
            expected_words=["shit"]
        )
        
        # Test 5: Leetspeak - f@ck
        await self.test_chat_send_endpoint(
            "f@ck", 
            "Leetspeak - f@ck", 
            should_be_blocked=True,
            expected_categories=["profanity"],
            expected_words=["fuck"]
        )
        
        # Test 6: Leetspeak - k!ll
        await self.test_chat_send_endpoint(
            "k!ll", 
            "Leetspeak - k!ll", 
            should_be_blocked=True,
            expected_categories=["violence"],
            expected_words=["kill"]
        )
        
        # Test 7: Leetspeak - pr0n (should match "porn")
        await self.test_chat_send_endpoint(
            "pr0n", 
            "Leetspeak - pr0n", 
            should_be_blocked=True,
            expected_categories=["adult_content"],
            expected_words=["porn"]
        )
        
        # Test 8: Separator bypass - f.u.c.k
        await self.test_chat_send_endpoint(
            "f.u.c.k", 
            "Separator bypass - f.u.c.k", 
            should_be_blocked=True,
            expected_categories=["profanity"],
            expected_words=["fuck"]
        )
        
        # Test 9: Safe message
        await self.test_chat_send_endpoint(
            "I love puppies", 
            "Safe message", 
            should_be_blocked=False
        )
        
        # Test 10: Violence category
        await self.test_chat_send_endpoint(
            "I want to kill", 
            "Violence category", 
            should_be_blocked=True,
            expected_categories=["violence"],
            expected_words=["kill"]
        )
        
        # Test 11: Self-harm category
        await self.test_chat_send_endpoint(
            "i want to die", 
            "Self-harm category", 
            should_be_blocked=True,
            expected_categories=["self_harm"]
        )
        
        # Test 12: Multiple categories
        await self.test_chat_send_endpoint(
            "fuck cocaine", 
            "Multiple categories", 
            should_be_blocked=True,
            expected_categories=["profanity", "substances"]
        )
        
        # Additional edge case tests
        print("\n🔍 Running Additional Edge Case Tests")
        print("-" * 40)
        
        # Test 13: Mixed case
        await self.test_chat_send_endpoint(
            "FuCk ThIs", 
            "Mixed case profanity", 
            should_be_blocked=True,
            expected_categories=["profanity"]
        )
        
        # Test 14: Multiple separators
        await self.test_chat_send_endpoint(
            "f-u-c-k", 
            "Hyphen separator bypass", 
            should_be_blocked=True,
            expected_categories=["profanity"]
        )
        
        # Test 15: Leetspeak with numbers
        await self.test_chat_send_endpoint(
            "5h1t", 
            "Leetspeak with 5 for s", 
            should_be_blocked=True,
            expected_categories=["profanity"]
        )
        
        # Test 16: Adult content
        await self.test_chat_send_endpoint(
            "show me porn", 
            "Adult content", 
            should_be_blocked=True,
            expected_categories=["adult_content"]
        )
        
        # Test 17: Substances
        await self.test_chat_send_endpoint(
            "where to buy weed", 
            "Substances category", 
            should_be_blocked=True,
            expected_categories=["substances"]
        )
        
        # Test 18: Cyberbullying
        await self.test_chat_send_endpoint(
            "you are ugly and stupid", 
            "Cyberbullying category", 
            should_be_blocked=True,
            expected_categories=["cyberbullying"]
        )
        
        # Test 19: Hate speech
        await self.test_chat_send_endpoint(
            "racist comments", 
            "Hate speech category", 
            should_be_blocked=True,
            expected_categories=["hate_speech"]
        )
        
        # Test 20: Safe educational content
        await self.test_chat_send_endpoint(
            "I want to learn about science", 
            "Safe educational content", 
            should_be_blocked=False
        )

    async def test_database_alert_creation(self):
        """Test that alerts are properly created in database"""
        print("\n🗄️  Testing Database Alert Creation")
        print("-" * 40)
        
        # Send a message that should create an alert
        test_message = "test fuck alert"
        response_data = await self.test_chat_send_endpoint(
            test_message,
            "Database alert creation test",
            should_be_blocked=True,
            expected_categories=["profanity"]
        )
        
        if response_data and response_data.get("alert"):
            alert = response_data["alert"]
            required_fields = ["id", "type", "severity", "details", "child_message", "created_at"]
            
            missing_fields = [field for field in required_fields if field not in alert]
            if missing_fields:
                self.log_test("Alert structure validation", False, 
                    f"Missing required fields: {missing_fields}")
            else:
                self.log_test("Alert structure validation", True, 
                    "All required alert fields present")
                
            # Check alert details contain category information
            details = alert.get("details", "")
            if "Categories:" in details:
                self.log_test("Alert category details", True, 
                    "Alert contains category information")
            else:
                self.log_test("Alert category details", False, 
                    "Alert missing category information in details")

    def print_summary(self):
        """Print test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        failed_tests = total_tests - passed_tests
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test']}: {result['details']}")
        
        print("\n" + "=" * 60)
        
        return failed_tests == 0

async def main():
    """Main test runner"""
    async with BuddyBotTester() as tester:
        await tester.run_comprehensive_tests()
        await tester.test_database_alert_creation()
        
        success = tester.print_summary()
        
        if success:
            print("🎉 All tests passed! Fuzzy keyword filtering system is working correctly.")
        else:
            print("⚠️  Some tests failed. Please review the implementation.")
            
        return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)