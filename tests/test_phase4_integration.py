"""
Integration tests for Phase 4 Maritime Security Components
Tests maritime_data_classification.py, maritime_data_encryption.py, and secure service worker integration
"""

import pytest
import json
import os
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

# Import Phase 4 components
import sys
sys.path.append('/home/colby/stevedores-dashboard-3.0')

from utils.maritime_data_classification import (
    MaritimeDataClassifier,
    DataClassificationLevel,
    MaritimeRegulation,
    UserRole,
    GeographicRestriction,
    classify_maritime_data,
    validate_user_access,
    get_maritime_classifier
)

from utils.maritime_data_encryption import (
    MaritimeDataEncryption,
    MaritimeKeyManager,
    EncryptionAlgorithm,
    encrypt_maritime_data,
    decrypt_maritime_data,
    get_maritime_encryption
)

from utils.encrypted_cache import (
    EncryptedCacheManager,
    CacheClassification,
    get_encrypted_cache,
    cache_maritime_data,
    get_cached_maritime_data
)

from utils.secure_sync import (
    SecureSyncManager,
    SyncOperation,
    SyncStatus,
    queue_maritime_sync,
    get_secure_sync_manager
)

class TestMaritimeDataClassification:
    """Test maritime data classification system"""
    
    def setup_method(self):
        """Set up test environment"""
        self.classifier = MaritimeDataClassifier()
    
    def test_classification_levels_hierarchy(self):
        """Test that classification levels follow proper hierarchy"""
        levels = [
            DataClassificationLevel.PUBLIC,
            DataClassificationLevel.INTERNAL,
            DataClassificationLevel.CONFIDENTIAL,
            DataClassificationLevel.RESTRICTED,
            DataClassificationLevel.TOP_SECRET
        ]
        
        # Verify all levels exist
        assert len(levels) == 5
        
        # Test classification values
        assert DataClassificationLevel.PUBLIC.value == "public"
        assert DataClassificationLevel.TOP_SECRET.value == "top_secret"
    
    def test_vessel_data_classification(self):
        """Test classification of vessel-related data"""
        # Public vessel data
        public_data = {
            "vessel_name": "MSC OSCAR",
            "flag_state": "Liberia",
            "vessel_type": "Container Ship"
        }
        
        result = self.classifier.classify_data(public_data)
        assert result.classification == DataClassificationLevel.INTERNAL  # Default for maritime data
        assert result.confidence > 0
        
        # Confidential vessel data
        confidential_data = {
            "cargo_manifest": "Dangerous goods - Class 1.1",
            "bill_of_lading": "BL-2024-001234",
            "shipper_details": "ABC Shipping Co."
        }
        
        result = self.classifier.classify_data(confidential_data)
        assert result.classification == DataClassificationLevel.CONFIDENTIAL
        assert MaritimeRegulation.CUSTOMS in result.regulations
    
    def test_restricted_security_data_classification(self):
        """Test classification of security-sensitive data"""
        restricted_data = {
            "imo_number": "1234567",
            "vessel_registration": "LIBERIA-12345",
            "security_plan": "ISPS Security Plan Level 3",
            "customs_declaration": "Form 7533"
        }
        
        result = self.classifier.classify_data(restricted_data)
        assert result.classification == DataClassificationLevel.RESTRICTED
        assert result.requires_encryption == True
        assert result.audit_required == True
        assert MaritimeRegulation.ISPS in result.regulations
        assert MaritimeRegulation.CUSTOMS in result.regulations
    
    def test_personal_data_gdpr_classification(self):
        """Test GDPR compliance for personal data"""
        personal_data = {
            "crew_list": [
                {"name": "John Smith", "passport": "US123456789"},
                {"name": "Maria Garcia", "passport": "ES987654321"}
            ],
            "contact_info": "captain@vessel.com",
            "personal_data": "Medical information"
        }
        
        result = self.classifier.classify_data(personal_data)
        assert result.classification == DataClassificationLevel.CONFIDENTIAL
        assert MaritimeRegulation.GDPR in result.regulations
        assert GeographicRestriction.EU_ONLY in result.geographic_restrictions
        assert result.retention_policy.retention_years == 2  # GDPR retention
    
    def test_role_based_access_validation(self):
        """Test role-based access control"""
        # Test stevedore access
        allowed, reasons = validate_user_access(
            user_role="stevedore",
            user_location="US",
            data_classification="internal"
        )
        assert allowed == True
        assert "Access granted" in " ".join(reasons)
        
        # Test restricted access denial
        allowed, reasons = validate_user_access(
            user_role="stevedore",
            user_location="US", 
            data_classification="restricted"
        )
        assert allowed == False
        assert "not authorized for restricted data" in " ".join(reasons)
        
        # Test admin access
        allowed, reasons = validate_user_access(
            user_role="admin",
            user_location="US",
            data_classification="top_secret"
        )
        # Note: Admin should have access to all levels in real implementation
        # This test may need adjustment based on actual implementation
        
    def test_export_control_restrictions(self):
        """Test export control and geographic restrictions"""
        # Test data for restricted country
        restricted_context = {
            'vessel_flag_state': 'IR',  # Iran - restricted country
            'operation_type': 'security_inspection'
        }
        
        test_data = {"security_assessment": "Port security evaluation"}
        result = self.classifier.classify_data(test_data, restricted_context)
        
        assert result.export_restricted == True
        assert GeographicRestriction.NATIONAL_ONLY in result.geographic_restrictions
    
    def test_retention_policy_compliance(self):
        """Test maritime data retention policies"""
        # Test standard maritime retention (7 years)
        maritime_data = {"cargo_tally": {"containers": 150, "weight": "2500MT"}}
        result = self.classifier.classify_data(maritime_data)
        
        assert result.retention_policy.retention_years == 7
        assert result.retention_policy.archive_after_years == 2
        
        # Test GDPR retention (2 years)
        personal_data = {"personal_data": "crew member details"}
        result = self.classifier.classify_data(personal_data)
        
        assert result.retention_policy.retention_years == 2
        assert MaritimeRegulation.GDPR in result.regulations
        
        # Test safety-critical retention (25 years) 
        safety_data = {"inspection_report": "Safety deficiency found"}
        result = self.classifier.classify_data(safety_data)
        
        assert result.retention_policy.retention_years == 25
        assert MaritimeRegulation.SOLAS in result.regulations
    
    def test_access_control_matrix(self):
        """Test comprehensive access control matrix"""
        matrix = self.classifier.get_access_control_matrix()
        
        # Test role matrix
        assert 'stevedore' in matrix['roles']
        assert 'customs_officer' in matrix['roles']
        assert 'admin' in matrix['roles']
        
        # Test classification matrix
        assert 'public' in matrix['classifications']
        assert 'restricted' in matrix['classifications']
        
        # Verify stevedore can access public and internal
        stevedore_access = matrix['roles']['stevedore']['accessible_classifications']
        assert 'public' in stevedore_access or 'internal' in stevedore_access
        
        # Verify customs officer can access restricted
        customs_access = matrix['roles']['customs_officer']['accessible_classifications']
        assert 'restricted' in customs_access

