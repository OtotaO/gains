#!/usr/bin/env python3
"""
GAINS Note Export Service
Exports transcribed text to various formats for note-taking integration
"""

import zmq
import json
import os
import time
from datetime import datetime
from pathlib import Path

class NoteExporter:
    def __init__(self, output_dir="notes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # ZMQ setup
        self.ctx = zmq.Context()
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.connect("tcp://localhost:5555")
        self.sub.setsockopt_string(zmq.SUBSCRIBE, "")
        
        # Note tracking
        self.current_session = []
        self.session_start = None
        self.last_commit_time = None
        
        # Export formats
        self.export_formats = ["txt", "md", "json"]
        
        print(f"📝 Note Exporter started - Output: {self.output_dir}")
    
    def start_listening(self):
        """Listen for ZMQ events and export notes"""
        print("🎯 Listening for speech and gesture events...")
        
        try:
            while True:
                try:
                    msg = self.sub.recv_json(zmq.NOBLOCK)
                    self.process_event(msg)
                except zmq.Again:
                    time.sleep(0.01)
                except KeyboardInterrupt:
                    break
        except KeyboardInterrupt:
            pass
        
        # Export final session
        if self.current_session:
            self.export_session()
    
    def process_event(self, msg):
        """Process ZMQ events and build notes"""
        event_type = msg.get("event")
        timestamp = msg.get("ts", time.time())
        
        if event_type == "asr.partial":
            # Track speech
            text = msg.get("text", "").strip()
            if text:
                if not self.session_start:
                    self.session_start = timestamp
                
                # Add to current session
                self.current_session.append({
                    "type": "speech",
                    "text": text,
                    "timestamp": timestamp,
                    "confidence": msg.get("confidence", 0),
                    "start": msg.get("start", 0),
                    "end": msg.get("end", 0)
                })
        
        elif event_type == "gesture.nod":
            # Commit current text
            if self.current_session:
                self.last_commit_time = timestamp
                
                # Mark the last speech entry as committed
                if self.current_session and self.current_session[-1]["type"] == "speech":
                    self.current_session[-1]["committed"] = True
                    self.current_session[-1]["commit_time"] = timestamp
                
                print(f"✅ Note committed: {self.current_session[-1]['text'][:50]}...")
                
                # Export if we have enough content or enough time has passed
                if self.should_export():
                    self.export_session()
    
    def should_export(self):
        """Determine if we should export the current session"""
        if not self.current_session:
            return False
        
        # Export if we have more than 5 entries or 30 seconds have passed
        committed_entries = [e for e in self.current_session if e.get("committed", False)]
        time_since_start = time.time() - self.session_start if self.session_start else 0
        
        return len(committed_entries) >= 5 or time_since_start > 30
    
    def export_session(self):
        """Export current session to all formats"""
        if not self.current_session:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Prepare session data
        session_data = {
            "session_id": timestamp,
            "start_time": self.session_start,
            "end_time": time.time(),
            "entries": self.current_session,
            "total_entries": len(self.current_session),
            "committed_entries": len([e for e in self.current_session if e.get("committed", False)])
        }
        
        # Export to different formats
        for format_type in self.export_formats:
            self.export_to_format(session_data, format_type, timestamp)
        
        print(f"📁 Session exported: {session_data['committed_entries']} entries")
        
        # Reset for next session
        self.current_session = []
        self.session_start = None
    
    def export_to_format(self, session_data, format_type, timestamp):
        """Export session to specific format"""
        filename = self.output_dir / f"gains_notes_{timestamp}.{format_type}"
        
        if format_type == "txt":
            self.export_txt(session_data, filename)
        elif format_type == "md":
            self.export_markdown(session_data, filename)
        elif format_type == "json":
            self.export_json(session_data, filename)
    
    def export_txt(self, session_data, filename):
        """Export as plain text"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"GAINS Notes - Session {session_data['session_id']}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 50 + "\n\n")
            
            for entry in session_data["entries"]:
                if entry.get("committed", False):
                    f.write(f"{entry['text']}\n\n")
    
    def export_markdown(self, session_data, filename):
        """Export as Markdown"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# GAINS Notes - Session {session_data['session_id']}\n\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\n")
            f.write(f"**Duration:** {session_data['end_time'] - session_data['start_time']:.1f}s\n")
            f.write(f"**Entries:** {session_data['committed_entries']}/{session_data['total_entries']}\n\n")
            f.write("---\n\n")
            
            for entry in session_data["entries"]:
                if entry.get("committed", False):
                    f.write(f"{entry['text']}\n\n")
    
    def export_json(self, session_data, filename):
        """Export as JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

def main():
    print("📝 GAINS Note Export Service")
    print("=" * 40)
    print("Exports transcribed text to txt, md, and json formats")
    print("Make sure all GAINS services are running")
    print()
    
    # Get output directory
    output_dir = input("Enter output directory (default: notes): ").strip() or "notes"
    
    # Start exporter
    exporter = NoteExporter(output_dir)
    exporter.start_listening()

if __name__ == "__main__":
    main() 