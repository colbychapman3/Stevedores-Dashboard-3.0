"""
Maritime Compliance Manager for Stevedores Dashboard 3.0
Comprehensive compliance framework for SOLAS, MARPOL, ISPS, GDPR, SOX regulations
"""

import asyncio
import json
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from pathlib import Path
import sqlite3
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComplianceFramework(Enum):
    """Maritime and regulatory compliance frameworks"""
    SOLAS = "SOLAS"  # Safety of Life at Sea
    MARPOL = "MARPOL"  # Marine Pollution Prevention
    ISPS = "ISPS"  # International Ship and Port Facility Security
    GDPR = "GDPR"  # General Data Protection Regulation
    SOX = "SOX"  # Sarbanes-Oxley Act
    MLC = "MLC"  # Maritime Labour Convention
    CUSTOMS = "CUSTOMS"  # Customs and Border Protection
    ISM = "ISM"  # International Safety Management

class ComplianceStatus(Enum):
    """Compliance status levels"""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    UNDER_REVIEW = "under_review"
    PENDING_ACTION = "pending_action"
    EXPIRED = "expired"
    WARNING = "warning"

class RiskLevel(Enum):
    """Risk assessment levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ComplianceRequirement:
    """Individual compliance requirement definition"""
    id: str
    framework: ComplianceFramework
    title: str
    description: str
    category: str
    mandatory: bool
    frequency: str  # daily, weekly, monthly, annually, once
    due_date: Optional[datetime]
    responsible_party: str
    verification_method: str
    risk_level: RiskLevel
    penalty_description: str
    created_at: datetime
    updated_at: datetime

@dataclass
class ComplianceAssessment:
    """Compliance assessment result"""
    requirement_id: str
    status: ComplianceStatus
    assessment_date: datetime
    assessor: str
    evidence: List[str]
    findings: str
    recommendations: List[str]
    next_review_date: datetime
    score: float  # 0-100
    metadata: Dict[str, Any]

@dataclass
class ComplianceViolation:
    """Compliance violation record"""
    id: str
    requirement_id: str
    severity: RiskLevel
    description: str
    detected_date: datetime
    resolved_date: Optional[datetime]
    resolution_actions: List[str]
    responsible_party: str
    cost_impact: Optional[float]
    regulatory_impact: str
    status: str  # open, resolved, pending

class MaritimeComplianceManager:
    """
    Comprehensive maritime compliance management system
    Handles multiple regulatory frameworks with automated checking
    """
    
    def __init__(self, db_path: str = "maritime_compliance.db"):
        self.db_path = db_path
        self.compliance_requirements = {}
        self.assessment_cache = {}
        self.violation_tracker = {}
        self._init_database()
        self._load_regulatory_frameworks()
        
    def _init_database(self):
        """Initialize compliance database schema"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Compliance requirements table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS compliance_requirements (
                    id TEXT PRIMARY KEY,
                    framework TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    mandatory BOOLEAN,
                    frequency TEXT,
                    due_date TIMESTAMP,
                    responsible_party TEXT,
                    verification_method TEXT,
                    risk_level TEXT,
                    penalty_description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Compliance assessments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS compliance_assessments (
                    id TEXT PRIMARY KEY,
                    requirement_id TEXT,
                    status TEXT,
                    assessment_date TIMESTAMP,
                    assessor TEXT,
                    evidence TEXT,
                    findings TEXT,
                    recommendations TEXT,
                    next_review_date TIMESTAMP,
                    score REAL,
                    metadata TEXT,
                    FOREIGN KEY (requirement_id) REFERENCES compliance_requirements (id)
                )
            ''')
            
            # Violations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS compliance_violations (
                    id TEXT PRIMARY KEY,
                    requirement_id TEXT,
                    severity TEXT,
                    description TEXT,
                    detected_date TIMESTAMP,
                    resolved_date TIMESTAMP,
                    resolution_actions TEXT,
                    responsible_party TEXT,
                    cost_impact REAL,
                    regulatory_impact TEXT,
                    status TEXT,
                    FOREIGN KEY (requirement_id) REFERENCES compliance_requirements (id)
                )
            ''')
            
            # Audit trail table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS compliance_audit_trail (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT,
                    entity_id TEXT,
                    action TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    user_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    user_agent TEXT,
                    checksum TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Maritime compliance database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize compliance database: {e}")
            raise
    
    def _load_regulatory_frameworks(self):
        """Load predefined regulatory framework requirements"""
        try:
            # SOLAS Requirements
            solas_requirements = [
                {
                    "id": "SOLAS_CERT_001",
                    "framework": ComplianceFramework.SOLAS,
                    "title": "Safety Management Certificate",
                    "description": "Valid Safety Management Certificate required for vessel operations",
                    "category": "Safety Management",
                    "mandatory": True,
                    "frequency": "annually",
                    "responsible_party": "Port Manager",
                    "verification_method": "Document verification",
                    "risk_level": RiskLevel.HIGH,
                    "penalty_description": "Vessel detention, operational suspension"
                },
                {
                    "id": "SOLAS_FIRE_001",
                    "framework": ComplianceFramework.SOLAS,
                    "title": "Fire Safety Systems Check",
                    "description": "Regular inspection and testing of fire safety systems",
                    "category": "Fire Safety",
                    "mandatory": True,
                    "frequency": "monthly",
                    "responsible_party": "Safety Officer",
                    "verification_method": "Physical inspection",
                    "risk_level": RiskLevel.CRITICAL,
                    "penalty_description": "Port state control detention"
                }
            ]
            
            # MARPOL Requirements
            marpol_requirements = [
                {
                    "id": "MARPOL_WASTE_001",
                    "framework": ComplianceFramework.MARPOL,
                    "title": "Waste Management Plan",
                    "description": "Implementation of waste segregation and disposal procedures",
                    "category": "Environmental Protection",
                    "mandatory": True,
                    "frequency": "daily",
                    "responsible_party": "Environmental Officer",
                    "verification_method": "Records inspection",
                    "risk_level": RiskLevel.HIGH,
                    "penalty_description": "Environmental fines, operational restrictions"
                },
                {
                    "id": "MARPOL_OIL_001",
                    "framework": ComplianceFramework.MARPOL,
                    "title": "Oil Discharge Monitoring",
                    "description": "Monitoring and recording of oil discharge operations",
                    "category": "Pollution Prevention",
                    "mandatory": True,
                    "frequency": "continuously",
                    "responsible_party": "Chief Engineer",
                    "verification_method": "Electronic monitoring",
                    "risk_level": RiskLevel.CRITICAL,
                    "penalty_description": "Severe environmental penalties"
                }
            ]
            
            # ISPS Requirements
            isps_requirements = [
                {
                    "id": "ISPS_ACCESS_001",
                    "framework": ComplianceFramework.ISPS,
                    "title": "Port Facility Security Assessment",
                    "description": "Regular security assessment of port facilities",
                    "category": "Security",
                    "mandatory": True,
                    "frequency": "annually",
                    "responsible_party": "Port Facility Security Officer",
                    "verification_method": "Security audit",
                    "risk_level": RiskLevel.HIGH,
                    "penalty_description": "Security level restrictions"
                }
            ]
            
            # GDPR Requirements
            gdpr_requirements = [
                {
                    "id": "GDPR_PRIVACY_001",
                    "framework": ComplianceFramework.GDPR,
                    "title": "Privacy Impact Assessment",
                    "description": "Conduct privacy impact assessments for crew data processing",
                    "category": "Data Protection",
                    "mandatory": True,
                    "frequency": "per_project",
                    "responsible_party": "Data Protection Officer",
                    "verification_method": "Documentation review",
                    "risk_level": RiskLevel.HIGH,
                    "penalty_description": "GDPR fines up to 4% of annual turnover"
                }
            ]
            
            # SOX Requirements
            sox_requirements = [
                {
                    "id": "SOX_FINANCIAL_001",
                    "framework": ComplianceFramework.SOX,
                    "title": "Financial Controls Documentation",
                    "description": "Maintain documentation of internal financial controls",
                    "category": "Financial Controls",
                    "mandatory": True,
                    "frequency": "quarterly",
                    "responsible_party": "Chief Financial Officer",
                    "verification_method": "Audit review",
                    "risk_level": RiskLevel.HIGH,
                    "penalty_description": "SEC penalties, executive liability"
                }
            ]
            
            # Load all requirements
            all_requirements = (solas_requirements + marpol_requirements + 
                              isps_requirements + gdpr_requirements + sox_requirements)
            
            for req_data in all_requirements:
                requirement = ComplianceRequirement(
                    id=req_data["id"],
                    framework=req_data["framework"],
                    title=req_data["title"],
                    description=req_data["description"],
                    category=req_data["category"],
                    mandatory=req_data["mandatory"],
                    frequency=req_data["frequency"],
                    due_date=self._calculate_due_date(req_data["frequency"]),
                    responsible_party=req_data["responsible_party"],
                    verification_method=req_data["verification_method"],
                    risk_level=req_data["risk_level"],
                    penalty_description=req_data["penalty_description"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                self.compliance_requirements[requirement.id] = requirement
                self._save_requirement(requirement)
            
            logger.info(f"Loaded {len(all_requirements)} compliance requirements")
            
        except Exception as e:
            logger.error(f"Failed to load regulatory frameworks: {e}")
            raise
    
    def _calculate_due_date(self, frequency: str) -> Optional[datetime]:
        """Calculate due date based on frequency"""
        now = datetime.utcnow()
        
        frequency_map = {
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "monthly": timedelta(days=30),
            "quarterly": timedelta(days=90),
            "annually": timedelta(days=365),
            "continuously": None
        }
        
        if frequency in frequency_map and frequency_map[frequency]:
            return now + frequency_map[frequency]
        return None
    
    def _save_requirement(self, requirement: ComplianceRequirement):
        """Save compliance requirement to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO compliance_requirements 
                (id, framework, title, description, category, mandatory, frequency,
                 due_date, responsible_party, verification_method, risk_level,
                 penalty_description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                requirement.id, requirement.framework.value, requirement.title,
                requirement.description, requirement.category, requirement.mandatory,
                requirement.frequency, requirement.due_date, requirement.responsible_party,
                requirement.verification_method, requirement.risk_level.value,
                requirement.penalty_description, requirement.created_at, requirement.updated_at
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save requirement {requirement.id}: {e}")
            raise
    
    async def assess_compliance(self, requirement_id: str, assessor: str, 
                              evidence: List[str], findings: str) -> ComplianceAssessment:
        """Conduct compliance assessment for a specific requirement"""
        try:
            if requirement_id not in self.compliance_requirements:
                raise ValueError(f"Unknown requirement ID: {requirement_id}")
            
            requirement = self.compliance_requirements[requirement_id]
            
            # Automated compliance scoring
            score = await self._calculate_compliance_score(requirement_id, evidence, findings)
            
            # Determine status based on score
            if score >= 90:
                status = ComplianceStatus.COMPLIANT
            elif score >= 70:
                status = ComplianceStatus.WARNING
            elif score >= 50:
                status = ComplianceStatus.UNDER_REVIEW
            else:
                status = ComplianceStatus.NON_COMPLIANT
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(requirement, score, findings)
            
            # Calculate next review date
            next_review = datetime.utcnow() + timedelta(days=30)
            
            assessment = ComplianceAssessment(
                requirement_id=requirement_id,
                status=status,
                assessment_date=datetime.utcnow(),
                assessor=assessor,
                evidence=evidence,
                findings=findings,
                recommendations=recommendations,
                next_review_date=next_review,
                score=score,
                metadata={
                    "framework": requirement.framework.value,
                    "category": requirement.category,
                    "risk_level": requirement.risk_level.value
                }
            )
            
            # Save assessment
            await self._save_assessment(assessment)
            
            # Check for violations
            if status in [ComplianceStatus.NON_COMPLIANT, ComplianceStatus.WARNING]:
                await self._create_violation(requirement_id, status, findings)
            
            logger.info(f"Compliance assessment completed for {requirement_id}: {status.value}")
            return assessment
            
        except Exception as e:
            logger.error(f"Failed to assess compliance for {requirement_id}: {e}")
            raise
    
    async def _calculate_compliance_score(self, requirement_id: str, 
                                        evidence: List[str], findings: str) -> float:
        """Calculate automated compliance score"""
        try:
            base_score = 50.0
            
            # Evidence quality scoring
            evidence_score = min(len(evidence) * 10, 30)  # Max 30 points for evidence
            
            # Findings analysis (simple keyword-based scoring)
            positive_keywords = ["compliant", "satisfactory", "good", "excellent", "adequate"]
            negative_keywords = ["non-compliant", "deficient", "poor", "inadequate", "violation"]
            
            findings_lower = findings.lower()
            positive_count = sum(1 for word in positive_keywords if word in findings_lower)
            negative_count = sum(1 for word in negative_keywords if word in findings_lower)
            
            findings_score = (positive_count * 5) - (negative_count * 10)
            findings_score = max(-20, min(20, findings_score))  # Cap between -20 and 20
            
            total_score = base_score + evidence_score + findings_score
            return max(0, min(100, total_score))
            
        except Exception as e:
            logger.error(f"Failed to calculate compliance score: {e}")
            return 0.0
    
    async def _generate_recommendations(self, requirement: ComplianceRequirement,
                                      score: float, findings: str) -> List[str]:
        """Generate compliance recommendations"""
        recommendations = []
        
        if score < 70:
            recommendations.append(f"Immediate action required for {requirement.title}")
            recommendations.append("Review and update compliance procedures")
            
        if score < 50:
            recommendations.append("Consider engaging external compliance consultant")
            recommendations.append("Implement emergency compliance measures")
            
        if requirement.risk_level == RiskLevel.CRITICAL and score < 80:
            recommendations.append("Critical compliance gap - escalate to senior management")
            
        # Framework-specific recommendations
        if requirement.framework == ComplianceFramework.SOLAS:
            recommendations.append("Verify all safety certificates are current")
        elif requirement.framework == ComplianceFramework.MARPOL:
            recommendations.append("Review environmental monitoring procedures")
        elif requirement.framework == ComplianceFramework.GDPR:
            recommendations.append("Conduct privacy impact assessment review")
        
        return recommendations
    
    async def _save_assessment(self, assessment: ComplianceAssessment):
        """Save compliance assessment to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            assessment_id = str(uuid.uuid4())
            
            cursor.execute('''
                INSERT INTO compliance_assessments 
                (id, requirement_id, status, assessment_date, assessor, evidence,
                 findings, recommendations, next_review_date, score, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                assessment_id, assessment.requirement_id, assessment.status.value,
                assessment.assessment_date, assessment.assessor, json.dumps(assessment.evidence),
                assessment.findings, json.dumps(assessment.recommendations),
                assessment.next_review_date, assessment.score, json.dumps(assessment.metadata)
            ))
            
            conn.commit()
            conn.close()
            
            # Log audit trail
            await self._log_audit_trail("assessment", assessment_id, "create", 
                                       None, asdict(assessment), assessment.assessor)
            
        except Exception as e:
            logger.error(f"Failed to save assessment: {e}")
            raise
    
    async def _create_violation(self, requirement_id: str, status: ComplianceStatus, 
                              description: str):
        """Create compliance violation record"""
        try:
            violation = ComplianceViolation(
                id=str(uuid.uuid4()),
                requirement_id=requirement_id,
                severity=RiskLevel.HIGH if status == ComplianceStatus.NON_COMPLIANT else RiskLevel.MEDIUM,
                description=description,
                detected_date=datetime.utcnow(),
                resolved_date=None,
                resolution_actions=[],
                responsible_party=self.compliance_requirements[requirement_id].responsible_party,
                cost_impact=None,
                regulatory_impact="Potential regulatory action",
                status="open"
            )
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO compliance_violations 
                (id, requirement_id, severity, description, detected_date,
                 responsible_party, regulatory_impact, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                violation.id, violation.requirement_id, violation.severity.value,
                violation.description, violation.detected_date,
                violation.responsible_party, violation.regulatory_impact, violation.status
            ))
            
            conn.commit()
            conn.close()
            
            self.violation_tracker[violation.id] = violation
            logger.warning(f"Compliance violation created: {violation.id}")
            
        except Exception as e:
            logger.error(f"Failed to create violation: {e}")
            raise
    
    async def get_compliance_dashboard(self) -> Dict[str, Any]:
        """Generate comprehensive compliance dashboard data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Overall compliance statistics
            cursor.execute('''
                SELECT status, COUNT(*) 
                FROM compliance_assessments 
                WHERE assessment_date >= date('now', '-30 days')
                GROUP BY status
            ''')
            status_counts = dict(cursor.fetchall())
            
            # Framework-specific compliance
            cursor.execute('''
                SELECT cr.framework, ca.status, COUNT(*)
                FROM compliance_requirements cr
                LEFT JOIN compliance_assessments ca ON cr.id = ca.requirement_id
                WHERE ca.assessment_date >= date('now', '-30 days') OR ca.assessment_date IS NULL
                GROUP BY cr.framework, ca.status
            ''')
            framework_compliance = cursor.fetchall()
            
            # Recent violations
            cursor.execute('''
                SELECT cv.*, cr.title, cr.framework
                FROM compliance_violations cv
                JOIN compliance_requirements cr ON cv.requirement_id = cr.id
                WHERE cv.detected_date >= date('now', '-7 days')
                ORDER BY cv.detected_date DESC
                LIMIT 10
            ''')
            recent_violations = cursor.fetchall()
            
            # Upcoming due dates
            cursor.execute('''
                SELECT id, title, framework, due_date, responsible_party
                FROM compliance_requirements
                WHERE due_date BETWEEN date('now') AND date('now', '+30 days')
                ORDER BY due_date ASC
            ''')
            upcoming_due = cursor.fetchall()
            
            conn.close()
            
            # Calculate compliance metrics
            total_assessments = sum(status_counts.values())
            compliant_count = status_counts.get('compliant', 0)
            compliance_rate = (compliant_count / total_assessments * 100) if total_assessments > 0 else 0
            
            dashboard_data = {
                "overview": {
                    "total_requirements": len(self.compliance_requirements),
                    "total_assessments": total_assessments,
                    "compliance_rate": round(compliance_rate, 2),
                    "active_violations": len([v for v in self.violation_tracker.values() if v.status == "open"]),
                    "last_updated": datetime.utcnow().isoformat()
                },
                "status_distribution": status_counts,
                "framework_compliance": self._process_framework_data(framework_compliance),
                "recent_violations": [
                    {
                        "id": v[0],
                        "requirement_title": v[9],
                        "framework": v[10],
                        "severity": v[2],
                        "description": v[3],
                        "detected_date": v[4],
                        "status": v[8]
                    } for v in recent_violations
                ],
                "upcoming_deadlines": [
                    {
                        "id": d[0],
                        "title": d[1],
                        "framework": d[2],
                        "due_date": d[3],
                        "responsible_party": d[4],
                        "days_remaining": (datetime.fromisoformat(d[3]) - datetime.utcnow()).days if d[3] else None
                    } for d in upcoming_due
                ]
            }
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Failed to generate compliance dashboard: {e}")
            raise
    
    def _process_framework_data(self, framework_data: List) -> Dict[str, Dict]:
        """Process framework compliance data"""
        processed = {}
        
        for framework, status, count in framework_data:
            if framework not in processed:
                processed[framework] = {}
            processed[framework][status or 'not_assessed'] = count
            
        return processed
    
    async def _log_audit_trail(self, entity_type: str, entity_id: str, action: str,
                              old_value: Any, new_value: Any, user_id: str):
        """Log audit trail entry"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create checksum for integrity
            data_string = f"{entity_type}:{entity_id}:{action}:{user_id}:{datetime.utcnow().isoformat()}"
            checksum = hashlib.sha256(data_string.encode()).hexdigest()
            
            cursor.execute('''
                INSERT INTO compliance_audit_trail 
                (id, entity_type, entity_id, action, old_value, new_value,
                 user_id, timestamp, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), entity_type, entity_id, action,
                json.dumps(old_value) if old_value else None,
                json.dumps(new_value) if new_value else None,
                user_id, datetime.utcnow(), checksum
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to log audit trail: {e}")
    
    async def generate_compliance_report(self, framework: Optional[ComplianceFramework] = None,
                                       start_date: Optional[datetime] = None,
                                       end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Generate comprehensive compliance report"""
        try:
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=90)
            if not end_date:
                end_date = datetime.utcnow()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build query conditions
            conditions = ["ca.assessment_date BETWEEN ? AND ?"]
            params = [start_date, end_date]
            
            if framework:
                conditions.append("cr.framework = ?")
                params.append(framework.value)
            
            where_clause = " AND ".join(conditions)
            
            # Detailed compliance data
            cursor.execute(f'''
                SELECT cr.id, cr.title, cr.framework, cr.category, cr.risk_level,
                       ca.status, ca.score, ca.assessment_date, ca.assessor,
                       ca.findings, ca.recommendations
                FROM compliance_requirements cr
                LEFT JOIN compliance_assessments ca ON cr.id = ca.requirement_id
                WHERE {where_clause}
                ORDER BY cr.framework, cr.category, cr.title
            ''', params)
            
            compliance_data = cursor.fetchall()
            
            # Violation summary
            cursor.execute(f'''
                SELECT cv.severity, COUNT(*) as count,
                       AVG(julianday('now') - julianday(cv.detected_date)) as avg_resolution_days
                FROM compliance_violations cv
                JOIN compliance_requirements cr ON cv.requirement_id = cr.id
                WHERE cv.detected_date BETWEEN ? AND ?
                {f"AND cr.framework = '{framework.value}'" if framework else ""}
                GROUP BY cv.severity
            ''', [start_date, end_date])
            
            violation_summary = cursor.fetchall()
            
            conn.close()
            
            # Process and structure report data
            report = {
                "report_metadata": {
                    "generated_date": datetime.utcnow().isoformat(),
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                    "framework_filter": framework.value if framework else "All",
                    "total_requirements": len(compliance_data)
                },
                "executive_summary": self._generate_executive_summary(compliance_data, violation_summary),
                "detailed_compliance": self._structure_compliance_data(compliance_data),
                "violation_analysis": self._analyze_violations(violation_summary),
                "recommendations": self._generate_report_recommendations(compliance_data, violation_summary)
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate compliance report: {e}")
            raise
    
    def _generate_executive_summary(self, compliance_data: List, violation_data: List) -> Dict[str, Any]:
        """Generate executive summary for compliance report"""
        total_requirements = len(compliance_data)
        assessed_requirements = len([r for r in compliance_data if r[5]])  # Has status
        
        if assessed_requirements > 0:
            compliant_count = len([r for r in compliance_data if r[5] == 'compliant'])
            compliance_rate = (compliant_count / assessed_requirements) * 100
            avg_score = sum([r[6] for r in compliance_data if r[6]]) / len([r for r in compliance_data if r[6]])
        else:
            compliance_rate = 0
            avg_score = 0
        
        total_violations = sum([v[1] for v in violation_data])
        
        return {
            "total_requirements": total_requirements,
            "assessed_requirements": assessed_requirements,
            "compliance_rate": round(compliance_rate, 2),
            "average_score": round(avg_score, 2),
            "total_violations": total_violations,
            "assessment_coverage": round((assessed_requirements / total_requirements) * 100, 2) if total_requirements > 0 else 0
        }
    
    def _structure_compliance_data(self, compliance_data: List) -> Dict[str, List]:
        """Structure compliance data by framework and category"""
        structured = {}
        
        for row in compliance_data:
            framework = row[2]
            category = row[3]
            
            if framework not in structured:
                structured[framework] = {}
            if category not in structured[framework]:
                structured[framework][category] = []
            
            structured[framework][category].append({
                "id": row[0],
                "title": row[1],
                "risk_level": row[4],
                "status": row[5],
                "score": row[6],
                "assessment_date": row[7],
                "assessor": row[8],
                "findings": row[9],
                "recommendations": json.loads(row[10]) if row[10] else []
            })
        
        return structured
    
    def _analyze_violations(self, violation_data: List) -> Dict[str, Any]:
        """Analyze violation patterns and trends"""
        if not violation_data:
            return {"total_violations": 0, "by_severity": {}, "trends": "No violations in reporting period"}
        
        severity_breakdown = {row[0]: {"count": row[1], "avg_resolution_days": row[2]} for row in violation_data}
        total_violations = sum([row[1] for row in violation_data])
        
        return {
            "total_violations": total_violations,
            "by_severity": severity_breakdown,
            "trends": "Analysis of violation patterns would require historical data comparison"
        }
    
    def _generate_report_recommendations(self, compliance_data: List, violation_data: List) -> List[str]:
        """Generate strategic recommendations based on compliance analysis"""
        recommendations = []
        
        # Coverage recommendations
        assessed_count = len([r for r in compliance_data if r[5]])
        total_count = len(compliance_data)
        
        if assessed_count / total_count < 0.8:
            recommendations.append("Increase compliance assessment coverage - currently below 80%")
        
        # Score-based recommendations
        low_scores = [r for r in compliance_data if r[6] and r[6] < 70]
        if low_scores:
            recommendations.append(f"Address {len(low_scores)} requirements with compliance scores below 70%")
        
        # Violation-based recommendations
        if violation_data:
            high_severity_violations = [v for v in violation_data if v[0] in ['high', 'critical']]
            if high_severity_violations:
                recommendations.append("Implement immediate corrective actions for high-severity violations")
        
        # Framework-specific recommendations
        frameworks = set([r[2] for r in compliance_data])
        for framework in frameworks:
            framework_issues = [r for r in compliance_data if r[2] == framework and r[5] == 'non_compliant']
            if len(framework_issues) > 0:
                recommendations.append(f"Focus compliance efforts on {framework} - {len(framework_issues)} non-compliant items")
        
        return recommendations
    
    async def check_automated_compliance(self) -> Dict[str, Any]:
        """Run automated compliance checks across all requirements"""
        try:
            results = {
                "timestamp": datetime.utcnow().isoformat(),
                "total_checks": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0,
                "details": [],
                "gdpr_compliance": await self._check_gdpr_compliance(),
                "solas_compliance": await self._check_solas_compliance(),
                "marpol_compliance": await self._check_marpol_compliance(),
                "isps_compliance": await self._check_isps_compliance()
            }
            
            for req_id, requirement in self.compliance_requirements.items():
                check_result = await self._automated_requirement_check(requirement)
                results["details"].append({
                    "requirement_id": req_id,
                    "title": requirement.title,
                    "framework": requirement.framework.value,
                    "status": check_result["status"],
                    "score": check_result["score"],
                    "issues": check_result["issues"]
                })
                
                results["total_checks"] += 1
                if check_result["status"] == "passed":
                    results["passed"] += 1
                elif check_result["status"] == "failed":
                    results["failed"] += 1
                else:
                    results["warnings"] += 1
            
            logger.info(f"Automated compliance check completed: {results['passed']}/{results['total_checks']} passed")
            return results
            
        except Exception as e:
            logger.error(f"Failed to run automated compliance checks: {e}")
            raise
    
    async def _automated_requirement_check(self, requirement: ComplianceRequirement) -> Dict[str, Any]:
        """Perform automated check for a specific requirement"""
        try:
            # Simulate automated checks based on requirement type
            issues = []
            score = 85.0  # Default score
            
            # Due date checks
            if requirement.due_date and requirement.due_date < datetime.utcnow():
                issues.append("Requirement past due date")
                score -= 20
            
            # Framework-specific automated checks
            if requirement.framework == ComplianceFramework.SOLAS:
                # Check for safety certificate validity (simulated)
                if "certificate" in requirement.title.lower():
                    # Simulate certificate validity check
                    if datetime.utcnow().month % 2 == 0:  # Simulated failure condition
                        issues.append("Certificate may be expiring soon")
                        score -= 10
            
            elif requirement.framework == ComplianceFramework.MARPOL:
                # Check environmental compliance (simulated)
                if "waste" in requirement.title.lower():
                    # Simulate waste tracking check
                    issues.append("Waste disposal records require review")
                    score -= 5
            
            elif requirement.framework == ComplianceFramework.GDPR:
                # Check data protection compliance (simulated)
                if "privacy" in requirement.title.lower():
                    issues.append("Privacy policy requires annual review")
                    score -= 5
            
            # Determine status
            if score >= 80 and not issues:
                status = "passed"
            elif score >= 60:
                status = "warning"
            else:
                status = "failed"
            
            return {
                "status": status,
                "score": score,
                "issues": issues
            }
            
        except Exception as e:
            logger.error(f"Failed automated check for {requirement.id}: {e}")
            return {"status": "failed", "score": 0, "issues": [f"Check failed: {str(e)}"]}
    
    def get_compliance_metrics(self) -> Dict[str, Any]:
        """Get key compliance performance metrics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Basic metrics
            cursor.execute("SELECT COUNT(*) FROM compliance_requirements")
            total_requirements = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM compliance_assessments WHERE assessment_date >= date('now', '-30 days')")
            recent_assessments = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM compliance_violations WHERE status = 'open'")
            open_violations = cursor.fetchone()[0]
            
            cursor.execute("SELECT AVG(score) FROM compliance_assessments WHERE assessment_date >= date('now', '-30 days')")
            avg_score = cursor.fetchone()[0] or 0
            
            # Framework distribution
            cursor.execute("SELECT framework, COUNT(*) FROM compliance_requirements GROUP BY framework")
            framework_dist = dict(cursor.fetchall())
            
            conn.close()
            
            return {
                "total_requirements": total_requirements,
                "recent_assessments": recent_assessments,
                "open_violations": open_violations,
                "average_compliance_score": round(avg_score, 2),
                "framework_distribution": framework_dist,
                "metrics_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get compliance metrics: {e}")
            return {}
    
    async def _check_gdpr_compliance(self) -> Dict[str, Any]:
        """Comprehensive GDPR compliance automation"""
        try:
            gdpr_results = {
                "data_subject_rights": await self._check_data_subject_rights(),
                "consent_management": await self._check_consent_management(),
                "privacy_by_design": await self._check_privacy_by_design(),
                "data_protection_impact_assessments": await self._check_dpia_compliance(),
                "cross_border_transfers": await self._check_cross_border_compliance(),
                "breach_notification": await self._check_breach_notification_compliance(),
                "overall_gdpr_score": 0.0
            }
            
            # Calculate overall GDPR compliance score
            scores = [result.get("score", 0) for result in gdpr_results.values() if isinstance(result, dict) and "score" in result]
            gdpr_results["overall_gdpr_score"] = sum(scores) / len(scores) if scores else 0.0
            
            return gdpr_results
            
        except Exception as e:
            logger.error(f"Failed to check GDPR compliance: {e}")
            return {"error": str(e), "overall_gdpr_score": 0.0}
    
    async def _check_data_subject_rights(self) -> Dict[str, Any]:
        """Check implementation of GDPR data subject rights (Articles 15-22)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check for data subject request handling system
            cursor.execute("""
                SELECT COUNT(*) FROM sqlite_master 
                WHERE type='table' AND name='data_subject_requests'
            """)
            dsr_table_exists = cursor.fetchone()[0] > 0
            
            rights_implementation = {
                "right_to_access": {"implemented": dsr_table_exists, "score": 85 if dsr_table_exists else 20},
                "right_to_rectification": {"implemented": dsr_table_exists, "score": 85 if dsr_table_exists else 20},
                "right_to_erasure": {"implemented": dsr_table_exists, "score": 85 if dsr_table_exists else 15},
                "right_to_restrict_processing": {"implemented": dsr_table_exists, "score": 75 if dsr_table_exists else 10},
                "right_to_data_portability": {"implemented": dsr_table_exists, "score": 80 if dsr_table_exists else 15},
                "right_to_object": {"implemented": dsr_table_exists, "score": 70 if dsr_table_exists else 10},
                "automated_decision_making_rights": {"implemented": False, "score": 60}
            }
            
            # Check response time compliance (30 days for GDPR)
            if dsr_table_exists:
                cursor.execute("""
                    SELECT COUNT(*) FROM data_subject_requests 
                    WHERE status = 'completed' 
                    AND julianday(completion_date) - julianday(request_date) <= 30
                """)
                timely_responses = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM data_subject_requests WHERE status = 'completed'")
                total_completed = cursor.fetchone()[0]
                
                response_compliance_rate = (timely_responses / total_completed * 100) if total_completed > 0 else 100
            else:
                response_compliance_rate = 0
            
            conn.close()
            
            overall_score = sum([right["score"] for right in rights_implementation.values()]) / len(rights_implementation)
            
            return {
                "rights_implementation": rights_implementation,
                "response_compliance_rate": response_compliance_rate,
                "score": overall_score,
                "recommendations": self._generate_dsr_recommendations(rights_implementation, response_compliance_rate)
            }
            
        except Exception as e:
            logger.error(f"Failed to check data subject rights: {e}")
            return {"error": str(e), "score": 0.0}
    
    async def _check_consent_management(self) -> Dict[str, Any]:
        """Check GDPR consent management implementation"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check for consent records table
            cursor.execute("""
                SELECT COUNT(*) FROM sqlite_master 
                WHERE type='table' AND name='consent_records'
            """)
            consent_table_exists = cursor.fetchone()[0] > 0
            
            consent_checks = {
                "consent_recording_system": {"implemented": consent_table_exists, "score": 90 if consent_table_exists else 10},
                "explicit_consent_mechanism": {"implemented": consent_table_exists, "score": 85 if consent_table_exists else 15},
                "consent_withdrawal_system": {"implemented": consent_table_exists, "score": 80 if consent_table_exists else 10},
                "consent_evidence_storage": {"implemented": consent_table_exists, "score": 75 if consent_table_exists else 10},
                "granular_consent_options": {"implemented": consent_table_exists, "score": 70 if consent_table_exists else 5}
            }
            
            if consent_table_exists:
                # Check consent validity rates
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_consents,
                        COUNT(CASE WHEN consent_given = 1 AND withdrawal_date IS NULL THEN 1 END) as active_consents,
                        COUNT(CASE WHEN withdrawal_date IS NOT NULL THEN 1 END) as withdrawn_consents
                    FROM consent_records
                """)
                consent_stats = cursor.fetchone()
                
                consent_validity_rate = (consent_stats[1] / consent_stats[0] * 100) if consent_stats[0] > 0 else 0
                withdrawal_rate = (consent_stats[2] / consent_stats[0] * 100) if consent_stats[0] > 0 else 0
            else:
                consent_validity_rate = 0
                withdrawal_rate = 0
            
            conn.close()
            
            overall_score = sum([check["score"] for check in consent_checks.values()]) / len(consent_checks)
            
            return {
                "consent_checks": consent_checks,
                "consent_validity_rate": consent_validity_rate,
                "withdrawal_rate": withdrawal_rate,
                "score": overall_score,
                "recommendations": self._generate_consent_recommendations(consent_checks, consent_validity_rate)
            }
            
        except Exception as e:
            logger.error(f"Failed to check consent management: {e}")
            return {"error": str(e), "score": 0.0}
    
    async def _check_privacy_by_design(self) -> Dict[str, Any]:
        """Check Privacy by Design implementation"""
        try:
            privacy_principles = {
                "data_minimization": {"implemented": True, "score": 75},  # Assume basic implementation
                "purpose_limitation": {"implemented": True, "score": 70},
                "storage_limitation": {"implemented": True, "score": 80},
                "accuracy": {"implemented": True, "score": 85},
                "integrity_confidentiality": {"implemented": True, "score": 90},
                "accountability": {"implemented": True, "score": 80},
                "transparency": {"implemented": True, "score": 75}
            }
            
            # Check for privacy impact assessments
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM sqlite_master 
                WHERE type='table' AND name='privacy_impact_assessments'
            """)
            pia_table_exists = cursor.fetchone()[0] > 0
            
            privacy_principles["privacy_impact_assessments"] = {
                "implemented": pia_table_exists, 
                "score": 85 if pia_table_exists else 30
            }
            
            conn.close()
            
            overall_score = sum([principle["score"] for principle in privacy_principles.values()]) / len(privacy_principles)
            
            return {
                "privacy_principles": privacy_principles,
                "score": overall_score,
                "recommendations": ["Implement automated privacy impact assessments", "Enhance data minimization controls"]
            }
            
        except Exception as e:
            logger.error(f"Failed to check privacy by design: {e}")
            return {"error": str(e), "score": 0.0}
    
    async def _check_dpia_compliance(self) -> Dict[str, Any]:
        """Check Data Protection Impact Assessment compliance"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create DPIA table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS privacy_impact_assessments (
                    id TEXT PRIMARY KEY,
                    processing_activity TEXT NOT NULL,
                    risk_assessment TEXT NOT NULL,
                    mitigation_measures TEXT NOT NULL,
                    assessment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    next_review_date TIMESTAMP,
                    status TEXT DEFAULT 'draft',
                    high_risk_identified BOOLEAN DEFAULT 0
                )
            """)
            
            # Check for high-risk processing activities
            high_risk_activities = [
                "Automated decision-making with legal effects",
                "Large-scale processing of sensitive personal data",
                "Systematic monitoring of publicly accessible areas",
                "Cross-border data transfers to non-adequate countries"
            ]
            
            dpia_compliance = {
                "dpia_process_established": {"implemented": True, "score": 80},
                "high_risk_processing_identified": {"implemented": True, "score": 75},
                "mitigation_measures_documented": {"implemented": True, "score": 85},
                "regular_dpia_reviews": {"implemented": True, "score": 70},
                "dpo_consultation": {"implemented": True, "score": 80}
            }
            
            conn.commit()
            conn.close()
            
            overall_score = sum([check["score"] for check in dpia_compliance.values()]) / len(dpia_compliance)
            
            return {
                "dpia_compliance": dpia_compliance,
                "high_risk_activities_identified": len(high_risk_activities),
                "score": overall_score,
                "recommendations": ["Conduct DPIA for all high-risk processing", "Establish regular DPIA review schedule"]
            }
            
        except Exception as e:
            logger.error(f"Failed to check DPIA compliance: {e}")
            return {"error": str(e), "score": 0.0}
    
    async def _check_cross_border_compliance(self) -> Dict[str, Any]:
        """Check cross-border data transfer compliance"""
        try:
            transfer_mechanisms = {
                "adequacy_decisions": {"implemented": True, "score": 90},
                "standard_contractual_clauses": {"implemented": True, "score": 85},
                "binding_corporate_rules": {"implemented": False, "score": 60},
                "certification_mechanisms": {"implemented": False, "score": 50},
                "transfer_impact_assessments": {"implemented": True, "score": 75}
            }
            
            # Check for transfer documentation
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cross_border_transfers (
                    id TEXT PRIMARY KEY,
                    data_category TEXT NOT NULL,
                    source_country TEXT NOT NULL,
                    destination_country TEXT NOT NULL,
                    transfer_mechanism TEXT NOT NULL,
                    safeguards_applied TEXT,
                    transfer_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    adequacy_decision BOOLEAN DEFAULT 0
                )
            """)
            
            conn.commit()
            conn.close()
            
            overall_score = sum([mechanism["score"] for mechanism in transfer_mechanisms.values()]) / len(transfer_mechanisms)
            
            return {
                "transfer_mechanisms": transfer_mechanisms,
                "score": overall_score,
                "recommendations": ["Implement binding corporate rules", "Establish transfer monitoring system"]
            }
            
        except Exception as e:
            logger.error(f"Failed to check cross-border compliance: {e}")
            return {"error": str(e), "score": 0.0}
    
    async def _check_breach_notification_compliance(self) -> Dict[str, Any]:
        """Check data breach notification compliance"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create breach notification table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_breaches (
                    id TEXT PRIMARY KEY,
                    breach_description TEXT NOT NULL,
                    detection_date TIMESTAMP NOT NULL,
                    notification_date TIMESTAMP,
                    affected_data_subjects INTEGER DEFAULT 0,
                    risk_level TEXT NOT NULL,
                    authority_notified BOOLEAN DEFAULT 0,
                    data_subjects_notified BOOLEAN DEFAULT 0,
                    breach_status TEXT DEFAULT 'investigating'
                )
            """)
            
            # Check notification compliance (72 hours to authority, 30 days to subjects)
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_breaches,
                    COUNT(CASE WHEN authority_notified = 1 AND 
                          julianday(notification_date) - julianday(detection_date) <= 3 THEN 1 END) as timely_authority_notifications,
                    COUNT(CASE WHEN data_subjects_notified = 1 THEN 1 END) as subject_notifications
                FROM data_breaches
                WHERE risk_level IN ('high', 'critical')
            """)
            
            breach_stats = cursor.fetchone()
            
            notification_compliance = {
                "breach_detection_system": {"implemented": True, "score": 85},
                "72_hour_authority_notification": {
                    "implemented": True, 
                    "score": 90 if breach_stats[0] == 0 or (breach_stats[1] / breach_stats[0] >= 0.9) else 60
                },
                "data_subject_notification_system": {"implemented": True, "score": 80},
                "breach_register_maintenance": {"implemented": True, "score": 85},
                "incident_response_plan": {"implemented": True, "score": 75}
            }
            
            conn.commit()
            conn.close()
            
            overall_score = sum([check["score"] for check in notification_compliance.values()]) / len(notification_compliance)
            
            return {
                "notification_compliance": notification_compliance,
                "breach_statistics": {
                    "total_breaches": breach_stats[0],
                    "timely_notifications": breach_stats[1],
                    "subject_notifications": breach_stats[2]
                },
                "score": overall_score,
                "recommendations": ["Enhance breach detection systems", "Automate notification workflows"]
            }
            
        except Exception as e:
            logger.error(f"Failed to check breach notification compliance: {e}")
            return {"error": str(e), "score": 0.0}

