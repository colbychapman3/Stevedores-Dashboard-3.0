"""
API Request/Response Validation for Stevedores Dashboard 3.0
Maritime-specific validation schemas and decorators
"""

import logging
from typing import Dict, Any, Optional, List, Union
from functools import wraps
from datetime import datetime, date
from flask import request, jsonify, g
from marshmallow import Schema, fields, validate, ValidationError, pre_load, post_load
from marshmallow.decorators import validates_schema

logger = logging.getLogger(__name__)

class MaritimeBaseSchema(Schema):
    """Base schema for maritime operations with common fields"""
    
    # Common maritime metadata
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    user_id = fields.Integer(dump_only=True)
    
    # Maritime operation context
    maritime_operation_id = fields.String(allow_none=True)
    port_code = fields.String(allow_none=True, validate=validate.Length(min=3, max=10))
    berth_number = fields.String(allow_none=True, validate=validate.Length(max=20))
    
    @pre_load
    def strip_strings(self, data, **kwargs):
        """Strip whitespace from string fields"""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    data[key] = value.strip()
        return data

class VesselSchema(MaritimeBaseSchema):
    """Validation schema for vessel operations"""
    
    # Required vessel identification
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    imo_number = fields.String(allow_none=True, validate=validate.Regexp(r'^\d{7}$'))
    vessel_type = fields.String(
        required=True,
        validate=validate.OneOf([
            'container', 'bulk_carrier', 'tanker', 'ro_ro', 'general_cargo',
            'passenger', 'offshore', 'fishing', 'tug', 'other'
        ])
    )
    
    # Vessel specifications
    length_overall = fields.Float(allow_none=True, validate=validate.Range(min=0, max=500))
    beam = fields.Float(allow_none=True, validate=validate.Range(min=0, max=100))
    draft = fields.Float(allow_none=True, validate=validate.Range(min=0, max=30))
    gross_tonnage = fields.Integer(allow_none=True, validate=validate.Range(min=0))
    
    # Cargo specifications
    total_cargo_capacity = fields.Integer(
        required=True, 
        validate=validate.Range(min=0, max=1000000)
    )
    cargo_type = fields.String(allow_none=True, validate=validate.Length(max=100))
    
    # Operational details
    status = fields.String(
        validate=validate.OneOf([
            'expected', 'arrived', 'berthed', 'operations_active', 
            'operations_complete', 'departed'
        ])
    )
    eta = fields.DateTime(allow_none=True)
    etd = fields.DateTime(allow_none=True)
    port_of_call = fields.String(allow_none=True, validate=validate.Length(max=100))
    
    # Equipment requirements
    heavy_equipment_count = fields.Integer(
        allow_none=True, 
        validate=validate.Range(min=0, max=50)
    )
    drivers_assigned = fields.Integer(
        allow_none=True, 
        validate=validate.Range(min=0, max=100)
    )
    tico_vehicles_needed = fields.Integer(
        allow_none=True, 
        validate=validate.Range(min=0, max=20)
    )
    
    # Progress tracking
    progress_percentage = fields.Float(
        allow_none=True, 
        validate=validate.Range(min=0, max=100)
    )
    
    @validates_schema
    def validate_dates(self, data, **kwargs):
        """Validate ETA/ETD relationship"""
        eta = data.get('eta')
        etd = data.get('etd')
        
        if eta and etd and eta >= etd:
            raise ValidationError('ETA must be before ETD')
    
    @validates_schema
    def validate_imo_number(self, data, **kwargs):
        """Validate IMO number check digit"""
        imo = data.get('imo_number')
        if imo and len(imo) == 7:
            # IMO check digit validation
            digits = [int(d) for d in imo[:6]]
            check_sum = sum(d * (7 - i) for i, d in enumerate(digits))
            if check_sum % 10 != int(imo[6]):
                raise ValidationError('Invalid IMO number check digit')

