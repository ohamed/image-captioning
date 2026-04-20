# Windows PowerShell Quick Reference for LLaVA Caption Generator

# ============================================================================
# SANITY CHECKS - RUN THESE FIRST
# ============================================================================

# *** CHECK 1: Is Ollama running? ***
Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -ErrorAction SilentlyContinue

# Expected output: JSON with model list
# If error: Start Ollama from Windows Start menu or system tray


# *** CHECK 2: List installed Ollama models ***
ollama list

# Expected: Should show llava:latest in the list
# If missing: Run: ollama pull llava:latest


# *** CHECK 3: Test model inference ***
$payload = @{
    model = "llava:latest"
    prompt = "Describe this image"
    images = @("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    stream = $false
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:11434/api/generate" `
    -Method POST `
    -ContentType "application/json" `
    -Body $payload

# Print response to verify it works
$response.Content | ConvertFrom-Json | Select-Object response


# *** CHECK 4: Verify Python and packages ***
python --version
python -c "import pandas, openpyxl, requests; print('All packages installed!')"


# *** CHECK 5: Verify input files exist ***
Test-Path "image_metadata.xlsx"
Test-Path "img\Reflector"
Test-Path "img\RU"
Test-Path "img\RU-Montage"
Test-Path "img\Visits"

# All should return True


# ============================================================================
# DEPENDENCY INSTALLATION
# ============================================================================

# Install Python packages (run once)
pip install pandas openpyxl requests

# Upgrade pip (recommended)
python -m pip install --upgrade pip

# Create virtual environment (optional but recommended)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Then install packages in the virtual environment
pip install pandas openpyxl requests


# ============================================================================
# DOWNLOAD MODELS
# ============================================================================

# Download LLaVA (required, ~6 GB)
ollama pull llava:latest

# Download alternative sizes
ollama pull llava:7b      # Smaller, faster (~5 GB)
ollama pull llava:13b     # Explicit 13B variant (~8 GB)
ollama pull llava:34b     # Larger, slower (~20 GB)

# List all available models on Ollama Hub
ollama list


# ============================================================================
# RUN THE SCRIPT - BASIC COMMANDS
# ============================================================================

# Basic: Process all images
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_with_ai.xlsx

# Test mode: Process only first 5 images
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_with_ai.xlsx `
  --limit 5

# Regenerate all: Overwrite existing captions
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_with_ai.xlsx `
  --overwrite

# Use smaller model (faster)
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_with_ai.xlsx `
  --model llava:7b

# Use larger model (better quality)
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_with_ai.xlsx `
  --model llava:13b

# Custom image root directory
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_with_ai.xlsx `
  --img_root "C:\path\to\images"

# Show help
python caption_llava_ollama.py --help


# ============================================================================
# DATA VALIDATION
# ============================================================================

# Check Excel columns
python -c "
import pandas as pd
df = pd.read_excel('image_metadata.xlsx')
print(f'Columns: {df.columns.tolist()}')
print(f'Total rows: {len(df)}')
print(f'Empty caption_ai: {df[\"caption_ai\"].isna().sum()}')
"

# Count images in each category
ls img\Reflector | Measure-Object
ls img\RU | Measure-Object
ls img\RU-Montage | Measure-Object
ls img\Visits | Measure-Object

# Find missing image files
python -c "
import pandas as pd
from pathlib import Path

df = pd.read_excel('image_metadata.xlsx')
missing = []

for idx, row in df.iterrows():
    path = Path('img') / row['category'] / str(row['image_id'])
    if not path.exists():
        missing.append((row['image_id'], row['category']))

print(f'Missing files: {len(missing)}')
for filename, category in missing[:10]:
    print(f'  {category}\{filename}')
"


# ============================================================================
# MONITOR & TROUBLESHOOT
# ============================================================================

# Check if Ollama process is running
Get-Process | Select-String ollama

# Kill Ollama process (if frozen)
Stop-Process -Name "ollama" -Force

# Check Ollama logs (if available)
Get-Content "$env:USERPROFILE\AppData\Local\Ollama\ollama.log" -Tail 50

# Monitor GPU usage while running (if CUDA available)
# Use Windows Task Manager: Performance tab → GPU

# Check available disk space
Get-Volume | Where-Object DriveLetter -eq "C"

# Check system memory
Get-ComputerInfo | Select-Object CsPhysicalMemory, CsTotalPhysicalMemory


# ============================================================================
# OUTPUT VALIDATION
# ============================================================================

# Compare input and output
python -c "
import pandas as pd

inp = pd.read_excel('image_metadata.xlsx')
out = pd.read_excel('image_metadata_with_ai.xlsx')

print(f'Input rows: {len(inp)}')
print(f'Output rows: {len(out)}')
print(f'Captions generated: {out[\"caption_ai\"].notna().sum()}')
print(f'Empty captions: {out[\"caption_ai\"].isna().sum()}')
print(f'Error markers: {(out[\"caption_ai\"] == \"[ERROR]\").sum()}')
print(f'Missing image markers: {(out[\"caption_ai\"] == \"[MISSING IMAGE]\").sum()}')
"

# View first 10 captions
python -c "
import pandas as pd
df = pd.read_excel('image_metadata_with_ai.xlsx')
print(df[['image_id', 'category', 'caption_ai']].head(10).to_string())
"

# View errors only
python -c "
import pandas as pd
df = pd.read_excel('image_metadata_with_ai.xlsx')
errors = df[df['caption_ai'].str.contains('\[ERROR\]|\[MISSING IMAGE\]', na=False, regex=True)]
print(errors[['image_id', 'category', 'caption_ai']])
"

# Export summary statistics
python -c "
import pandas as pd
df = pd.read_excel('image_metadata_with_ai.xlsx')

summary = {
    'Total': len(df),
    'Success': df['caption_ai'].notna().sum(),
    'Errors': (df['caption_ai'] == '[ERROR]').sum(),
    'Missing': (df['caption_ai'] == '[MISSING IMAGE]').sum(),
}

for key, val in summary.items():
    print(f'{key}: {val}')
"


# ============================================================================
# CLEANUP & MAINTENANCE
# ============================================================================

# Remove output files
Remove-Item image_metadata_with_ai.xlsx

# Clear Ollama cache (removes all models - caution!)
ollama rm llava:latest
ollama rm llava:7b

# Get Ollama models disk usage
ls "$env:USERPROFILE\.ollama\models"

# Restart Ollama service (if needed)
# Windows: Just restart from Start menu or kill + reopen app

# Check Ollama configuration
$env:OLLAMA_HOST  # Should be set or default to localhost:11434


# ============================================================================
# COMMON WORKFLOWS
# ============================================================================

# Workflow 1: Quick test (safe)
Write-Host "Step 1: Testing Ollama..."
Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -ErrorAction Stop

Write-Host "Step 2: Processing 5 rows..."
python caption_llava_ollama.py --input image_metadata.xlsx --output test.xlsx --limit 5

Write-Host "Step 3: Review results..."
python -c "import pandas as pd; df = pd.read_excel('test.xlsx'); print(df[['image_id', 'caption_ai']].head())"


# Workflow 2: Full batch processing
Write-Host "Starting full batch..."
$startTime = Get-Date

python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_with_ai.xlsx

$endTime = Get-Date
$duration = $endTime - $startTime
Write-Host "Completed in $($duration.TotalMinutes) minutes"


# Workflow 3: Reprocess with different model
Write-Host "Pulling llava:7b..."
ollama pull llava:7b

Write-Host "Reprocessing with faster model..."
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_llava7b.xlsx `
  --model llava:7b `
  --overwrite


# ============================================================================
# PERFORMANCE MONITORING
# ============================================================================

# Start with verbose output and timing
$watch = [System.Diagnostics.Stopwatch]::StartNew()

python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output output.xlsx `
  --limit 10

$watch.Stop()
Write-Host "Time: $($watch.Elapsed.TotalSeconds) seconds"
Write-Host "Average per image: $($watch.Elapsed.TotalSeconds / 10) seconds"


# ============================================================================
# EMERGENCY FIXES
# ============================================================================

# Fix: Script says "Ollama is not running"
# Solution 1: Check if running
Get-Process | findstr ollama

# Solution 2: Start Ollama manually
# Click Windows Start → Search "Ollama" → Click app


# Fix: "Model not found" error
# Solution: Download the model
ollama pull llava:latest
# Then retry script


# Fix: Script hangs or very slow
# Solution 1: Check Ollama is responsive
$timeout = 180  # 3 minutes
Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -ErrorAction Stop

# Solution 2: Try with smaller model
ollama pull llava:7b
python caption_llava_ollama.py --input ... --model llava:7b

# Solution 3: Close other apps and retry


# Fix: Excel file won't open or corrupted
# Solution 1: Make sure script completed (check for "✓ Complete!" message)

# Solution 2: Check disk space
Get-Volume -DriveLetter C | Select-Object SizeRemaining, Size

# Solution 3: Retry with smaller batch
python caption_llava_ollama.py --input ... --limit 50


# ============================================================================
# USEFUL REFERENCES
# ============================================================================

# Ollama documentation: https://github.com/ollama/ollama
# LLaVA models: https://ollama.ai/library/llava
# Python requests: https://docs.python-requests.org/
# pandas: https://pandas.pydata.org/docs/
# openpyxl: https://openpyxl.readthedocs.io/

# Ollama API endpoint: http://localhost:11434
# Default timeout: 120 seconds (edit in script if needed)
# Base image models: llava:7b, llava:13b, llava:34b
