import subprocess
import sys
result = subprocess.run(
    [sys.executable, "-m", "pip", "list"],
    capture_output=True, text=True, encoding="utf-8", errors="replace"
)
output = result.stdout + "\n---STDERR---\n" + result.stderr
with open("pip_list_out.txt", "w", encoding="utf-8") as f:
    f.write(output)
print("written, exit=", result.returncode)
