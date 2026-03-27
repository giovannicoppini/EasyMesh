# SURF SHYFEM - EasyMesh Integration Testing Guide

## Overview
This guide provides step-by-step instructions to test the EasyMesh integration in SURF SHYFEM v2.0.4.

## Pre-Testing Checklist

- [ ] EasyMesh Docker image successfully built: `surf_shyfem:x86_64-v2.0.4-easymesh`
- [ ] Original image backed up or tagged
- [ ] System storage has >5GB free space (93% disk usage currently **CRITICAL**)
- [ ] SURF config file prepared with `"use_easymesh": true`
- [ ] Portal/database connection verified and working
- [ ] Original test domain data (Porto Potenza) available

**ACTION REQUIRED:** The Protocoast system disk is currently 93% full. Before running integration tests, clear space:
```bash
# On Ubuntu host
df -h                          # Check current usage
du -sh /home/* /var/log/* /tmp/* | sort -rh | head -20  # Identify large dirs
# Then cleanup (e.g., old logs, temp files, Docker images)
docker system prune -a
sudo journalctl --vacuum=50M
```

---

## Phase 1: Unit Tests (Container-Level)

### Test 1.1: EasyMesh Import Verification
**Objective:** Verify EasyMesh is installed and importable inside container

```bash
# Run container and test import
docker run --rm surf_shyfem:x86_64-v2.0.4-easymesh python3 -c \
  "import easymesh; print(f'EasyMesh version: {easymesh.__version__}')"

# Expected output: EasyMesh version: X.X.X
# Error handling: If ImportError → module not installed (check Dockerfile pip step)
```

**Pass Criteria:**
- ✓ EasyMesh module imports successfully
- ✓ Version number displayed

---

### Test 1.2: Integration Module Import
**Objective:** Verify SURF's EasyMesh wrapper module is accessible

```bash
docker run --rm surf_shyfem:x86_64-v2.0.4-easymesh python3 << 'EOF'
from surf_shyfem.preprocessing.core.meshing.easymesh_3d import (
    run_easymesh_3d,
    validate_easymesh_output
)
print("✓ easymesh_3d module imported successfully")
print(f"  run_easymesh_3d: {run_easymesh_3d.__doc__[:80]}...")
print(f"  validate_easymesh_output: {validate_easymesh_output.__doc__[:80]}...")
EOF

# Expected: Functions listed with docstrings
# Error: If ModuleNotFoundError → file not copied to container
```

**Pass Criteria:**
- ✓ Both functions import without error
- ✓ Docstrings present and accessible

---

### Test 1.3: Modified create_grid_3d Integration
**Objective:** Verify conditional logic for EasyMesh vs legacy shypre

```bash
docker run --rm surf_shyfem:x86_64-v2.0.4-easymesh python3 << 'EOF'
from surf_shyfem.preprocessing.core.meshing.create_grid_3d import create_grid_3d
import inspect

# Check signature includes config parameter
sig = inspect.signature(create_grid_3d)
print(f"Function signature: {sig}")
print(f"Parameters: {list(sig.parameters.keys())}")

# Should include 'config' parameter
if 'config' in sig.parameters:
    print("✓ Config parameter present")
else:
    print("✗ Config parameter missing")
EOF

# Expected: config parameter in signature
```

**Pass Criteria:**
- ✓ `config` parameter present in function signature
- ✓ Backward compatibility maintained (all original params still present)

---

## Phase 2: Configuration Tests

### Test 2.1: Config File Format
**Objective:** Verify SURF config accepts EasyMesh settings

**Valid Configuration (EasyMesh Enabled):**
```json
{
  "meshing": {
    "use_easymesh": true,
    "easymesh": {
      "resolution": {
        "sizemin": 100.0,
        "sizemax": 5000.0
      },
      "optimize_bandwidth": true,
      "refine_bathymetry": false,
      "gradient_threshold": 0.1
    }
  }
}
```

**Valid Configuration (Legacy shypre - Fallback):**
```json
{
  "meshing": {
    "use_easymesh": false
  }
}
```

