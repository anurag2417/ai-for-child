#!/usr/bin/env python3
"""
Backend API Testing for BuddyBot Extension Installation Feature
Tests the mandatory extension installation flow and related endpoints.
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime

# Backend URL from frontend environment
BACKEND_URL = "https://get-restart.preview.emergentagent.com/api"

class BuddyBotTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_results = []
        self.access_token = None
        self.user_id = None
        
    async def log_test(self, test_name: str, success: bool, details: str = "", response_data: dict = None):
        """Log test results with details."""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")
        if response_data and not success:
            print(f"   Response: {json.dumps(response_data, indent=2)}")
        
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "response": response_data
        })
        print()

    async def test_register_new_user(self):
        """Test user registration - should return extension_installed: false"""
        test_name = "User Registration with Extension Status"
        
        # Use timestamp to ensure unique email
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_email = f"newuser_{timestamp}@test.com"
        
        payload = {
            "name": "Test User",
            "email": test_email,
            "password": "password123"
        }
        
        try:
            response = await self.client.post(f"{BACKEND_URL}/auth/register", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check required fields
                required_fields = ["user_id", "name", "email", "token", "extension_installed"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    await self.log_test(test_name, False, f"Missing fields: {missing_fields}", data)
                    return False
                
                # Check extension_installed is False for new users
                if data.get("extension_installed") is not False:
                    await self.log_test(test_name, False, f"Expected extension_installed=false, got {data.get('extension_installed')}", data)
                    return False
                
                # Store for later tests
                self.access_token = data.get("token")
                self.user_id = data.get("user_id")
                self.test_email = test_email
                
                await self.log_test(test_name, True, f"New user registered with extension_installed=false")
                return True
            else:
                await self.log_test(test_name, False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_test(test_name, False, f"Exception: {str(e)}")
            return False

    async def test_extension_status_endpoint(self):
        """Test GET /auth/extension-status endpoint"""
        test_name = "Extension Status Endpoint"
        
        if not self.access_token:
            await self.log_test(test_name, False, "No access token available")
            return False
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = await self.client.get(f"{BACKEND_URL}/auth/extension-status", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check required fields
                if "extension_installed" not in data:
                    await self.log_test(test_name, False, "Missing extension_installed field", data)
                    return False
                
                # Should be False for new user
                if data.get("extension_installed") is not False:
                    await self.log_test(test_name, False, f"Expected extension_installed=false, got {data.get('extension_installed')}", data)
                    return False
                
                await self.log_test(test_name, True, "Extension status correctly shows false for new user")
                return True
            else:
                await self.log_test(test_name, False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_test(test_name, False, f"Exception: {str(e)}")
            return False

    async def test_auth_me_endpoint(self):
        """Test GET /auth/me endpoint for extension fields"""
        test_name = "Auth Me Endpoint Extension Fields"
        
        if not self.access_token:
            await self.log_test(test_name, False, "No access token available")
            return False
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = await self.client.get(f"{BACKEND_URL}/auth/me", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check required extension fields
                required_fields = ["extension_installed", "extension_device_id"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    await self.log_test(test_name, False, f"Missing fields: {missing_fields}", data)
                    return False
                
                # Check values
                if data.get("extension_installed") is not False:
                    await self.log_test(test_name, False, f"Expected extension_installed=false, got {data.get('extension_installed')}", data)
                    return False
                
                if data.get("extension_device_id") is not None:
                    await self.log_test(test_name, False, f"Expected extension_device_id=null, got {data.get('extension_device_id')}", data)
                    return False
                
                await self.log_test(test_name, True, "Auth me endpoint correctly shows extension fields")
                return True
            else:
                await self.log_test(test_name, False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_test(test_name, False, f"Exception: {str(e)}")
            return False

    async def test_confirm_extension(self):
        """Test POST /auth/confirm-extension endpoint"""
        test_name = "Confirm Extension Installation"
        
        if not self.access_token:
            await self.log_test(test_name, False, "No access token available")
            return False
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        payload = {"device_id": "test_device_123"}
        
        try:
            response = await self.client.post(f"{BACKEND_URL}/auth/confirm-extension", json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check required fields
                required_fields = ["status", "extension_installed", "device_id"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    await self.log_test(test_name, False, f"Missing fields: {missing_fields}", data)
                    return False
                
                # Check values
                if data.get("status") != "confirmed":
                    await self.log_test(test_name, False, f"Expected status='confirmed', got {data.get('status')}", data)
                    return False
                
                if data.get("extension_installed") is not True:
                    await self.log_test(test_name, False, f"Expected extension_installed=true, got {data.get('extension_installed')}", data)
                    return False
                
                if data.get("device_id") != "test_device_123":
                    await self.log_test(test_name, False, f"Expected device_id='test_device_123', got {data.get('device_id')}", data)
                    return False
                
                await self.log_test(test_name, True, "Extension confirmation successful")
                return True
            else:
                await self.log_test(test_name, False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_test(test_name, False, f"Exception: {str(e)}")
            return False

    async def test_extension_status_after_confirmation(self):
        """Test extension status after confirmation"""
        test_name = "Extension Status After Confirmation"
        
        if not self.access_token:
            await self.log_test(test_name, False, "No access token available")
            return False
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = await self.client.get(f"{BACKEND_URL}/auth/extension-status", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Should now be True
                if data.get("extension_installed") is not True:
                    await self.log_test(test_name, False, f"Expected extension_installed=true, got {data.get('extension_installed')}", data)
                    return False
                
                if data.get("device_id") != "test_device_123":
                    await self.log_test(test_name, False, f"Expected device_id='test_device_123', got {data.get('device_id')}", data)
                    return False
                
                await self.log_test(test_name, True, "Extension status correctly updated after confirmation")
                return True
            else:
                await self.log_test(test_name, False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_test(test_name, False, f"Exception: {str(e)}")
            return False

    async def test_auth_me_after_confirmation(self):
        """Test /auth/me after extension confirmation"""
        test_name = "Auth Me After Extension Confirmation"
        
        if not self.access_token:
            await self.log_test(test_name, False, "No access token available")
            return False
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = await self.client.get(f"{BACKEND_URL}/auth/me", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check updated values
                if data.get("extension_installed") is not True:
                    await self.log_test(test_name, False, f"Expected extension_installed=true, got {data.get('extension_installed')}", data)
                    return False
                
                if data.get("extension_device_id") != "test_device_123":
                    await self.log_test(test_name, False, f"Expected extension_device_id='test_device_123', got {data.get('extension_device_id')}", data)
                    return False
                
                await self.log_test(test_name, True, "Auth me correctly shows updated extension status")
                return True
            else:
                await self.log_test(test_name, False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_test(test_name, False, f"Exception: {str(e)}")
            return False

    async def test_login_with_extension_status(self):
        """Test login returns extension_installed field"""
        test_name = "Login Returns Extension Status"
        
        if not hasattr(self, 'test_email'):
            await self.log_test(test_name, False, "No test email available")
            return False
        
        payload = {
            "email": self.test_email,
            "password": "password123"
        }
        
        try:
            response = await self.client.post(f"{BACKEND_URL}/auth/login", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check extension_installed field is present
                if "extension_installed" not in data:
                    await self.log_test(test_name, False, "Missing extension_installed field", data)
                    return False
                
                # Should be True since we confirmed it
                if data.get("extension_installed") is not True:
                    await self.log_test(test_name, False, f"Expected extension_installed=true, got {data.get('extension_installed')}", data)
                    return False
                
                await self.log_test(test_name, True, "Login correctly returns extension_installed=true")
                return True
            else:
                await self.log_test(test_name, False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_test(test_name, False, f"Exception: {str(e)}")
            return False

    async def test_existing_user_login(self):
        """Test login with existing test credentials"""
        test_name = "Existing User Login Extension Status"
        
        payload = {
            "email": "test@example.com",
            "password": "test123456"
        }
        
        try:
            response = await self.client.post(f"{BACKEND_URL}/auth/login", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check extension_installed field is present
                if "extension_installed" not in data:
                    await self.log_test(test_name, False, "Missing extension_installed field", data)
                    return False
                
                # For existing user, could be true or false
                extension_status = data.get("extension_installed")
                if extension_status not in [True, False]:
                    await self.log_test(test_name, False, f"Invalid extension_installed value: {extension_status}", data)
                    return False
                
                await self.log_test(test_name, True, f"Existing user login returns extension_installed={extension_status}")
                return True
            else:
                await self.log_test(test_name, False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            await self.log_test(test_name, False, f"Exception: {str(e)}")
            return False

    async def run_all_tests(self):
        """Run all extension installation tests"""
        print("🚀 Starting BuddyBot Extension Installation Tests")
        print("=" * 60)
        print()
        
        # Test sequence following the review request flow
        tests = [
            self.test_register_new_user,
            self.test_extension_status_endpoint,
            self.test_auth_me_endpoint,
            self.test_confirm_extension,
            self.test_extension_status_after_confirmation,
            self.test_auth_me_after_confirmation,
            self.test_login_with_extension_status,
            self.test_existing_user_login,
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                result = await test()
                if result:
                    passed += 1
            except Exception as e:
                await self.log_test(test.__name__, False, f"Test execution error: {str(e)}")
        
        print("=" * 60)
        print(f"📊 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All extension installation tests PASSED!")
            return True
        else:
            print(f"❌ {total - passed} tests FAILED")
            return False

    async def cleanup(self):
        """Clean up resources"""
        await self.client.aclose()

async def main():
    """Main test runner"""
    tester = BuddyBotTester()
    try:
        success = await tester.run_all_tests()
        return 0 if success else 1
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)