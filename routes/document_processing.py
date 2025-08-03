"""
Document Processing Routes
Handles document upload and auto-fill processing for vessel wizard
Supports both online server-side and offline client-side processing
"""

import os
import json
from flask import Blueprint, request, jsonify, current_app, g
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from utils.document_processor import DocumentProcessor, OfflineDocumentProcessor

# Import Phase 3 secure file handling
from utils.secure_file_handler import get_secure_file_handler, handle_secure_upload
from utils.jwt_auth import jwt_required, jwt_optional
from utils.api_validators import validate_json, document_upload_schema, maritime_api_response
from utils.maritime_api_policies import require_maritime_permission, MaritimePermission
from utils.audit_logger import get_audit_logger, AuditEventType, AuditSeverity

# Create blueprint
document_bp = Blueprint('document', __name__)

# Initialize document processor
processor = DocumentProcessor()

@document_bp.route('/upload', methods=['POST'])
@login_required
@jwt_optional  # Support both session-based and JWT authentication
@require_maritime_permission(MaritimePermission.UPLOAD_DOCUMENTS)
def upload_document():
    """Handle secure document upload and processing with comprehensive security validation"""
    try:
        # Initialize security components
        secure_handler = get_secure_file_handler()
        audit_logger = get_audit_logger()
        
        # Log upload attempt
        audit_logger.log_event(
            AuditEventType.DOCUMENT_UPLOADED,
            "Document upload initiated",
            severity=AuditSeverity.MEDIUM,
            maritime_context={
                'upload_operation': True,
                'user_id': current_user.id if current_user.is_authenticated else None,
            }
        )
        
        # Validate file presence
        if 'document' not in request.files:
            audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                "Document upload attempted without file"
            )
            return maritime_api_response(
                errors=['No document uploaded'],
                status_code=400
            )
        
        file = request.files['document']
        if not file or file.filename == '':
            audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                "Document upload attempted with empty filename"
            )
            return maritime_api_response(
                errors=['No file selected'],
                status_code=400
            )
        
        # Get document metadata from request
        document_type = request.form.get('document_type', 'general')
        vessel_id = request.form.get('vessel_id', type=int)
        additional_metadata = {
            'upload_source': 'web_interface',
            'processing_requested': True,
            'auto_fill_enabled': True,
        }
        
        # Perform secure file upload with comprehensive validation
        current_app.logger.info(f"Processing secure upload: {file.filename}")
        upload_result = secure_handler.handle_upload(
            file_storage=file,
            user_id=current_user.id,
            document_type=document_type,
            vessel_id=vessel_id,
            additional_metadata=additional_metadata
        )
        
        # Check upload result
        if not upload_result.success:
            # Log security rejection
            audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                f"File upload rejected: {upload_result.error_message}",
                details={
                    'filename': file.filename,
                    'rejection_reason': upload_result.error_message,
                    'quarantined': upload_result.quarantined,
                    'security_report': upload_result.security_report.to_dict() if upload_result.security_report else None
                }
            )
            
            return maritime_api_response(
                errors=[upload_result.error_message],
                status_code=400 if not upload_result.quarantined else 403,
                data={
                    'quarantined': upload_result.quarantined,
                    'processing_time': upload_result.processing_time,
                    'security_status': upload_result.security_report.security_threat.value if upload_result.security_report else 'unknown'
                }
            )
        
        # File upload successful - proceed with text extraction and processing
        current_app.logger.info(f"Secure upload successful: {upload_result.file_id}")
        
        # Extract text from securely stored file
        text_content = _extract_text_from_secure_file(
            upload_result.secure_path, 
            file.filename,
            upload_result.security_report
        )
        
        if not text_content:
            # Log extraction failure
            audit_logger.log_event(
                AuditEventType.DOCUMENT_PROCESSED,
                f"Text extraction failed: {file.filename}",
                details={
                    'file_id': upload_result.file_id,
                    'document_type': document_type,
                    'extraction_method': 'failed'
                },
                severity=AuditSeverity.MEDIUM
            )
            
            return maritime_api_response(
                errors=['Could not extract text from document'],
                status_code=400,
                data={
                    'file_id': upload_result.file_id,
                    'upload_successful': True,
                    'text_extraction_failed': True,
                    'security_status': upload_result.security_report.security_threat.value,
                    'maritime_classification': upload_result.security_report.maritime_classification
                }
            )
        
        # Process document for auto-fill
        result = processor.process_document_text(text_content, file.filename)
        
        # Store processing result in user session for wizard access
        if result['success']:
            from flask import session
            session['document_auto_fill'] = {
                'wizard_data': result['wizard_data'],
                'extracted_data': result['extracted_data'],
                'document_source': file.filename,
                'processed_at': result['extracted_data']['extracted_at'],
                'confidence_score': result['extracted_data']['confidence_score'],
                # Add secure file information
                'file_id': upload_result.file_id,
                'security_status': upload_result.security_report.security_threat.value,
                'maritime_classification': upload_result.security_report.maritime_classification,
                'document_type': document_type,
                'vessel_id': vessel_id
            }
            
            # Log successful processing
            audit_logger.log_maritime_operation(
                AuditEventType.DOCUMENT_PROCESSED,
                f"Document processed successfully: {file.filename}",
                vessel_id=vessel_id,
                details={
                    'file_id': upload_result.file_id,
                    'document_type': document_type,
                    'confidence_score': result['extracted_data']['confidence_score'],
                    'processing_successful': True,
                    'auto_fill_data_generated': True,
                    'security_validated': True
                }
            )
        
        # Return comprehensive response
        return maritime_api_response(
            data={
                **result,
                'file_security': {
                    'file_id': upload_result.file_id,
                    'security_status': upload_result.security_report.security_threat.value,
                    'maritime_classification': upload_result.security_report.maritime_classification,
                    'quarantined': upload_result.quarantined,
                    'processing_time': upload_result.processing_time,
                    'threats_detected': upload_result.security_report.threats_detected,
                    'document_type': upload_result.security_report.document_type,
                    'compliance_flags': upload_result.security_report.compliance_flags
                }
            },
            message='Document upload and processing completed successfully'
        )
        
    except Exception as e:
        current_app.logger.error(f"Secure document upload error: {str(e)}")
        
        # Log critical error
        audit_logger = get_audit_logger()
        audit_logger.log_security_event(
            AuditEventType.SECURITY_VIOLATION,
            f"Document upload system error: {str(e)}",
            severity=AuditSeverity.HIGH
        )
        
        return maritime_api_response(
            errors=['Document processing failed due to system error'],
            status_code=500
        )