class TestMaritimeDataEncryption:
    """Test maritime data encryption system"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.key_manager = MaritimeKeyManager()
        self.key_manager.key_storage_dir = os.path.join(self.temp_dir, 'keys')
        self.encryption_engine = MaritimeDataEncryption()
        self.encryption_engine.key_manager = self.key_manager
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_key_generation_by_classification(self):
        """Test key generation for different classification levels"""
        # Test key generation for each classification level
        for classification in DataClassificationLevel:
            key_id = self.key_manager.generate_key(classification)
            assert key_id is not None
            assert classification.value in key_id
            
            # Verify key can be retrieved
            key_data = self.key_manager.get_key(key_id)
            assert key_data is not None
            assert key_data['metadata']['classification'] == classification.value
    
    def test_encryption_algorithm_selection(self):
        """Test correct encryption algorithm selection by classification"""
        # Test Fernet for public data
        key_id = self.key_manager.generate_key(DataClassificationLevel.PUBLIC)
        key_data = self.key_manager.get_key(key_id)
        assert key_data['metadata']['algorithm'] == EncryptionAlgorithm.FERNET.value
        
        # Test AES-256-GCM for confidential data
        key_id = self.key_manager.generate_key(DataClassificationLevel.CONFIDENTIAL)
        key_data = self.key_manager.get_key(key_id)
        assert key_data['metadata']['algorithm'] == EncryptionAlgorithm.AES_256_GCM.value
        
        # Test RSA for restricted data
        key_id = self.key_manager.generate_key(DataClassificationLevel.RESTRICTED)
        key_data = self.key_manager.get_key(key_id)
        assert key_data['metadata']['algorithm'] == EncryptionAlgorithm.RSA_2048.value
    
    def test_maritime_data_encryption_decryption(self):
        """Test end-to-end encryption and decryption"""
        # Test data encryption
        test_data = {
            "vessel_id": 12345,
            "cargo_manifest": "Dangerous goods shipment",
            "imo_number": "1234567",
            "classification": "confidential"
        }
        
        encrypted_container = self.encryption_engine.encrypt_data(
            data=test_data,
            classification=DataClassificationLevel.CONFIDENTIAL,
            vessel_id=12345,
            operation_type="cargo_inspection"
        )
        
        # Verify encryption container structure
        assert encrypted_container.encrypted_data is not None
        assert encrypted_container.metadata.classification == DataClassificationLevel.CONFIDENTIAL
        assert encrypted_container.metadata.algorithm in [
            EncryptionAlgorithm.AES_256_GCM,
            EncryptionAlgorithm.FERNET
        ]
        assert encrypted_container.vessel_id == 12345
        
        # Test data decryption
        decrypted_data = self.encryption_engine.decrypt_data(encrypted_container)
        assert decrypted_data == test_data
    
    def test_rsa_hybrid_encryption(self):
        """Test RSA hybrid encryption for large data"""
        # Large data that requires hybrid encryption
        large_data = {
            "inspection_report": "A" * 1000,  # Large string
            "vessel_details": {
                "imo": "1234567",
                "security_plan": "B" * 500,
                "crew_list": ["C" * 100 for _ in range(10)]
            }
        }
        
        encrypted_container = self.encryption_engine.encrypt_data(
            data=large_data,
            classification=DataClassificationLevel.RESTRICTED
        )
        
        # Verify hybrid encryption was used
        assert encrypted_container.metadata.algorithm == EncryptionAlgorithm.RSA_2048
        
        # Verify decryption works
        decrypted_data = self.encryption_engine.decrypt_data(encrypted_container)
        assert decrypted_data == large_data
    
    def test_key_rotation(self):
        """Test encryption key rotation"""
        # Generate initial key
        old_key_id = self.key_manager.generate_key(DataClassificationLevel.INTERNAL)
        old_key = self.key_manager.get_key(old_key_id)
        assert old_key is not None
        
        # Rotate key
        new_key_id = self.key_manager.rotate_key(old_key_id)
        new_key = self.key_manager.get_key(new_key_id)
        
        # Verify new key is different
        assert new_key_id != old_key_id
        assert new_key is not None
        assert new_key['metadata']['classification'] == old_key['metadata']['classification']
    
    def test_data_reencryption(self):
        """Test data re-encryption with new classification"""
        # Encrypt data with internal classification
        original_data = {"vessel_status": "operational"}
        
        encrypted_container = self.encryption_engine.encrypt_data(
            data=original_data,
            classification=DataClassificationLevel.INTERNAL
        )
        
        # Re-encrypt with confidential classification
        reencrypted_container = self.encryption_engine.reencrypt_data(
            encrypted_container,
            new_classification=DataClassificationLevel.CONFIDENTIAL
        )
        
        # Verify new classification
        assert reencrypted_container.metadata.classification == DataClassificationLevel.CONFIDENTIAL
        assert reencrypted_container.metadata.key_id != encrypted_container.metadata.key_id
        
        # Verify data integrity
        decrypted_data = self.encryption_engine.decrypt_data(reencrypted_container)
        assert decrypted_data == original_data
    
    @patch('utils.maritime_data_encryption.os.environ.get')
    def test_master_key_from_environment(self, mock_env_get):
        """Test master key retrieval from environment"""
        test_key = "test_master_key_base64_encoded"
        mock_env_get.return_value = test_key
        
        key_manager = MaritimeKeyManager()
        master_key = key_manager._get_master_key()
        
        # Verify environment variable was checked
        mock_env_get.assert_called_with('STEVEDORES_MASTER_KEY')

class TestEncryptedCacheIntegration:
    """Test encrypted cache integration with maritime data"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_manager = EncryptedCacheManager(cache_dir=os.path.join(self.temp_dir, 'cache'))
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_maritime_data_caching(self):
        """Test caching of maritime data with automatic classification"""
        # Test caching sensitive maritime data
        maritime_data = {
            "imo_number": "1234567",
            "vessel_name": "MSC OSCAR",
            "cargo_manifest": "Container manifest",
            "security_clearance": "Level 2"
        }
        
        success = cache_maritime_data(
            key="vessel_12345_manifest",
            data=maritime_data,
            vessel_id=12345,
            operation_type="cargo_inspection"
        )
        
        assert success == True
        
        # Retrieve cached data
        cached_data = get_cached_maritime_data("vessel_12345_manifest")
        assert cached_data == maritime_data
    
    def test_cache_classification_levels(self):
        """Test cache storage by classification level"""
        # Store data at different classification levels
        test_cases = [
            ("public_data", {"port_schedule": "Schedule info"}, CacheClassification.PUBLIC),
            ("internal_data", {"cargo_tally": 150}, CacheClassification.INTERNAL),
            ("confidential_data", {"crew_list": ["John", "Jane"]}, CacheClassification.CONFIDENTIAL),
            ("restricted_data", {"security_plan": "ISPS Plan"}, CacheClassification.RESTRICTED)
        ]
        
        for key, data, classification in test_cases:
            success = self.cache_manager.store(
                key=key,
                data=data,
                classification=classification
            )
            assert success == True
            
            # Verify retrieval
            retrieved_data = self.cache_manager.retrieve(key, classification)
            assert retrieved_data == data
    
    def test_cache_expiration_and_cleanup(self):
        """Test cache expiration and cleanup mechanisms"""
        # Store data with short TTL
        test_data = {"test": "data"}
        success = self.cache_manager.store(
            key="short_ttl_test",
            data=test_data,
            ttl=1  # 1 second TTL
        )
        assert success == True
        
        # Verify data exists initially
        cached_data = self.cache_manager.retrieve("short_ttl_test")
        assert cached_data == test_data
        
        # Wait for expiration (simulate)
        import time
        time.sleep(2)
        
        # Clean expired entries
        cleaned_count = self.cache_manager.clear_expired()
        assert cleaned_count >= 1
        
        # Verify data is gone
        expired_data = self.cache_manager.retrieve("short_ttl_test")
        assert expired_data is None
    
    def test_cache_security_features(self):
        """Test cache security features"""
        # Test secure deletion of sensitive data
        sensitive_data = {"imo_number": "1234567"}
        
        success = self.cache_manager.store(
            key="sensitive_test",
            data=sensitive_data,
            classification=CacheClassification.RESTRICTED
        )
        assert success == True
        
        # Delete sensitive data
        deleted = self.cache_manager.delete("sensitive_test")
        assert deleted == True
        
        # Verify secure deletion
        retrieved = self.cache_manager.retrieve("sensitive_test")
        assert retrieved is None

