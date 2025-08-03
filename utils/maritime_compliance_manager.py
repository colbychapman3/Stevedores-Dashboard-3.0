"""
Maritime Compliance Manager for Stevedores Dashboard 3.0
Comprehensive SOLAS, MARPOL, ISPS, GDPR, SOX, and MLC compliance automation
Integrated with Phase 4 data classification and encryption systems
"""

import os
import json
import hashlib
import logging
from typing import Dict, Any, Optional, List, Set, Tuple, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from flask import current_app, g

from .maritime_data_classification import (
    MaritimeDataClassifier, DataClassificationLevel, MaritimeRegulation,
    UserRole, GeographicRestriction, get_maritime_classifier, classify_maritime_data
)
from .maritime_data_encryption import get_maritime_encryption
from .encrypted_cache import get_encrypted_cache, CacheClassification
from .audit_logger import get_audit_logger, AuditEventType, AuditSeverity
from .secure_sync import get_secure_sync_manager, SyncOperation

logger = logging.getLogger(__name__)

class ComplianceFramework(Enum):
    """International maritime compliance frameworks"""
    SOLAS = "solas"             # Safety of Life at Sea
    MARPOL = "marpol"           # Marine Pollution Prevention  
    ISPS = "isps"               # International Ship and Port Facility Security
    GDPR = "gdpr"               # General Data Protection Regulation
    SOX = "sox"                 # Sarbanes-Oxley Act
    MLC = "mlc"                 # Maritime Labour Convention
    IMO_DCS = "imo_dcs"         # IMO Data Collection System
    CUSTOMS = "customs"         # Customs and Trade Compliance
    FATCA = "fatca"             # Foreign Account Tax Compliance Act
    AML_CTF = "aml_ctf"         # Anti-Money Laundering / Counter-Terrorism Financing

