"""
Comprehensive Maritime Data Classification System for Stevedores Dashboard 3.0
SOLAS, MARPOL, ISPS, and GDPR compliant data classification and handling

This module provides comprehensive data classification for maritime operations according to:
- SOLAS (Safety of Life at Sea) Convention requirements
- MARPOL (Marine Pollution) Convention compliance
- ISPS (International Ship and Port Facility Security) Code
- GDPR (General Data Protection Regulation) for personal data
- SOX (Sarbanes-Oxley) for financial controls
- MLC (Maritime Labour Convention) for crew welfare data

Classification Levels:
- PUBLIC: Publicly available maritime information
- INTERNAL: Internal operational data
- CONFIDENTIAL: Sensitive operational and commercial data
- RESTRICTED: Safety-critical and security-sensitive data
- SECRET: Highly classified security and emergency data

Data Retention Periods:
- Safety Records: 25 years (SOLAS requirement)
- Environmental: 10 years (MARPOL requirement) 
- Security: 15 years (ISPS requirement)
- Financial: 7 years (SOX requirement)
- Personal Data: Variable (GDPR compliance)
"""

import os
import json
import re
import hashlib
import logging
from typing import Dict, Any, Optional, List, Union, Tuple, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum, IntEnum
from flask import current_app, g
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

class MaritimeDataClassification(IntEnum):
    """Maritime data classification levels with numeric hierarchy"""
    PUBLIC = 1          # Publicly available information
    INTERNAL = 2        # Internal operational data
    CONFIDENTIAL = 3    # Sensitive commercial/operational data
    RESTRICTED = 4      # Safety-critical and security-sensitive
    SECRET = 5          # Highly classified security/emergency data

class MaritimeRegulatory(Enum):
    """Maritime regulatory frameworks"""
    SOLAS = "solas"        # Safety of Life at Sea
    MARPOL = "marpol"      # Marine Pollution Prevention
    ISPS = "isps"          # Ship and Port Facility Security
    STCW = "stcw"          # Standards of Training, Certification and Watchkeeping
    MLC = "mlc"            # Maritime Labour Convention
    GDPR = "gdpr"          # European General Data Protection Regulation
    SOX = "sox"            # Sarbanes-Oxley Financial Controls
    HIPAA = "hipaa"        # Health Insurance Portability (crew medical)
    CUSTOMS = "customs"    # International customs regulations
    ENVIRONMENTAL = "env"  # Environmental protection regulations

class DataRetentionPeriod(Enum):
    """Data retention periods for different regulatory requirements"""
    SOLAS_SAFETY = 25 * 365        # 25 years for safety records
    MARPOL_ENVIRONMENTAL = 10 * 365 # 10 years for environmental records
    ISPS_SECURITY = 15 * 365        # 15 years for security records
    SOX_FINANCIAL = 7 * 365         # 7 years for financial records
    MLC_LABOUR = 3 * 365            # 3 years for labour records
    STCW_TRAINING = 5 * 365         # 5 years for training records
    GDPR_PERSONAL = 2 * 365         # 2 years default for personal data
    CUSTOMS_TRADE = 6 * 365         # 6 years for customs/trade records
    OPERATIONAL_DEFAULT = 1 * 365   # 1 year for general operational data
    PERMANENT = 99 * 365            # Permanent retention

class PersonalDataType(Enum):
    """GDPR personal data types for maritime operations"""
    BASIC_IDENTITY = "basic_identity"      # Name, contact details
    SENSITIVE_IDENTITY = "sensitive_id"    # Passport, SSN, medical ID
    BIOMETRIC = "biometric"                # Fingerprints, photos, medical data
    LOCATION = "location"                  # GPS tracking, vessel positions
    BEHAVIORAL = "behavioral"              # Work patterns, performance data
    FINANCIAL = "financial"                # Salary, benefits, tax information
    MEDICAL = "medical"                    # Health records, medical certificates
    COMMUNICATION = "communication"        # Emails, phone logs, radio traffic
    CONTRACTUAL = "contractual"            # Employment contracts, agreements
    DISCIPLINARY = "disciplinary"          # Incident reports, disciplinary actions

class MaritimeDataSubject(Enum):
    """Data subjects in maritime operations for GDPR compliance"""
    CREW_MEMBER = "crew_member"            # Ship crew and maritime workers
    PASSENGER = "passenger"                # Passengers on vessels
    PORT_WORKER = "port_worker"            # Stevedores and port personnel
    CONTRACTOR = "contractor"              # External contractors and vendors
    VISITOR = "visitor"                    # Port and vessel visitors
    PILOT = "pilot"                        # Maritime pilots
    SURVEYOR = "surveyor"                  # Ship surveyors and inspectors
    AGENT = "agent"                        # Ship agents and representatives
    CUSTOMS_OFFICER = "customs_officer"    # Government officials
    EMERGENCY_CONTACT = "emergency_contact" # Emergency contact persons

class UserRole(Enum):
    """Maritime user roles with access permissions"""
    STEVEDORE = "stevedore"                # Cargo handling operations
    VESSEL_OPERATOR = "vessel_operator"     # Ship operations and crew
    PORT_AUTHORITY = "port_authority"       # Port management and safety
    CUSTOMS_OFFICER = "customs_officer"     # Customs and border control
    TERMINAL_OPERATOR = "terminal_operator" # Terminal operations
    MARINE_SURVEYOR = "marine_surveyor"     # Inspections and surveys
    PILOT = "pilot"                        # Harbor pilot services
    SECURITY_OFFICER = "security_officer"   # Port and vessel security
    EMERGENCY_RESPONDER = "emergency_responder" # Emergency services
    ADMIN = "admin"                        # System administration

class GeographicRestriction(Enum):
    """Geographic restrictions for data access"""
    UNRESTRICTED = "unrestricted"          # No geographic restrictions
    EU_ONLY = "eu_only"                    # European Union only
    NATIONAL_ONLY = "national_only"        # National boundaries only
    PORT_ONLY = "port_only"                # Port facility only
    VESSEL_ONLY = "vessel_only"            # Vessel-specific access
    EXPORT_CONTROLLED = "export_controlled" # Export control restrictions

@dataclass
class DataRetentionPolicy:
    """Data retention policy with maritime compliance requirements"""
    
    retention_days: int                    # Days to retain data
    archive_after_days: int               # Days before archiving
    purge_after_days: int                 # Days before secure deletion
    legal_hold_override: bool             # Legal hold can override policy
    regulation_basis: List[MaritimeRegulatory] # Regulations requiring retention
    backup_required: bool = True          # Requires secure backup
    immutable_required: bool = False      # Requires immutable storage
    
    def is_retention_expired(self, created_date: datetime) -> bool:
        """Check if retention period has expired"""
        expiry_date = created_date + timedelta(days=self.retention_days)
        return datetime.now(timezone.utc) > expiry_date
    
    def should_archive(self, created_date: datetime) -> bool:
        """Check if data should be archived"""
        archive_date = created_date + timedelta(days=self.archive_after_days)
        return datetime.now(timezone.utc) > archive_date
    
    def should_purge(self, created_date: datetime) -> bool:
        """Check if data should be purged"""
        if self.legal_hold_override:
            return False  # Cannot purge under legal hold
        
        purge_date = created_date + timedelta(days=self.purge_after_days)
        return datetime.now(timezone.utc) > purge_date

