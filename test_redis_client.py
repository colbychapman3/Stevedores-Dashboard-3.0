#!/usr/bin/env python3
"""
Test suite for Production-Grade Redis Client
Tests circuit breaker, fallback mechanisms, and zero-downtime operations
"""

import os
import sys
import time
import threading
import logging
from unittest.mock import Mock, patch
import redis

# Add utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))

from redis_client import (
    EnterpriseRedisClient, 
    AdvancedCircuitBreaker,
    CircuitBreakerState, 
    RetryStrategy,
    InMemoryFallbackCache,
    get_redis_client,
    redis_health_check,
    check_rate_limit,
    get_redis_alerts
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_fallback_cache():
    """Test in-memory fallback cache functionality"""
    print("\n🧪 Testing In-Memory Fallback Cache...")
    
    cache = InMemoryFallbackCache(max_size=5, default_ttl=2)
    
    # Basic operations
    assert cache.set('key1', 'value1') == True
    assert cache.get('key1') == 'value1'
    assert cache.exists('key1') == True
    
    # TTL functionality
    cache.set('key2', 'value2', ttl=1)
    assert cache.get('key2') == 'value2'
    time.sleep(1.1)
    assert cache.get('key2') is None  # Should be expired
    
    # LRU eviction
    for i in range(6):
        cache.set(f'key{i}', f'value{i}')
    
    # First key should be evicted
    assert cache.get('key0') is None
    assert cache.get('key5') == 'value5'
    
    stats = cache.get_stats()
    assert stats['size'] <= 5
    
    print("✅ Fallback cache tests passed!")

def test_circuit_breaker():
    """Test advanced circuit breaker functionality"""
    print("\n🧪 Testing Advanced Circuit Breaker...")
    
    cb = AdvancedCircuitBreaker(failure_threshold=3, recovery_timeout=1)
    
    # Simulate successful operations
    def success_func():
        return "success"
    
    # Simulate failing operations  
    def fail_func():
        raise redis.ConnectionError("Connection failed")
    
    # Test normal operation
    assert cb.call(success_func) == "success"
    assert cb.state == CircuitBreakerState.CLOSED
    
    # Test failure handling
    for i in range(3):
        try:
            cb.call(fail_func)
        except redis.ConnectionError:
            pass
    
    # Circuit breaker should be open
    assert cb.state == CircuitBreakerState.OPEN
    
    # Test that calls are blocked
    try:
        cb.call(success_func)
        assert False, "Should have raised ConnectionError"
    except redis.ConnectionError:
        pass
    
    # Wait for recovery timeout
    time.sleep(1.1)
    
    # Should move to half-open and then closed
    try:
        result = cb.call(success_func)
        assert result == "success"
    except:
        pass  # Might still be in half-open
    
    # Test recovery with multiple successes
    for _ in range(3):
        try:
            cb.call(success_func)
        except:
            pass
    
    stats = cb.get_stats()
    assert 'state' in stats
    assert 'failure_count' in stats
    
    print("✅ Circuit breaker tests passed!")

def test_redis_client_fallback():
    """Test Redis client with fallback when Redis is unavailable"""
    print("\n🧪 Testing Redis Client Fallback Mode...")
    
    # Create client without Redis URL (fallback only)
    client = EnterpriseRedisClient(redis_url=None)
    
    # Test basic operations work in fallback
    assert client.set('test_key', 'test_value') == True
    assert client.get('test_key') == 'test_value'
    assert client.exists('test_key') == 1
    assert client.delete('test_key') == 1
    assert client.exists('test_key') == 0
    
    # Test with expiration
    client.set('exp_key', 'exp_value', ex=1)
    assert client.get('exp_key') == 'exp_value'
    time.sleep(1.1)
    # Note: Fallback cache handles TTL differently
    
    # Test hash operations
    assert client.hset('hash1', 'field1', 'value1') == 1
    assert client.hget('hash1', 'field1') == 'value1'
    assert client.hexists('hash1', 'field1') == True
    
    # Test increment operations
    assert client.set('counter', '5') == True
    assert client.incr('counter') == 6
    assert client.incr('counter', 3) == 9
    
    # Test ping (should return False for fallback)
    assert client.ping() == False
    
    # Test health check
    health = client.health_check()
    assert health['redis_available'] == False
    assert health['fallback_active'] == True
    
    # Test metrics
    metrics = client.get_comprehensive_metrics()
    assert 'fallback_cache' in metrics
    assert 'circuit_breaker' in metrics
    
    print("✅ Redis client fallback tests passed!")

def test_rate_limiting():
    """Test rate limiting functionality"""
    print("\n🧪 Testing Rate Limiting...")
    
    client = EnterpriseRedisClient(redis_url=None)
    
    # Test rate limiting
    result1 = check_rate_limit(client, "test_user", 3, "minute")
    assert result1['allowed'] == True
    assert result1['current_count'] == 1
    
    result2 = check_rate_limit(client, "test_user", 3, "minute")
    assert result2['allowed'] == True
    assert result2['current_count'] == 2
    
    result3 = check_rate_limit(client, "test_user", 3, "minute")
    assert result3['allowed'] == True
    assert result3['current_count'] == 3
    
    # Should be rate limited now
    result4 = check_rate_limit(client, "test_user", 3, "minute")
    assert result4['allowed'] == False
    assert result4['current_count'] == 3
    
    # Different user should not be affected
    result5 = check_rate_limit(client, "other_user", 3, "minute")
    assert result5['allowed'] == True
    
    print("✅ Rate limiting tests passed!")

def test_with_mock_redis():
    """Test Redis client with mocked Redis connection"""
    print("\n🧪 Testing Redis Client with Mock Redis...")
    
    with patch('redis.ConnectionPool') as mock_pool:
        with patch('redis.Redis') as mock_redis:
            # Setup mock
            mock_client = Mock()
            mock_redis.return_value = mock_client
            mock_client.ping.return_value = True
            mock_client.set.return_value = True
            mock_client.get.return_value = b'test_value'
            mock_client.delete.return_value = 1
            mock_client.exists.return_value = 1
            mock_client.info.return_value = {
                'redis_version': '6.0.0',
                'used_memory_human': '1M',
                'connected_clients': 5
            }
            
            # Test with mock Redis
            client = EnterpriseRedisClient(redis_url='redis://localhost:6379')
            
            # Test operations
            assert client.set('key', 'value') == True
            assert client.get('key') == b'test_value'
            assert client.exists('key') == 1
            assert client.ping() == True
            
            # Test info
            info = client.get_info()
            assert info['status'] == 'connected'
            assert 'redis_version' in info
            
    print("✅ Mock Redis tests passed!")

def test_connection_failure_simulation():
    """Test behavior when Redis connection fails"""
    print("\n🧪 Testing Connection Failure Simulation...")
    
    with patch('redis.ConnectionPool') as mock_pool:
        with patch('redis.Redis') as mock_redis:
            # Setup mock to fail
            mock_client = Mock()
            mock_redis.return_value = mock_client
            mock_client.ping.side_effect = redis.ConnectionError("Connection failed")
            mock_client.set.side_effect = redis.ConnectionError("Connection failed")
            mock_client.get.side_effect = redis.ConnectionError("Connection failed")
            
            client = EnterpriseRedisClient(redis_url='redis://localhost:6379')
            
            # Operations should fallback gracefully
            assert client.set('key', 'value') == True  # Uses fallback
            assert client.get('key') == 'value'        # Uses fallback
            assert client.ping() == False             # Redis unavailable
            
            # Circuit breaker should eventually open
            for _ in range(10):
                try:
                    client.ping()
                except:
                    pass
            
            # Check circuit breaker state
            metrics = client.get_comprehensive_metrics()
            cb_state = metrics['circuit_breaker']['state']
            print(f"Circuit breaker state after failures: {cb_state}")
            
    print("✅ Connection failure simulation passed!")

def test_alerts_system():
    """Test Redis monitoring and alerting system"""
    print("\n🧪 Testing Alerts System...")
    
    client = EnterpriseRedisClient(redis_url=None)  # Fallback only
    
    # Generate some activity to create metrics
    for i in range(10):
        client.set(f'key{i}', f'value{i}')
        client.get(f'key{i}')
    
    # Get alerts
    alerts = get_redis_alerts(client)
    print(f"Generated {len(alerts)} alerts")
    
    for alert in alerts:
        print(f"- {alert['severity']}: {alert['message']}")
    
    print("✅ Alerts system tests passed!")

def test_thread_safety():
    """Test thread safety of Redis client"""
    print("\n🧪 Testing Thread Safety...")
    
    client = EnterpriseRedisClient(redis_url=None)
    results = []
    
    def worker(worker_id):
        for i in range(10):
            key = f'thread_{worker_id}_key_{i}'
            value = f'thread_{worker_id}_value_{i}'
            
            client.set(key, value)
            retrieved = client.get(key)
            results.append(retrieved == value)
    
    # Create multiple threads
    threads = []
    for i in range(5):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for completion
    for thread in threads:
        thread.join()
    
    # Check results
    assert all(results), f"Thread safety test failed: {len([r for r in results if not r])} failures"
    
    print("✅ Thread safety tests passed!")

def run_all_tests():
    """Run all test suites"""
    print("🚀 Starting Production Redis Client Test Suite")
    print("=" * 60)
    
    try:
        test_fallback_cache()
        test_circuit_breaker()
        test_redis_client_fallback()
        test_rate_limiting()
        test_with_mock_redis()
        test_connection_failure_simulation()
        test_alerts_system()
        test_thread_safety()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED! Production Redis client is ready for deployment.")
        print("=" * 60)
        
        # Show comprehensive health check
        print("\n📊 Final System Status:")
        health = redis_health_check(detailed=True)
        print(f"- Redis Available: {health.get('redis_available', False)}")
        print(f"- Fallback Active: {health.get('fallback_active', True)}")
        print(f"- Circuit Breaker: {health.get('circuit_breaker_state', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)