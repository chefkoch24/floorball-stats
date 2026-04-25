"""Run the full data refresh pipeline (equivalent to `make refresh-all-leagues`)."""
import subprocess
import sys

result = subprocess.run(["make", "refresh-all-leagues"], check=False)
sys.exit(result.returncode)
