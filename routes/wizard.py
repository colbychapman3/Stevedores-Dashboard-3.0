"""
Enhanced 4-step vessel wizard routes
Ported from stevedores-dashboard-2.0 with offline support
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from datetime import datetime, time
import json

wizard_bp = Blueprint('wizard', __name__)

def get_db_and_models():
    """Get database and models to avoid circular imports"""
    from app import db
    from models.vessel import create_vessel_model
    from models.cargo_tally import create_cargo_tally_model
    Vessel = create_vessel_model(db)
    CargoTally = create_cargo_tally_model(db)
    return db, Vessel, CargoTally

@wizard_bp.route('/', methods=['GET', 'POST'])
@login_required
def vessel_wizard():
    """Enhanced 4-step vessel creation wizard"""
    if request.method == 'GET':
        return render_template('wizard/vessel_wizard.html')
    
    # Handle POST - process completed wizard
    try:
        db, Vessel, CargoTally = get_db_and_models()
        
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Create vessel from wizard data
        vessel = Vessel(
            # Step 1: Vessel Information
            name=data.get('vesselName', '').strip(),
            vessel_type=data.get('vesselType', ''),
            port_of_call=data.get('port', ''),
            eta=datetime.fromisoformat(data.get('operationDate')) if data.get('operationDate') else None,
            
            # Step 2: Cargo Configuration
            total_cargo_capacity=int(data.get('totalAutomobiles', 0)),
            cargo_type=data.get('cargoType', 'automobile'),
            heavy_equipment_count=int(data.get('heavyEquipment', 0)),
            
            # Step 3: Operational Parameters
            shift_start=time.fromisoformat(data.get('shiftStart')) if data.get('shiftStart') else None,
            shift_end=time.fromisoformat(data.get('shiftEnd')) if data.get('shiftEnd') else None,
            drivers_assigned=int(data.get('driversAssigned', 0)),
            tico_vehicles_needed=int(data.get('ticoVehicles', 0)),
            
            # Status and metadata
            status='expected',
            created_by_id=current_user.id,
            wizard_completed=True,
            document_source=data.get('documentSource')
        )
        
        db.session.add(vessel)
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'vessel_id': vessel.id,
                'message': 'Vessel operation created successfully!',
                'redirect_url': url_for('vessel_details', vessel_id=vessel.id)
            })
        
        flash(f'Vessel operation "{vessel.name}" created successfully!', 'success')
        return redirect(url_for('vessel_details', vessel_id=vessel.id))
        
    except Exception as e:
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Error creating vessel operation: {str(e)}', 'error')
        return render_template('wizard/vessel_wizard.html')

@wizard_bp.route('/api/save-step', methods=['POST'])
@login_required
def save_wizard_step():
    """Save wizard step data for offline persistence"""
    try:
        data = request.get_json()
        step = data.get('step')
        step_data = data.get('data', {})
        
        # Store in session for now (could use IndexedDB in production)
        if 'wizard_data' not in session:
            session['wizard_data'] = {}
        
        session['wizard_data'][f'step_{step}'] = step_data
        session['wizard_data']['last_saved'] = datetime.utcnow().isoformat()
        
        return jsonify({
            'success': True,
            'message': f'Step {step} data saved'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@wizard_bp.route('/api/load-saved', methods=['GET'])
@login_required
def load_saved_wizard_data():
    """Load saved wizard data"""
    try:
        wizard_data = session.get('wizard_data', {})
        return jsonify({
            'success': True,
            'data': wizard_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@wizard_bp.route('/api/document-upload', methods=['POST'])
@login_required
def process_document_upload():
    """Process uploaded maritime documents for auto-fill"""
    try:
        if 'document' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['document']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Simple document processing (enhanced in Day 2)
        filename = file.filename.lower()
        extracted_data = {}
        
        if filename.endswith('.txt'):
            content = file.read().decode('utf-8')
            extracted_data = extract_data_from_text(content)
        elif filename.endswith('.csv'):
            # Basic CSV processing
            content = file.read().decode('utf-8')
            extracted_data = extract_data_from_csv(content)
        else:
            return jsonify({'error': 'File type not supported yet'}), 400
        
        return jsonify({
            'success': True,
            'extracted_data': extracted_data,
            'filename': file.filename
        })
        
    except Exception as e:
        return jsonify({'error': f'Document processing failed: {str(e)}'}), 500

def extract_data_from_text(content):
    """Basic text extraction for maritime documents"""
    extracted = {}
    lines = content.lower().split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Vessel name extraction
        if 'vessel:' in line or 'ship name:' in line:
            extracted['vesselName'] = line.split(':')[-1].strip().title()
        
        # Vessel type extraction  
        if 'type:' in line and any(vtype in line for vtype in ['car carrier', 'roro', 'container']):
            if 'car carrier' in line:
                extracted['vesselType'] = 'Car Carrier'
            elif 'roro' in line:
                extracted['vesselType'] = 'RoRo'
            elif 'container' in line:
                extracted['vesselType'] = 'Container Ship'
        
        # Port extraction
        if 'port:' in line or 'destination:' in line:
            extracted['port'] = line.split(':')[-1].strip().title()
        
        # Automobile count extraction
        if 'automobiles:' in line or 'cars:' in line or 'vehicles:' in line:
            try:
                numbers = [int(s) for s in line.split() if s.isdigit()]
                if numbers:
                    extracted['totalAutomobiles'] = str(numbers[-1])
            except:
                pass
        
        # Heavy equipment extraction
        if 'heavy equipment:' in line or 'trucks:' in line:
            try:
                numbers = [int(s) for s in line.split() if s.isdigit()]
                if numbers:
                    extracted['heavyEquipment'] = str(numbers[-1])
            except:
                pass
    
    return extracted

def extract_data_from_csv(content):
    """Basic CSV extraction for maritime documents"""
    extracted = {}
    lines = content.split('\n')
    
    if len(lines) > 1:
        # Simple CSV parsing - assumes header row
        headers = [h.strip().lower() for h in lines[0].split(',')]
        if len(lines) > 1:
            values = [v.strip() for v in lines[1].split(',')]
            
            for i, header in enumerate(headers):
                if i < len(values):
                    if 'vessel' in header or 'ship' in header:
                        extracted['vesselName'] = values[i].title()
                    elif 'type' in header:
                        extracted['vesselType'] = values[i].title()
                    elif 'port' in header:
                        extracted['port'] = values[i].title()
                    elif 'auto' in header or 'car' in header:
                        try:
                            extracted['totalAutomobiles'] = str(int(values[i]))
                        except:
                            pass
    
    return extracted