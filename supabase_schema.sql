-- Stevedores Dashboard 3.0 - Maritime Operations Database Schema
-- Optimized for Supabase deployment with RLS (Row Level Security)

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table for authentication and maritime personnel management
CREATE TABLE users (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    role VARCHAR(20) DEFAULT 'operator',
    company VARCHAR(100),
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vessels table for maritime operations management
CREATE TABLE vessels (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    imo_number VARCHAR(20) UNIQUE, -- International Maritime Organization number
    vessel_type VARCHAR(50) NOT NULL,
    flag_state VARCHAR(50),
    port_of_call VARCHAR(100),
    next_port VARCHAR(100),
    status VARCHAR(50) DEFAULT 'expected',
    
    -- Cargo and operational details
    total_cargo_capacity INTEGER DEFAULT 0,
    cargo_loaded INTEGER DEFAULT 0,
    progress_percentage FLOAT DEFAULT 0.0,
    
    -- Equipment requirements
    heavy_equipment_count INTEGER DEFAULT 0,
    drivers_assigned INTEGER DEFAULT 0,
    tico_vehicles_needed INTEGER DEFAULT 0,
    
    -- Scheduling
    eta TIMESTAMP WITH TIME ZONE,
    etd TIMESTAMP WITH TIME ZONE,
    actual_arrival TIMESTAMP WITH TIME ZONE,
    actual_departure TIMESTAMP WITH TIME ZONE,
    
    -- Wizard data storage (JSON for flexibility)
    wizard_step_1_data JSONB DEFAULT '{}',
    wizard_step_2_data JSONB DEFAULT '{}',
    wizard_step_3_data JSONB DEFAULT '{}',
    wizard_step_4_data JSONB DEFAULT '{}',
    
    -- Operations data
    berth_assignment VARCHAR(20),
    priority_level VARCHAR(20) DEFAULT 'normal',
    special_requirements TEXT,
    
    -- User assignment
    user_id UUID REFERENCES users(id),
    assigned_supervisor UUID REFERENCES users(id),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Cargo tallies for real-time tracking
CREATE TABLE cargo_tallies (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    vessel_id UUID REFERENCES vessels(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    
    -- Tally details
    cargo_count INTEGER NOT NULL,
    tally_type VARCHAR(20) DEFAULT 'loaded', -- 'loaded', 'discharged', 'damaged'
    cargo_type VARCHAR(50) DEFAULT 'container',
    location VARCHAR(50), -- deck, hold, berth location
    
    -- Equipment used
    equipment_type VARCHAR(30), -- crane, forklift, etc.
    equipment_id VARCHAR(20),
    
    -- Quality control
    condition VARCHAR(20) DEFAULT 'good', -- good, damaged, missing
    notes TEXT,
    
    -- Sync management for offline operations
    synced BOOLEAN DEFAULT true,
    sync_timestamp TIMESTAMP WITH TIME ZONE,
    offline_id VARCHAR(50), -- for offline-generated records
    
    -- Position tracking
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Timestamps
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document processing records
CREATE TABLE document_processing (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    vessel_id UUID REFERENCES vessels(id),
    user_id UUID REFERENCES users(id),
    
    -- Document details
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(20),
    file_size INTEGER,
    
    -- Processing results
    processing_status VARCHAR(20) DEFAULT 'pending', -- pending, processed, failed
    extracted_data JSONB DEFAULT '{}',
    confidence_score FLOAT,
    
    -- Auto-fill integration
    wizard_data_filled JSONB DEFAULT '{}',
    auto_fill_success BOOLEAN DEFAULT false,
    
    -- Timestamps
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sync operations log for offline functionality
CREATE TABLE sync_operations (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    
    -- Sync details
    operation_type VARCHAR(30) NOT NULL, -- vessel_create, cargo_tally, document_process
    entity_id UUID, -- ID of the synced entity
    entity_type VARCHAR(30),
    
    -- Sync status
    sync_status VARCHAR(20) DEFAULT 'pending', -- pending, completed, failed, conflict
    conflict_resolution VARCHAR(30), -- client_wins, server_wins, merged
    
    -- Data
    sync_data JSONB,
    conflict_data JSONB,
    error_message TEXT,
    
    -- Timestamps
    initiated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0
);

-- Operational shifts and assignments
CREATE TABLE operational_shifts (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    
    -- Shift details
    shift_name VARCHAR(50) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    
    -- Personnel
    supervisor_id UUID REFERENCES users(id),
    operators JSONB DEFAULT '[]', -- array of user IDs
    
    -- Vessel assignments
    assigned_vessels JSONB DEFAULT '[]', -- array of vessel IDs
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance optimization
CREATE INDEX idx_vessels_status ON vessels(status);
CREATE INDEX idx_vessels_user_id ON vessels(user_id);
CREATE INDEX idx_vessels_eta ON vessels(eta);
CREATE INDEX idx_cargo_tallies_vessel_id ON cargo_tallies(vessel_id);
CREATE INDEX idx_cargo_tallies_timestamp ON cargo_tallies(timestamp);
CREATE INDEX idx_cargo_tallies_synced ON cargo_tallies(synced);
CREATE INDEX idx_sync_operations_user_id ON sync_operations(user_id);
CREATE INDEX idx_sync_operations_status ON sync_operations(sync_status);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add updated_at triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_vessels_updated_at BEFORE UPDATE ON vessels 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_operational_shifts_updated_at BEFORE UPDATE ON operational_shifts 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) policies for multi-tenancy
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE vessels ENABLE ROW LEVEL SECURITY;
ALTER TABLE cargo_tallies ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_processing ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_operations ENABLE ROW LEVEL SECURITY;

-- Basic RLS policies (you can customize these based on your security requirements)
-- Users can only see their own records
CREATE POLICY "Users can view own profile" ON users FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON users FOR UPDATE USING (auth.uid() = id);

-- Vessels: users can see vessels they created or are assigned to
CREATE POLICY "Users can view assigned vessels" ON vessels FOR SELECT 
    USING (auth.uid() = user_id OR auth.uid() = assigned_supervisor);
CREATE POLICY "Users can insert own vessels" ON vessels FOR INSERT 
    WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update assigned vessels" ON vessels FOR UPDATE 
    USING (auth.uid() = user_id OR auth.uid() = assigned_supervisor);

-- Cargo tallies: linked to vessel permissions
CREATE POLICY "Users can view vessel cargo tallies" ON cargo_tallies FOR SELECT 
    USING (EXISTS (SELECT 1 FROM vessels WHERE vessels.id = cargo_tallies.vessel_id 
                  AND (vessels.user_id = auth.uid() OR vessels.assigned_supervisor = auth.uid())));
CREATE POLICY "Users can insert cargo tallies" ON cargo_tallies FOR INSERT 
    WITH CHECK (EXISTS (SELECT 1 FROM vessels WHERE vessels.id = cargo_tallies.vessel_id 
                       AND (vessels.user_id = auth.uid() OR vessels.assigned_supervisor = auth.uid())));

-- Sample data for testing
INSERT INTO users (id, username, email, password_hash, first_name, last_name, role, company) VALUES
(uuid_generate_v4(), 'demo_supervisor', 'supervisor@maritime.demo', 'hashed_password_here', 'John', 'Smith', 'supervisor', 'Maritime Operations Inc'),
(uuid_generate_v4(), 'demo_operator', 'operator@maritime.demo', 'hashed_password_here', 'Maria', 'Garcia', 'operator', 'Maritime Operations Inc');

-- Sample vessel for testing
INSERT INTO vessels (name, imo_number, vessel_type, flag_state, port_of_call, total_cargo_capacity, status, eta) VALUES
('MV Atlantic Trader', '1234567', 'Container Ship', 'USA', 'Port of Los Angeles', 2000, 'expected', NOW() + INTERVAL '2 days'),
('MV Pacific Explorer', '2345678', 'Bulk Carrier', 'Panama', 'Port of Long Beach', 1500, 'berthed', NOW()),
('MV Global Pioneer', '3456789', 'Car Carrier', 'Liberia', 'Port of Charleston', 1800, 'operations_active', NOW() - INTERVAL '6 hours');

-- Sample cargo tallies
INSERT INTO cargo_tallies (vessel_id, cargo_count, tally_type, location, condition) 
SELECT v.id, 150, 'loaded', 'Berth A1', 'good' FROM vessels v WHERE v.name = 'MV Pacific Explorer';

INSERT INTO cargo_tallies (vessel_id, cargo_count, tally_type, location, condition) 
SELECT v.id, 85, 'loaded', 'Berth A1', 'good' FROM vessels v WHERE v.name = 'MV Pacific Explorer';