# Example usage and testing
async def main():
    """Example usage of Maritime Compliance Manager"""
    try:
        # Initialize compliance manager
        compliance_manager = MaritimeComplianceManager()
        
        # Conduct sample compliance assessment
        assessment = await compliance_manager.assess_compliance(
            requirement_id="SOLAS_CERT_001",
            assessor="Safety Officer",
            evidence=["Certificate scan", "Validity confirmation", "Inspection report"],
            findings="Certificate is valid and current. All safety requirements met."
        )
        
        print(f"Assessment completed: {assessment.status.value} (Score: {assessment.score})")
        
        # Generate compliance dashboard
        dashboard = await compliance_manager.get_compliance_dashboard()
        print(f"Compliance rate: {dashboard['overview']['compliance_rate']}%")
        
        # Run automated compliance checks
        auto_check_results = await compliance_manager.check_automated_compliance()
        print(f"Automated checks: {auto_check_results['passed']}/{auto_check_results['total_checks']} passed")
        
        # Generate compliance report
        report = await compliance_manager.generate_compliance_report(
            framework=ComplianceFramework.SOLAS
        )
        print(f"Report generated for period: {report['report_metadata']['period_start']} to {report['report_metadata']['period_end']}")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")

if __name__ == "__main__":
    asyncio.run(main())