class CargoTallySchema(MaritimeBaseSchema):
    """Validation schema for cargo tally operations"""
    
    # Required fields
    vessel_id = fields.Integer(required=True)
    tally_type = fields.String(
        required=True,
        validate=validate.OneOf(['loaded', 'discharged', 'damaged', 'rejected'])
    )
    cargo_count = fields.Integer(
        required=True,
        validate=validate.Range(min=0, max=10000)
    )
    
    # Optional details
    location = fields.String(allow_none=True, validate=validate.Length(max=100))
    notes = fields.String(allow_none=True, validate=validate.Length(max=500))
    shift_period = fields.String(
        allow_none=True,
        validate=validate.OneOf(['morning', 'afternoon', 'night'])
    )
    
    # Cargo details
    cargo_description = fields.String(allow_none=True, validate=validate.Length(max=200))
    unit_type = fields.String(
        allow_none=True,
        validate=validate.OneOf(['container', 'pallet', 'bag', 'ton', 'piece', 'other'])
    )
    weight_per_unit = fields.Float(allow_none=True, validate=validate.Range(min=0))
    
    # Quality control
    damage_type = fields.String(allow_none=True, validate=validate.Length(max=100))
    inspector_signature = fields.String(allow_none=True, validate=validate.Length(max=100))
    
    # Timestamps
    timestamp = fields.DateTime(allow_none=True)

class DocumentUploadSchema(MaritimeBaseSchema):
    """Validation schema for maritime document uploads"""
    
    # Required fields
    document_type = fields.String(
        required=True,
        validate=validate.OneOf([
            'bill_of_lading', 'manifest', 'customs_declaration', 'inspection_report',
            'damage_report', 'tally_sheet', 'delivery_receipt', 'other'
        ])
    )
    filename = fields.String(required=True, validate=validate.Length(min=1, max=255))
    
    # Optional metadata
    vessel_id = fields.Integer(allow_none=True)
    description = fields.String(allow_none=True, validate=validate.Length(max=500))
    reference_number = fields.String(allow_none=True, validate=validate.Length(max=100))
    
    # File validation
    file_size = fields.Integer(validate=validate.Range(min=1, max=50*1024*1024))  # 50MB max
    mime_type = fields.String(allow_none=True)
    
    # Security metadata
    scanned_for_malware = fields.Boolean(allow_none=True)
    classification_level = fields.String(
        allow_none=True,
        validate=validate.OneOf(['public', 'internal', 'confidential', 'restricted'])
    )

class SyncOperationSchema(MaritimeBaseSchema):
    """Validation schema for offline sync operations"""
    
    # Sync metadata
    operation_type = fields.String(
        required=True,
        validate=validate.OneOf(['create', 'update', 'delete'])
    )
    table_name = fields.String(
        required=True,
        validate=validate.OneOf(['vessels', 'cargo_tallies', 'documents', 'users'])
    )
    record_id = fields.String(allow_none=True)
    
    # Sync data
    data = fields.Dict(required=True)
    client_timestamp = fields.DateTime(required=True)
    
    # Conflict resolution
    client_hash = fields.String(allow_none=True)
    conflict_resolution_strategy = fields.String(
        allow_none=True,
        validate=validate.OneOf(['client_wins', 'server_wins', 'merge', 'manual'])
    )

class UserAuthSchema(Schema):
    """Validation schema for user authentication"""
    
    email = fields.Email(required=True)
    password = fields.String(
        required=True,
        validate=validate.Length(min=8, max=128)
    )
    remember_me = fields.Boolean(allow_none=True)
    
    @pre_load
    def normalize_email(self, data, **kwargs):
        """Normalize email to lowercase"""
        if 'email' in data:
            data['email'] = data['email'].lower().strip()
        return data

class ApiResponseSchema(Schema):
    """Standard API response schema"""
    
    success = fields.Boolean(required=True)
    message = fields.String(allow_none=True)
    data = fields.Raw(allow_none=True)
    errors = fields.List(fields.String(), allow_none=True)
    timestamp = fields.DateTime(dump_only=True)
    request_id = fields.String(dump_only=True)