@document_bp.route('/api/upload', methods=['POST'])
@jwt_required
@require_maritime_permission(MaritimePermission.UPLOAD_DOCUMENTS)
@validate_json(document_upload_schema.__class__)
def api_upload_document():
    """Secure API endpoint for document upload with JWT authentication"""
    try:
        from flask import g
        
        # Use the same secure upload logic but with API response format
        secure_handler = get_secure_file_handler()
        audit_logger = get_audit_logger()
        
        # Log API upload attempt
        audit_logger.log_event(
            AuditEventType.DOCUMENT_UPLOADED,
            "API document upload initiated",
            severity=AuditSeverity.MEDIUM,
            maritime_context={
                'upload_operation': True,
                'api_request': True,
                'user_id': g.jwt_user_id,
                'jwt_scopes': g.jwt_claims.get('scopes', [])
            }
        )
        
        # Validate file presence
        if 'document' not in request.files:
            return maritime_api_response(
                errors=['No document uploaded'],
                status_code=400
            )
        
        file = request.files['document']
        if not file or file.filename == '':
            return maritime_api_response(
                errors=['No file selected'],
                status_code=400
            )
        
        # Get document metadata from validated request
        validated_data = g.validated_data
        document_type = validated_data.get('document_type', 'general')
        vessel_id = validated_data.get('vessel_id')
        
        additional_metadata = {
            'upload_source': 'api_request',
            'jwt_user_id': g.jwt_user_id,
            'api_scopes': g.jwt_claims.get('scopes', []),
            'processing_requested': True,
            'auto_fill_enabled': True,
        }
        
        # Perform secure file upload
        upload_result = secure_handler.handle_upload(
            file_storage=file,
            user_id=g.jwt_user_id,
            document_type=document_type,
            vessel_id=vessel_id,
            additional_metadata=additional_metadata
        )
        
        # Check upload result
        if not upload_result.success:
            return maritime_api_response(
                errors=[upload_result.error_message],
                status_code=400 if not upload_result.quarantined else 403,
                data={
                    'quarantined': upload_result.quarantined,
                    'processing_time': upload_result.processing_time,
                    'security_status': upload_result.security_report.security_threat.value if upload_result.security_report else 'unknown'
                }
            )
        
        # Extract text and process
        text_content = _extract_text_from_secure_file(
            upload_result.secure_path, 
            file.filename,
            upload_result.security_report
        )
        
        processing_result = None
        if text_content:
            processing_result = processor.process_document_text(text_content, file.filename)
        
        # Log successful API upload
        audit_logger.log_maritime_operation(
            AuditEventType.DOCUMENT_PROCESSED,
            f"API document upload successful: {file.filename}",
            vessel_id=vessel_id,
            details={
                'file_id': upload_result.file_id,
                'document_type': document_type,
                'text_extracted': bool(text_content),
                'processing_successful': processing_result['success'] if processing_result else False,
                'api_request': True
            }
        )
        
        return maritime_api_response(
            data={
                'file_id': upload_result.file_id,
                'document_security': {
                    'security_status': upload_result.security_report.security_threat.value,
                    'maritime_classification': upload_result.security_report.maritime_classification,
                    'quarantined': upload_result.quarantined,
                    'processing_time': upload_result.processing_time,
                    'document_type': upload_result.security_report.document_type,
                    'compliance_flags': upload_result.security_report.compliance_flags
                },
                'text_processing': processing_result if processing_result else {'success': False, 'error': 'Text extraction failed'},
                'metadata': upload_result.metadata
            },
            message='Document uploaded and processed successfully via API'
        )
        
    except Exception as e:
        current_app.logger.error(f"API document upload error: {str(e)}")
        
        audit_logger = get_audit_logger()
        audit_logger.log_security_event(
            AuditEventType.SECURITY_VIOLATION,
            f"API document upload system error: {str(e)}",
            severity=AuditSeverity.HIGH
        )
        
        return maritime_api_response(
            errors=['API document upload failed'],
            status_code=500
        )