**Test:**
```bash
# Save one of the above configs to file and pass to SURF
curl -X POST http://127.0.0.1:9005/api/simulation/create \
  -H "Content-Type: application/json" \
  -d @config.json
```

**Pass Criteria:**
- ✓ Config accepted without validation errors
- ✓ SURF echoes back config in response

---

## Phase 3: Integration Tests (SURF-Level)

### Test 3.1: Mesh Generation with EasyMesh
**Objective:** Run SURF simulation STEP 1 (grid generation) using EasyMesh

**Setup:**
```bash
# 1. Prepare test config with EasyMesh enabled
cat > test_config.json << 'EOF'
{
  "domain": "porto_potenza",
  "simulation_type": "hindcast",
  "date_start": "2022-01-15",
  "date_end": "2022-01-16",
  "duration_hours": 24,
  "output_frequency_hours": 1,
  "meshing": {
    "use_easymesh": true,
    "easymesh": {
      "resolution": {
        "sizemin": 500.0,
        "sizemax": 8000.0
      },
      "optimize_bandwidth": true,
      "refine_bathymetry": false
    }
  }
}
EOF

# 2. Submit simulation via SURF API
RESPONSE=$(curl -s -X POST http://127.0.0.1:9005/api/simulation/create \
  -H "Content-Type: application/json" \
  -d @test_config.json)

SIM_ID=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['simulation_id'])")
echo "Simulation ID: $SIM_ID"

# 3. Monitor Step 1 progress
for i in {1..30}; do
  STATUS=$(curl -s http://127.0.0.1:9005/api/simulation/status/${SIM_ID}/)
  STEP=$(echo $STATUS | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('current_step', 'unknown'))")
  PROGRESS=$(echo $STATUS | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('current_step_progress', 0))")
  
  echo "[$i] Step: $STEP, Progress: $PROGRESS%"
  
  if [[ "$STEP" == "STEP_2" || "$STEP" == "COMPLETED" ]]; then
    echo "Step 1 completed!"
    break
  fi
  
  sleep 5
done
```

**Expected Output:**
```
Simulation ID: sim_20260328_001
[1] Step: STEP_1, Progress: 0%
[2] Step: STEP_1, Progress: 15%
[3] Step: STEP_1, Progress: 42%
[4] Step: STEP_1, Progress: 87%
[5] Step: STEP_1, Progress: 100%
[6] Step: STEP_2, Progress: 0%
Step 1 completed!
```

**Pass Criteria:**
- ✓ Simulation created successfully
- ✓ STEP 1 shows progress updates (not stuck on 0%)
- ✓ STEP 1 completes within 5-10 minutes
- ✓ No HTTP 500 errors in status API calls
- ✓ Advances to STEP 2 (preprocessing complete)

**Failure Modes:**
| Error | Likely Cause | Fix |
|-------|-------------|-----|
| HTTP 500 on creation | Config format wrong | Validate JSON, check easymesh params |
| STEP 1 stuck at 0% | Mesh generation crashing | Check logs: `journalctl -u oceansar-backend -f` |
| "EasyMesh not found" | Module not installed | Rebuild image, verify pip install |
| STEP 1 timeout (>15min) | Mesh too complex or system overloaded | Reduce `sizemin`, increase `sizemax`, free disk space |

---

### Test 3.2: Mesh File Validation
**Objective:** Verify output mesh files (grid_3d.grd, grid_3d.bas) are correctly generated

```bash
# After STEP 1 completes, check mesh files exist in simulation directory
# Inside container:
docker exec <container_id> ls -lh /app/data/simulations/${SIM_ID}/step_1/

# Expected output:
# grid_3d.grd   (ASCII file, 5-50 MB depending on domain)
# grid_3d.bas   (binary file, 10-100 MB depending on domain)
# grid_3d.log   (log file, ~1 KB)

# Validate ASCII grid file format
docker exec <container_id> head -20 /app/data/simulations/${SIM_ID}/step_1/grid_3d.grd | \
  grep -E "^[0-9]+ [0-9]+ [0-9.]+ [0-9.]+ [0-9.]+$"

# Expected: Multiple lines with 5 numbers (node_id, element_type, x, y, z)
```

