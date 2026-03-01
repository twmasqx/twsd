Nexus Vision — Android packaging notes

This document explains how to package the Kivy mobile UI using Buildozer.

Important safety & limitations
- The APK produced by these steps contains only a Kivy UI client (no Scapy/libpcap).
- Low-level packet capture/injection requires root and native drivers and cannot be bundled in a Play-Store-safe APK.
- Recommended architecture: keep Scapy on a PC/Raspberry Pi as a server and have the mobile app consume its API.

Quick Buildozer steps (WSL recommended)
1. Install WSL Ubuntu or use a Linux machine.
2. Install dependencies:
   sudo apt update
   sudo apt install -y python3-pip python3-venv git openjdk-11-jdk build-essential libssl-dev libffi-dev zlib1g-dev libjpeg-dev unzip zip
3. Install buildozer and cython:
   python3 -m pip install --user --upgrade pip
   python3 -m pip install --user buildozer cython
   export PATH=$PATH:~/.local/bin
4. Initialize and edit the spec in the project root:
   buildozer init
   # edit buildozer.spec (requirements, package.name, package.domain)
5. Build (first run downloads Android SDK/NDK; be patient):
   buildozer -v android debug
6. Deploy to device (connected via USB, with developer mode and USB debugging enabled):
   buildozer android debug deploy run

Docker alternative
- Use a Kivy/Buildozer Docker image to build on Windows without WSL.
- Example:
  docker run --rm -v ${PWD}:/home/user/hostcwd kivy/buildozer buildozer android debug

If you want, I can:
- Convert more of the desktop UI into Kivy widgets and polish for touch.
- Scaffold a small Flask/WebSocket server to run Scapy on a PC and expose a safe API for the mobile client.