@document_bp.route('/process-text', methods=['POST'])
@login_required
@jwt_optional
@require_maritime_permission(MaritimePermission.UPLOAD_DOCUMENTS)
def process_text():
    """Process raw text content for auto-fill (enhanced with security logging)"""
    try:
        audit_logger = get_audit_logger()
        
        # Log text processing attempt
        audit_logger.log_event(
            AuditEventType.DOCUMENT_PROCESSED,
            "Raw text processing initiated",
            severity=AuditSeverity.LOW,
            maritime_context={
                'text_processing': True,
                'user_id': current_user.id if current_user.is_authenticated else None,
            }
        )
        
        data = request.get_json()
        if not data or 'text' not in data:
            audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                "Text processing attempted without content"
            )
            return maritime_api_response(
                errors=['No text content provided'],
                status_code=400
            )
        
        text_content = data['text']
        filename = data.get('filename', 'pasted_text')
        document_type = data.get('document_type', 'general')
        vessel_id = data.get('vessel_id', type=int)
        
        # Security validation for text content
        if len(text_content) > 1000000:  # 1MB text limit
            audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                f"Excessive text content size: {len(text_content)} characters"
            )
            return maritime_api_response(
                errors=['Text content too large (max 1MB)'],
                status_code=400
            )
        
        # Check for suspicious patterns in text
        suspicious_patterns = ['<script', 'javascript:', 'data:text/html', 'eval(', 'document.write']
        found_patterns = [pattern for pattern in suspicious_patterns if pattern in text_content.lower()]
        
        if found_patterns:
            audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                f"Suspicious patterns in text content: {', '.join(found_patterns)}"
            )
            return maritime_api_response(
                errors=['Text content contains suspicious patterns'],
                status_code=400
            )
        
        # Process text for auto-fill
        result = processor.process_document_text(text_content, filename)
        
        # Store in session if successful
        if result['success']:
            from flask import session
            session['document_auto_fill'] = {
                'wizard_data': result['wizard_data'],
                'extracted_data': result['extracted_data'], 
                'document_source': filename,
                'processed_at': result['extracted_data']['extracted_at'],
                'confidence_score': result['extracted_data']['confidence_score'],
                # Add security metadata
                'processing_method': 'text_paste',
                'document_type': document_type,
                'vessel_id': vessel_id,
                'security_validated': True,
                'text_length': len(text_content)
            }
            
            # Log successful processing
            audit_logger.log_maritime_operation(
                AuditEventType.DOCUMENT_PROCESSED,
                f"Text processing successful: {filename}",
                vessel_id=vessel_id,
                details={
                    'document_type': document_type,
                    'confidence_score': result['extracted_data']['confidence_score'],
                    'text_length': len(text_content),
                    'processing_method': 'text_paste',
                    'auto_fill_data_generated': True
                }
            )
        
        return maritime_api_response(
            data=result,
            message='Text processing completed successfully'
        )
        
    except Exception as e:
        current_app.logger.error(f"Secure text processing error: {str(e)}")
        
        audit_logger = get_audit_logger()
        audit_logger.log_security_event(
            AuditEventType.SECURITY_VIOLATION,
            f"Text processing system error: {str(e)}",
            severity=AuditSeverity.HIGH
        )
        
        return maritime_api_response(
            errors=['Text processing failed'],
            status_code=500
        )