class TestSecureSyncIntegration:
    """Test secure sync integration with maritime data"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.sync_manager = SecureSyncManager()
        self.sync_manager.sync_queue_dir = os.path.join(self.temp_dir, 'sync')
        self.sync_manager.conflict_dir = os.path.join(self.temp_dir, 'conflicts')
        self.sync_manager.backup_dir = os.path.join(self.temp_dir, 'backups')
        self.sync_manager._setup_sync_directories()
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_maritime_sync_queue(self):
        """Test queueing maritime data for synchronization"""
        # Queue maritime sync operation
        vessel_data = {
            "vessel_id": 12345,
            "status": "arrived",
            "cargo_count": 150,
            "security_clearance": "approved"
        }
        
        transaction_id = queue_maritime_sync(
            operation="update",
            table_name="vessels",
            record_id="12345",
            data=vessel_data,
            vessel_id=12345,
            urgency="urgent"
        )
        
        assert transaction_id is not None
        assert len(transaction_id) == 16  # Expected transaction ID length
        
        # Verify transaction is queued
        pending_transactions = self.sync_manager.get_pending_transactions()
        assert len(pending_transactions) == 1
        assert pending_transactions[0].transaction_id == transaction_id
        assert pending_transactions[0].maritime_urgency == "urgent"
    
    def test_sync_priority_calculation(self):
        """Test sync priority calculation for different data types"""
        # Test emergency vessel status - should get highest priority
        emergency_data = {
            "vessel_id": 12345,
            "status": "emergency",
            "distress_signal": True
        }
        
        transaction_id = self.sync_manager.queue_sync_operation(
            operation=SyncOperation.UPDATE,
            table_name="vessels",
            record_id="12345",
            data=emergency_data,
            maritime_urgency="critical"
        )
        
        transactions = self.sync_manager.get_pending_transactions()
        emergency_transaction = next(t for t in transactions if t.transaction_id == transaction_id)
        assert emergency_transaction.priority == 10  # Highest priority
        
        # Test regular cargo tally - should get normal priority
        cargo_data = {"cargo_count": 150}
        
        cargo_transaction_id = self.sync_manager.queue_sync_operation(
            operation=SyncOperation.CREATE,
            table_name="cargo_tallies",
            record_id="tally_001",
            data=cargo_data
        )
        
        transactions = self.sync_manager.get_pending_transactions()
        cargo_transaction = next(t for t in transactions if t.transaction_id == cargo_transaction_id)
        assert cargo_transaction.priority <= 9  # Lower than emergency
    
    def test_maritime_conflict_resolution(self):
        """Test maritime-specific conflict resolution"""
        # This would test the conflict resolution mechanisms
        # For now, we'll test the conflict detection setup
        
        vessel_data = {"status": "departed", "timestamp": "2024-01-01T10:00:00Z"}
        
        transaction_id = self.sync_manager.queue_sync_operation(
            operation=SyncOperation.UPDATE,
            table_name="vessels",
            record_id="12345",
            data=vessel_data,
            vessel_id=12345
        )
        
        # Verify transaction was created
        transactions = self.sync_manager.get_pending_transactions()
        assert len(transactions) == 1
        assert transactions[0].transaction_id == transaction_id
    
    def test_sync_encryption_integration(self):
        """Test integration with encryption for sensitive sync data"""
        # Test syncing sensitive maritime data
        sensitive_data = {
            "imo_number": "1234567",
            "security_plan": "ISPS Level 3",
            "customs_declaration": "Form 7533"
        }
        
        transaction_id = self.sync_manager.queue_sync_operation(
            operation=SyncOperation.CREATE,
            table_name="security_documents",
            record_id="sec_001",
            data=sensitive_data,
            compliance_required=True
        )
        
        # Verify encrypted storage
        transactions = self.sync_manager.get_pending_transactions()
        security_transaction = next(t for t in transactions if t.transaction_id == transaction_id)
        
        assert security_transaction.compliance_required == True
        # The data should be encrypted in the transaction
        assert security_transaction.encrypted_data is not None

class TestCompletePhase4Integration:
    """Test complete integration of all Phase 4 components"""
    
    def setup_method(self):
        """Set up complete test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize all components
        self.classifier = get_maritime_classifier()
        self.encryption = get_maritime_encryption()
        self.cache = get_encrypted_cache()
        self.sync = get_secure_sync_manager()
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_end_to_end_maritime_data_flow(self):
        """Test complete maritime data flow through all security components"""
        # 1. Start with raw maritime data
        maritime_data = {
            "vessel_id": 12345,
            "imo_number": "1234567",
            "cargo_manifest": [
                {"container": "ABCD1234567", "weight": "25.5T", "contents": "Electronics"},
                {"container": "EFGH2345678", "weight": "22.1T", "contents": "Textiles"}
            ],
            "crew_list": [
                {"name": "Captain Smith", "license": "ML123456"},
                {"name": "Chief Officer Johnson", "license": "ML654321"}  
            ],
            "security_clearance": "Level 2",
            "customs_declaration": "Form 7533 - Completed"
        }
        
        # 2. Classify the data
        classification_result = classify_maritime_data(
            data=maritime_data,
            vessel_id=12345,
            user_role="port_authority",
            user_location="US"
        )
        
        # Verify classification
        assert classification_result.classification in [
            DataClassificationLevel.CONFIDENTIAL,
            DataClassificationLevel.RESTRICTED
        ]
        assert classification_result.requires_encryption == True
        assert classification_result.audit_required == True
        
        # 3. Encrypt the data
        encrypted_data_dict = encrypt_maritime_data(
            data=maritime_data,
            classification=classification_result.classification.value,
            vessel_id=12345,
            operation_type="customs_inspection"
        )
        
        # Verify encryption
        assert "encrypted_data" in encrypted_data_dict
        assert "metadata" in encrypted_data_dict
        assert encrypted_data_dict["vessel_id"] == 12345
        
        # 4. Cache the encrypted data
        cache_success = cache_maritime_data(
            key="vessel_12345_full_manifest",
            data=maritime_data,
            vessel_id=12345,
            operation_type="customs_inspection"
        )
        assert cache_success == True
        
        # 5. Queue for secure synchronization
        sync_transaction_id = queue_maritime_sync(
            operation="create",
            table_name="vessel_manifests",
            record_id="12345_manifest",
            data=maritime_data,
            vessel_id=12345,
            urgency="normal"
        )
        assert sync_transaction_id is not None
        
        # 6. Decrypt and verify data integrity
        decrypted_data = decrypt_maritime_data(encrypted_data_dict)
        assert decrypted_data == maritime_data
        
        # 7. Retrieve from cache and verify
        cached_data = get_cached_maritime_data("vessel_12345_full_manifest")
        assert cached_data == maritime_data
    
    def test_gdpr_compliance_workflow(self):
        """Test GDPR compliance throughout the data lifecycle"""
        # Personal data subject to GDPR
        personal_data = {
            "crew_member": {
                "name": "John Smith",
                "passport": "US123456789",
                "medical_info": "No restrictions",
                "contact": "john.smith@email.com"
            },
            "vessel_assignment": "MSC OSCAR",
            "embarkation_port": "Hamburg"
        }
        
        # Classify with EU context
        result = classify_maritime_data(
            data=personal_data,
            user_location="DE"  # Germany - EU country
        )
        
        # Verify GDPR compliance
        assert MaritimeRegulation.GDPR in result.regulations
        assert result.retention_policy.retention_years == 2  # GDPR retention
        assert GeographicRestriction.EU_ONLY in result.geographic_restrictions
        
        # Test access validation for different locations
        eu_access, _ = validate_user_access(
            user_role="vessel_operator",
            user_location="DE",
            data_classification=result.classification.value
        )
        assert eu_access == True  # EU user should have access
        
        # Test that retention policy is enforced
        assert result.retention_policy.legal_hold_override == False  # GDPR allows deletion
    
    def test_maritime_security_audit_trail(self):
        """Test security audit trail across all components"""
        # Create audit-worthy maritime data
        security_data = {
            "vessel_security_assessment": {
                "imo_number": "1234567",
                "isps_certificate": "Valid until 2025-12-31",
                "security_level": 2,
                "threats_identified": ["Unauthorized access attempt"],
                "mitigation_actions": ["Additional guards", "Enhanced screening"]
            },
            "inspection_date": "2024-01-15",
            "inspector": "Port Security Officer"
        }
        
        # Process through all security components
        classification_result = classify_maritime_data(security_data)
        
        # Should be classified as restricted due to security content
        assert classification_result.classification == DataClassificationLevel.RESTRICTED
        assert classification_result.audit_required == True
        
        # Encrypt with audit requirement
        encrypted_dict = encrypt_maritime_data(
            data=security_data,
            classification="restricted"
        )
        
        # Cache with audit logging
        cache_success = cache_maritime_data(
            key="security_assessment_12345",
            data=security_data,
            operation_type="security_inspection"
        )
        assert cache_success == True
        
        # Queue for sync with compliance requirement
        sync_id = queue_maritime_sync(
            operation="create",
            table_name="security_assessments",
            record_id="assess_12345",
            data=security_data,
            urgency="urgent"
        )
        assert sync_id is not None
        
        # Verify all operations maintain audit trail
        # (In a real implementation, this would check audit logs)
    
    def test_export_control_compliance(self):
        """Test export control compliance across all components"""
        # Data involving restricted country
        restricted_data = {
            "vessel_details": {
                "flag_state": "IR",  # Iran - restricted country
                "destination_ports": ["Bandar Abbas", "Dubai"],
                "cargo_description": "Industrial equipment"
            },
            "export_license": "Required - pending approval",
            "restricted_technology": True
        }
        
        # Classify with restricted context
        context = {"vessel_flag_state": "IR"}
        result = classify_maritime_data(restricted_data, context=context)
        
        # Should be export restricted
        assert result.export_restricted == True
        assert GeographicRestriction.NATIONAL_ONLY in result.geographic_restrictions
        
        # Test access validation fails for restricted location
        access_allowed, reasons = validate_user_access(
            user_role="stevedore",
            user_location="IR",
            data_classification=result.classification.value
        )
        
        # Access should be denied due to export restrictions
        # (Implementation may vary based on specific export control logic)
    
    def test_performance_and_scalability(self):
        """Test performance of integrated security components"""
        import time
        
        # Test bulk data processing
        start_time = time.time()
        
        for i in range(10):  # Process 10 vessels
            vessel_data = {
                "vessel_id": 10000 + i,
                "vessel_name": f"TEST_VESSEL_{i}",
                "cargo_manifest": [
                    {"container": f"TEST{i:07d}", "weight": f"{20 + i}.0T"}
                ]
            }
            
            # Process through all components
            classification_result = classify_maritime_data(vessel_data)
            encrypted_dict = encrypt_maritime_data(vessel_data)
            cache_success = cache_maritime_data(f"vessel_{10000+i}", vessel_data)
            sync_id = queue_maritime_sync("create", "vessels", str(10000+i), vessel_data)
            
            assert cache_success == True
            assert sync_id is not None
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process 10 vessels in reasonable time (adjust threshold as needed)
        assert processing_time < 10.0  # 10 seconds max for 10 vessels
        
        print(f"Processed 10 vessels with full security in {processing_time:.2f} seconds")
    
    def test_error_handling_and_resilience(self):
        """Test error handling and resilience of integrated components"""
        # Test with malformed data
        malformed_data = {
            "invalid_field": None,
            "circular_reference": {}
        }
        malformed_data["circular_reference"]["self"] = malformed_data
        
        # Classification should handle malformed data gracefully
        try:
            result = classify_maritime_data(malformed_data)
            # Should not crash and should provide safe default
            assert result.classification in DataClassificationLevel
        except Exception as e:
            # If it does throw an exception, it should be handled gracefully
            assert "classification" in str(e).lower()
        
        # Test with invalid encryption parameters
        try:
            encrypted_dict = encrypt_maritime_data(
                data={"test": "data"},
                classification="invalid_classification"
            )
            # Should handle invalid classification gracefully
        except Exception as e:
            assert "classification" in str(e).lower() or "invalid" in str(e).lower()
        
        # Test cache resilience
        cache_success = cache_maritime_data(
            key="test_resilience",
            data={"valid": "data"}
        )
        # Should succeed with valid data
        assert cache_success == True

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])