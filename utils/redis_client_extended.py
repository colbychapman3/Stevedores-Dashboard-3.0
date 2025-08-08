# Additional methods and functions for the enhanced Redis client

def add_redis_client_extensions():
    """Add the remaining methods to the EnterpriseRedisClient class"""
    
    def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check with diagnostics"""
        now = time.time()
        
        # Skip frequent health checks
        if now - self._last_health_check < 5:  # 5 seconds minimum interval
            return self._health_status.copy()
        
        self._last_health_check = now
        
        health_data = {
            'redis_available': False,
            'response_time_ms': None,
            'circuit_breaker_state': self._circuit_breaker.state.value,
            'connection_pool_available': self._connection_pool is not None,
            'fallback_active': True,
            'last_error': self._health_status.get('error'),
            'uptime_check': now
        }
        
        if self._client and self._initialized:
            try:
                start_time = time.time()
                ping_result = self._client.ping()
                response_time = (time.time() - start_time) * 1000
                
                health_data.update({
                    'redis_available': ping_result,
                    'response_time_ms': round(response_time, 2),
                    'last_error': None
                })
                
                self._update_health_status(True, None)
                
                # Check connection pool stats if available
                if self._connection_pool:
                    pool_stats = {
                        'max_connections': self._connection_pool.max_connections,
                        'created_connections': self._connection_pool.created_connections,
                    }
                    health_data['connection_pool'] = pool_stats
                
            except Exception as e:
                error_msg = str(e)
                health_data['last_error'] = error_msg
                self._update_health_status(False, error_msg)
                logger.debug(f"Health check failed: {error_msg}")
        
        # Add fallback cache stats
        health_data['fallback_cache'] = self._fallback_cache.get_stats()
        
        return health_data

    def reconnect(self, force: bool = False) -> bool:
        """Attempt to reconnect to Redis"""
        if not self.redis_url:
            logger.warning("Cannot reconnect: No Redis URL configured")
            return False
        
        if not force and self._initialized and self.ping():
            logger.info("Redis connection already healthy, skipping reconnect")
            return True
        
        logger.info("🔄 Attempting Redis reconnection...")
        
        # Close existing connection
        self.close()
        
        # Reset circuit breaker if forced
        if force:
            self._circuit_breaker.force_close("Manual reconnection")
        
        # Reinitialize
        self._initialized = False
        self._initialize_client()
        
        success = self._initialized and self.ping()
        if success:
            logger.info("✅ Redis reconnection successful")
        else:
            logger.error("❌ Redis reconnection failed")
        
        return success

    def close(self):
        """Close Redis connection and cleanup resources"""
        logger.info("🔄 Closing Redis connection...")
        
        if self._connection_pool:
            try:
                self._connection_pool.disconnect()
                logger.debug("Connection pool disconnected")
            except Exception as e:
                logger.warning(f"Error disconnecting connection pool: {e}")
        
        self._client = None
        self._connection_pool = None
        self._initialized = False
        
        logger.info("✅ Redis connection closed")

    def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics for monitoring and alerting"""
        with self._metrics_lock:
            metrics_data = asdict(self._metrics)
        
        # Add circuit breaker stats
        metrics_data['circuit_breaker'] = self._circuit_breaker.get_stats()
        
        # Add fallback cache stats
        metrics_data['fallback_cache'] = self._fallback_cache.get_stats()
        
        # Add health information
        metrics_data['health'] = self.health_check()
        
        # Connection pool information
        if self._connection_pool:
            metrics_data['connection_pool'] = {
                'max_connections': self._connection_pool.max_connections,
                'created_connections': getattr(self._connection_pool, 'created_connections', 0)
            }
        
        # Calculate derived metrics
        metrics_data['derived'] = {
            'availability_percent': 100.0 - metrics_data['failure_rate'],
            'fallback_dependency_percent': (
                (metrics_data['fallback_hits'] / max(metrics_data['total_requests'], 1)) * 100
            ),
            'avg_response_time_category': self._categorize_response_time(metrics_data['avg_response_time_ms'])
        }
        
        return metrics_data

    def _categorize_response_time(self, response_time_ms: float) -> str:
        """Categorize response time for monitoring"""
        if response_time_ms < 1:
            return 'excellent'
        elif response_time_ms < 5:
            return 'good'
        elif response_time_ms < 10:
            return 'acceptable'
        elif response_time_ms < 50:
            return 'slow'
        else:
            return 'critical'

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def __del__(self):
        """Destructor - cleanup resources"""
        try:
            self.close()
        except:
            pass

    # Add methods to class
    setattr(EnterpriseRedisClient, 'health_check', health_check)
    setattr(EnterpriseRedisClient, 'reconnect', reconnect)
    setattr(EnterpriseRedisClient, 'close', close)
    setattr(EnterpriseRedisClient, 'get_comprehensive_metrics', get_comprehensive_metrics)
    setattr(EnterpriseRedisClient, '_categorize_response_time', _categorize_response_time)
    setattr(EnterpriseRedisClient, '__enter__', __enter__)
    setattr(EnterpriseRedisClient, '__exit__', __exit__)
    setattr(EnterpriseRedisClient, '__del__', __del__)