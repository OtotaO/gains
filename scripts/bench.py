#!/usr/bin/env python3
"""
GAINS Latency Benchmarking Script
Measures speech start → nod commit timing for performance analysis
"""

import zmq
import time
import json
import statistics
import threading
from collections import deque
from datetime import datetime

class LatencyBenchmark:
    def __init__(self, sample_size=20):
        self.sample_size = sample_size
        self.latencies = deque(maxlen=sample_size)
        self.speech_start_times = {}
        self.nod_times = []
        self.asr_events = []
        
        # ZMQ setup
        self.ctx = zmq.Context()
        self.sub = self.ctx.socket(zmq.SUB)
        self.sub.connect("tcp://localhost:5555")
        self.sub.setsockopt_string(zmq.SUBSCRIBE, "")
        
        # Statistics
        self.stats = {
            "total_samples": 0,
            "completed_samples": 0,
            "p50_latency": 0,
            "p95_latency": 0,
            "p99_latency": 0,
            "min_latency": float('inf'),
            "max_latency": 0,
            "mean_latency": 0
        }
    
    def start_listening(self):
        """Start listening for ZMQ events"""
        print("🎯 Starting latency benchmark...")
        print("📊 Collecting samples (speak → nod to measure timing)")
        print("⏱️  Press Ctrl+C to stop and see results\n")
        
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
        
        self.calculate_statistics()
        self.print_results()
    
    def process_event(self, msg):
        """Process ZMQ events and track timing"""
        event_type = msg.get("event")
        timestamp = msg.get("ts", time.time())
        
        if event_type == "asr.partial":
            # Track speech start
            text = msg.get("text", "").strip()
            if text and not self.speech_start_times:
                self.speech_start_times[timestamp] = {
                    "text": text,
                    "start_time": timestamp,
                    "confidence": msg.get("confidence", 0)
                }
                print(f"🗣️  Speech detected: '{text[:50]}...'")
        
        elif event_type == "gesture.nod":
            # Calculate latency if we have speech start
            if self.speech_start_times:
                speech_start = min(self.speech_start_times.keys())
                latency = timestamp - speech_start
                
                if latency > 0 and latency < 10:  # Sanity check: 0-10 seconds
                    self.latencies.append(latency)
                    self.stats["completed_samples"] += 1
                    
                    speech_info = self.speech_start_times[speech_start]
                    print(f"✅ Nod detected! Latency: {latency:.3f}s | Text: '{speech_info['text'][:30]}...'")
                    
                    # Clear speech tracking for next sample
                    self.speech_start_times.clear()
                    
                    # Check if we have enough samples
                    if self.stats["completed_samples"] >= self.sample_size:
                        print(f"\n🎉 Collected {self.sample_size} samples! Calculating statistics...")
                        self.calculate_statistics()
                        self.print_results()
                        return
    
    def calculate_statistics(self):
        """Calculate latency statistics"""
        if not self.latencies:
            return
        
        latencies = list(self.latencies)
        latencies.sort()
        
        self.stats.update({
            "total_samples": len(latencies),
            "p50_latency": statistics.median(latencies),
            "p95_latency": latencies[int(len(latencies) * 0.95)],
            "p99_latency": latencies[int(len(latencies) * 0.99)] if len(latencies) > 1 else latencies[0],
            "min_latency": min(latencies),
            "max_latency": max(latencies),
            "mean_latency": statistics.mean(latencies)
        })
    
    def print_results(self):
        """Print benchmark results"""
        print("\n" + "="*60)
        print("📊 GAINS LATENCY BENCHMARK RESULTS")
        print("="*60)
        
        if self.stats["total_samples"] == 0:
            print("❌ No samples collected. Make sure services are running.")
            return
        
        print(f"📈 Samples collected: {self.stats['total_samples']}")
        print(f"⏱️  Mean latency: {self.stats['mean_latency']:.3f}s")
        print(f"📊 P50 latency: {self.stats['p50_latency']:.3f}s")
        print(f"📊 P95 latency: {self.stats['p95_latency']:.3f}s")
        print(f"📊 P99 latency: {self.stats['p99_latency']:.3f}s")
        print(f"📊 Min latency: {self.stats['min_latency']:.3f}s")
        print(f"📊 Max latency: {self.stats['max_latency']:.3f}s")
        
        # Performance assessment
        p95 = self.stats['p95_latency']
        if p95 < 0.5:
            rating = "🚀 EXCELLENT"
        elif p95 < 1.0:
            rating = "✅ GOOD"
        elif p95 < 2.0:
            rating = "⚠️  ACCEPTABLE"
        else:
            rating = "❌ NEEDS IMPROVEMENT"
        
        print(f"\n🎯 Performance Rating: {rating}")
        print(f"📋 Target: P95 < 1.0s (Current: {p95:.3f}s)")
        
        # Save results
        self.save_results()
    
    def save_results(self):
        """Save benchmark results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_results_{timestamp}.json"
        
        results = {
            "timestamp": timestamp,
            "stats": self.stats,
            "raw_latencies": list(self.latencies)
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Results saved to: {filename}")

def main():
    print("🎯 GAINS Latency Benchmark")
    print("="*40)
    print("This script measures speech → nod commit latency")
    print("Make sure all GAINS services are running:")
    print("  - python services/bus/hub.py")
    print("  - python services/asr/server.py")
    print("  - python services/vision/nod.py")
    print("  - python services/tts/voice.py")
    print()
    
    # Get sample size from user
    try:
        sample_size = int(input("Enter number of samples to collect (default 20): ") or "20")
    except ValueError:
        sample_size = 20
    
    print(f"\n🎯 Will collect {sample_size} samples")
    print("🗣️  Speak clearly and nod to commit each phrase")
    print("⏹️  Press Ctrl+C to stop early\n")
    
    # Start benchmark
    benchmark = LatencyBenchmark(sample_size)
    benchmark.start_listening()

if __name__ == "__main__":
    main() 