**Pass Criteria:**
- ✓ Both `grid_3d.grd` and `grid_3d.bas` exist
- ✓ Files have expected sizes (not 0 bytes, not suspiciously small)
- ✓ ASCII grid file contains valid node coordinates
- ✓ Binary bas file is readable (no obvious corruption)

---

### Test 3.3: Full Simulation Run (Optional)
**Objective:** Complete full SURF simulation using EasyMesh-generated mesh

**Setup:**
```bash
# Use same config as Test 3.1, but monitor full run
# Dashboard: http://161.9.255.154/surfapp/dashboard/

# Or use API polling:
SIM_ID="sim_20260328_001"  # From Test 3.1

# Run until completion or error
while true; do
  STATUS=$(curl -s http://127.0.0.1:9005/api/simulation/status/${SIM_ID}/)
  STEP=$(echo $STATUS | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('current_step'))")
  ERROR=$(echo $STATUS | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('error', ''))")
  
  echo "[$(date)] Step: $STEP"
  
  if [[ ! -z "$ERROR" ]]; then
    echo "ERROR: $ERROR"
    break
  fi
  
  if [[ "$STEP" == "COMPLETED" ]]; then
    echo "SUCCESS: Simulation complete!"
    break
  fi
  
  sleep 10
done
```

**Expected Timeline:**
- STEP_1 (Mesh generation): 5-15 minutes
- STEP_2 (Data preprocessing): 10-20 minutes
- STEP_3 (Solver initialization): 2-5 minutes
- STEP_4 (Simulation): 30-60 minutes
- **Total: ~1-2 hours**

**Pass Criteria:**
- ✓ No errors in any step
- ✓ Solver executes successfully with EasyMesh grid
- ✓ Output files (netCDF) generated correctly
- ✓ Results can be visualized (if visualization available)

---

## Phase 4: Comparison Tests

### Test 4.1: EasyMesh vs Legacy Shypre
**Objective:** Compare mesh quality and performance

**Setup - Run Two Simulations:**

**Simulation A - EasyMesh:**
```json
{"meshing": {"use_easymesh": true, "easymesh": {"resolution": {"sizemin": 500, "sizemax": 8000}}}}
```

**Simulation B - Legacy:**
```json
{"meshing": {"use_easymesh": false}}
```

**Comparison Metrics:**

| Metric | Command | Expected |
|--------|---------|----------|
| **Mesh node count** | `wc -l grid_3d.grd` | EasyMesh ≈ shypre (±5%) |
| **Generation time** | Compare STEP_1 duration | EasyMesh faster (target: 20-30% speedup) |
| **Solver convergence** | Final error tolerance | Both similar |
| **Output accuracy** | Compare netCDF results | Within 5% agreement on key vars |
| **Memory usage** | `docker stats` | EasyMesh slightly higher (Python) |

**Pass Criteria:**
- ✓ Mesh statistics within 5% of legacy shypre
- ✓ EasyMesh generation time ≤ legacy time
- ✓ Solver produces valid output
- ✓ Results spatially coherent (no NaN/Inf values)

---

## Phase 5: Rollback Tests

### Test 5.1: Revert to Legacy Shypre
**Objective:** Verify rollback procedure works

```bash
# 1. Stop running SURF instance
~/oceansar-manage.sh stop

# 2. Revert to original image in compose or deployment
docker tag surf_shyfem:x86_64-v2.0.4 surf_shyfem:x86_64-v2.0.4-backup-easymesh
# Then restart with original image...

# 3. Test with legacy config
curl -X POST http://127.0.0.1:9005/api/simulation/create \
  -H "Content-Type: application/json" \
  -d '{"meshing": {"use_easymesh": false}}'

# 4. Verify STEP 1 runs with shypre (monitor logs)
journalctl -u oceansar-backend -f | grep "shypre"
```

**Pass Criteria:**
- ✓ Service restarts without errors
- ✓ Simulation runs with legacy shypre
- ✓ No trace of EasyMesh code execution in logs

---

## Troubleshooting Guide

### Problem: "ModuleNotFoundError: No module named 'easymesh'"

