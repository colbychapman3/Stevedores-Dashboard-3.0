#!/usr/bin/env python3
"""
Production Monitoring Script for Stevedores Dashboard 3.0
Real-time monitoring of worker health, diagnostic logs, and crash analysis

Usage:
    python production_monitor.py --watch-diagnostics
    python production_monitor.py --analyze-crashes
    python production_monitor.py --health-check
"""

import os
import sys
import time
import json
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
import psutil
import subprocess
from typing import Dict, List, Any, Optional
import glob
import threading
from collections import defaultdict

# Setup monitoring logger
monitor_logger = logging.getLogger('stevedores.monitor')
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s [MONITOR] %(levelname)s %(message)s')
handler.setFormatter(formatter)
monitor_logger.addHandler(handler)
monitor_logger.setLevel(logging.INFO)


class WorkerCrashAnalyzer:
    """Analyzes worker crashes and diagnostic logs"""
    
    def __init__(self):
        self.diagnostic_log_pattern = '/tmp/stevedores_diagnostic_*.json'
        self.crash_patterns = [
            'TERM signal',
            'Worker.*aborted',
            'Database.*failed',
            'CRITICAL',
            'terminated',
            'crash'
        ]
    
    def find_diagnostic_logs(self) -> List[Path]:
        """Find all diagnostic log files"""
        log_files = glob.glob(self.diagnostic_log_pattern)
        return [Path(f) for f in sorted(log_files, key=os.path.getmtime, reverse=True)]
    
    def analyze_diagnostic_log(self, log_file: Path) -> Dict[str, Any]:
        """Analyze a single diagnostic log file"""
        try:
            with open(log_file, 'r') as f:
                data = json.load(f)
            
            checkpoints = data.get('checkpoints', [])
            if not checkpoints:
                return {'status': 'empty', 'file': str(log_file)}
            
            # Analyze checkpoint statuses
            status_counts = defaultdict(int)
            critical_errors = []
            warnings = []
            last_checkpoint = None
            
            for checkpoint in checkpoints:
                status = checkpoint.get('status', 'unknown')
                status_counts[status] += 1
                
                if status == 'critical':
                    critical_errors.append({
                        'name': checkpoint.get('name'),
                        'error': checkpoint.get('error_info'),
                        'timestamp': checkpoint.get('timestamp')
                    })
                elif status == 'error':
                    critical_errors.append({
                        'name': checkpoint.get('name'),
                        'error': checkpoint.get('error_info'),
                        'timestamp': checkpoint.get('timestamp')
                    })
                elif status == 'warning':
                    warnings.append({
                        'name': checkpoint.get('name'),
                        'error': checkpoint.get('error_info'),
                        'timestamp': checkpoint.get('timestamp')
                    })
                
                last_checkpoint = checkpoint
            
            # Determine if this represents a crash
            is_crash = (
                status_counts['critical'] > 0 or
                status_counts['error'] > 0 or
                (last_checkpoint and last_checkpoint.get('status') in ['critical', 'error'])
            )
            
            analysis = {
                'file': str(log_file),
                'worker_id': data.get('worker_id'),
                'checkpoint_count': len(checkpoints),
                'status_counts': dict(status_counts),
                'critical_errors': critical_errors,
                'warnings': warnings,
                'last_checkpoint': last_checkpoint.get('name') if last_checkpoint else None,
                'last_status': last_checkpoint.get('status') if last_checkpoint else None,
                'is_crash': is_crash,
                'file_modified': datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
            }
            
            return analysis
            
        except Exception as e:
            return {
                'status': 'error',
                'file': str(log_file),
                'error': str(e)
            }
    
    def analyze_all_crashes(self) -> Dict[str, Any]:
        """Analyze all available diagnostic logs"""
        log_files = self.find_diagnostic_logs()
        
        if not log_files:
            return {
                'status': 'no_logs',
                'message': f'No diagnostic logs found matching pattern: {self.diagnostic_log_pattern}'
            }
        
        analyses = []
        crash_count = 0
        total_logs = len(log_files)
        
        for log_file in log_files[:20]:  # Analyze last 20 logs
            analysis = self.analyze_diagnostic_log(log_file)
            analyses.append(analysis)
            
            if analysis.get('is_crash'):
                crash_count += 1
        
        # Identify common failure patterns
        failure_patterns = defaultdict(int)
        for analysis in analyses:
            if analysis.get('is_crash'):
                for error in analysis.get('critical_errors', []):
                    checkpoint_name = error.get('name', 'unknown')
                    failure_patterns[checkpoint_name] += 1
        
        return {
            'status': 'analyzed',
            'total_logs': total_logs,
            'analyzed_logs': len(analyses),
            'crash_count': crash_count,
            'crash_rate': crash_count / len(analyses) if analyses else 0,
            'common_failure_points': dict(failure_patterns),
            'recent_analyses': analyses[:5],  # Most recent 5
            'log_files_found': [str(f) for f in log_files]
        }