# Validation decorator factory
def validate_json(schema_class, load_json=True):
    """
    Decorator to validate JSON request data against a marshmallow schema
    
    Args:
        schema_class: Marshmallow schema class
        load_json: Whether to load JSON from request (default True)
    
    Usage:
        @app.route('/api/vessels', methods=['POST'])
        @validate_json(VesselSchema)
        def create_vessel():
            # Access validated data via g.validated_data
            vessel_data = g.validated_data
            return jsonify({'success': True})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                schema = schema_class()
                
                if load_json:
                    if not request.is_json:
                        return jsonify({
                            'success': False,
                            'error': 'Content-Type must be application/json'
                        }), 400
                    
                    json_data = request.get_json(force=True)
                    if json_data is None:
                        return jsonify({
                            'success': False,
                            'error': 'Invalid JSON data'
                        }), 400
                else:
                    json_data = request.form.to_dict()
                
                # Validate data
                validated_data = schema.load(json_data)
                
                # Store validated data in Flask's g object
                g.validated_data = validated_data
                
                return f(*args, **kwargs)
                
            except ValidationError as err:
                logger.warning(f"Validation error for {request.endpoint}: {err.messages}")
                return jsonify({
                    'success': False,
                    'error': 'Validation failed',
                    'validation_errors': err.messages
                }), 400
            except Exception as e:
                logger.error(f"Unexpected validation error: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Internal validation error'
                }), 500
        
        return decorated_function
    return decorator

def validate_query_params(schema_class):
    """
    Decorator to validate query parameters against a marshmallow schema
    
    Args:
        schema_class: Marshmallow schema class
    
    Usage:
        @app.route('/api/vessels')
        @validate_query_params(VesselQuerySchema)
        def list_vessels():
            # Access validated params via g.validated_params
            filters = g.validated_params
            return jsonify({'vessels': []})
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                schema = schema_class()
                query_data = request.args.to_dict()
                
                # Handle multi-value parameters
                for key in request.args.keys():
                    values = request.args.getlist(key)
                    if len(values) > 1:
                        query_data[key] = values
                
                validated_params = schema.load(query_data)
                g.validated_params = validated_params
                
                return f(*args, **kwargs)
                
            except ValidationError as err:
                logger.warning(f"Query parameter validation error: {err.messages}")
                return jsonify({
                    'success': False,
                    'error': 'Invalid query parameters',
                    'validation_errors': err.messages
                }), 400
        
        return decorated_function
    return decorator

def serialize_response(schema_class, many=False):
    """
    Decorator to serialize response data using marshmallow schema
    
    Args:
        schema_class: Marshmallow schema class
        many: Whether to serialize list of objects (default False)
    
    Usage:
        @app.route('/api/vessels/<int:vessel_id>')
        @serialize_response(VesselSchema)
        def get_vessel(vessel_id):
            vessel = get_vessel_by_id(vessel_id)
            return vessel  # Will be serialized automatically
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
                
                # Handle different return types
                if isinstance(result, tuple):
                    data, status_code = result[:2]
                    headers = result[2] if len(result) > 2 else {}
                else:
                    data = result
                    status_code = 200
                    headers = {}
                
                # Skip serialization for error responses
                if status_code >= 400:
                    return result
                
                # Serialize data
                schema = schema_class(many=many)
                serialized_data = schema.dump(data)
                
                response_data = {
                    'success': True,
                    'data': serialized_data,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                return jsonify(response_data), status_code, headers
                
            except Exception as e:
                logger.error(f"Response serialization error: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Response serialization failed'
                }), 500
        
        return decorated_function
    return decorator

def maritime_api_response(data=None, message=None, errors=None, status_code=200):
    """
    Create standardized maritime API response
    
    Args:
        data: Response data
        message: Success/info message
        errors: List of error messages
        status_code: HTTP status code
    
    Returns:
        Flask response object
    """
    response_data = {
        'success': status_code < 400,
        'timestamp': datetime.utcnow().isoformat(),
        'maritime_context': True,
    }
    
    if data is not None:
        response_data['data'] = data
    
    if message:
        response_data['message'] = message
    
    if errors:
        response_data['errors'] = errors if isinstance(errors, list) else [errors]
    
    # Add request context
    if hasattr(g, 'jwt_claims'):
        response_data['user_id'] = g.jwt_claims.get('user_id')
    
    return jsonify(response_data), status_code

# Schema instances for common use
vessel_schema = VesselSchema()
cargo_tally_schema = CargoTallySchema()
document_upload_schema = DocumentUploadSchema()
sync_operation_schema = SyncOperationSchema()
user_auth_schema = UserAuthSchema()
api_response_schema = ApiResponseSchema()