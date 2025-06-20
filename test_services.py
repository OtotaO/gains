#!/usr/bin/env python3
"""
Test script for GAINS services
Run this to verify all dependencies are working correctly
"""

import sys
import time
import zmq

def test_zmq():
    """Test ZeroMQ functionality"""
    print("Testing ZeroMQ...")
    try:
        ctx = zmq.Context()
        pub = ctx.socket(zmq.PUB)
        sub = ctx.socket(zmq.SUB)
        
        pub.bind("tcp://*:5556")
        time.sleep(0.1)  # Give time for binding
        sub.connect("tcp://localhost:5556")
        sub.setsockopt_string(zmq.SUBSCRIBE, "")
        time.sleep(0.1)  # Give time for connection
        
        # Send test message
        test_msg = {"event": "test", "data": "hello"}
        pub.send_json(test_msg)
        time.sleep(0.1)  # Give time for message to arrive
        
        # Receive with timeout
        sub.setsockopt(zmq.RCVTIMEO, 2000)  # 2 second timeout
        try:
            received = sub.recv_json()
            if received == test_msg:
                print("✓ ZeroMQ working correctly")
                return True
            else:
                print(f"✗ ZeroMQ message mismatch: {received} != {test_msg}")
                return False
        except zmq.Again:
            print("✗ ZeroMQ timeout")
            return False
            
    except Exception as e:
        print(f"✗ ZeroMQ error: {e}")
        return False
    finally:
        try:
            pub.close()
            sub.close()
            ctx.term()
        except:
            pass

def test_imports():
    """Test all required imports"""
    print("Testing imports...")
    
    try:
        import faster_whisper
        print("✓ faster-whisper imported")
    except ImportError as e:
        print(f"✗ faster-whisper import failed: {e}")
        return False
    
    try:
        import sounddevice
        print("✓ sounddevice imported")
    except ImportError as e:
        print(f"✗ sounddevice import failed: {e}")
        return False
    
    try:
        import cv2
        print("✓ opencv imported")
    except ImportError as e:
        print(f"✗ opencv import failed: {e}")
        return False
    
    try:
        import mediapipe
        print("✓ mediapipe imported")
    except ImportError as e:
        print(f"✗ mediapipe import failed: {e}")
        return False
    
    return True

def test_services():
    """Test service imports"""
    print("Testing service imports...")
    
    try:
        sys.path.append('services')
        import bus.hub
        print("✓ bus.hub imported")
    except Exception as e:
        print(f"✗ bus.hub import failed: {e}")
        return False
    
    try:
        import asr.server
        print("✓ asr.server imported")
    except Exception as e:
        print(f"✗ asr.server import failed: {e}")
        return False
    
    try:
        import vision.nod
        print("✓ vision.nod imported")
    except Exception as e:
        print(f"✗ vision.nod import failed: {e}")
        return False
    
    try:
        import tts.voice
        print("✓ tts.voice imported")
    except Exception as e:
        print(f"✗ tts.voice import failed: {e}")
        return False
    
    return True

def main():
    print("GAINS Service Test")
    print("=" * 50)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    print()
    
    # Test services
    if not test_services():
        all_passed = False
    
    print()
    
    # Test ZeroMQ
    if not test_zmq():
        all_passed = False
    
    print()
    print("=" * 50)
    
    if all_passed:
        print("🎉 All tests passed! GAINS is ready to run.")
        print("\nNext steps:")
        print("1. Start the hub: python services/bus/hub.py")
        print("2. Start ASR: python services/asr/server.py")
        print("3. Start vision: python services/vision/nod.py")
        print("4. Start TTS: python services/tts/voice.py")
        print("5. Launch UI: cd tauri-app && pnpm tauri dev")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main() 