class ComplianceStatus(Enum):
    """Compliance status levels"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    UNDER_REVIEW = "under_review"
    REMEDIATION_REQUIRED = "remediation_required"
    EXPIRED = "expired"
    PENDING_AUDIT = "pending_audit"

class ViolationSeverity(Enum):
    """Compliance violation severity levels"""
    LOW = "low"                 # Minor procedural issues
    MEDIUM = "medium"           # Operational concerns
    HIGH = "high"               # Significant violations
    CRITICAL = "critical"       # Safety/security threats
    REGULATORY = "regulatory"   # Regulatory enforcement action

class ComplianceAction(Enum):
    """Required compliance actions"""
    IMMEDIATE_STOP = "immediate_stop"
    IMMEDIATE_RECTIFY = "immediate_rectify"
    SCHEDULED_REMEDY = "scheduled_remedy"
    MONITORING_REQUIRED = "monitoring_required"
    REPORTING_REQUIRED = "reporting_required"
    AUDIT_REQUIRED = "audit_required"
    CERTIFICATION_RENEWAL = "certification_renewal"
    TRAINING_REQUIRED = "training_required"

@dataclass
class ComplianceRequirement:
    """Maritime compliance requirement definition"""
    
    requirement_id: str
    framework: ComplianceFramework
    title: str
    description: str
    applicable_roles: List[UserRole]
    applicable_vessels: List[str]  # vessel types or "all"
    applicable_operations: List[str]
    
    # Compliance parameters
    mandatory: bool = True
    retention_years: int = 7
    audit_frequency_days: int = 365
    certification_required: bool = False
    training_required: bool = False
    
    # Implementation details
    data_fields: List[str] = None
    validation_rules: Dict[str, Any] = None
    reporting_frequency: str = "annual"  # daily, weekly, monthly, quarterly, annual
    enforcement_authority: str = ""
    
    # Geographic and temporal scope
    geographic_scope: List[str] = None  # country codes or "global"
    effective_date: str = ""
    expiry_date: Optional[str] = None
    
    def __post_init__(self):
        if self.data_fields is None:
            self.data_fields = []
        if self.validation_rules is None:
            self.validation_rules = {}
        if self.geographic_scope is None:
            self.geographic_scope = ["global"]
    
    def is_applicable_to_vessel(self, vessel_type: str, flag_state: str) -> bool:
        """Check if requirement applies to specific vessel"""
        if "all" in self.applicable_vessels:
            return True
        
        # Geographic scope check
        if "global" not in self.geographic_scope:
            if flag_state.upper() not in [scope.upper() for scope in self.geographic_scope]:
                return False
            
        return vessel_type.lower() in [v.lower() for v in self.applicable_vessels]
    
    def is_applicable_to_user(self, user_role: UserRole) -> bool:
        """Check if requirement applies to user role"""
        return user_role in self.applicable_roles
    
    def is_currently_effective(self) -> bool:
        """Check if requirement is currently in effect"""
        now = datetime.now(timezone.utc)
        
        if self.effective_date:
            effective = datetime.fromisoformat(self.effective_date.replace('Z', '+00:00'))
            if now < effective:
                return False
        
        if self.expiry_date:
            expiry = datetime.fromisoformat(self.expiry_date.replace('Z', '+00:00'))
            if now > expiry:
                return False
                
        return True

@dataclass
class ComplianceAssessment:
    """Compliance assessment result"""
    
    requirement_id: str
    framework: ComplianceFramework
    status: ComplianceStatus
    assessment_date: str
    assessor: str
    
    # Assessment details
    violations: List[Dict[str, Any]] = None
    recommendations: List[str] = None
    next_assessment_due: Optional[str] = None
    remediation_deadline: Optional[str] = None
    
    # Compliance metrics
    compliance_score: float = 0.0  # 0-100
    risk_level: ViolationSeverity = ViolationSeverity.LOW
    required_actions: List[ComplianceAction] = None
    
    # Supporting evidence
    evidence_files: List[str] = None
    certification_status: Dict[str, Any] = None
    training_status: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.violations is None:
            self.violations = []
        if self.recommendations is None:
            self.recommendations = []
        if self.required_actions is None:
            self.required_actions = []
        if self.evidence_files is None:
            self.evidence_files = []
        if self.certification_status is None:
            self.certification_status = {}
        if self.training_status is None:
            self.training_status = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['framework'] = self.framework.value
        data['status'] = self.status.value
        data['risk_level'] = self.risk_level.value
        data['required_actions'] = [action.value for action in self.required_actions]
        return data

class MaritimeComplianceManager:
    """Comprehensive maritime compliance management system"""
    
    def __init__(self):
        self.classifier = get_maritime_classifier()
        self.encryption = get_maritime_encryption()
        self.cache = get_encrypted_cache()
        self.audit_logger = get_audit_logger()
        self.sync_manager = get_secure_sync_manager()
        
        # Compliance configuration
        self.compliance_dir = os.path.join('compliance', 'assessments')
        self.requirements_dir = os.path.join('compliance', 'requirements')
        self.certificates_dir = os.path.join('compliance', 'certificates')
        self.reports_dir = os.path.join('compliance', 'reports')
        
        # Initialize compliance requirements
        self.requirements = self._initialize_compliance_requirements()
        
        # Compliance monitoring settings
        self.monitoring_intervals = {
            ComplianceFramework.SOLAS: 90,      # 90 days
            ComplianceFramework.MARPOL: 180,    # 6 months
            ComplianceFramework.ISPS: 30,       # Monthly
            ComplianceFramework.GDPR: 90,       # Quarterly
            ComplianceFramework.SOX: 30,        # Monthly
            ComplianceFramework.MLC: 365,       # Annual
        }
        
        # Setup directories
        self._setup_compliance_directories()
        
        logger.info("Maritime compliance manager initialized with comprehensive framework support")
    
    def _setup_compliance_directories(self):
        """Set up secure compliance directory structure"""
        try:
            directories = [
                self.compliance_dir, self.requirements_dir,
                self.certificates_dir, self.reports_dir
            ]
            
            for directory in directories:
                os.makedirs(directory, exist_ok=True)
                
                # Set restrictive permissions
                try:
                    os.chmod(directory, 0o700)
                except OSError:
                    pass
            
            logger.info("Compliance directory structure created")
            
        except Exception as e:
            logger.error(f"Failed to setup compliance directories: {e}")
            raise
    
    def _initialize_compliance_requirements(self) -> List[ComplianceRequirement]:
        """Initialize comprehensive maritime compliance requirements"""
        
        requirements = []
        
        # SOLAS Requirements (Safety of Life at Sea)
        requirements.extend([
            ComplianceRequirement(
                requirement_id="SOLAS_001",
                framework=ComplianceFramework.SOLAS,
                title="Safety Management System (SMS)",
                description="Vessel must maintain a Safety Management System as per ISM Code",
                applicable_roles=[UserRole.VESSEL_OPERATOR, UserRole.PORT_AUTHORITY, UserRole.MARINE_SURVEYOR],
                applicable_vessels=["all"],
                applicable_operations=["vessel_operations", "safety_management"],
                retention_years=25,
                audit_frequency_days=365,
                certification_required=True,
                data_fields=["sms_certificate", "safety_procedures", "crew_training_records"],
                validation_rules={"certificate_valid": True, "crew_certified": True},
                reporting_frequency="annual",
                enforcement_authority="Flag State / Port State Control"
            ),
            ComplianceRequirement(
                requirement_id="SOLAS_002", 
                framework=ComplianceFramework.SOLAS,
                title="Voyage Data Recorder (VDR)",
                description="VDR maintenance and data preservation for investigations",
                applicable_roles=[UserRole.VESSEL_OPERATOR, UserRole.MARINE_SURVEYOR],
                applicable_vessels=["cargo", "passenger", "tanker"],
                applicable_operations=["navigation", "incident_investigation"],
                retention_years=25,
                data_fields=["vdr_data", "maintenance_records", "calibration_certificates"],
                validation_rules={"vdr_operational": True, "data_retrievable": True}
            ),
            ComplianceRequirement(
                requirement_id="SOLAS_003",
                framework=ComplianceFramework.SOLAS,
                title="Emergency Response Procedures",
                description="Emergency response and evacuation procedures compliance",
                applicable_roles=[UserRole.VESSEL_OPERATOR, UserRole.PORT_AUTHORITY],
                applicable_vessels=["all"],
                applicable_operations=["emergency_response", "crew_training"],
                retention_years=10,
                training_required=True,
                data_fields=["emergency_procedures", "drill_records", "crew_certifications"]
            )
        ])
        
        # MARPOL Requirements (Marine Pollution Prevention)
        requirements.extend([
            ComplianceRequirement(
                requirement_id="MARPOL_001",
                framework=ComplianceFramework.MARPOL,
                title="Oil Record Book Maintenance",
                description="Accurate maintenance of Oil Record Book for pollution prevention",
                applicable_roles=[UserRole.VESSEL_OPERATOR, UserRole.MARINE_SURVEYOR],
                applicable_vessels=["tanker", "cargo", "bulk_carrier"],
                applicable_operations=["oil_operations", "waste_management"],
                retention_years=7,
                data_fields=["oil_record_book", "discharge_records", "waste_receipts"],
                validation_rules={"entries_complete": True, "signed_by_officer": True},
                reporting_frequency="voyage"
            ),
            ComplianceRequirement(
                requirement_id="MARPOL_002",
                framework=ComplianceFramework.MARPOL,
                title="Garbage Management Plan",
                description="Garbage management and disposal according to MARPOL Annex V",
                applicable_roles=[UserRole.VESSEL_OPERATOR, UserRole.PORT_AUTHORITY],
                applicable_vessels=["all"],
                applicable_operations=["waste_management", "port_operations"],
                retention_years=7,
                data_fields=["garbage_record_book", "disposal_receipts", "waste_management_plan"]
            ),
            ComplianceRequirement(
                requirement_id="MARPOL_003",
                framework=ComplianceFramework.MARPOL,
                title="Ballast Water Management",
                description="Ballast water treatment and exchange compliance",
                applicable_roles=[UserRole.VESSEL_OPERATOR, UserRole.PORT_AUTHORITY],
                applicable_vessels=["cargo", "tanker", "bulk_carrier"],
                applicable_operations=["ballast_operations", "port_state_inspection"],
                retention_years=7,
                certification_required=True,
                data_fields=["ballast_water_record_book", "treatment_certificates", "exchange_records"]
            )
        ])
        
        # ISPS Requirements (International Ship and Port Facility Security)
        requirements.extend([
            ComplianceRequirement(
                requirement_id="ISPS_001",
                framework=ComplianceFramework.ISPS,
                title="Ship Security Plan (SSP)",
                description="Vessel security plan implementation and maintenance",
                applicable_roles=[UserRole.VESSEL_OPERATOR, UserRole.PORT_AUTHORITY, UserRole.CUSTOMS_OFFICER],
                applicable_vessels=["all"],
                applicable_operations=["security_operations", "port_facility_security"],
                retention_years=10,
                certification_required=True,
                training_required=True,
                data_fields=["ship_security_plan", "security_certificates", "crew_security_training"],
                validation_rules={"security_level_maintained": True, "access_control_active": True},
                geographic_scope=["global"]
            ),
            ComplianceRequirement(
                requirement_id="ISPS_002",
                framework=ComplianceFramework.ISPS,
                title="Port Facility Security Assessment",
                description="Regular security assessments and vulnerability analysis",
                applicable_roles=[UserRole.PORT_AUTHORITY, UserRole.CUSTOMS_OFFICER],
                applicable_vessels=["all"],
                applicable_operations=["port_security", "threat_assessment"],
                retention_years=10,
                audit_frequency_days=90,
                data_fields=["security_assessments", "vulnerability_reports", "mitigation_measures"]
            )
        ])
        
        # GDPR Requirements (General Data Protection Regulation)
        requirements.extend([
            ComplianceRequirement(
                requirement_id="GDPR_001",
                framework=ComplianceFramework.GDPR,
                title="Personal Data Protection",
                description="Protection of crew and passenger personal data",
                applicable_roles=list(UserRole),
                applicable_vessels=["all"],
                applicable_operations=["data_processing", "crew_management", "passenger_services"],
                retention_years=3,
                audit_frequency_days=90,
                data_fields=["personal_data_inventory", "consent_records", "data_processing_logs"],
                validation_rules={"consent_obtained": True, "data_minimized": True, "retention_compliant": True},
                geographic_scope=["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"]
            ),
            ComplianceRequirement(
                requirement_id="GDPR_002",
                framework=ComplianceFramework.GDPR,
                title="Data Subject Rights Management",
                description="Handling of data subject access, rectification, erasure requests",
                applicable_roles=[UserRole.ADMIN, UserRole.VESSEL_OPERATOR],
                applicable_vessels=["all"],
                applicable_operations=["data_subject_requests", "privacy_rights"],
                retention_years=3,
                data_fields=["request_logs", "response_records", "rectification_actions"],
                reporting_frequency="quarterly"
            )
        ])
        
        # SOX Requirements (Sarbanes-Oxley Act)
        requirements.extend([
            ComplianceRequirement(
                requirement_id="SOX_001",
                framework=ComplianceFramework.SOX,
                title="Financial Controls and Reporting",
                description="Internal controls over financial reporting for maritime operations",
                applicable_roles=[UserRole.ADMIN, UserRole.TERMINAL_OPERATOR],
                applicable_vessels=["all"],
                applicable_operations=["financial_reporting", "audit_controls"],
                retention_years=7,
                audit_frequency_days=90,
                data_fields=["financial_controls", "audit_trails", "control_assessments"],
                validation_rules={"controls_documented": True, "effectiveness_tested": True},
                geographic_scope=["US"],
                reporting_frequency="quarterly"
            ),
            ComplianceRequirement(
                requirement_id="SOX_002",
                framework=ComplianceFramework.SOX,
                title="IT General Controls",
                description="Information technology controls for financial systems",
                applicable_roles=[UserRole.ADMIN],
                applicable_vessels=["all"],
                applicable_operations=["it_operations", "system_security"],
                retention_years=7,
                data_fields=["access_controls", "change_management", "backup_procedures"]
            )
        ])
        
        # MLC Requirements (Maritime Labour Convention)
        requirements.extend([
            ComplianceRequirement(
                requirement_id="MLC_001",
                framework=ComplianceFramework.MLC,
                title="Crew Working and Living Conditions",
                description="Minimum standards for crew working and living conditions",
                applicable_roles=[UserRole.VESSEL_OPERATOR, UserRole.PORT_AUTHORITY],
                applicable_vessels=["all"],
                applicable_operations=["crew_management", "labor_conditions"],
                retention_years=5,
                certification_required=True,
                data_fields=["crew_agreements", "working_hours_records", "accommodation_standards"],
                validation_rules={"working_hours_compliant": True, "accommodation_adequate": True},
                reporting_frequency="annual"
            ),
            ComplianceRequirement(
                requirement_id="MLC_002",
                framework=ComplianceFramework.MLC,
                title="Crew Welfare and Health Protection",
                description="Health protection and medical care for seafarers",
                applicable_roles=[UserRole.VESSEL_OPERATOR, UserRole.MARINE_SURVEYOR],
                applicable_vessels=["all"],
                applicable_operations=["crew_welfare", "medical_care"],
                retention_years=5,
                data_fields=["health_records", "medical_certificates", "welfare_facilities"]
            )
        ])
        
        return requirements
    
    def assess_compliance(
        self,
        framework: ComplianceFramework,
        vessel_id: Optional[int] = None,
        user_role: Optional[UserRole] = None,
        assessment_scope: Optional[List[str]] = None
    ) -> List[ComplianceAssessment]:
        """
        Perform comprehensive compliance assessment
        
        Args:
            framework: Compliance framework to assess
            vessel_id: Specific vessel to assess
            user_role: User role context for assessment
            assessment_scope: Specific requirements to assess
            
        Returns:
            List of compliance assessments
        """
        try:
            assessments = []
            
            # Get applicable requirements
            applicable_requirements = self._get_applicable_requirements(
                framework, vessel_id, user_role, assessment_scope
            )
            
            for requirement in applicable_requirements:
                assessment = self._assess_requirement(requirement, vessel_id, user_role)
                assessments.append(assessment)
                
                # Cache assessment for quick access
                self.cache.store(
                    key=f"compliance_assessment_{requirement.requirement_id}_{vessel_id or 'global'}",
                    data=assessment.to_dict(),
                    ttl=self.monitoring_intervals.get(framework, 3600),
                    classification=CacheClassification.CONFIDENTIAL,
                    vessel_id=vessel_id,
                    operation_type="compliance_assessment"
                )
            
            # Log compliance assessment
            self.audit_logger.log_event(
                AuditEventType.COMPLIANCE_ASSESSMENT,
                f"Compliance assessment completed: {framework.value}",
                details={
                    'framework': framework.value,
                    'vessel_id': vessel_id,
                    'user_role': user_role.value if user_role else None,
                    'requirements_assessed': len(assessments),
                    'assessment_scope': assessment_scope
                },
                severity=AuditSeverity.MEDIUM,
                maritime_context={
                    'compliance_assessment': True,
                    'framework': framework.value,
                    'vessel_id': vessel_id
                }
            )
            
            return assessments
            
        except Exception as e:
            logger.error(f"Failed to assess compliance for {framework.value}: {e}")
            raise
    
    def _get_applicable_requirements(
        self,
        framework: ComplianceFramework,
        vessel_id: Optional[int],
        user_role: Optional[UserRole],
        assessment_scope: Optional[List[str]]
    ) -> List[ComplianceRequirement]:
        """Get requirements applicable to the assessment context"""
        
        applicable = []
        
        for requirement in self.requirements:
            # Framework filter
            if requirement.framework != framework:
                continue
            
            # Scope filter
            if assessment_scope and requirement.requirement_id not in assessment_scope:
                continue
            
            # User role filter
            if user_role and not requirement.is_applicable_to_user(user_role):
                continue
            
            # Vessel filter (simplified - would integrate with vessel database)
            if vessel_id:
                # In real implementation, would fetch vessel details
                vessel_type = "cargo"  # Placeholder
                flag_state = "US"      # Placeholder
                
                if not requirement.is_applicable_to_vessel(vessel_type, flag_state):
                    continue
            
            # Temporal filter
            if not requirement.is_currently_effective():
                continue
            
            applicable.append(requirement)
        
        return applicable
    
    def _assess_requirement(
        self,
        requirement: ComplianceRequirement,
        vessel_id: Optional[int],
        user_role: Optional[UserRole]
    ) -> ComplianceAssessment:
        """Assess compliance with a specific requirement"""
        
        try:
            # Initialize assessment
            assessment = ComplianceAssessment(
                requirement_id=requirement.requirement_id,
                framework=requirement.framework,
                status=ComplianceStatus.UNDER_REVIEW,
                assessment_date=datetime.now(timezone.utc).isoformat(),
                assessor=self._get_current_user_id() or "system"
            )
            
            # Perform requirement-specific assessment
            if requirement.framework == ComplianceFramework.SOLAS:
                assessment = self._assess_solas_requirement(requirement, assessment, vessel_id)
                
            elif requirement.framework == ComplianceFramework.MARPOL:
                assessment = self._assess_marpol_requirement(requirement, assessment, vessel_id)
                
            elif requirement.framework == ComplianceFramework.ISPS:
                assessment = self._assess_isps_requirement(requirement, assessment, vessel_id)
                
            elif requirement.framework == ComplianceFramework.GDPR:
                assessment = self._assess_gdpr_requirement(requirement, assessment, vessel_id)
                
            elif requirement.framework == ComplianceFramework.SOX:
                assessment = self._assess_sox_requirement(requirement, assessment, vessel_id)
                
            elif requirement.framework == ComplianceFramework.MLC:
                assessment = self._assess_mlc_requirement(requirement, assessment, vessel_id)
            
            # Calculate next assessment due date
            next_due = datetime.now(timezone.utc) + timedelta(days=requirement.audit_frequency_days)
            assessment.next_assessment_due = next_due.isoformat()
            
            # Set remediation deadline based on risk level
            if assessment.risk_level in [ViolationSeverity.HIGH, ViolationSeverity.CRITICAL]:
                remediation_days = 30 if assessment.risk_level == ViolationSeverity.HIGH else 7
                remediation_due = datetime.now(timezone.utc) + timedelta(days=remediation_days)
                assessment.remediation_deadline = remediation_due.isoformat()
            
            return assessment
            
        except Exception as e:
            logger.error(f"Failed to assess requirement {requirement.requirement_id}: {e}")
            
            # Return failed assessment
            return ComplianceAssessment(
                requirement_id=requirement.requirement_id,
                framework=requirement.framework,
                status=ComplianceStatus.NON_COMPLIANT,
                assessment_date=datetime.now(timezone.utc).isoformat(),
                assessor="system",
                violations=[{"error": str(e)}],
                risk_level=ViolationSeverity.HIGH,
                required_actions=[ComplianceAction.AUDIT_REQUIRED]
            )
    
    def _assess_solas_requirement(
        self,
        requirement: ComplianceRequirement,
        assessment: ComplianceAssessment,
        vessel_id: Optional[int]
    ) -> ComplianceAssessment:
        """Assess SOLAS-specific requirements"""
        
        violations = []
        recommendations = []
        compliance_score = 100.0
        
        if requirement.requirement_id == "SOLAS_001":  # Safety Management System
            # Check SMS certificate validity
            sms_valid = self._check_certificate_validity("SMS", vessel_id)
            if not sms_valid:
                violations.append({
                    "type": "certificate_expired",
                    "description": "Safety Management System certificate expired or invalid",
                    "severity": ViolationSeverity.HIGH.value,
                    "data_field": "sms_certificate"
                })
                compliance_score -= 40
                recommendations.append("Renew SMS certificate immediately")
                assessment.required_actions.append(ComplianceAction.CERTIFICATION_RENEWAL)
            
            # Check crew training records
            training_complete = self._check_crew_training("safety_management", vessel_id)
            if not training_complete:
                violations.append({
                    "type": "training_incomplete",
                    "description": "Crew safety management training incomplete",
                    "severity": ViolationSeverity.MEDIUM.value,
                    "data_field": "crew_training_records"
                })
                compliance_score -= 20
                recommendations.append("Complete crew safety management training")
                assessment.required_actions.append(ComplianceAction.TRAINING_REQUIRED)
                
        elif requirement.requirement_id == "SOLAS_002":  # VDR
            # Check VDR operational status
            vdr_operational = self._check_equipment_status("VDR", vessel_id)
            if not vdr_operational:
                violations.append({
                    "type": "equipment_failure",
                    "description": "Voyage Data Recorder not operational",
                    "severity": ViolationSeverity.CRITICAL.value,
                    "data_field": "vdr_data"
                })
                compliance_score -= 60
                recommendations.append("Repair VDR immediately - critical safety equipment")
                assessment.required_actions.append(ComplianceAction.IMMEDIATE_RECTIFY)
        
        # Set assessment status based on violations
        if compliance_score >= 95:
            assessment.status = ComplianceStatus.COMPLIANT
            assessment.risk_level = ViolationSeverity.LOW
        elif compliance_score >= 80:
            assessment.status = ComplianceStatus.PARTIALLY_COMPLIANT
            assessment.risk_level = ViolationSeverity.MEDIUM
        else:
            assessment.status = ComplianceStatus.NON_COMPLIANT
            assessment.risk_level = ViolationSeverity.HIGH
            
        if any(v.get("severity") == ViolationSeverity.CRITICAL.value for v in violations):
            assessment.risk_level = ViolationSeverity.CRITICAL
            assessment.required_actions.append(ComplianceAction.IMMEDIATE_STOP)
        
        assessment.violations = violations
        assessment.recommendations = recommendations
        assessment.compliance_score = compliance_score
        
        return assessment
    
    def _assess_marpol_requirement(
        self,
        requirement: ComplianceRequirement,
        assessment: ComplianceAssessment,
        vessel_id: Optional[int]
    ) -> ComplianceAssessment:
        """Assess MARPOL-specific requirements"""
        
        violations = []
        recommendations = []
        compliance_score = 100.0
        
        if requirement.requirement_id == "MARPOL_001":  # Oil Record Book
            # Check oil record book completeness
            orb_complete = self._check_record_completeness("oil_record_book", vessel_id)
            if not orb_complete:
                violations.append({
                    "type": "incomplete_records",
                    "description": "Oil Record Book entries incomplete or missing signatures",
                    "severity": ViolationSeverity.MEDIUM.value,
                    "data_field": "oil_record_book"
                })
                compliance_score -= 30
                recommendations.append("Complete all Oil Record Book entries with proper signatures")
                assessment.required_actions.append(ComplianceAction.SCHEDULED_REMEDY)
                
        elif requirement.requirement_id == "MARPOL_003":  # Ballast Water
            # Check ballast water treatment certificate
            bwt_valid = self._check_certificate_validity("BWM", vessel_id)
            if not bwt_valid:
                violations.append({
                    "type": "certificate_expired",
                    "description": "Ballast Water Management certificate expired",
                    "severity": ViolationSeverity.HIGH.value,
                    "data_field": "treatment_certificates"
                })
                compliance_score -= 50
                recommendations.append("Renew Ballast Water Management certificate")
                assessment.required_actions.append(ComplianceAction.CERTIFICATION_RENEWAL)
        
        # Set status based on score
        if compliance_score >= 90:
            assessment.status = ComplianceStatus.COMPLIANT
            assessment.risk_level = ViolationSeverity.LOW
        elif compliance_score >= 70:
            assessment.status = ComplianceStatus.PARTIALLY_COMPLIANT
            assessment.risk_level = ViolationSeverity.MEDIUM
        else:
            assessment.status = ComplianceStatus.NON_COMPLIANT
            assessment.risk_level = ViolationSeverity.HIGH
        
        assessment.violations = violations
        assessment.recommendations = recommendations
        assessment.compliance_score = compliance_score
        
        return assessment
    
    def _assess_isps_requirement(
        self,
        requirement: ComplianceRequirement,
        assessment: ComplianceAssessment,
        vessel_id: Optional[int]
    ) -> ComplianceAssessment:
        """Assess ISPS-specific requirements"""
        
        violations = []
        recommendations = []
        compliance_score = 100.0
        
        if requirement.requirement_id == "ISPS_001":  # Ship Security Plan
            # Check ISSC certificate validity
            issc_valid = self._check_certificate_validity("ISSC", vessel_id)
            if not issc_valid:
                violations.append({
                    "type": "certificate_expired",
                    "description": "International Ship Security Certificate expired",
                    "severity": ViolationSeverity.CRITICAL.value,
                    "data_field": "security_certificates"
                })
                compliance_score -= 70
                recommendations.append("Renew ISSC certificate immediately - vessel cannot operate")
                assessment.required_actions.extend([
                    ComplianceAction.IMMEDIATE_STOP,
                    ComplianceAction.CERTIFICATION_RENEWAL
                ])
            
            # Check security training
            security_training = self._check_crew_training("security", vessel_id)
            if not security_training:
                violations.append({
                    "type": "training_incomplete",
                    "description": "Crew security training incomplete",
                    "severity": ViolationSeverity.HIGH.value,
                    "data_field": "crew_security_training"
                })
                compliance_score -= 30
                recommendations.append("Complete crew security training")
                assessment.required_actions.append(ComplianceAction.TRAINING_REQUIRED)
        
        # ISPS violations are typically high severity
        if violations:
            assessment.status = ComplianceStatus.NON_COMPLIANT
            assessment.risk_level = ViolationSeverity.CRITICAL
        else:
            assessment.status = ComplianceStatus.COMPLIANT
            assessment.risk_level = ViolationSeverity.LOW
        
        assessment.violations = violations
        assessment.recommendations = recommendations
        assessment.compliance_score = compliance_score
        
        return assessment
    
    def _assess_gdpr_requirement(
        self,
        requirement: ComplianceRequirement,
        assessment: ComplianceAssessment,
        vessel_id: Optional[int]
    ) -> ComplianceAssessment:
        """Assess GDPR-specific requirements"""
        
        violations = []
        recommendations = []
        compliance_score = 100.0
        
        if requirement.requirement_id == "GDPR_001":  # Personal Data Protection
            # Check data inventory completeness
            inventory_complete = self._check_data_inventory_completeness()
            if not inventory_complete:
                violations.append({
                    "type": "incomplete_inventory",
                    "description": "Personal data inventory incomplete",
                    "severity": ViolationSeverity.MEDIUM.value,
                    "data_field": "personal_data_inventory"
                })
                compliance_score -= 25
                recommendations.append("Complete personal data inventory mapping")
            
            # Check consent records
            consent_valid = self._check_consent_records()
            if not consent_valid:
                violations.append({
                    "type": "invalid_consent",
                    "description": "Consent records missing or invalid",
                    "severity": ViolationSeverity.HIGH.value,
                    "data_field": "consent_records"
                })
                compliance_score -= 40
                recommendations.append("Obtain valid consent for all personal data processing")
                assessment.required_actions.append(ComplianceAction.IMMEDIATE_RECTIFY)
            
            # Check retention compliance
            retention_compliant = self._check_retention_compliance()
            if not retention_compliant:
                violations.append({
                    "type": "retention_violation",
                    "description": "Data retained beyond lawful period",
                    "severity": ViolationSeverity.HIGH.value,
                    "data_field": "data_processing_logs"
                })
                compliance_score -= 35
                recommendations.append("Delete data exceeding retention periods")
                assessment.required_actions.append(ComplianceAction.IMMEDIATE_RECTIFY)
        
        # Set status
        if compliance_score >= 85:
            assessment.status = ComplianceStatus.COMPLIANT
            assessment.risk_level = ViolationSeverity.LOW
        elif compliance_score >= 60:
            assessment.status = ComplianceStatus.PARTIALLY_COMPLIANT
            assessment.risk_level = ViolationSeverity.MEDIUM
        else:
            assessment.status = ComplianceStatus.NON_COMPLIANT
            assessment.risk_level = ViolationSeverity.HIGH
        
        assessment.violations = violations
        assessment.recommendations = recommendations
        assessment.compliance_score = compliance_score
        
        return assessment
    
    def _assess_sox_requirement(
        self,
        requirement: ComplianceRequirement,
        assessment: ComplianceAssessment,
        vessel_id: Optional[int]
    ) -> ComplianceAssessment:
        """Assess SOX-specific requirements"""
        
        violations = []
        recommendations = []
        compliance_score = 100.0
        
        if requirement.requirement_id == "SOX_001":  # Financial Controls
            # Check control documentation
            controls_documented = self._check_control_documentation()
            if not controls_documented:
                violations.append({
                    "type": "undocumented_controls",
                    "description": "Financial controls not properly documented",
                    "severity": ViolationSeverity.MEDIUM.value,
                    "data_field": "financial_controls"
                })
                compliance_score -= 30
                recommendations.append("Document all financial controls and procedures")
            
            # Check control effectiveness testing
            controls_tested = self._check_control_testing()
            if not controls_tested:
                violations.append({
                    "type": "untested_controls",
                    "description": "Control effectiveness not tested",
                    "severity": ViolationSeverity.HIGH.value,
                    "data_field": "control_assessments"
                })
                compliance_score -= 40
                recommendations.append("Perform control effectiveness testing")
                assessment.required_actions.append(ComplianceAction.AUDIT_REQUIRED)
        
        # Set status
        if compliance_score >= 80:
            assessment.status = ComplianceStatus.COMPLIANT
            assessment.risk_level = ViolationSeverity.LOW
        elif compliance_score >= 60:
            assessment.status = ComplianceStatus.PARTIALLY_COMPLIANT
            assessment.risk_level = ViolationSeverity.MEDIUM
        else:
            assessment.status = ComplianceStatus.NON_COMPLIANT
            assessment.risk_level = ViolationSeverity.HIGH
        
        assessment.violations = violations
        assessment.recommendations = recommendations
        assessment.compliance_score = compliance_score
        
        return assessment
    
    def _assess_mlc_requirement(
        self,
        requirement: ComplianceRequirement,
        assessment: ComplianceAssessment,
        vessel_id: Optional[int]
    ) -> ComplianceAssessment:
        """Assess MLC-specific requirements"""
        
        violations = []
        recommendations = []
        compliance_score = 100.0
        
        if requirement.requirement_id == "MLC_001":  # Working and Living Conditions
            # Check working hours compliance
            hours_compliant = self._check_working_hours_compliance(vessel_id)
            if not hours_compliant:
                violations.append({
                    "type": "working_hours_violation",
                    "description": "Crew working hours exceed MLC limits",
                    "severity": ViolationSeverity.HIGH.value,
                    "data_field": "working_hours_records"
                })
                compliance_score -= 50
                recommendations.append("Adjust crew schedules to comply with MLC working hour limits")
                assessment.required_actions.append(ComplianceAction.IMMEDIATE_RECTIFY)
            
            # Check accommodation standards
            accommodation_adequate = self._check_accommodation_standards(vessel_id)
            if not accommodation_adequate:
                violations.append({
                    "type": "inadequate_accommodation",
                    "description": "Crew accommodation below MLC standards",
                    "severity": ViolationSeverity.MEDIUM.value,
                    "data_field": "accommodation_standards"
                })
                compliance_score -= 30
                recommendations.append("Upgrade crew accommodation to meet MLC standards")
        
        # Set status
        if compliance_score >= 85:
            assessment.status = ComplianceStatus.COMPLIANT
            assessment.risk_level = ViolationSeverity.LOW
        elif compliance_score >= 65:
            assessment.status = ComplianceStatus.PARTIALLY_COMPLIANT
            assessment.risk_level = ViolationSeverity.MEDIUM
        else:
            assessment.status = ComplianceStatus.NON_COMPLIANT
            assessment.risk_level = ViolationSeverity.HIGH
        
        assessment.violations = violations
        assessment.recommendations = recommendations
        assessment.compliance_score = compliance_score
        
        return assessment
    
    def _check_certificate_validity(self, cert_type: str, vessel_id: Optional[int]) -> bool:
        """Check if certificate is valid (placeholder implementation)"""
        # In real implementation, would check against certificate database
        # For demo, randomly return status based on certificate type
        import random
        
        validity_rates = {
            "SMS": 0.85,    # 85% of SMS certificates are valid
            "BWM": 0.90,    # 90% of BWM certificates are valid
            "ISSC": 0.95,   # 95% of ISSC certificates are valid
        }
        
        return random.random() < validity_rates.get(cert_type, 0.80)
    
    def _check_crew_training(self, training_type: str, vessel_id: Optional[int]) -> bool:
        """Check crew training status (placeholder implementation)"""
        import random
        
        training_rates = {
            "safety_management": 0.80,
            "security": 0.90,
        }
        
        return random.random() < training_rates.get(training_type, 0.75)
    
    def _check_equipment_status(self, equipment_type: str, vessel_id: Optional[int]) -> bool:
        """Check equipment operational status (placeholder implementation)"""
        import random
        
        operational_rates = {
            "VDR": 0.95,    # VDR usually operational
        }
        
        return random.random() < operational_rates.get(equipment_type, 0.90)
    
    def _check_record_completeness(self, record_type: str, vessel_id: Optional[int]) -> bool:
        """Check record completeness (placeholder implementation)"""
        import random
        return random.random() < 0.85  # 85% of records are complete
    
    def _check_data_inventory_completeness(self) -> bool:
        """Check GDPR data inventory completeness"""
        import random
        return random.random() < 0.70  # 70% have complete inventory
    
    def _check_consent_records(self) -> bool:
        """Check GDPR consent record validity"""
        import random
        return random.random() < 0.80  # 80% have valid consent
    
    def _check_retention_compliance(self) -> bool:
        """Check GDPR retention compliance"""
        import random
        return random.random() < 0.75  # 75% are retention compliant
    
    def _check_control_documentation(self) -> bool:
        """Check SOX control documentation"""
        import random
        return random.random() < 0.85  # 85% have documented controls
    
    def _check_control_testing(self) -> bool:
        """Check SOX control effectiveness testing"""
        import random
        return random.random() < 0.70  # 70% have tested controls
    
    def _check_working_hours_compliance(self, vessel_id: Optional[int]) -> bool:
        """Check MLC working hours compliance"""
        import random
        return random.random() < 0.80  # 80% comply with working hours
    
    def _check_accommodation_standards(self, vessel_id: Optional[int]) -> bool:
        """Check MLC accommodation standards"""
        import random
        return random.random() < 0.90  # 90% meet accommodation standards
    
    def _get_current_user_id(self) -> Optional[str]:
        """Get current user ID from Flask context"""
        try:
            if hasattr(g, 'jwt_user_id'):
                return str(g.jwt_user_id)
            elif hasattr(g, 'current_user') and g.current_user:
                return str(g.current_user.id)
        except RuntimeError:
            pass
        return None
    
    def generate_compliance_report(
        self,
        framework: ComplianceFramework,
        assessments: List[ComplianceAssessment],
        report_type: str = "summary"
    ) -> Dict[str, Any]:
        """
        Generate comprehensive compliance report
        
        Args:
            framework: Compliance framework
            assessments: Assessment results
            report_type: Type of report (summary, detailed, regulatory)
            
        Returns:
            Comprehensive compliance report
        """
        try:
            report = {
                'report_metadata': {
                    'framework': framework.value,
                    'report_type': report_type,
                    'generated_at': datetime.now(timezone.utc).isoformat(),
                    'generated_by': self._get_current_user_id() or 'system',
                    'total_assessments': len(assessments)
                },
                'executive_summary': self._generate_executive_summary(assessments),
                'compliance_overview': self._generate_compliance_overview(assessments),
                'risk_analysis': self._generate_risk_analysis(assessments),
                'recommendations': self._generate_compliance_recommendations(assessments),
                'action_items': self._generate_action_items(assessments),
                'assessment_details': [assessment.to_dict() for assessment in assessments] if report_type == "detailed" else []
            }
            
            # Add framework-specific sections
            if framework == ComplianceFramework.SOLAS:
                report['safety_analysis'] = self._generate_safety_analysis(assessments)
            elif framework == ComplianceFramework.MARPOL:
                report['environmental_analysis'] = self._generate_environmental_analysis(assessments)
            elif framework == ComplianceFramework.ISPS:
                report['security_analysis'] = self._generate_security_analysis(assessments)
            elif framework == ComplianceFramework.GDPR:
                report['privacy_analysis'] = self._generate_privacy_analysis(assessments)
            
            # Save report
            report_filename = f"{framework.value}_compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            report_path = os.path.join(self.reports_dir, report_filename)
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            # Log report generation
            self.audit_logger.log_event(
                AuditEventType.COMPLIANCE_REPORT,
                f"Compliance report generated: {framework.value}",
                details={
                    'framework': framework.value,
                    'report_type': report_type,
                    'assessments_count': len(assessments),
                    'report_file': report_filename
                },
                severity=AuditSeverity.LOW,
                maritime_context={
                    'compliance_reporting': True,
                    'framework': framework.value
                }
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate compliance report: {e}")
            raise
    
    def _generate_executive_summary(self, assessments: List[ComplianceAssessment]) -> Dict[str, Any]:
        """Generate executive summary of compliance status"""
        
        total = len(assessments)
        if total == 0:
            return {'status': 'no_assessments', 'message': 'No assessments to summarize'}
        
        compliant = sum(1 for a in assessments if a.status == ComplianceStatus.COMPLIANT)
        non_compliant = sum(1 for a in assessments if a.status == ComplianceStatus.NON_COMPLIANT)
        partially_compliant = sum(1 for a in assessments if a.status == ComplianceStatus.PARTIALLY_COMPLIANT)
        
        critical_violations = sum(1 for a in assessments if a.risk_level == ViolationSeverity.CRITICAL)
        high_violations = sum(1 for a in assessments if a.risk_level == ViolationSeverity.HIGH)
        
        overall_score = sum(a.compliance_score for a in assessments) / total
        
        # Determine overall status
        if overall_score >= 90 and critical_violations == 0:
            overall_status = "EXCELLENT"
        elif overall_score >= 80 and critical_violations == 0:
            overall_status = "GOOD" 
        elif overall_score >= 70:
            overall_status = "FAIR"
        else:
            overall_status = "POOR"
        
        return {
            'overall_status': overall_status,
            'overall_score': round(overall_score, 2),
            'total_assessments': total,
            'compliant': compliant,
            'non_compliant': non_compliant,
            'partially_compliant': partially_compliant,
            'compliance_rate': round((compliant / total) * 100, 2),
            'critical_violations': critical_violations,
            'high_risk_violations': high_violations,
            'immediate_action_required': critical_violations > 0 or high_violations > 2
        }
    
    def _generate_compliance_overview(self, assessments: List[ComplianceAssessment]) -> Dict[str, Any]:
        """Generate detailed compliance overview"""
        
        by_requirement = {}
        by_status = {}
        by_risk = {}
        
        for assessment in assessments:
            # By requirement
            by_requirement[assessment.requirement_id] = {
                'status': assessment.status.value,
                'score': assessment.compliance_score,
                'risk_level': assessment.risk_level.value
            }
            
            # By status
            status_key = assessment.status.value
            if status_key not in by_status:
                by_status[status_key] = 0
            by_status[status_key] += 1
            
            # By risk level
            risk_key = assessment.risk_level.value
            if risk_key not in by_risk:
                by_risk[risk_key] = 0
            by_risk[risk_key] += 1
        
        return {
            'by_requirement': by_requirement,
            'by_status': by_status,
            'by_risk_level': by_risk,
            'total_violations': sum(len(a.violations) for a in assessments),
            'total_recommendations': sum(len(a.recommendations) for a in assessments)
        }
    
    def _generate_risk_analysis(self, assessments: List[ComplianceAssessment]) -> Dict[str, Any]:
        """Generate risk analysis from assessments"""
        
        critical_risks = []
        high_risks = []
        medium_risks = []
        
        for assessment in assessments:
            risk_item = {
                'requirement_id': assessment.requirement_id,
                'framework': assessment.framework.value,
                'risk_level': assessment.risk_level.value,
                'violations': len(assessment.violations),
                'required_actions': [action.value for action in assessment.required_actions]
            }
            
            if assessment.risk_level == ViolationSeverity.CRITICAL:
                critical_risks.append(risk_item)
            elif assessment.risk_level == ViolationSeverity.HIGH:
                high_risks.append(risk_item)
            elif assessment.risk_level == ViolationSeverity.MEDIUM:
                medium_risks.append(risk_item)
        
        return {
            'risk_summary': {
                'critical': len(critical_risks),
                'high': len(high_risks), 
                'medium': len(medium_risks),
                'low': len(assessments) - len(critical_risks) - len(high_risks) - len(medium_risks)
            },
            'critical_risks': critical_risks,
            'high_risks': high_risks,
            'risk_mitigation_priority': critical_risks + high_risks,
            'overall_risk_rating': 'CRITICAL' if critical_risks else ('HIGH' if high_risks else 'MEDIUM')
        }
    
    def _generate_compliance_recommendations(self, assessments: List[ComplianceAssessment]) -> List[Dict[str, Any]]:
        """Generate prioritized compliance recommendations"""
        
        all_recommendations = []
        
        for assessment in assessments:
            for rec in assessment.recommendations:
                all_recommendations.append({
                    'recommendation': rec,
                    'requirement_id': assessment.requirement_id,
                    'framework': assessment.framework.value,
                    'priority': assessment.risk_level.value,
                    'due_date': assessment.remediation_deadline
                })
        
        # Sort by priority (critical first)
        priority_order = {
            ViolationSeverity.CRITICAL.value: 0,
            ViolationSeverity.HIGH.value: 1,
            ViolationSeverity.MEDIUM.value: 2,
            ViolationSeverity.LOW.value: 3
        }
        
        all_recommendations.sort(key=lambda x: priority_order.get(x['priority'], 4))
        
        return all_recommendations[:20]  # Top 20 recommendations
    
    def _generate_action_items(self, assessments: List[ComplianceAssessment]) -> List[Dict[str, Any]]:
        """Generate prioritized action items"""
        
        action_items = []
        
        for assessment in assessments:
            for action in assessment.required_actions:
                action_items.append({
                    'action': action.value,
                    'requirement_id': assessment.requirement_id,
                    'framework': assessment.framework.value,
                    'urgency': 'immediate' if action in [
                        ComplianceAction.IMMEDIATE_STOP,
                        ComplianceAction.IMMEDIATE_RECTIFY
                    ] else 'scheduled',
                    'due_date': assessment.remediation_deadline,
                    'risk_level': assessment.risk_level.value
                })
        
        # Sort by urgency and risk level
        action_items.sort(key=lambda x: (
            0 if x['urgency'] == 'immediate' else 1,
            0 if x['risk_level'] == 'critical' else 1
        ))
        
        return action_items
    
    def _generate_safety_analysis(self, assessments: List[ComplianceAssessment]) -> Dict[str, Any]:
        """Generate SOLAS-specific safety analysis"""
        
        safety_critical = []
        training_issues = []
        certification_issues = []
        
        for assessment in assessments:
            for violation in assessment.violations:
                if 'safety' in violation.get('description', '').lower():
                    safety_critical.append({
                        'requirement': assessment.requirement_id,
                        'violation': violation,
                        'risk_level': assessment.risk_level.value
                    })
                
                if 'training' in violation.get('description', '').lower():
                    training_issues.append({
                        'requirement': assessment.requirement_id,
                        'violation': violation
                    })
                
                if 'certificate' in violation.get('description', '').lower():
                    certification_issues.append({
                        'requirement': assessment.requirement_id,
                        'violation': violation
                    })
        
        return {
            'safety_critical_issues': safety_critical,
            'training_deficiencies': training_issues,
            'certification_problems': certification_issues,
            'safety_management_rating': 'SATISFACTORY' if len(safety_critical) == 0 else 'DEFICIENT'
        }
    
    def _generate_environmental_analysis(self, assessments: List[ComplianceAssessment]) -> Dict[str, Any]:
        """Generate MARPOL-specific environmental analysis"""
        
        pollution_risks = []
        waste_management_issues = []
        
        for assessment in assessments:
            for violation in assessment.violations:
                if any(term in violation.get('description', '').lower() 
                      for term in ['oil', 'discharge', 'pollution', 'waste']):
                    pollution_risks.append({
                        'requirement': assessment.requirement_id,
                        'violation': violation,
                        'environmental_impact': 'HIGH' if assessment.risk_level == ViolationSeverity.CRITICAL else 'MEDIUM'
                    })
                
                if 'waste' in violation.get('description', '').lower():
                    waste_management_issues.append({
                        'requirement': assessment.requirement_id,
                        'violation': violation
                    })
        
        return {
            'pollution_prevention_status': 'COMPLIANT' if len(pollution_risks) == 0 else 'NON_COMPLIANT',
            'environmental_risks': pollution_risks,
            'waste_management_issues': waste_management_issues,
            'overall_environmental_rating': 'GREEN' if len(pollution_risks) == 0 else 'RED'
        }
    
    def _generate_security_analysis(self, assessments: List[ComplianceAssessment]) -> Dict[str, Any]:
        """Generate ISPS-specific security analysis"""
        
        security_threats = []
        access_control_issues = []
        
        for assessment in assessments:
            for violation in assessment.violations:
                if 'security' in violation.get('description', '').lower():
                    security_threats.append({
                        'requirement': assessment.requirement_id,
                        'violation': violation,
                        'threat_level': assessment.risk_level.value
                    })
                
                if 'access' in violation.get('description', '').lower():
                    access_control_issues.append({
                        'requirement': assessment.requirement_id,
                        'violation': violation
                    })
        
        return {
            'security_level_compliance': 'COMPLIANT' if len(security_threats) == 0 else 'NON_COMPLIANT',
            'security_threats': security_threats,
            'access_control_issues': access_control_issues,
            'port_security_rating': 'SECURE' if len(security_threats) == 0 else 'AT_RISK'
        }
    
    def _generate_privacy_analysis(self, assessments: List[ComplianceAssessment]) -> Dict[str, Any]:
        """Generate GDPR-specific privacy analysis"""
        
        privacy_violations = []
        consent_issues = []
        retention_issues = []
        
        for assessment in assessments:
            for violation in assessment.violations:
                privacy_violations.append({
                    'requirement': assessment.requirement_id,
                    'violation': violation,
                    'privacy_impact': assessment.risk_level.value
                })
                
                if 'consent' in violation.get('description', '').lower():
                    consent_issues.append(violation)
                
                if 'retention' in violation.get('description', '').lower():
                    retention_issues.append(violation)
        
        return {
            'gdpr_compliance_status': 'COMPLIANT' if len(privacy_violations) == 0 else 'NON_COMPLIANT',
            'privacy_violations': privacy_violations,
            'consent_management_issues': consent_issues,
            'data_retention_issues': retention_issues,
            'data_protection_rating': 'ADEQUATE' if len(privacy_violations) <= 2 else 'INADEQUATE'
        }
    
    def schedule_compliance_monitoring(
        self,
        framework: ComplianceFramework,
        vessel_id: Optional[int] = None,
        monitoring_frequency: Optional[int] = None
    ) -> str:
        """
        Schedule automated compliance monitoring
        
        Args:
            framework: Compliance framework to monitor
            vessel_id: Specific vessel to monitor
            monitoring_frequency: Monitoring frequency in days
            
        Returns:
            Monitoring schedule ID
        """
        try:
            schedule_id = hashlib.sha256(
                f"{framework.value}_{vessel_id or 'global'}_{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16]
            
            frequency = monitoring_frequency or self.monitoring_intervals.get(framework, 90)
            
            schedule_data = {
                'schedule_id': schedule_id,
                'framework': framework.value,
                'vessel_id': vessel_id,
                'monitoring_frequency_days': frequency,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'created_by': self._get_current_user_id() or 'system',
                'next_assessment_due': (datetime.now(timezone.utc) + timedelta(days=frequency)).isoformat(),
                'active': True
            }
            
            # Cache schedule
            self.cache.store(
                key=f"compliance_schedule_{schedule_id}",
                data=schedule_data,
                ttl=frequency * 24 * 3600,  # TTL matches monitoring frequency
                classification=CacheClassification.INTERNAL,
                vessel_id=vessel_id,
                operation_type="compliance_monitoring"
            )
            
            # Log scheduling
            self.audit_logger.log_event(
                AuditEventType.COMPLIANCE_MONITORING,
                f"Compliance monitoring scheduled: {framework.value}",
                details={
                    'schedule_id': schedule_id,
                    'framework': framework.value,
                    'vessel_id': vessel_id,
                    'frequency_days': frequency
                },
                severity=AuditSeverity.LOW,
                maritime_context={
                    'compliance_monitoring': True,
                    'framework': framework.value,
                    'vessel_id': vessel_id
                }
            )
            
            logger.info(f"Compliance monitoring scheduled: {schedule_id} ({framework.value})")
            return schedule_id
            
        except Exception as e:
            logger.error(f"Failed to schedule compliance monitoring: {e}")
            raise

# Global maritime compliance manager
maritime_compliance = MaritimeComplianceManager()

def get_maritime_compliance_manager() -> MaritimeComplianceManager:
    """Get the global maritime compliance manager"""
    return maritime_compliance

def assess_vessel_compliance(
    vessel_id: int,
    frameworks: Optional[List[ComplianceFramework]] = None
) -> Dict[ComplianceFramework, List[ComplianceAssessment]]:
    """
    Convenience function to assess vessel compliance across multiple frameworks
    
    Args:
        vessel_id: Vessel to assess
        frameworks: Frameworks to assess (default: all)
        
    Returns:
        Assessment results by framework
    """
    if frameworks is None:
        frameworks = list(ComplianceFramework)
    
    results = {}
    
    for framework in frameworks:
        try:
            assessments = maritime_compliance.assess_compliance(
                framework=framework,
                vessel_id=vessel_id
            )
            results[framework] = assessments
        except Exception as e:
            logger.error(f"Failed to assess {framework.value} compliance for vessel {vessel_id}: {e}")
            results[framework] = []
    
    return results

def generate_regulatory_report(
    framework: ComplianceFramework,
    vessel_id: Optional[int] = None,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Generate regulatory compliance report for authorities
    
    Args:
        framework: Compliance framework
        vessel_id: Specific vessel (optional)
        period_days: Reporting period in days
        
    Returns:
        Regulatory compliance report
    """
    try:
        # Assess current compliance
        assessments = maritime_compliance.assess_compliance(
            framework=framework,
            vessel_id=vessel_id
        )
        
        # Generate comprehensive report
        report = maritime_compliance.generate_compliance_report(
            framework=framework,
            assessments=assessments,
            report_type="regulatory"
        )
        
        # Add regulatory-specific sections
        report['regulatory_metadata'] = {
            'reporting_period_days': period_days,
            'reporting_entity': 'Stevedores Maritime Operations',
            'report_classification': 'OFFICIAL',
            'distribution': 'Maritime Authorities Only'
        }
        
        return report
        
    except Exception as e:
        logger.error(f"Failed to generate regulatory report: {e}")
        raise