@dataclass
class DataClassificationRule:
    """Data classification rule with maritime context"""
    
    rule_id: str                          # Unique rule identifier
    name: str                             # Human-readable rule name
    field_patterns: List[str]             # Field name patterns to match
    content_patterns: List[str]           # Content patterns to match
    data_types: List[str]                 # Data types this rule applies to
    classification: MaritimeDataClassification # Assigned classification
    regulations: List[MaritimeRegulatory] # Applicable regulations
    retention_policy: DataRetentionPolicy # Data retention requirements
    access_roles: List[UserRole]          # Roles allowed to access
    geographic_restrictions: List[GeographicRestriction] # Geographic access limits
    requires_encryption: bool             # Encryption requirement
    audit_required: bool                  # Audit logging requirement
    export_restricted: bool               # Export control restrictions
    personal_data_types: List[PersonalDataType] = field(default_factory=list)
    data_subjects: List[MaritimeDataSubject] = field(default_factory=list)
    priority: int = 5                     # Rule priority (1-10, higher wins)
    active: bool = True                   # Rule is active
    
    def matches_field(self, field_name: str) -> bool:
        """Check if field name matches patterns"""
        if not self.active or not self.field_patterns:
            return False
            
        field_lower = field_name.lower()
        return any(
            re.search(pattern.lower(), field_lower) 
            for pattern in self.field_patterns
        )
    
    def matches_content(self, content: Any) -> bool:
        """Check if content matches patterns"""
        if not self.active or not self.content_patterns:
            return False
        
        content_str = str(content).lower()
        return any(
            re.search(pattern.lower(), content_str) 
            for pattern in self.content_patterns
        )
    
    def matches_data_type(self, data_type: str) -> bool:
        """Check if data type matches"""
        if not self.data_types:
            return True  # Match all types if none specified
        return data_type.lower() in [dt.lower() for dt in self.data_types]

@dataclass
class ClassificationResult:
    """Result of data classification analysis"""
    
    classification: MaritimeDataClassification
    confidence: float                      # Classification confidence (0-1)
    matched_rules: List[Dict[str, Any]]    # Rules that matched with details
    regulations: List[MaritimeRegulatory]  # Applicable regulations
    retention_policy: DataRetentionPolicy  # Retention requirements
    access_roles: List[UserRole]           # Authorized roles
    geographic_restrictions: List[GeographicRestriction] # Geographic limits
    requires_encryption: bool              # Encryption requirement
    audit_required: bool                   # Audit requirement
    export_restricted: bool                # Export restrictions
    personal_data_types: List[PersonalDataType] # GDPR personal data types
    data_subjects: List[MaritimeDataSubject] # GDPR data subjects
    warnings: List[str]                    # Classification warnings
    recommendations: List[str]             # Security recommendations
    classification_timestamp: str          # When classification was performed
    classification_id: str                 # Unique classification ID
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'classification': self.classification.name,
            'classification_level': self.classification.value,
            'confidence': self.confidence,
            'matched_rules': self.matched_rules,
            'regulations': [reg.value for reg in self.regulations],
            'retention_policy': {
                'retention_days': self.retention_policy.retention_days,
                'archive_after_days': self.retention_policy.archive_after_days,
                'purge_after_days': self.retention_policy.purge_after_days,
                'legal_hold_override': self.retention_policy.legal_hold_override,
                'regulation_basis': [reg.value for reg in self.retention_policy.regulation_basis],
                'backup_required': self.retention_policy.backup_required,
                'immutable_required': self.retention_policy.immutable_required
            },
            'access_roles': [role.value for role in self.access_roles],
            'geographic_restrictions': [gr.value for gr in self.geographic_restrictions],
            'requires_encryption': self.requires_encryption,
            'audit_required': self.audit_required,
            'export_restricted': self.export_restricted,
            'personal_data_types': [pdt.value for pdt in self.personal_data_types],
            'data_subjects': [ds.value for ds in self.data_subjects],
            'warnings': self.warnings,
            'recommendations': self.recommendations,
            'classification_timestamp': self.classification_timestamp,
            'classification_id': self.classification_id
        }

