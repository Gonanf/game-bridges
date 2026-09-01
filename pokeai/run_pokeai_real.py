#!/usr/bin/env python3
import subprocess, sys, time, os

# Aseguramos venv correcto
venv_py = '/home/chaos/proyectos/game-bridges/pokeai/.venv311/bin/python'
if not os.path.exists(venv_py):
    print(f"ERROR: {venv_py} not found")
    sys.exit(1)

rom = 'roms/pokemon_firered.gba'
if not os.path.exists(rom):
    print(f"ERROR: ROM {rom} not found")
    sys.exit(1)

print("=== Lanzando pokeai real (FireRed traducida) ===")
print(f"Using: {venv_py}")
print(f"ROM: {rom}")
print("Ctrl+C para detener\n")

try:
    subprocess.run([venv_py, 'harness.py', '--rom', rom], check=True)
except KeyboardInterrupt:
    print("\nDetenido por usuario")
except subprocess.CalledProcessError as e:
    print(f"Error: {e}")