**Diagnosis:**
```bash
docker run --rm surf_shyfem:x86_64-v2.0.4-easymesh python3 -m pip list | grep -i easymesh
```

**Solution:**
- Verify Dockerfile includes: `RUN pip install --no-cache-dir easymesh`
- Rebuild image: `docker build -t surf_shyfem:x86_64-v2.0.4-easymesh .`
- Or: `pip install easymesh` inside running container (temporary)

---

### Problem: "STEP 1 stuck at 0% for >15 minutes"

**Diagnosis:**
```bash
# Check logs for errors
curl http://127.0.0.1:9005/api/simulation/status/${SIM_ID}/
# Look for 'error' field

# Check container logs
docker logs -f <container_id> | grep -i "error\|exception\|mesh"
```

**Common Causes & Fixes:**
1. **Disk full (93% usage)**
   - Clean tmp: `docker exec <cid> rm -rf /tmp/*`
   - Clean logs: `docker exec <cid> truncate -s 0 /var/log/messages`

2. **EasyMesh crashes silently**
   - Reduce `sizemax` parameter (coarser mesh)
   - Increase `sizemin` (fewer nodes)
   - Enable `optimize_bandwidth: false` (skip optimization)

3. **Bathymetry data invalid**
   - Check input bathymetry file exists
   - Verify coordinates match domain bounds
   - Try test domain known to work (Porto Potenza)

---

### Problem: "STEP 1 completes but mesh has 0 nodes/elements"

**Diagnosis:**
```bash
docker exec <cid> ls -lh /app/data/simulations/${SIM_ID}/step_1/grid_3d.grd
# If file size is <1KB → likely generation failed
```

**Solution:**
- Check for errors in grid generation log
- Verify domain shapefile is valid (2D mesh succeeds but 3D fails)
- Try with `refine_bathymetry: false`
- Increase elevation offset if bathymetry too shallow

---

### Problem: "STEP 2 or later returns different results vs legacy shypre"

**Diagnosis:**
```bash
# Compare node coordinates
diff -u legacy_run/grid_3d.grd easymesh_run/grid_3d.grd | head -50
```

**Solution:**
- Small differences (<5%) are normal and expected
- If >10% difference: check `sizemin`/`sizemax` parameters
- Verify both runs use exact same bathymetry and domain
- Run 10+ simulations and average results (variability normal)

---

## Success Criteria - Full Integration

**All of the following must be TRUE:**

1. ✅ **Container Tests (Phase 1)**: 3/3 pass
2. ✅ **Configuration (Phase 2)**: Valid JSON, no parsing errors
3. ✅ **SURF Integration (Phase 3)**: Test 3.1 STEP 1 completes without errors
4. ✅ **Mesh Validation (Phase 3)**: Mesh files generated with expected formats
5. ✅ **Full Run (Phase 3)**: Optional but recommended, all 4 steps complete
6. ✅ **Comparison (Phase 4)**: EasyMesh ≥ performance of legacy shypre
7. ✅ **Rollback (Phase 5)**: Can revert to legacy without issues

---

## Post-Integration Actions

**After all tests pass:**

1. **Document Results**
   - Save test run logs
   - Record mesh statistics (node count, element count)
   - Note performance metrics (generation time, solver time)

2. **Promote to Production**
   - Tag new image: `docker tag surf_shyfem:x86_64-v2.0.4-easymesh surf_shyfem:latest`
   - Update deployment script to use new tag
   - Notify users that EasyMesh is now default

3. **Monitor for Regressions**
   - Keep legacy mode available as fallback
   - Monitor STEP 1 duration (alert if >20min)
   - Check mesh quality metrics over time

4. **Cleanup**
   - Archive test logs
   - Free disk space (current 93% is critical)
   - Remove temporary Docker images

---

## Contact & Support

If tests fail or issues arise:
1. Review logs in `/tmp/surf_easymesh_deploy_*/`
2. Check EasyMesh documentation: https://cmcc-foundation.github.io/easymesh
3. Verify system resources (disk, memory, CPU)
4. Consider rollback to legacy shypre as immediate fix