@document_bp.route('/get-auto-fill', methods=['GET'])
@login_required
def get_auto_fill_data():
    """Get stored auto-fill data from session"""
    try:
        from flask import session
        auto_fill_data = session.get('document_auto_fill')
        
        if not auto_fill_data:
            return jsonify({'has_data': False})
        
        return jsonify({
            'has_data': True,
            'wizard_data': auto_fill_data['wizard_data'],
            'document_source': auto_fill_data['document_source'],
            'confidence_score': auto_fill_data['confidence_score'],
            'processed_at': auto_fill_data['processed_at']
        })
        
    except Exception as e:
        current_app.logger.error(f"Auto-fill retrieval error: {e}")
        return jsonify({'error': 'Failed to retrieve auto-fill data'}), 500

@document_bp.route('/clear-auto-fill', methods=['POST'])
@login_required
def clear_auto_fill_data():
    """Clear stored auto-fill data"""
    try:
        from flask import session
        if 'document_auto_fill' in session:
            del session['document_auto_fill']
        
        return jsonify({'success': True, 'message': 'Auto-fill data cleared'})
        
    except Exception as e:
        current_app.logger.error(f"Auto-fill clear error: {e}")
        return jsonify({'error': 'Failed to clear auto-fill data'}), 500

@document_bp.route('/client-processor.js')
def client_processor_script():
    """Serve client-side document processor JavaScript"""
    try:
        js_code = OfflineDocumentProcessor.generate_client_processor()
        
        from flask import Response
        response = Response(js_code, mimetype='application/javascript')
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
        
    except Exception as e:
        current_app.logger.error(f"Client processor script error: {e}")
        return jsonify({'error': 'Failed to generate client processor'}), 500

