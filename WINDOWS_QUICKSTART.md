# LLaVA Caption Generator for Windows — Quick Start

## 1. Install Dependencies

```bash
pip install pandas openpyxl requests
```

## 2. Install & Start Ollama

1. **Download Ollama**: https://ollama.ai (download for Windows)
2. **Run the installer** and complete setup
3. **Start Ollama**: The desktop app will run in the background (system tray)

## 3. Download the LLaVA Model

Open **PowerShell** (or Command Prompt) and run:

```powershell
ollama pull llava:latest
```

This downloads ~6 GB. First time takes 5-10 minutes depending on connection speed.

## 4. Verify Setup (Sanity Checks)

### Check 1: Is Ollama running?

```powershell
Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -ErrorAction SilentlyContinue
```

✓ Should return JSON with available models (if Ollama is running).

### Check 2: Is LLaVA installed?

```powershell
ollama list
```

✓ You should see `llava:latest` in the list.

### Check 3: Test a quick inference

```powershell
$body = @{
    model = "llava:latest"
    prompt = "What do you see?"
    images = @("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    stream = $false
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:11434/api/generate" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body | Select-Object -ExpandProperty Content
```

✓ Should return JSON with a `"response"` field containing text.

## 5. Prepare Your Data

Your Excel file must have these columns:
- `project_id`
- `category` (one of: Reflector, RU, RU-Montage, Visits)
- `image_id` (filename like `20180105_101214.jpg`)
- `caption` (existing manual caption)
- `caption_ai` (will be filled by script)

Your folder structure must be:
```
img\
├── Reflector\
│   ├── 20180105_101214.jpg
│   └── ...
├── RU\
├── RU-Montage\
└── Visits\
```

## 6. Run the Script

### Basic (process all images):
```powershell
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_with_ai.xlsx
```

### Test mode (first 5 images only):
```powershell
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_with_ai.xlsx `
  --limit 5
```

### Regenerate all captions (overwrite existing):
```powershell
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_with_ai.xlsx `
  --overwrite
```

### Use different model size (faster, lower quality):
```powershell
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output image_metadata_with_ai.xlsx `
  --model llava:7b
```

First, pull the smaller model:
```powershell
ollama pull llava:7b
```

## Expected Output

The script will print progress like:

```
Loading Excel file: image_metadata.xlsx
Loaded 120 rows
Processing first 5 rows

Starting caption generation...
  Model: llava:latest
  Overwrite existing: False
  Total rows: 5

[  1] Processing: img\Reflector\20180105_101214.jpg
    ✓ Large stainless steel disc with milled surface features and mounting...
[  2] Processing: img\Reflector\20180105_101224.jpg
    ✓ Rectangular steel plate positioned horizontally...
[  3] MISSING: img\Reflector\missing_image.jpg
[  4] Processing: img\RU\image001.jpg
    ✓ Beryllium reflector housing clamped...
[  5] Processing: img\Visits\photo.jpg
    ✓ Person examining mounted assembly...

======================================================================
SUMMARY
======================================================================
Processed:  5
Skipped:    0
Success:    4
Errors:     1

Saving to: image_metadata_with_ai.xlsx
✓ Complete!
```

## Troubleshooting

### "Ollama is not running at http://localhost:11434"

**Solution**: 
1. Click the Windows Start menu
2. Search for "Ollama"
3. Click to start the Ollama desktop app
4. You should see the icon in the system tray (bottom-right)
5. Try the script again

### "Model 'llava:latest' not found"

**Solution**: 
```powershell
ollama pull llava:latest
```

Wait for download to complete, then retry the script.

### Script is very slow or hangs

**Possible causes:**

1. **First run**: Model is loading (takes 30-60 seconds). This is normal. Wait.

2. **CPU-only system**: Large models are slow on CPU. Try:
   ```powershell
   ollama pull llava:7b
   python caption_llava_ollama.py --input ... --model llava:7b
   ```

3. **System overload**: Close other apps, especially heavy ones (Chrome, Slack, etc.)

4. **Timeout**: If it still hangs, you can edit `OLLAMA_TIMEOUT = 120` in the script to `240` (4 minutes)

### Low quality captions

Try a larger model:
```powershell
ollama pull llava:13b
python caption_llava_ollama.py --input ... --model llava:13b
```

## Advanced Options

### Process only first 100 rows:
```powershell
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output test_output.xlsx `
  --limit 100
```

### Custom image folder:
```powershell
python caption_llava_ollama.py `
  --input image_metadata.xlsx `
  --output output.xlsx `
  --img_root C:\path\to\images
```

### View help:
```powershell
python caption_llava_ollama.py --help
```

## Model Performance (Rough Estimates)

On modern GPU (RTX 3060+):
- **llava:7b** → ~5-10 sec/image (fastest, decent quality)
- **llava:latest** (13B) → ~10-20 sec/image (balanced)
- **llava:13b** → ~15-25 sec/image (explicit 13B variant)

On CPU-only:
- ~60-120 sec/image (very slow)

## Tips for Best Results

1. **Test first**: Always use `--limit 5` for quick verification before full batch

2. **Check images**: Make sure images are:
   - Clear and well-lit
   - Not blurry
   - Technical/lab photos (not artwork or diagrams)

3. **Review output**: Open the Excel file and spot-check a few captions

4. **Monitor**: Watch the terminal output for `[ERROR]` or `[MISSING IMAGE]` entries

5. **Backup**: Keep original Excel file; script writes to a different file by default

## File Locations Check

```powershell
# Check Excel file
Test-Path image_metadata.xlsx

# Check image folder
Test-Path img\Reflector
Test-Path img\RU
Test-Path img\RU-Montage
Test-Path img\Visits

# Check Python installed
python --version

# Check required packages
python -c "import pandas, requests, openpyxl; print('All packages OK')"
```

## Next Steps

1. Run `--limit 5` first to test
2. Review the output file for caption quality
3. Adjust `--model` if needed (try `llava:7b` for speed or `llava:13b` for quality)
4. Run full batch: remove `--limit` flag
5. Save the results

---

**Questions?** Check the troubleshooting section above, or verify Ollama is running in the system tray.

**Happy captioning!** 🎯
