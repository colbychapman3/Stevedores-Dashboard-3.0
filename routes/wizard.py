"""
Enhanced 4-step vessel wizard routes
Ported from stevedores-dashboard-2.0 with offline support
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from flask_wtf.csrf import exempt
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

        # Add debug logging for request details
        print(f"🔍 Request method: {request.method}")
        print(f"🔍 Request is_json: {request.is_json}")
        print(f"🔍 Request content_type: {request.content_type}")
        print(f"🔍 Request headers: {dict(request.headers)}")

        if request.is_json:
            data = request.get_json()
            print(f"🔍 JSON data received: {len(data) if data else 0} fields")
        else:
            data = request.form.to_dict()
            print(f"🔍 Form data received: {len(data)} fields")
        
        # Handle custom shipping line
        shipping_line = data.get('shippingLine', '')
        if shipping_line == 'Create Other':
            shipping_line = data.get('customShippingLine', '').strip()
        
        # Create vessel from wizard data
        vessel = Vessel(
            # Step 1: Vessel Information
            name=data.get('vesselName', '').strip(),
            shipping_line=shipping_line,
            vessel_type=data.get('vesselType', ''),
            port_of_call=data.get('port', 'Colonel Island'),
            operation_start_date=datetime.fromisoformat(data.get('operationStartDate')).date() if data.get('operationStartDate') else None,
            operation_end_date=datetime.fromisoformat(data.get('operationEndDate')).date() if data.get('operationEndDate') else None,
            stevedoring_company=data.get('stevedoringCompany', 'APS Stevedoring'),
            operation_type=data.get('operationType', ''),
            berth_assignment=data.get('berthAssignment', ''),
            operations_manager=data.get('operationsManager', ''),
            
            # Step 2: Team Assignments (JSON)
            team_assignments=json.dumps(collect_team_assignments(data)),
            
            # Step 3: Cargo Configuration (JSON)
            cargo_configuration=json.dumps(collect_cargo_configuration(data)),
            
            # Step 4: Operational Parameters
            total_drivers=int(data.get('totalDrivers', 0)),
            shift_start_time=time.fromisoformat(data.get('shiftStartTime')) if data.get('shiftStartTime') else None,
            shift_end_time=time.fromisoformat(data.get('shiftEndTime')) if data.get('shiftEndTime') else None,
            ship_start_time=time.fromisoformat(data.get('shipStartTime')) if data.get('shipStartTime') else None,
            ship_complete_time=time.fromisoformat(data.get('shipCompleteTime')) if data.get('shipCompleteTime') else None,
            number_of_breaks=int(data.get('numberOfBreaks', 0)),
            target_completion=datetime.fromisoformat(data.get('targetCompletion')) if data.get('targetCompletion') else None,
            number_of_vans=int(data.get('numberOfVans', 0)),
            number_of_wagons=int(data.get('numberOfWagons', 0)),
            number_of_low_decks=int(data.get('numberOfLowDecks', 0)),
            van_details=json.dumps(collect_van_details(data)),
            wagon_details=json.dumps(collect_wagon_details(data)),
            
            # Legacy fields for backward compatibility
            eta=datetime.fromisoformat(data.get('operationStartDate')) if data.get('operationStartDate') else None,
            total_cargo_capacity=int(data.get('dischargeTotalAutos', 0)) + int(data.get('loadingTotalAutos', 0)) + int(data.get('loadbackTotalAutos', 0)),
            drivers_assigned=int(data.get('totalDrivers', 0)),
            tico_vehicles_needed=int(data.get('numberOfVans', 0)) + int(data.get('numberOfWagons', 0)),
            
            # Status and metadata
            status='expected',
            created_by_id=current_user.id,
            wizard_completed=True,
            document_source=data.get('documentSource')
        )
        
        db.session.add(vessel)
        db.session.commit()
        
        # Debug logging
        print(f"✅ Vessel created successfully! ID: {vessel.id}, Name: {vessel.name}")
        print(f"📊 Vessel details - Shipping Line: {vessel.shipping_line}, Type: {vessel.vessel_type}")
        print(f"📅 Operation dates: {vessel.operation_start_date} to {vessel.operation_end_date}")
        print(f"🚢 Status: {vessel.status}, Wizard completed: {vessel.wizard_completed}")

        # Verify vessel was actually saved
        vessel_count = db.session.query(db.func.count(Vessel.id)).scalar()
        print(f"🔢 Total vessels in database now: {vessel_count}")

        # Double-check by querying the vessel back
        saved_vessel = Vessel.query.get(vessel.id)
        if saved_vessel:
            print(f"✅ Verification: Vessel {saved_vessel.id} successfully retrieved from database")
        else:
            print(f"❌ ERROR: Could not retrieve vessel {vessel.id} from database after creation!")
        
        if request.is_json:
            return jsonify({
                'success': True,
                'vessel_id': vessel.id,
                'message': 'Vessel operation created successfully!',
                'redirect_url': url_for('dashboard')
            })
        
        flash(f'Vessel operation "{vessel.name}" created successfully!', 'success')
        return redirect(url_for('dashboard'))
        
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

def collect_team_assignments(data):
    """Collect team assignment data from form"""
    teams = {
        'auto_operations': [],
        'high_heavy': []
    }
    
    # Collect auto operations team
    auto_members = int(data.get('autoOperationsMembers', 0))
    for i in range(1, auto_members + 1):
        member_name = data.get(f'autoOperationsMember{i}', '')
        if member_name == 'Custom':
            member_name = data.get(f'autoOperationsMemberCustom{i}', '')
        
        if member_name:
            teams['auto_operations'].append({
                'name': member_name,
                'position': i
            })
    
    # Collect high heavy team
    heavy_members = int(data.get('highHeavyMembers', 0))
    for i in range(1, heavy_members + 1):
        member_name = data.get(f'highHeavyMember{i}', '')
        if member_name == 'Custom':
            member_name = data.get(f'highHeavyMemberCustom{i}', '')
        
        if member_name:
            teams['high_heavy'].append({
                'name': member_name,
                'position': i
            })
    
    return teams

def collect_cargo_configuration(data):
    """Collect cargo configuration data from form"""
    cargo_config = {}
    
    operation_type = data.get('operationType', '')
    
    if operation_type in ['Discharge Only', 'Discharge + Loadback']:
        cargo_config['discharge'] = {
            'total_autos': int(data.get('dischargeTotalAutos', 0)),
            'heavy_equipment': int(data.get('dischargeHeavy', 0)),
            'vehicle_types': collect_vehicle_types(data, 'discharge')
        }
    
    if operation_type == 'Loading Only':
        cargo_config['loading'] = {
            'total_autos': int(data.get('loadingTotalAutos', 0)),
            'heavy_equipment': int(data.get('loadingHeavy', 0)),
            'vehicle_types': collect_vehicle_types(data, 'loading')
        }
    
    if operation_type == 'Discharge + Loadback':
        cargo_config['loadback'] = {
            'total_autos': int(data.get('loadbackTotalAutos', 0)),
            'heavy_equipment': int(data.get('loadbackHeavy', 0)),
            'vehicle_types': collect_vehicle_types(data, 'loadback')
        }
    
    return cargo_config

def collect_vehicle_types(data, section):
    """Collect vehicle type data for a specific section"""
    vehicle_types = []
    
    # Look for dynamically added vehicle types
    counter = 1
    while True:
        vehicle_type = data.get(f'{section}VehicleType{counter}', '')
        quantity = data.get(f'{section}Quantity{counter}', '')
        location = data.get(f'{section}Location{counter}', '')
        
        if not vehicle_type:
            break
        
        vehicle_types.append({
            'type': vehicle_type,
            'quantity': int(quantity) if quantity else 0,
            'location': location
        })
        
        counter += 1
    
    return vehicle_types

def collect_van_details(data):
    """Collect van details from form"""
    van_details = []
    
    num_vans = int(data.get('numberOfVans', 0))
    for i in range(1, num_vans + 1):
        van_id = data.get(f'van{i}Id', '')
        driver_name = data.get(f'van{i}Driver', '')
        
        if van_id or driver_name:
            van_details.append({
                'van_number': i,
                'id_number': van_id,
                'driver_name': driver_name
            })
    
    return van_details

def collect_wagon_details(data):
    """Collect wagon details from form"""
    wagon_details = []
    
    num_wagons = int(data.get('numberOfWagons', 0))
    for i in range(1, num_wagons + 1):
        wagon_id = data.get(f'wagon{i}Id', '')
        driver_name = data.get(f'wagon{i}Driver', '')
        
        if wagon_id or driver_name:
            wagon_details.append({
                'wagon_number': i,
                'id_number': wagon_id,
                'driver_name': driver_name
            })
    
    return wagon_details