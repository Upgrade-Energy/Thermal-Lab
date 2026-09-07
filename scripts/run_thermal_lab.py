"""Launch the standalone Thermal Lab desktop interface."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

if __name__=='__main__':
    from thermal_lab.desktop import main
    main()