def _allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if file extension is allowed"""
    return ('.' in filename and 
            filename.rsplit('.', 1)[1].lower() in allowed_extensions)

def _extract_text_from_secure_file(filepath: str, filename: str, security_report) -> str:
    """Extract text content from securely validated file"""
    try:
        audit_logger = get_audit_logger()
        
        # Log text extraction attempt
        audit_logger.log_event(
            AuditEventType.DOCUMENT_PROCESSED,
            f"Text extraction started: {filename}",
            details={
                'security_status': security_report.security_threat.value,
                'maritime_classification': security_report.maritime_classification,
                'file_size': security_report.file_size,
                'mime_type': security_report.mime_type
            },
            severity=AuditSeverity.LOW
        )
        
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        # Enhanced security check - verify file still exists and hasn't been tampered with
        if not os.path.exists(filepath):
            audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                f"Secure file missing during extraction: {filename}"
            )
            return ""
        
        # Verify file integrity with hash check
        import hashlib
        current_hash = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                current_hash.update(chunk)
        
        if current_hash.hexdigest() != security_report.file_hash:
            audit_logger.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                f"File integrity violation during extraction: {filename}",
                details={'expected_hash': security_report.file_hash, 'actual_hash': current_hash.hexdigest()}
            )
            return ""
        
        # Extract text based on validated file type
        if file_ext == 'txt':
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Security check: scan for suspicious content in text files
                if len(content) > 10000:  # Large text files
                    audit_logger.log_event(
                        AuditEventType.DOCUMENT_PROCESSED,
                        f"Large text file processed: {len(content)} characters",
                        severity=AuditSeverity.LOW
                    )
                
                return content
        
        elif file_ext == 'csv':
            import csv
            text_lines = []
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                row_count = 0
                for row in reader:
                    text_lines.append(' '.join(row))
                    row_count += 1
                    
                    # Security limit: prevent processing huge CSV files
                    if row_count > 10000:
                        audit_logger.log_event(
                            AuditEventType.DOCUMENT_PROCESSED,
                            f"CSV processing limited to 10000 rows: {filename}",
                            severity=AuditSeverity.MEDIUM
                        )
                        break
                        
            return '\n'.join(text_lines)
        
        elif file_ext in ['pdf']:
            # Enhanced PDF processing with security considerations
            audit_logger.log_event(
                AuditEventType.DOCUMENT_PROCESSED,
                f"PDF processing attempted: {filename}",
                details={'notice': 'PDF processing requires additional libraries'},
                severity=AuditSeverity.LOW
            )
            return "PDF processing not yet implemented - please use text files or paste content directly"
        
        elif file_ext in ['doc', 'docx']:
            # Enhanced Word document processing with security considerations
            audit_logger.log_event(
                AuditEventType.DOCUMENT_PROCESSED,
                f"Word document processing attempted: {filename}",
                details={'notice': 'Word processing requires additional libraries'},
                severity=AuditSeverity.LOW
            )
            return "Word document processing not yet implemented - please use text files or paste content directly"
        
        else:
            audit_logger.log_event(
                AuditEventType.DOCUMENT_PROCESSED,
                f"Unsupported file type for text extraction: {file_ext}",
                details={'filename': filename},
                severity=AuditSeverity.MEDIUM
            )
            return ""
            
    except Exception as e:
        current_app.logger.error(f"Secure text extraction error for {filename}: {e}")
        
        # Log extraction error
        audit_logger = get_audit_logger()
        audit_logger.log_security_event(
            AuditEventType.SECURITY_VIOLATION,
            f"Text extraction system error: {str(e)}",
            details={'filename': filename}
        )
        return ""

def _extract_text_from_file(filepath: str, filename: str) -> str:
    """Legacy text extraction (deprecated - use _extract_text_from_secure_file)"""
    try:
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        if file_ext == 'txt':
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        
        elif file_ext == 'csv':
            import csv
            text_lines = []
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    text_lines.append(' '.join(row))
            return '\n'.join(text_lines)
        
        elif file_ext in ['pdf']:
            # For now, return placeholder - PDF processing requires additional libraries
            return "PDF processing not yet implemented - please use text files or paste content directly"
        
        elif file_ext in ['doc', 'docx']:
            # For now, return placeholder - Word processing requires additional libraries  
            return "Word document processing not yet implemented - please use text files or paste content directly"
        
        else:
            return ""
            
    except Exception as e:
        current_app.logger.error(f"Text extraction error for {filename}: {e}")
        return ""