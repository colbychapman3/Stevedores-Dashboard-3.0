"""
Document Processing Routes
Handles document upload and auto-fill processing for vessel wizard
Supports both online server-side and offline client-side processing
"""

import os
import json
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from utils.document_processor import DocumentProcessor, OfflineDocumentProcessor

# Create blueprint
document_bp = Blueprint('document', __name__)

# Initialize document processor
processor = DocumentProcessor()

@document_bp.route('/upload', methods=['POST'])
@login_required
def upload_document():
    """Handle document upload and processing"""
    try:
        if 'document' not in request.files:
            return jsonify({'error': 'No document uploaded'}), 400
        
        file = request.files['document']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type
        allowed_extensions = {'txt', 'pdf', 'doc', 'docx', 'csv'}
        if not _allowed_file(file.filename, allowed_extensions):
            return jsonify({'error': 'Unsupported file type'}), 400
        
        # Secure filename and save temporarily
        filename = secure_filename(file.filename)
        upload_folder = current_app.config.get('UPLOAD_FOLDER', '/tmp/stevedores_uploads')
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Extract text from file
        text_content = _extract_text_from_file(filepath, filename)
        
        if not text_content:
            return jsonify({'error': 'Could not extract text from document'}), 400
        
        # Process document for auto-fill
        result = processor.process_document_text(text_content, filename)
        
        # Clean up temporary file
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Store processing result in user session for wizard access
        if result['success']:
            # Store in session (or could store in database for persistence)
            from flask import session
            session['document_auto_fill'] = {
                'wizard_data': result['wizard_data'],
                'extracted_data': result['extracted_data'],
                'document_source': filename,
                'processed_at': result['extracted_data']['extracted_at'],
                'confidence_score': result['extracted_data']['confidence_score']
            }
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Document upload error: {e}")
        return jsonify({'error': 'Document processing failed'}), 500

@document_bp.route('/process-text', methods=['POST'])
@login_required 
def process_text():
    """Process raw text content for auto-fill (for offline text extraction)"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text content provided'}), 400
        
        text_content = data['text']
        filename = data.get('filename', 'uploaded_document')
        
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
                'confidence_score': result['extracted_data']['confidence_score']
            }
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Text processing error: {e}")
        return jsonify({'error': 'Text processing failed'}), 500

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

def _extract_text_from_file(filepath: str, filename: str) -> str:
    """Extract text content from uploaded file"""
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