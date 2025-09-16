"""
Document Processing for Offline Auto-fill
Extracts vessel data from uploaded documents for wizard auto-population
Supports offline operation with client-side processing
"""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

class DocumentProcessor:
    """Process maritime documents to extract vessel data for auto-fill"""
    
    def __init__(self):
        self.vessel_patterns = self._initialize_patterns()
        self.cargo_patterns = self._initialize_cargo_patterns()
        self.operational_patterns = self._initialize_operational_patterns()
    
    def _initialize_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize regex patterns for vessel data extraction"""
        return {
            'vessel_name': re.compile(r'(?:vessel|ship|mv|m/v)\s*:?\s*([a-zA-Z0-9\s\-\.]+?)(?:\s*(?:type|cargo|port|eta|berth)|$)', re.IGNORECASE),
            'vessel_type': re.compile(r'(?:type|class|category)\s*:?\s*(container ship|bulk carrier|tanker|roro|general cargo|automobile|car carrier)(?:\s|$)', re.IGNORECASE),
            'port_of_call': re.compile(r'(?:port\s*of\s*call|destination|port)\s*:?\s*([a-zA-Z\s\-\.]+?)(?:\s*(?:eta|etd|cargo|berth)|$)', re.IGNORECASE),
            'eta': re.compile(r'(?:eta|arrival|expected)\s*:?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', re.IGNORECASE),
            'etd': re.compile(r'(?:etd|departure|sailing)\s*:?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', re.IGNORECASE),
        }
    
    def _initialize_cargo_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize patterns for cargo information"""
        return {
            'total_capacity': re.compile(r'(?:capacity|total|units?)\s*:?\s*(\d+)', re.IGNORECASE),
            'cargo_type': re.compile(r'(?:cargo|commodity)\s*:?\s*(containers?|automobiles?|bulk|steel|grain|machinery)', re.IGNORECASE),
            'heavy_equipment': re.compile(r'(?:heavy\s*equipment|machinery)\s*:?\s*(\d+)', re.IGNORECASE),
            'teus': re.compile(r'(\d+)\s*teus?', re.IGNORECASE),
            'containers': re.compile(r'(\d+)\s*containers?', re.IGNORECASE),
            'units': re.compile(r'(\d+)\s*units?', re.IGNORECASE),
        }
    
    def _initialize_operational_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize patterns for operational data"""
        return {
            'berth': re.compile(r'(?:berth|pier|dock)\s*:?\s*([a-zA-Z0-9\s\-]+?)(?:\s*(?:crew|driver|personnel|tico)|$)', re.IGNORECASE),
            'shift_time': re.compile(r'(?:shift|working)\s*(?:hours?)?\s*:?\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', re.IGNORECASE),
            'crew_size': re.compile(r'(?:crew|personnel)\s*:?\s*(\d+)', re.IGNORECASE),
            'drivers': re.compile(r'(?:drivers?\s*assigned|operators?)\s*:?\s*(\d+)', re.IGNORECASE),
            'tico_vehicles': re.compile(r'(?:tico\s*vehicles?|yard\s*truck|terminal\s*tractor)s?\s*:?\s*(\d+)', re.IGNORECASE),
        }
    
    def process_document_text(self, text: str, filename: str = "") -> Dict[str, Any]:
        """Process document text and extract vessel data"""
        try:
            # Clean and normalize text
            text = self._clean_text(text)
            
            # Extract data sections
            vessel_data = self._extract_vessel_data(text)
            cargo_data = self._extract_cargo_data(text)
            operational_data = self._extract_operational_data(text)
            
            # Combine and validate
            extracted_data = {
                **vessel_data,
                **cargo_data,
                **operational_data,
                'document_source': filename,
                'extracted_at': datetime.utcnow().isoformat(),
                'confidence_score': self._calculate_confidence(vessel_data, cargo_data, operational_data)
            }
            
            # Format for wizard steps
            wizard_data = self._format_for_wizard(extracted_data)
            
            return {
                'success': True,
                'extracted_data': extracted_data,
                'wizard_data': wizard_data,
                'document_source': filename
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'document_source': filename
            }
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize document text"""
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common document formatting artifacts
        text = re.sub(r'[^\w\s\-:\/\.]', ' ', text)
        
        return text
    
    def _extract_vessel_data(self, text: str) -> Dict[str, Any]:
        """Extract basic vessel information"""
        data = {}
        
        # Extract vessel name
        name_match = self.vessel_patterns['vessel_name'].search(text)
        if name_match:
            data['vessel_name'] = name_match.group(1).strip().title()
        
        # Extract vessel type
        type_match = self.vessel_patterns['vessel_type'].search(text)
        if type_match:
            vessel_type = type_match.group(1).strip().title()
            data['vessel_type'] = self._normalize_vessel_type(vessel_type)
        
        # Extract port of call
        port_match = self.vessel_patterns['port_of_call'].search(text)
        if port_match:
            data['port_of_call'] = port_match.group(1).strip().title()
        
        # Extract ETA
        eta_match = self.vessel_patterns['eta'].search(text)
        if eta_match:
            data['eta'] = self._parse_date(eta_match.group(1))
        
        # Extract ETD
        etd_match = self.vessel_patterns['etd'].search(text)
        if etd_match:
            data['etd'] = self._parse_date(etd_match.group(1))
            
        return data
    
    def _extract_cargo_data(self, text: str) -> Dict[str, Any]:
        """Extract cargo information"""
        data = {}
        
        # Extract cargo type
        cargo_match = self.cargo_patterns['cargo_type'].search(text)
        if cargo_match:
            data['cargo_type'] = cargo_match.group(1).strip().lower()
        
        # Extract capacity/units (try multiple patterns)
        capacity = None
        for pattern_name in ['teus', 'containers', 'units', 'total_capacity']:
            match = self.cargo_patterns[pattern_name].search(text)
            if match:
                capacity = int(match.group(1))
                break
        
        if capacity:
            data['total_cargo_capacity'] = capacity
        
        # Extract heavy equipment count
        heavy_match = self.cargo_patterns['heavy_equipment'].search(text)
        if heavy_match:
            data['heavy_equipment_count'] = int(heavy_match.group(1))
            
        return data
    
    def _extract_operational_data(self, text: str) -> Dict[str, Any]:
        """Extract operational parameters"""
        data = {}
        
        # Extract berth information
        berth_match = self.operational_patterns['berth'].search(text)
        if berth_match:
            data['current_berth'] = berth_match.group(1).strip()
        
        # Extract shift times
        shift_match = self.operational_patterns['shift_time'].search(text)
        if shift_match:
            data['shift_start'] = self._parse_time(shift_match.group(1))
            data['shift_end'] = self._parse_time(shift_match.group(2))
        
        # Extract crew/personnel counts
        crew_match = self.operational_patterns['crew_size'].search(text)
        if crew_match:
            data['crew_size'] = int(crew_match.group(1))
        
        drivers_match = self.operational_patterns['drivers'].search(text)
        if drivers_match:
            data['drivers_assigned'] = int(drivers_match.group(1))
        
        tico_match = self.operational_patterns['tico_vehicles'].search(text)
        if tico_match:
            data['tico_vehicles_needed'] = int(tico_match.group(1))
            
        return data
    
    def _normalize_vessel_type(self, vessel_type: str) -> str:
        """Normalize vessel type to standard values"""
        type_mapping = {
            'container': 'Container Ship',
            'bulk': 'Bulk Carrier', 
            'tanker': 'Tanker',
            'roro': 'RoRo Vessel',
            'general cargo': 'General Cargo',
            'automobile': 'Car Carrier'
        }
        
        vessel_type_lower = vessel_type.lower()
        for key, value in type_mapping.items():
            if key in vessel_type_lower:
                return value
        
        return vessel_type.title()
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to ISO format"""
        try:
            # Try different date formats
            formats = [
                '%m/%d/%Y', '%m-%d-%Y', '%d/%m/%Y', '%d-%m-%Y',
                '%Y-%m-%d', '%m/%d/%y', '%m-%d-%y'
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    # If 2-digit year, assume it's in 2000s
                    if dt.year < 2000:
                        dt = dt.replace(year=dt.year + 2000)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            return None
        except Exception:
            return None
    
    def _parse_time(self, time_str: str) -> Optional[str]:
        """Parse time string to HH:MM format"""
        try:
            # Ensure time is in HH:MM format
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 2:
                    hour = int(parts[0])
                    minute = int(parts[1])
                    return f"{hour:02d}:{minute:02d}"
            return None
        except Exception:
            return None
    
    def _calculate_confidence(self, vessel_data: Dict, cargo_data: Dict, operational_data: Dict) -> float:
        """Calculate confidence score for extracted data"""
        score = 0
        max_score = 10
        
        # Key fields contribute more to confidence
        key_fields = {
            'vessel_name': 3,
            'vessel_type': 2, 
            'cargo_type': 2,
            'total_cargo_capacity': 2,
            'eta': 1
        }
        
        all_data = {**vessel_data, **cargo_data, **operational_data}
        
        for field, weight in key_fields.items():
            if field in all_data and all_data[field]:
                score += weight
        
        return min(score / max_score, 1.0)
    
    def _format_for_wizard(self, extracted_data: Dict[str, Any]) -> Dict[str, Dict]:
        """Format extracted data for wizard step structure"""
        wizard_data = {
            'step_1': {
                'vessel_name': extracted_data.get('vessel_name', ''),
                'vessel_type': extracted_data.get('vessel_type', ''),
                'port_of_call': extracted_data.get('port_of_call', ''),
                'eta': extracted_data.get('eta', ''),
                'etd': extracted_data.get('etd', '')
            },
            'step_2': {
                'total_cargo_capacity': extracted_data.get('total_cargo_capacity', ''),
                'cargo_type': extracted_data.get('cargo_type', 'automobile'),
                'heavy_equipment_count': extracted_data.get('heavy_equipment_count', 0)
            },
            'step_3': {
                'shift_start': extracted_data.get('shift_start', ''),
                'shift_end': extracted_data.get('shift_end', ''),
                'drivers_assigned': extracted_data.get('drivers_assigned', ''),
                'tico_vehicles_needed': extracted_data.get('tico_vehicles_needed', ''),
                'current_berth': extracted_data.get('current_berth', '')
            },
            'step_4': {
                'document_source': extracted_data.get('document_source', ''),
                'confidence_score': extracted_data.get('confidence_score', 0),
                'auto_filled': True,
                'extracted_at': extracted_data.get('extracted_at', '')
            }
        }
        
        return wizard_data

class OfflineDocumentProcessor:
    """Client-side document processing for offline operation"""
    
    @staticmethod
    def generate_client_processor() -> str:
        """Generate JavaScript code for client-side document processing"""
        return r'''
        class OfflineDocumentProcessor {
            constructor() {
                this.patterns = this.initializePatterns();
            }
            
            initializePatterns() {
                return {
                    vessel_name: /(?:vessel|ship|mv|m\/v)\s*:?\s*([a-zA-Z0-9\s\-\.]+)/i,
                    vessel_type: /(?:type|class|category)\s*:?\s*(container|bulk|tanker|roro|general cargo|automobile)/i,
                    port_of_call: /(?:port\s*of\s*call|destination|port)\s*:?\s*([a-zA-Z\s\-\.]+)/i,
                    eta: /(?:eta|arrival|expected)\s*:?\s*(\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4}|\d{4}-\d{2}-\d{2})/i,
                    cargo_type: /(?:cargo|commodity)\s*:?\s*(containers?|automobiles?|bulk|steel|grain|machinery)/i,
                    total_capacity: /(?:capacity|total|units?)\s*:?\s*(\d+)/i,
                    berth: /(?:berth|pier|dock)\s*:?\s*([a-zA-Z0-9\s\-]+)/i,
                    crew_size: /(?:crew|personnel|workers?)\s*:?\s*(\d+)/i,
                };
            }
            
            processText(text, filename = '') {
                try {
                    const cleanText = this.cleanText(text);
                    const extracted = this.extractData(cleanText);
                    
                    return {
                        success: true,
                        wizard_data: this.formatForWizard(extracted),
                        confidence_score: this.calculateConfidence(extracted),
                        document_source: filename,
                        extracted_at: new Date().toISOString()
                    };
                } catch (error) {
                    return {
                        success: false,
                        error: error.message,
                        document_source: filename
                    };
                }
            }
            
            cleanText(text) {
                return text.replace(/\\s+/g, ' ').trim();
            }
            
            extractData(text) {
                const data = {};
                
                Object.keys(this.patterns).forEach(key => {
                    const match = text.match(this.patterns[key]);
                    if (match) {
                        data[key] = match[1].trim();
                    }
                });
                
                return data;
            }
            
            formatForWizard(data) {
                return {
                    step_1: {
                        vessel_name: data.vessel_name || '',
                        vessel_type: this.normalizeVesselType(data.vessel_type || ''),
                        port_of_call: data.port_of_call || '',
                        eta: this.parseDate(data.eta || '')
                    },
                    step_2: {
                        total_cargo_capacity: parseInt(data.total_capacity) || '',
                        cargo_type: data.cargo_type || 'automobile'
                    },
                    step_3: {
                        current_berth: data.berth || '',
                        crew_size: parseInt(data.crew_size) || ''
                    },
                    step_4: {
                        auto_filled: true,
                        document_source: data.document_source || ''
                    }
                };
            }
            
            normalizeVesselType(type) {
                const mapping = {
                    'container': 'Container Ship',
                    'bulk': 'Bulk Carrier',
                    'tanker': 'Tanker',
                    'roro': 'RoRo Vessel',
                    'automobile': 'Car Carrier'
                };
                
                const lowerType = type.toLowerCase();
                for (const [key, value] of Object.entries(mapping)) {
                    if (lowerType.includes(key)) {
                        return value;
                    }
                }
                return type;
            }
            
            parseDate(dateStr) {
                if (!dateStr) return '';
                try {
                    const date = new Date(dateStr);
                    return date.toISOString().split('T')[0];
                } catch {
                    return '';
                }
            }
            
            calculateConfidence(data) {
                const keyFields = ['vessel_name', 'vessel_type', 'cargo_type'];
                const score = keyFields.reduce((acc, field) => {
                    return acc + (data[field] ? 1 : 0);
                }, 0);
                return score / keyFields.length;
            }
        }
        
        // Global instance for use in wizard
        window.documentProcessor = new OfflineDocumentProcessor();
        '''