class ProductionHealthMonitor:
    """Monitors production health in real-time"""
    
    def __init__(self):
        self.gunicorn_processes = []
        self.monitoring = False
        
    def find_gunicorn_processes(self) -> List[psutil.Process]:
        """Find all Gunicorn processes"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                if (proc.info['name'] and 'gunicorn' in proc.info['name'].lower()) or \
                   (proc.info['cmdline'] and any('gunicorn' in cmd for cmd in proc.info['cmdline'])):
                    processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes
    
    def get_process_health(self, process: psutil.Process) -> Dict[str, Any]:
        """Get health information for a process"""
        try:
            with process.oneshot():
                return {
                    'pid': process.pid,
                    'status': process.status(),
                    'cpu_percent': process.cpu_percent(),
                    'memory_mb': process.memory_info().rss / 1024 / 1024,
                    'memory_percent': process.memory_percent(),
                    'create_time': datetime.fromtimestamp(process.create_time()).isoformat(),
                    'uptime_seconds': time.time() - process.create_time(),
                    'num_threads': process.num_threads(),
                    'connections': len(process.connections()) if hasattr(process, 'connections') else 0
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            return {
                'pid': process.pid,
                'status': 'error',
                'error': str(e)
            }
    
    def check_application_health(self) -> Dict[str, Any]:
        """Check application health via HTTP endpoint"""
        try:
            import requests
            
            # Try localhost first, then common production URLs
            urls_to_try = [
                'http://localhost:8000/health',
                'http://localhost:5000/health',
                'http://127.0.0.1:8000/health',
                'http://127.0.0.1:5000/health'
            ]
            
            for url in urls_to_try:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        return {
                            'status': 'healthy',
                            'url': url,
                            'response_time_ms': response.elapsed.total_seconds() * 1000,
                            'response_data': response.json()
                        }
                except requests.RequestException:
                    continue
            
            return {
                'status': 'unreachable',
                'message': 'Could not reach health endpoint on any common port'
            }
            
        except ImportError:
            return {
                'status': 'no_requests',
                'message': 'requests library not available for health check'
            }
    
    def monitor_once(self) -> Dict[str, Any]:
        """Perform one monitoring cycle"""
        monitor_time = datetime.utcnow()
        
        # Find Gunicorn processes
        gunicorn_processes = self.find_gunicorn_processes()
        
        # Get process health
        process_health = []
        for proc in gunicorn_processes:
            health = self.get_process_health(proc)
            process_health.append(health)
        
        # Check application health
        app_health = self.check_application_health()
        
        # System resources
        system_health = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
        
        return {
            'timestamp': monitor_time.isoformat(),
            'gunicorn_process_count': len(gunicorn_processes),
            'process_health': process_health,
            'application_health': app_health,
            'system_health': system_health
        }
    
    def start_monitoring(self, interval: int = 10):
        """Start continuous monitoring"""
        self.monitoring = True
        monitor_logger.info(f"Starting production monitoring (interval: {interval}s)")
        
        while self.monitoring:
            health_data = self.monitor_once()
            
            # Log summary
            proc_count = health_data['gunicorn_process_count']
            app_status = health_data['application_health']['status']
            cpu_percent = health_data['system_health']['cpu_percent']
            memory_percent = health_data['system_health']['memory_percent']
            
            monitor_logger.info(
                f"Health Check: {proc_count} processes, app={app_status}, "
                f"CPU={cpu_percent:.1f}%, Memory={memory_percent:.1f}%"
            )
            
            # Check for problems
            problems = []
            
            # Check for dead processes
            dead_processes = [p for p in health_data['process_health'] if p.get('status') == 'zombie']
            if dead_processes:
                problems.append(f"{len(dead_processes)} zombie processes")
            
            # Check for high resource usage
            if cpu_percent > 90:
                problems.append(f"High CPU usage: {cpu_percent:.1f}%")
            if memory_percent > 90:
                problems.append(f"High memory usage: {memory_percent:.1f}%")
            
            # Check application health
            if app_status != 'healthy':
                problems.append(f"Application unhealthy: {app_status}")
            
            if problems:
                monitor_logger.warning(f"Problems detected: {'; '.join(problems)}")
            
            time.sleep(interval)
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.monitoring = False
        monitor_logger.info("Stopping production monitoring")


def watch_diagnostic_logs():
    """Watch diagnostic logs in real-time"""
    monitor_logger.info("Watching diagnostic logs for new entries...")
    
    # Monitor /tmp for new diagnostic files
    existing_files = set(glob.glob('/tmp/stevedores_diagnostic_*.json'))
    
    while True:
        current_files = set(glob.glob('/tmp/stevedores_diagnostic_*.json'))
        new_files = current_files - existing_files
        
        for new_file in new_files:
            monitor_logger.info(f"New diagnostic log detected: {new_file}")
            
            # Analyze the new file
            analyzer = WorkerCrashAnalyzer()
            analysis = analyzer.analyze_diagnostic_log(Path(new_file))
            
            if analysis.get('is_crash'):
                monitor_logger.error(f"CRASH DETECTED in {new_file}")
                monitor_logger.error(f"Critical errors: {len(analysis.get('critical_errors', []))}")
                
                for error in analysis.get('critical_errors', [])[:3]:  # Show first 3 errors
                    monitor_logger.error(f"  - {error.get('name')}: {error.get('error')}")
            else:
                monitor_logger.info(f"Clean diagnostic log: {analysis.get('checkpoint_count')} checkpoints")
        
        existing_files = current_files
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description='Production Monitor for Stevedores Dashboard 3.0')
    parser.add_argument('--watch-diagnostics', action='store_true', 
                       help='Watch diagnostic logs in real-time')
    parser.add_argument('--analyze-crashes', action='store_true',
                       help='Analyze all crash logs')
    parser.add_argument('--health-check', action='store_true',
                       help='Perform one-time health check')
    parser.add_argument('--monitor', action='store_true',
                       help='Start continuous health monitoring')
    parser.add_argument('--interval', type=int, default=10,
                       help='Monitoring interval in seconds (default: 10)')
    
    args = parser.parse_args()
    
    if args.watch_diagnostics:
        try:
            watch_diagnostic_logs()
        except KeyboardInterrupt:
            monitor_logger.info("Diagnostic log watching stopped")
    
    elif args.analyze_crashes:
        analyzer = WorkerCrashAnalyzer()
        analysis = analyzer.analyze_all_crashes()
        
        print(json.dumps(analysis, indent=2))
        
        if analysis['status'] == 'analyzed':
            monitor_logger.info(f"Analyzed {analysis['analyzed_logs']} logs")
            monitor_logger.info(f"Crash rate: {analysis['crash_rate']:.1%}")
            
            if analysis['common_failure_points']:
                monitor_logger.warning("Common failure points:")
                for point, count in analysis['common_failure_points'].items():
                    monitor_logger.warning(f"  - {point}: {count} occurrences")
    
    elif args.health_check:
        monitor = ProductionHealthMonitor()
        health_data = monitor.monitor_once()
        print(json.dumps(health_data, indent=2))
    
    elif args.monitor:
        monitor = ProductionHealthMonitor()
        try:
            monitor.start_monitoring(args.interval)
        except KeyboardInterrupt:
            monitor.stop_monitoring()
            monitor_logger.info("Monitoring stopped")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()