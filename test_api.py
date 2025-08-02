#!/usr/bin/env python3
"""
Test script for Lexsy AI Assistant API
Run this after deployment to verify all endpoints work
"""

import requests
import json
import time
from typing import Dict, Any

class APITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
    def test_endpoint(self, method: str, endpoint: str, **kwargs) -> Dict[Any, Any]:
        """Test an API endpoint and return results"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            return {
                "success": True,
                "status_code": response.status_code,
                "url": url,
                "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
                "time_ms": response.elapsed.total_seconds() * 1000
            }
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": str(e)
            }
    
    def run_basic_tests(self):
        """Run basic API health tests"""
        print("🧪 Running Basic API Tests")
        print("=" * 50)
        
        tests = [
            ("GET", "/health", "Health Check"),
            ("GET", "/", "Root Endpoint"),
            ("GET", "/api/status", "API Status"),
            ("GET", "/api/docs", "API Documentation"),
        ]
        
        results = []
        
        for method, endpoint, description in tests:
            print(f"\n📋 Testing: {description}")
            result = self.test_endpoint(method, endpoint)
            
            if result["success"]:
                status = "✅ PASS" if result["status_code"] < 400 else "❌ FAIL"
                print(f"{status} - {result['status_code']} - {result['time_ms']:.0f}ms")
                if endpoint in ["/health", "/", "/api/status"]:
                    print(f"Response: {json.dumps(result['response'], indent=2)}")
            else:
                print(f"❌ ERROR - {result['error']}")
            
            results.append(result)
        
        return results
    
    def run_client_tests(self):
        """Test client management endpoints"""
        print("\n\n👥 Running Client Management Tests")
        print("=" * 50)
        
        # Initialize demo data
        print("\n📋 Initializing demo data...")
        result = self.test_endpoint("POST", "/api/init-demo")
        
        if result["success"] and result["status_code"] == 200:
            print("✅ Demo data initialized successfully")
            demo_data = result["response"]
            
            # Extract client IDs
            clients = demo_data.get("data", {}).get("clients", {}).get("clients", [])
            lexsy_client_id = None
            
            for client in clients:
                if "lexsy" in client.get("email", "").lower():
                    lexsy_client_id = client["id"]
                    break
            
            if lexsy_client_id:
                print(f"📍 Found Lexsy client ID: {lexsy_client_id}")
                
                # Test client endpoints
                tests = [
                    ("GET", "/api/clients/", "List Clients"),
                    ("GET", f"/api/clients/{lexsy_client_id}", "Get Lexsy Client"),
                    ("GET", f"/api/clients/{lexsy_client_id}/stats", "Client Statistics"),
                ]
                
                for method, endpoint, description in tests:
                    print(f"\n📋 Testing: {description}")
                    result = self.test_endpoint(method, endpoint)
                    
                    if result["success"] and result["status_code"] < 400:
                        print(f"✅ PASS - {result['status_code']}")
                        if "stats" in endpoint:
                            stats = result["response"]
                            print(f"   📊 Documents: {stats.get('documents_uploaded', 0)}")
                            print(f"   📧 Emails: {stats.get('emails_ingested', 0)}")
                            print(f"   💬 Conversations: {stats.get('conversations', 0)}")
                    else:
                        print(f"❌ FAIL - {result.get('status_code', 'ERROR')}")
                
                return lexsy_client_id
        else:
            print(f"❌ Failed to initialize demo data: {result}")
            return None
    
    def run_chat_tests(self, client_id: int):
        """Test chat functionality"""
        print(f"\n\n💬 Running Chat Tests (Client ID: {client_id})")
        print("=" * 50)
        
        # Test questions
        questions = [
            "What equity grant was proposed for John Smith?",
            "What are the vesting terms discussed?",
            "How many shares are available in our equity incentive plan?",
            "Summarize the key legal documents"
        ]
        
        for i, question in enumerate(questions, 1):
            print(f"\n📋 Question {i}: {question}")
            
            result = self.test_endpoint(
                "POST", 
                f"/api/chat/{client_id}/ask",
                json={"question": question, "include_history": True},
                headers={"Content-Type": "application/json"}
            )
            
            if result["success"] and result["status_code"] == 200:
                response_data = result["response"]
                print(f"✅ PASS - Response in {result['time_ms']:.0f}ms")
                print(f"   🤖 Answer: {response_data.get('answer', '')[:100]}...")
                print(f"   📚 Sources: {response_data.get('context_used', 0)}")
                print(f"   🔤 Tokens: {response_data.get('tokens_used', 0)}")
            else:
                print(f"❌ FAIL - {result.get('status_code', 'ERROR')}")
                if not result["success"]:
                    print(f"   Error: {result['error']}")
    
    def run_search_tests(self, client_id: int):
        """Test search functionality"""
        print(f"\n\n🔍 Running Search Tests (Client ID: {client_id})")
        print("=" * 50)
        
        searches = [
            ("John Smith", None, "Search for John Smith"),
            ("equity", "document", "Search documents for equity"),
            ("vesting", "email", "Search emails for vesting"),
        ]
        
        for query, source_filter, description in searches:
            print(f"\n📋 {description}")
            
            search_data = {"query": query, "n_results": 3}
            if source_filter:
                search_data["source_filter"] = source_filter
            
            result = self.test_endpoint(
                "POST",
                f"/api/chat/{client_id}/search", 
                json=search_data,
                headers={"Content-Type": "application/json"}
            )
            
            if result["success"] and result["status_code"] == 200:
                response_data = result["response"]
                print(f"✅ PASS - Found {response_data.get('results_count', 0)} results")
                
                for i, res in enumerate(response_data.get('results', [])[:2], 1):
                    print(f"   📄 Result {i}: {res.get('metadata', {}).get('source_type', 'unknown')} - Score: {res.get('similarity_score', 0):.3f}")
            else:
                print(f"❌ FAIL - {result.get('status_code', 'ERROR')}")
    
    def run_full_test_suite(self):
        """Run complete test suite"""
        print("🚀 Lexsy AI Assistant - Full API Test Suite")
        print("=" * 60)
        print(f"Testing URL: {self.base_url}")
        print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Basic tests
        basic_results = self.run_basic_tests()
        
        # Check if basic tests passed
        basic_success = all(r["success"] and r["status_code"] < 400 for r in basic_results if r["success"])
        
        if not basic_success:
            print("\n❌ Basic tests failed. Stopping here.")
            return
        
        # Client tests (includes demo data initialization)
        client_id = self.run_client_tests()
        
        if client_id:
            # Chat tests
            self.run_chat_tests(client_id)
            
            # Search tests 
            self.run_search_tests(client_id)
        
        print("\n\n🎉 Test Suite Complete!")
        print("=" * 60)

def main():
    """Main test function"""
    import sys
    
    # Get URL from command line or use default
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    print(f"Testing API at: {url}")
    
    tester = APITester(url)
    tester.run_full_test_suite()

if __name__ == "__main__":
    main()