class MaritimeDataClassifier:
    """Maritime data classification engine with international compliance"""
    
    def __init__(self):
        self.classification_rules = self._initialize_classification_rules()
        self.audit_logger = self._get_audit_logger()
        
        # Maritime-specific settings
        self.sensitive_imo_countries = {'IR', 'KP', 'SY', 'AF', 'BY', 'MM', 'VE'}
        self.eu_countries = {
            'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
            'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
            'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
        }
        
        # Pattern libraries for enhanced classification
        self.personal_data_patterns = {
            PersonalDataType.BASIC_IDENTITY: [
                r'\b(name|first_name|last_name|full_name)\b',
                r'\b(email|email_address|contact_email)\b',
                r'\b(phone|telephone|mobile|contact_number)\b',
                r'\b(address|home_address|contact_address)\b'
            ],
            PersonalDataType.SENSITIVE_IDENTITY: [
                r'\b(passport|passport_number|passport_id)\b',
                r'\b(ssn|social_security|national_id)\b',
                r'\b(license|driving_license|pilot_license)\b',
                r'\b(certificate|medical_certificate|training_cert)\b'
            ],
            PersonalDataType.BIOMETRIC: [
                r'\b(fingerprint|biometric|photo|image)\b',
                r'\b(medical_data|health_record|medical_info)\b',
                r'\b(dna|genetic|biological)\b'
            ],
            PersonalDataType.LOCATION: [
                r'\b(gps|location|position|coordinates)\b',
                r'\b(latitude|longitude|lat|lon)\b',
                r'\b(tracking|vessel_position|ship_location)\b'
            ],
            PersonalDataType.FINANCIAL: [
                r'\b(salary|wage|payment|compensation)\b',
                r'\b(bank|account|financial|tax)\b',
                r'\b(credit|debit|payment_method)\b'
            ]
        }
        
        self.maritime_sensitive_patterns = {
            'security': [
                r'\b(security|isps|threat|terrorism)\b',
                r'\b(restricted|classified|confidential)\b',
                r'\b(access_control|security_plan)\b'
            ],
            'safety': [
                r'\b(safety|solas|emergency|accident)\b',
                r'\b(incident|injury|casualty|fatality)\b',
                r'\b(hazard|dangerous|toxic|explosive)\b'
            ],
            'environmental': [
                r'\b(pollution|marpol|oil_spill|discharge)\b',
                r'\b(waste|garbage|sewage|ballast)\b',
                r'\b(emission|environmental|ecology)\b'
            ],
            'customs': [
                r'\b(customs|import|export|duty)\b',
                r'\b(declaration|manifest|cargo_list)\b',
                r'\b(contraband|smuggling|prohibited)\b'
            ]
        }
        
        logger.info("Maritime data classifier initialized with comprehensive compliance rules")
    
    def _get_audit_logger(self):
        """Get audit logger for classification operations"""
        try:
            from .audit_logger import get_audit_logger
            return get_audit_logger()
        except ImportError:
            logger.warning("Audit logger not available - classification will not be audited")
            return None
    
    def _initialize_classification_rules(self) -> List[DataClassificationRule]:
        """Initialize comprehensive maritime data classification rules"""
        
        # Define retention policies for different compliance requirements
        solas_safety_retention = DataRetentionPolicy(
            retention_days=DataRetentionPeriod.SOLAS_SAFETY.value,
            archive_after_days=5 * 365,  # 5 years
            purge_after_days=30 * 365,   # 30 years (with 5-year grace period)
            legal_hold_override=True,
            regulation_basis=[MaritimeRegulatory.SOLAS],
            backup_required=True,
            immutable_required=True
        )
        
        marpol_environmental_retention = DataRetentionPolicy(
            retention_days=DataRetentionPeriod.MARPOL_ENVIRONMENTAL.value,
            archive_after_days=3 * 365,  # 3 years
            purge_after_days=15 * 365,   # 15 years
            legal_hold_override=True,
            regulation_basis=[MaritimeRegulatory.MARPOL],
            backup_required=True,
            immutable_required=True
        )
        
        isps_security_retention = DataRetentionPolicy(
            retention_days=DataRetentionPeriod.ISPS_SECURITY.value,
            archive_after_days=5 * 365,  # 5 years
            purge_after_days=20 * 365,   # 20 years
            legal_hold_override=True,
            regulation_basis=[MaritimeRegulatory.ISPS],
            backup_required=True,
            immutable_required=True
        )
        
        gdpr_personal_retention = DataRetentionPolicy(
            retention_days=DataRetentionPeriod.GDPR_PERSONAL.value,
            archive_after_days=365,      # 1 year
            purge_after_days=3 * 365,    # 3 years
            legal_hold_override=False,   # GDPR right to erasure
            regulation_basis=[MaritimeRegulatory.GDPR],
            backup_required=True,
            immutable_required=False
        )
        
        sox_financial_retention = DataRetentionPolicy(
            retention_days=DataRetentionPeriod.SOX_FINANCIAL.value,
            archive_after_days=2 * 365,  # 2 years
            purge_after_days=10 * 365,   # 10 years
            legal_hold_override=True,
            regulation_basis=[MaritimeRegulatory.SOX],
            backup_required=True,
            immutable_required=True
        )
        
        operational_default_retention = DataRetentionPolicy(
            retention_days=DataRetentionPeriod.OPERATIONAL_DEFAULT.value,
            archive_after_days=180,      # 6 months
            purge_after_days=2 * 365,    # 2 years
            legal_hold_override=False,
            regulation_basis=[],
            backup_required=False,
            immutable_required=False
        )
        
        rules = [
            # SECRET - Critical national security and counter-terrorism
            DataClassificationRule(
                rule_id="MARITIME_SECRET_001",
                name="Critical Security Intelligence",
                field_patterns=[
                    r'security_clearance', r'classified_info', r'intelligence_report',
                    r'threat_assessment', r'counter_terrorism', r'national_security'
                ],
                content_patterns=[
                    r'top secret', r'classified', r'security threat', r'terrorist',
                    r'national security', r'counter intelligence', r'surveillance'
                ],
                data_types=['security', 'intelligence', 'threat'],
                classification=MaritimeDataClassification.SECRET,
                regulations=[MaritimeRegulatory.ISPS, MaritimeRegulatory.CUSTOMS],
                retention_policy=isps_security_retention,
                access_roles=[UserRole.SECURITY_OFFICER, UserRole.PORT_AUTHORITY],
                geographic_restrictions=[GeographicRestriction.NATIONAL_ONLY],
                requires_encryption=True,
                audit_required=True,
                export_restricted=True,
                priority=10
            ),
            
            # RESTRICTED - Vessel Security and ISPS Compliance
            DataClassificationRule(
                rule_id="MARITIME_RESTRICTED_001",
                name="ISPS Security Plans and Certificates",
                field_patterns=[
                    r'isps_certificate', r'security_plan', r'vessel_security',
                    r'port_facility_security', r'security_assessment', r'access_control'
                ],
                content_patterns=[
                    r'isps', r'security plan', r'restricted area', r'security level',
                    r'access control', r'security officer', r'security equipment'
                ],
                data_types=['security', 'certificate', 'plan'],
                classification=MaritimeDataClassification.RESTRICTED,
                regulations=[MaritimeRegulatory.ISPS, MaritimeRegulatory.SOLAS],
                retention_policy=isps_security_retention,
                access_roles=[
                    UserRole.SECURITY_OFFICER, UserRole.PORT_AUTHORITY, 
                    UserRole.VESSEL_OPERATOR, UserRole.CUSTOMS_OFFICER
                ],
                geographic_restrictions=[GeographicRestriction.PORT_ONLY],
                requires_encryption=True,
                audit_required=True,
                export_restricted=True,
                priority=9
            ),
            
            # RESTRICTED - Safety Critical Data (SOLAS)
            DataClassificationRule(
                rule_id="MARITIME_RESTRICTED_002",
                name="SOLAS Safety Critical Data",
                field_patterns=[
                    r'safety_certificate', r'solas_certificate', r'inspection_report',
                    r'deficiency_report', r'emergency_plan', r'safety_management'
                ],
                content_patterns=[
                    r'safety deficiency', r'unsafe condition', r'psc detention',
                    r'emergency response', r'life saving', r'fire safety', r'structural_integrity'
                ],
                data_types=['safety', 'certificate', 'inspection', 'emergency'],
                classification=MaritimeDataClassification.RESTRICTED,
                regulations=[MaritimeRegulatory.SOLAS, MaritimeRegulatory.STCW],
                retention_policy=solas_safety_retention,
                access_roles=[
                    UserRole.PORT_AUTHORITY, UserRole.MARINE_SURVEYOR, 
                    UserRole.VESSEL_OPERATOR, UserRole.EMERGENCY_RESPONDER
                ],
                geographic_restrictions=[GeographicRestriction.UNRESTRICTED],
                requires_encryption=True,
                audit_required=True,
                export_restricted=False,
                priority=9
            ),
            
            # RESTRICTED - Customs and Trade Security
            DataClassificationRule(
                rule_id="MARITIME_RESTRICTED_003",
                name="Customs and Trade Security",
                field_patterns=[
                    r'customs_declaration', r'c_tpat', r'aeo_certificate',
                    r'customs_bond', r'duty_calculation', r'trade_security'
                ],
                content_patterns=[
                    r'customs examination', r'prohibited goods', r'duty evasion',
                    r'contraband', r'suspicious cargo', r'trade violation'
                ],
                data_types=['customs', 'trade', 'security'],
                classification=MaritimeDataClassification.RESTRICTED,
                regulations=[MaritimeRegulatory.CUSTOMS],
                retention_policy=DataRetentionPolicy(
                    retention_days=DataRetentionPeriod.CUSTOMS_TRADE.value,
                    archive_after_days=2 * 365,
                    purge_after_days=10 * 365,
                    legal_hold_override=True,
                    regulation_basis=[MaritimeRegulatory.CUSTOMS],
                    backup_required=True,
                    immutable_required=True
                ),
                access_roles=[UserRole.CUSTOMS_OFFICER, UserRole.PORT_AUTHORITY],
                geographic_restrictions=[GeographicRestriction.NATIONAL_ONLY],
                requires_encryption=True,
                audit_required=True,
                export_restricted=True,
                priority=9
            ),
            
            # CONFIDENTIAL - Personal Data (GDPR)
            DataClassificationRule(
                rule_id="MARITIME_CONFIDENTIAL_001",
                name="Personal Data - GDPR Protected",
                field_patterns=[
                    r'crew_list', r'passenger_list', r'personal_data', r'contact_info',
                    r'email', r'phone', r'address', r'passport', r'national_id'
                ],
                content_patterns=[
                    r'personal information', r'crew member', r'passenger',
                    r'contact details', r'identity document', r'private data'
                ],
                data_types=['personal', 'crew', 'passenger', 'contact'],
                classification=MaritimeDataClassification.CONFIDENTIAL,
                regulations=[MaritimeRegulatory.GDPR, MaritimeRegulatory.MLC],
                retention_policy=gdpr_personal_retention,
                access_roles=[
                    UserRole.VESSEL_OPERATOR, UserRole.PORT_AUTHORITY, 
                    UserRole.ADMIN
                ],
                geographic_restrictions=[GeographicRestriction.EU_ONLY],
                requires_encryption=True,
                audit_required=True,
                export_restricted=False,
                personal_data_types=[
                    PersonalDataType.BASIC_IDENTITY,
                    PersonalDataType.SENSITIVE_IDENTITY,
                    PersonalDataType.CONTRACTUAL
                ],
                data_subjects=[
                    MaritimeDataSubject.CREW_MEMBER,
                    MaritimeDataSubject.PASSENGER,
                    MaritimeDataSubject.PORT_WORKER
                ],
                priority=8
            ),
            
            # CONFIDENTIAL - Medical and Health Data
            DataClassificationRule(
                rule_id="MARITIME_CONFIDENTIAL_002",
                name="Medical and Health Records",
                field_patterns=[
                    r'medical_certificate', r'health_record', r'medical_data',
                    r'vaccination', r'medical_examination', r'fitness_certificate'
                ],
                content_patterns=[
                    r'medical condition', r'health status', r'medical treatment',
                    r'vaccination record', r'medical fitness', r'health clearance'
                ],
                data_types=['medical', 'health', 'certificate'],
                classification=MaritimeDataClassification.CONFIDENTIAL,
                regulations=[MaritimeRegulatory.GDPR, MaritimeRegulatory.HIPAA, MaritimeRegulatory.MLC],
                retention_policy=DataRetentionPolicy(
                    retention_days=DataRetentionPeriod.MLC_LABOUR.value,
                    archive_after_days=365,
                    purge_after_days=5 * 365,
                    legal_hold_override=False,
                    regulation_basis=[MaritimeRegulatory.GDPR, MaritimeRegulatory.MLC],
                    backup_required=True,
                    immutable_required=False
                ),
                access_roles=[
                    UserRole.VESSEL_OPERATOR, UserRole.PORT_AUTHORITY,
                    UserRole.MARINE_SURVEYOR
                ],
                geographic_restrictions=[GeographicRestriction.EU_ONLY],
                requires_encryption=True,
                audit_required=True,
                export_restricted=True,
                personal_data_types=[PersonalDataType.MEDICAL, PersonalDataType.BIOMETRIC],
                data_subjects=[
                    MaritimeDataSubject.CREW_MEMBER,
                    MaritimeDataSubject.PORT_WORKER
                ],
                priority=8
            ),
            
            # CONFIDENTIAL - Commercial and Cargo Information
            DataClassificationRule(
                rule_id="MARITIME_CONFIDENTIAL_003",
                name="Commercial and Cargo Information",
                field_patterns=[
                    r'cargo_manifest', r'bill_of_lading', r'commercial_invoice',
                    r'shipping_instruction', r'cargo_value', r'freight_rate'
                ],
                content_patterns=[
                    r'dangerous goods', r'hazardous cargo', r'commercial value',
                    r'shipper details', r'consignee', r'freight charges'
                ],
                data_types=['cargo', 'commercial', 'manifest'],
                classification=MaritimeDataClassification.CONFIDENTIAL,
                regulations=[MaritimeRegulatory.CUSTOMS, MaritimeRegulatory.MARPOL],
                retention_policy=DataRetentionPolicy(
                    retention_days=7 * 365,  # 7 years standard
                    archive_after_days=2 * 365,
                    purge_after_days=10 * 365,
                    legal_hold_override=True,
                    regulation_basis=[MaritimeRegulatory.CUSTOMS],
                    backup_required=True,
                    immutable_required=False
                ),
                access_roles=[
                    UserRole.STEVEDORE, UserRole.TERMINAL_OPERATOR,
                    UserRole.CUSTOMS_OFFICER, UserRole.VESSEL_OPERATOR
                ],
                geographic_restrictions=[GeographicRestriction.UNRESTRICTED],
                requires_encryption=True,
                audit_required=True,
                export_restricted=False,
                priority=7
            ),
            
            # CONFIDENTIAL - Environmental Compliance (MARPOL)
            DataClassificationRule(
                rule_id="MARITIME_CONFIDENTIAL_004",
                name="Environmental Compliance Data",
                field_patterns=[
                    r'oil_record_book', r'garbage_record', r'ballast_water',
                    r'emission_report', r'environmental_log', r'pollution_incident'
                ],
                content_patterns=[
                    r'oil discharge', r'pollution incident', r'environmental violation',
                    r'marpol', r'waste disposal', r'emission levels'
                ],
                data_types=['environmental', 'pollution', 'emission'],
                classification=MaritimeDataClassification.CONFIDENTIAL,
                regulations=[MaritimeRegulatory.MARPOL, MaritimeRegulatory.ENVIRONMENTAL],
                retention_policy=marpol_environmental_retention,
                access_roles=[
                    UserRole.VESSEL_OPERATOR, UserRole.PORT_AUTHORITY,
                    UserRole.MARINE_SURVEYOR
                ],
                geographic_restrictions=[GeographicRestriction.UNRESTRICTED],
                requires_encryption=True,
                audit_required=True,
                export_restricted=False,
                priority=7
            ),
            
            # CONFIDENTIAL - Financial Records (SOX)
            DataClassificationRule(
                rule_id="MARITIME_CONFIDENTIAL_005",
                name="Financial Records and Controls",
                field_patterns=[
                    r'financial_record', r'payment', r'invoice', r'account',
                    r'audit_trail', r'financial_control', r'revenue'
                ],
                content_patterns=[
                    r'financial transaction', r'payment record', r'audit control',
                    r'financial reporting', r'revenue recognition'
                ],
                data_types=['financial', 'payment', 'audit'],
                classification=MaritimeDataClassification.CONFIDENTIAL,
                regulations=[MaritimeRegulatory.SOX],
                retention_policy=sox_financial_retention,
                access_roles=[UserRole.ADMIN, UserRole.PORT_AUTHORITY],
                geographic_restrictions=[GeographicRestriction.UNRESTRICTED],
                requires_encryption=True,
                audit_required=True,
                export_restricted=False,
                priority=7
            ),
            
            # INTERNAL - Operational Data
            DataClassificationRule(
                rule_id="MARITIME_INTERNAL_001",
                name="Maritime Operational Data",
                field_patterns=[
                    r'cargo_tally', r'vessel_schedule', r'berth_assignment',
                    r'work_order', r'terminal_operation', r'loading_plan'
                ],
                content_patterns=[
                    r'cargo operations', r'vessel movement', r'terminal operations',
                    r'work schedule', r'berth allocation', r'loading sequence'
                ],
                data_types=['operational', 'schedule', 'tally'],
                classification=MaritimeDataClassification.INTERNAL,
                regulations=[MaritimeRegulatory.SOLAS],
                retention_policy=operational_default_retention,
                access_roles=[
                    UserRole.STEVEDORE, UserRole.TERMINAL_OPERATOR,
                    UserRole.PORT_AUTHORITY, UserRole.PILOT, UserRole.VESSEL_OPERATOR
                ],
                geographic_restrictions=[GeographicRestriction.PORT_ONLY],
                requires_encryption=False,
                audit_required=False,
                export_restricted=False,
                priority=5
            ),
            
            # INTERNAL - Training and Certification
            DataClassificationRule(
                rule_id="MARITIME_INTERNAL_002",
                name="Training and Certification Records",
                field_patterns=[
                    r'training_record', r'certification', r'competency',
                    r'stcw_certificate', r'training_plan', r'skill_assessment'
                ],
                content_patterns=[
                    r'training completion', r'certification status', r'competency assessment',
                    r'skill development', r'training requirement'
                ],
                data_types=['training', 'certification', 'competency'],
                classification=MaritimeDataClassification.INTERNAL,
                regulations=[MaritimeRegulatory.STCW, MaritimeRegulatory.MLC],
                retention_policy=DataRetentionPolicy(
                    retention_days=DataRetentionPeriod.STCW_TRAINING.value,
                    archive_after_days=2 * 365,
                    purge_after_days=7 * 365,
                    legal_hold_override=False,
                    regulation_basis=[MaritimeRegulatory.STCW],
                    backup_required=True,
                    immutable_required=False
                ),
                access_roles=[
                    UserRole.VESSEL_OPERATOR, UserRole.PORT_AUTHORITY,
                    UserRole.MARINE_SURVEYOR, UserRole.ADMIN
                ],
                geographic_restrictions=[GeographicRestriction.UNRESTRICTED],
                requires_encryption=False,
                audit_required=True,
                export_restricted=False,
                priority=5
            ),
            
            # PUBLIC - General Maritime Information
            DataClassificationRule(
                rule_id="MARITIME_PUBLIC_001",
                name="Public Maritime Information",
                field_patterns=[
                    r'vessel_name', r'flag_state', r'port_schedule',
                    r'weather_info', r'tide_table', r'public_notice'
                ],
                content_patterns=[
                    r'public information', r'general maritime', r'published schedule',
                    r'weather forecast', r'public notice', r'general announcement'
                ],
                data_types=['public', 'schedule', 'weather', 'notice'],
                classification=MaritimeDataClassification.PUBLIC,
                regulations=[],
                retention_policy=DataRetentionPolicy(
                    retention_days=365,  # 1 year
                    archive_after_days=180,
                    purge_after_days=2 * 365,
                    legal_hold_override=False,
                    regulation_basis=[],
                    backup_required=False,
                    immutable_required=False
                ),
                access_roles=list(UserRole),  # All roles can access
                geographic_restrictions=[GeographicRestriction.UNRESTRICTED],
                requires_encryption=False,
                audit_required=False,
                export_restricted=False,
                priority=1
            )
        ]
        
        return rules
    
    def classify_data(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ClassificationResult:
        """
        Classify maritime data according to international regulations
        
        Args:
            data: Data to classify
            context: Additional context (vessel_id, user_role, etc.)
            
        Returns:
            ClassificationResult: Comprehensive classification analysis
        """
        try:
            classification_id = str(uuid.uuid4())
            classification_timestamp = datetime.now(timezone.utc).isoformat()
            
            matched_rules = []
            all_classifications = []
            all_regulations = set()
            all_personal_data_types = set()
            all_data_subjects = set()
            warnings = []
            recommendations = []
            
            # Enhanced pattern matching with context awareness
            for field_name, field_value in data.items():
                field_rules = self._find_matching_rules(field_name, field_value, context)
                
                for rule in field_rules:
                    matched_rules.append({
                        'rule_id': rule.rule_id,
                        'name': rule.name,
                        'field_matched': field_name,
                        'classification': rule.classification.name,
                        'priority': rule.priority,
                        'confidence': self._calculate_rule_confidence(rule, field_name, field_value)
                    })
                    
                    all_classifications.append(rule.classification)
                    all_regulations.update(rule.regulations)
                    all_personal_data_types.update(rule.personal_data_types)
                    all_data_subjects.update(rule.data_subjects)
            
            # Apply contextual classification rules
            if context:
                context_rules = self._apply_contextual_classification(data, context)
                matched_rules.extend(context_rules)
                for rule_info in context_rules:
                    all_classifications.append(MaritimeDataClassification[rule_info['classification']])
            
            # Determine final classification using priority-weighted algorithm
            final_classification = self._determine_final_classification(
                all_classifications, matched_rules
            )
            
            # Calculate overall confidence
            confidence = self._calculate_overall_confidence(matched_rules, data)
            
            # Get consolidated requirements
            result_rule = self._get_consolidated_requirements(
                final_classification, matched_rules, all_regulations
            )
            
            # Enhanced context processing
            if context:
                self._apply_enhanced_context_requirements(
                    result_rule, context, warnings, recommendations
                )
            
            # Generate comprehensive warnings and recommendations
            self._generate_comprehensive_analysis(
                data, final_classification, matched_rules, warnings, recommendations, context
            )
            
            # Audit logging
            self._log_classification_event(
                final_classification, confidence, matched_rules, context, classification_id
            )
            
            return ClassificationResult(
                classification=final_classification,
                confidence=confidence,
                matched_rules=matched_rules,
                regulations=list(all_regulations),
                retention_policy=result_rule['retention_policy'],
                access_roles=result_rule['access_roles'],
                geographic_restrictions=result_rule['geographic_restrictions'],
                requires_encryption=result_rule['requires_encryption'],
                audit_required=result_rule['audit_required'],
                export_restricted=result_rule['export_restricted'],
                personal_data_types=list(all_personal_data_types),
                data_subjects=list(all_data_subjects),
                warnings=warnings,
                recommendations=recommendations,
                classification_timestamp=classification_timestamp,
                classification_id=classification_id
            )
            
        except Exception as e:
            logger.error(f"Failed to classify data: {e}")
            return self._get_safe_default_classification(str(e))
    
    def _find_matching_rules(
        self, 
        field_name: str, 
        field_value: Any, 
        context: Optional[Dict[str, Any]] = None
    ) -> List[DataClassificationRule]:
        """Find rules that match field name, content, and context"""
        matching_rules = []
        data_type = context.get('data_type', 'unknown') if context else 'unknown'
        
        for rule in self.classification_rules:
            if not rule.active:
                continue
                
            # Check data type compatibility
            if not rule.matches_data_type(data_type):
                continue
            
            # Check field pattern match
            field_match = rule.matches_field(field_name)
            
            # Check content pattern match
            content_match = rule.matches_content(field_value)
            
            # Enhanced personal data detection
            personal_data_match = self._check_personal_data_patterns(field_name, field_value)
            
            # Maritime-specific pattern matching
            maritime_match = self._check_maritime_patterns(field_name, field_value)
            
            if field_match or content_match or personal_data_match or maritime_match:
                matching_rules.append(rule)
        
        # Sort by priority (higher priority first)
        matching_rules.sort(key=lambda x: x.priority, reverse=True)
        
        return matching_rules
    
    def _check_personal_data_patterns(self, field_name: str, field_value: Any) -> bool:
        """Enhanced personal data pattern detection"""
        field_str = field_name.lower()
        value_str = str(field_value).lower()
        combined_str = f"{field_str} {value_str}"
        
        for data_type, patterns in self.personal_data_patterns.items():
            for pattern in patterns:
                if re.search(pattern, combined_str):
                    return True
        
        return False
    
    def _check_maritime_patterns(self, field_name: str, field_value: Any) -> bool:
        """Enhanced maritime-specific pattern detection"""
        field_str = field_name.lower()
        value_str = str(field_value).lower()
        combined_str = f"{field_str} {value_str}"
        
        for category, patterns in self.maritime_sensitive_patterns.items():
            for pattern in patterns:
                if re.search(pattern, combined_str):
                    return True
        
        return False
    
    def _calculate_rule_confidence(
        self, 
        rule: DataClassificationRule, 
        field_name: str, 
        field_value: Any
    ) -> float:
        """Calculate confidence score for rule match"""
        confidence = 0.0
        
        # Field pattern match confidence
        if rule.matches_field(field_name):
            confidence += 0.4
        
        # Content pattern match confidence
        if rule.matches_content(field_value):
            confidence += 0.4
        
        # Personal data pattern confidence
        if self._check_personal_data_patterns(field_name, field_value):
            confidence += 0.3
        
        # Maritime pattern confidence
        if self._check_maritime_patterns(field_name, field_value):
            confidence += 0.3
        
        # Priority weight (higher priority = higher confidence)
        priority_weight = rule.priority / 10.0
        confidence *= priority_weight
        
        return min(confidence, 1.0)
    
    def _apply_contextual_classification(
        self, 
        data: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply contextual classification rules"""
        context_rules = []
        
        # Vessel flag state considerations
        vessel_flag = context.get('vessel_flag_state', '').upper()
        if vessel_flag in self.sensitive_imo_countries:
            context_rules.append({
                'rule_id': 'CONTEXT_FLAG_STATE',
                'name': 'Sensitive Flag State Classification',
                'field_matched': 'context.vessel_flag_state',
                'classification': MaritimeDataClassification.RESTRICTED.name,
                'priority': 8,
                'confidence': 0.8
            })
        
        # Emergency context
        if context.get('is_emergency', False):
            context_rules.append({
                'rule_id': 'CONTEXT_EMERGENCY',
                'name': 'Emergency Context Classification',
                'field_matched': 'context.is_emergency',
                'classification': MaritimeDataClassification.RESTRICTED.name,
                'priority': 9,
                'confidence': 0.9
            })
        
        # High security port
        port_security_level = context.get('port_security_level', 1)
        if port_security_level >= 3:
            context_rules.append({
                'rule_id': 'CONTEXT_HIGH_SECURITY',
                'name': 'High Security Port Classification',
                'field_matched': 'context.port_security_level',
                'classification': MaritimeDataClassification.RESTRICTED.name,
                'priority': 7,
                'confidence': 0.7
            })
        
        # User role elevation
        user_role = context.get('user_role', '').lower()
        if user_role in ['customs_officer', 'security_officer']:
            context_rules.append({
                'rule_id': 'CONTEXT_PRIVILEGED_USER',
                'name': 'Privileged User Context',
                'field_matched': 'context.user_role',
                'classification': MaritimeDataClassification.CONFIDENTIAL.name,
                'priority': 6,
                'confidence': 0.6
            })
        
        return context_rules
    
    def _determine_final_classification(
        self, 
        classifications: List[MaritimeDataClassification],
        matched_rules: List[Dict[str, Any]]
    ) -> MaritimeDataClassification:
        """Determine final classification using priority-weighted algorithm"""
        
        if not classifications:
            return MaritimeDataClassification.INTERNAL
        
        # Weight classifications by rule priority and confidence
        classification_scores = {}
        
        for i, classification in enumerate(classifications):
            if classification not in classification_scores:
                classification_scores[classification] = 0
            
            # Add weighted score based on rule priority and confidence
            if i < len(matched_rules):
                rule = matched_rules[i]
                weight = rule['priority'] * rule['confidence']
                classification_scores[classification] += weight
            else:
                classification_scores[classification] += classification.value
        
        # Return classification with highest weighted score
        final_classification = max(
            classification_scores.keys(),
            key=lambda x: classification_scores[x]
        )
        
        return final_classification
    
    def _calculate_overall_confidence(
        self, 
        matched_rules: List[Dict[str, Any]], 
        data: Dict[str, Any]
    ) -> float:
        """Calculate overall classification confidence"""
        
        if not matched_rules:
            return 0.1  # Low confidence for default classification
        
        # Average confidence weighted by rule priority
        total_weighted_confidence = 0
        total_weight = 0
        
        for rule in matched_rules:
            weight = rule['priority']
            confidence = rule['confidence']
            total_weighted_confidence += confidence * weight
            total_weight += weight
        
        base_confidence = total_weighted_confidence / total_weight if total_weight > 0 else 0
        
        # Adjust based on number of fields vs matched rules
        field_coverage = len(matched_rules) / max(len(data), 1)
        coverage_bonus = min(field_coverage * 0.2, 0.2)
        
        final_confidence = min(base_confidence + coverage_bonus, 1.0)
        return round(final_confidence, 3)
    
    def _get_consolidated_requirements(
        self,
        classification: MaritimeDataClassification,
        matched_rules: List[Dict[str, Any]],
        regulations: Set[MaritimeRegulatory]
    ) -> Dict[str, Any]:
        """Get consolidated security and compliance requirements"""
        
        # Find the most restrictive rule for this classification
        base_rule = None
        for rule in self.classification_rules:
            if rule.classification == classification:
                base_rule = rule
                break
        
        if not base_rule:
            # Create safe default
            base_rule = self.classification_rules[-1]  # Use most restrictive default
        
        # Consolidate requirements from all matched rules
        requires_encryption = base_rule.requires_encryption
        audit_required = base_rule.audit_required
        export_restricted = base_rule.export_restricted
        access_roles = set(base_rule.access_roles)
        geographic_restrictions = set(base_rule.geographic_restrictions)
        
        # Apply more restrictive requirements from matched rules
        for rule_dict in matched_rules:
            rule = next(
                (r for r in self.classification_rules if r.rule_id == rule_dict['rule_id']),
                None
            )
            if rule:
                requires_encryption = requires_encryption or rule.requires_encryption
                audit_required = audit_required or rule.audit_required
                export_restricted = export_restricted or rule.export_restricted
                access_roles.intersection_update(rule.access_roles)
                geographic_restrictions.update(rule.geographic_restrictions)
        
        return {
            'retention_policy': base_rule.retention_policy,
            'requires_encryption': requires_encryption,
            'audit_required': audit_required,
            'export_restricted': export_restricted,
            'access_roles': list(access_roles),
            'geographic_restrictions': list(geographic_restrictions)
        }
    
    def _apply_enhanced_context_requirements(
        self,
        requirements: Dict[str, Any],
        context: Dict[str, Any],
        warnings: List[str],
        recommendations: List[str]
    ):
        """Apply enhanced context-specific requirements"""
        
        # Vessel flag state restrictions
        vessel_flag = context.get('vessel_flag_state', '').upper()
        if vessel_flag in self.sensitive_imo_countries:
            requirements['export_restricted'] = True
            requirements['geographic_restrictions'] = [GeographicRestriction.NATIONAL_ONLY]
            warnings.append(f"Vessel flag state {vessel_flag} requires enhanced export restrictions")
            recommendations.append("Implement additional access controls for sensitive flag state")
        
        # EU GDPR compliance
        user_location = context.get('user_location', '').upper()
        if user_location in self.eu_countries:
            if not any(isinstance(gr, GeographicRestriction) and gr == GeographicRestriction.EU_ONLY 
                      for gr in requirements['geographic_restrictions']):
                recommendations.append("Consider EU-specific data handling procedures for GDPR compliance")
        
        # Emergency escalation
        if context.get('is_emergency', False):
            requirements['audit_required'] = True
            recommendations.append("Emergency context requires comprehensive audit trail and immediate backup")
        
        # High-risk port operations
        port_security_level = context.get('port_security_level', 1)
        if port_security_level >= 3:
            requirements['requires_encryption'] = True
            requirements['audit_required'] = True
            warnings.append("High-risk port operations require enhanced security measures")
        
        # Time-sensitive operations
        operation_urgency = context.get('operation_urgency', 'normal')
        if operation_urgency in ['urgent', 'critical']:
            recommendations.append("Time-sensitive operations may require expedited processing with maintained security")
    
    def _generate_comprehensive_analysis(
        self,
        data: Dict[str, Any],
        classification: MaritimeDataClassification,
        matched_rules: List[Dict[str, Any]],
        warnings: List[str],
        recommendations: List[str],
        context: Optional[Dict[str, Any]] = None
    ):
        """Generate comprehensive security analysis with warnings and recommendations"""
        
        # Data sensitivity analysis
        sensitive_indicators = [
            'password', 'secret', 'key', 'token', 'imo', 'ssn', 'passport',
            'medical', 'financial', 'security', 'classified', 'restricted'
        ]
        
        data_str = json.dumps(data, default=str).lower()
        found_indicators = [indicator for indicator in sensitive_indicators if indicator in data_str]
        
        if found_indicators and classification.value <= MaritimeDataClassification.INTERNAL.value:
            warnings.append(
                f"Potentially sensitive data found ({', '.join(found_indicators)}) "
                f"but classified as {classification.name}"
            )
            recommendations.append("Review classification - sensitive data may require higher security level")
        
        # Regulatory compliance analysis
        regulation_conflicts = self._check_regulation_conflicts(matched_rules)
        if regulation_conflicts:
            warnings.extend(regulation_conflicts)
            recommendations.append("Resolve regulatory conflicts through data segregation or enhanced controls")
        
        # Access control analysis
        if len(matched_rules) > 5:
            warnings.append("High number of classification rules matched - may indicate over-broad data collection")
            recommendations.append("Consider data minimization to reduce classification complexity")
        
        # Geographic compliance analysis
        if context:
            geo_warnings = self._analyze_geographic_compliance(context, matched_rules)
            warnings.extend(geo_warnings)
        
        # Retention analysis
        retention_warnings = self._analyze_retention_requirements(matched_rules)
        warnings.extend(retention_warnings)
        
        # Security recommendations
        security_recs = self._generate_security_recommendations(classification, matched_rules, context)
        recommendations.extend(security_recs)
    
    def _check_regulation_conflicts(self, matched_rules: List[Dict[str, Any]]) -> List[str]:
        """Check for conflicts between different regulatory requirements"""
        conflicts = []
        
        # Check for GDPR vs long-term retention conflicts
        has_gdpr = any('gdpr' in str(rule).lower() for rule in matched_rules)
        has_long_retention = any(rule.get('priority', 0) >= 8 for rule in matched_rules)
        
        if has_gdpr and has_long_retention:
            conflicts.append(
                "GDPR data subject rights may conflict with long-term maritime retention requirements"
            )
        
        return conflicts
    
    def _analyze_geographic_compliance(
        self, 
        context: Dict[str, Any], 
        matched_rules: List[Dict[str, Any]]
    ) -> List[str]:
        """Analyze geographic compliance requirements"""
        warnings = []
        
        user_location = context.get('user_location', '').upper()
        vessel_flag = context.get('vessel_flag_state', '').upper()
        
        # Check for export control issues
        if vessel_flag in self.sensitive_imo_countries and user_location not in self.sensitive_imo_countries:
            warnings.append(
                f"Potential export control violation: sensitive flag state {vessel_flag} data "
                f"accessed from {user_location}"
            )
        
        # Check EU data adequacy
        if user_location in self.eu_countries and vessel_flag not in self.eu_countries:
            warnings.append(
                "Cross-border data transfer from EU may require adequacy decision or safeguards"
            )
        
        return warnings
    
    def _analyze_retention_requirements(self, matched_rules: List[Dict[str, Any]]) -> List[str]:
        """Analyze data retention requirement conflicts"""
        warnings = []
        
        # Extract retention periods from rules
        retention_periods = []
        for rule_dict in matched_rules:
            rule = next(
                (r for r in self.classification_rules if r.rule_id == rule_dict['rule_id']),
                None
            )
            if rule:
                retention_periods.append(rule.retention_policy.retention_days)
        
        if len(set(retention_periods)) > 2:  # More than 2 different retention periods
            warnings.append(
                "Multiple conflicting retention requirements found - using longest period"
            )
        
        return warnings
    
    def _generate_security_recommendations(
        self,
        classification: MaritimeDataClassification,
        matched_rules: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Generate security-specific recommendations"""
        recommendations = []
        
        # Classification-based recommendations
        if classification.value >= MaritimeDataClassification.CONFIDENTIAL.value:
            recommendations.append("Implement encryption at rest and in transit")
            recommendations.append("Enable comprehensive audit logging")
            recommendations.append("Restrict access to authorized personnel only")
        
        if classification.value >= MaritimeDataClassification.RESTRICTED.value:
            recommendations.append("Consider implementing data loss prevention (DLP) controls")
            recommendations.append("Enable real-time security monitoring")
            recommendations.append("Implement multi-factor authentication for access")
        
        if classification.value == MaritimeDataClassification.SECRET.value:
            recommendations.append("Implement air-gapped systems for highest sensitivity")
            recommendations.append("Enable continuous compliance monitoring")
            recommendations.append("Consider physical security controls")
        
        # Context-based recommendations
        if context:
            if context.get('is_emergency', False):
                recommendations.append("Ensure emergency access procedures maintain security controls")
            
            if context.get('remote_access', False):
                recommendations.append("Implement additional VPN and endpoint security for remote access")
        
        return recommendations
    
    def _log_classification_event(
        self,
        classification: MaritimeDataClassification,
        confidence: float,
        matched_rules: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
        classification_id: str
    ):
        """Log classification event for audit purposes"""
        if not self.audit_logger:
            return
        
        try:
            from .audit_logger import AuditEventType, AuditSeverity
            
            severity = AuditSeverity.LOW
            if classification.value >= MaritimeDataClassification.CONFIDENTIAL.value:
                severity = AuditSeverity.MEDIUM
            if classification.value >= MaritimeDataClassification.RESTRICTED.value:
                severity = AuditSeverity.HIGH
            
            self.audit_logger.log_event(
                AuditEventType.DATA_ACCESS,  # Using existing enum
                f"Maritime data classified as {classification.name}",
                details={
                    'classification_id': classification_id,
                    'classification': classification.name,
                    'classification_level': classification.value,
                    'confidence': confidence,
                    'matched_rules_count': len(matched_rules),
                    'matched_rules': [rule['rule_id'] for rule in matched_rules],
                    'context': context or {}
                },
                severity=severity,
                maritime_context={
                    'data_classification': True,
                    'classification_level': classification.name,
                    'classification_confidence': confidence,
                    'regulatory_compliance': True
                }
            )
            
        except Exception as e:
            logger.warning(f"Failed to log classification event: {e}")
    
    def _get_safe_default_classification(self, error_msg: str) -> ClassificationResult:
        """Get safe default classification in case of errors"""
        return ClassificationResult(
            classification=MaritimeDataClassification.CONFIDENTIAL,
            confidence=0.0,
            matched_rules=[],
            regulations=[MaritimeRegulatory.GDPR, MaritimeRegulatory.SOLAS],
            retention_policy=DataRetentionPolicy(
                retention_days=7 * 365,
                archive_after_days=2 * 365,
                purge_after_days=10 * 365,
                legal_hold_override=True,
                regulation_basis=[MaritimeRegulatory.GDPR],
                backup_required=True,
                immutable_required=False
            ),
            access_roles=[UserRole.ADMIN],
            geographic_restrictions=[GeographicRestriction.EU_ONLY],
            requires_encryption=True,
            audit_required=True,
            export_restricted=True,
            personal_data_types=[],
            data_subjects=[],
            warnings=[f"Classification failed: {error_msg}"],
            recommendations=["Manual review required due to classification error"],
            classification_timestamp=datetime.now(timezone.utc).isoformat(),
            classification_id=str(uuid.uuid4())
        )
    
    # Additional utility methods
    
    def get_classification_rules_summary(self) -> Dict[str, Any]:
        """Get summary of all classification rules"""
        summary = {
            'total_rules': len(self.classification_rules),
            'active_rules': len([r for r in self.classification_rules if r.active]),
            'by_classification': {},
            'by_regulation': {},
            'encryption_required': 0,
            'audit_required': 0,
            'export_restricted': 0
        }
        
        for rule in self.classification_rules:
            if not rule.active:
                continue
                
            # Count by classification
            class_name = rule.classification.name
            if class_name not in summary['by_classification']:
                summary['by_classification'][class_name] = 0
            summary['by_classification'][class_name] += 1
            
            # Count by regulation
            for reg in rule.regulations:
                reg_name = reg.value
                if reg_name not in summary['by_regulation']:
                    summary['by_regulation'][reg_name] = 0
                summary['by_regulation'][reg_name] += 1
            
            # Count security requirements
            if rule.requires_encryption:
                summary['encryption_required'] += 1
            if rule.audit_required:
                summary['audit_required'] += 1
            if rule.export_restricted:
                summary['export_restricted'] += 1
        
        return summary
    
    def validate_user_access(
        self,
        user_role: str,
        user_location: str,
        classification_result: ClassificationResult
    ) -> Tuple[bool, List[str]]:
        """Validate if user can access classified data"""
        access_allowed = True
        reasons = []
        
        try:
            # Check role-based access
            try:
                user_role_enum = UserRole(user_role.lower())
                if user_role_enum not in classification_result.access_roles:
                    access_allowed = False
                    reasons.append(
                        f"Role '{user_role}' not authorized for "
                        f"{classification_result.classification.name} data"
                    )
            except ValueError:
                access_allowed = False
                reasons.append(f"Invalid user role: {user_role}")
            
            # Check geographic restrictions
            user_country = user_location.upper()
            
            for restriction in classification_result.geographic_restrictions:
                if restriction == GeographicRestriction.EU_ONLY and user_country not in self.eu_countries:
                    access_allowed = False
                    reasons.append("EU-only data access restricted to EU countries")
                
                elif restriction == GeographicRestriction.EXPORT_CONTROLLED:
                    if user_country in self.sensitive_imo_countries:
                        access_allowed = False
                        reasons.append("Export-controlled data restricted for your location")
            
            # Check export restrictions
            if classification_result.export_restricted and user_country in self.sensitive_imo_countries:
                access_allowed = False
                reasons.append("Export-restricted data not available in your jurisdiction")
            
            if access_allowed:
                reasons.append("Access granted based on role and location validation")
                
        except Exception as e:
            access_allowed = False
            reasons.append(f"Access validation error: {str(e)}")
        
        return access_allowed, reasons
    
    def get_retention_schedule(self, days_ahead: int = 365) -> List[Dict[str, Any]]:
        """Get data retention schedule for maritime compliance"""
        schedule = []
        
        for rule in self.classification_rules:
            if not rule.active:
                continue
                
            schedule.append({
                'rule_id': rule.rule_id,
                'rule_name': rule.name,
                'classification': rule.classification.name,
                'retention_days': rule.retention_policy.retention_days,
                'archive_after_days': rule.retention_policy.archive_after_days,
                'purge_after_days': rule.retention_policy.purge_after_days,
                'regulation_basis': [reg.value for reg in rule.retention_policy.regulation_basis],
                'legal_hold_override': rule.retention_policy.legal_hold_override,
                'backup_required': rule.retention_policy.backup_required,
                'immutable_required': rule.retention_policy.immutable_required
            })
        
        return schedule

# Global maritime data classifier instance
maritime_classifier = MaritimeDataClassifier()

def get_maritime_classifier() -> MaritimeDataClassifier:
    """Get the global maritime data classifier"""
    return maritime_classifier

def classify_maritime_data(
    data: Dict[str, Any],
    vessel_id: Optional[int] = None,
    user_role: Optional[str] = None,
    user_location: Optional[str] = None,
    **kwargs
) -> ClassificationResult:
    """
    Convenience function to classify maritime data with comprehensive context
    
    Args:
        data: Data to classify
        vessel_id: Associated vessel ID
        user_role: Current user's role
        user_location: User's geographic location
        **kwargs: Additional context parameters
        
    Returns:
        ClassificationResult: Comprehensive classification analysis
    """
    context = {
        'vessel_id': vessel_id,
        'user_role': user_role,
        'user_location': user_location,
        **kwargs
    }
    
    # Remove None values
    context = {k: v for k, v in context.items() if v is not None}
    
    return maritime_classifier.classify_data(data, context if context else None)

def validate_user_access(
    user_role: str,
    user_location: str,
    data_classification: str
) -> Tuple[bool, List[str]]:
    """Validate user access to classified maritime data"""
    try:
        classification_level = MaritimeDataClassification[data_classification.upper()]
        
        # Create a mock classification result for validation
        mock_result = ClassificationResult(
            classification=classification_level,
            confidence=1.0,
            matched_rules=[],
            regulations=[],
            retention_policy=DataRetentionPolicy(
                retention_days=365,
                archive_after_days=180,
                purge_after_days=730,
                legal_hold_override=False,
                regulation_basis=[]
            ),
            access_roles=[UserRole.ADMIN],  # Will be overridden by rule lookup
            geographic_restrictions=[GeographicRestriction.UNRESTRICTED],
            requires_encryption=False,
            audit_required=False,
            export_restricted=False,
            personal_data_types=[],
            data_subjects=[],
            warnings=[],
            recommendations=[],
            classification_timestamp=datetime.now(timezone.utc).isoformat(),
            classification_id=str(uuid.uuid4())
        )
        
        # Get actual access requirements from rules
        for rule in maritime_classifier.classification_rules:
            if rule.classification == classification_level:
                mock_result.access_roles = rule.access_roles
                mock_result.geographic_restrictions = rule.geographic_restrictions
                mock_result.export_restricted = rule.export_restricted
                break
        
        return maritime_classifier.validate_user_access(
            user_role, user_location, mock_result
        )
        
    except KeyError:
        return False, [f"Invalid classification level: {data_classification}"]
    except Exception as e:
        return False, [f"Access validation error: {str(e)}"]

def get_classification_levels() -> List[str]:
    """Get all available maritime classification levels"""
    return [level.name for level in MaritimeDataClassification]

def get_maritime_roles() -> List[str]:
    """Get all maritime user roles"""
    return [role.value for role in UserRole]

def get_regulations() -> List[str]:
    """Get all maritime regulations"""
    return [reg.value for reg in MaritimeRegulatory]

def get_personal_data_types() -> List[str]:
    """Get all GDPR personal data types"""
    return [pdt.value for pdt in PersonalDataType]

def get_data_subjects() -> List[str]:
    """Get all maritime data subjects"""
    return [ds.value for ds in MaritimeDataSubject]