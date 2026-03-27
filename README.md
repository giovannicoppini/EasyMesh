# EasyMesh

EasyMesh integration package for SURF SHYFEM v2.0.4.

## Contents

- `easymesh_3d.py`: EasyMesh wrapper module used by SHYFEM preprocessing.
- `create_grid_3d_modified.py`: patched meshing orchestration.
- `deploy_easymesh.sh`: deployment helper script.
- `Dockerfile.patch`: manual Dockerfile instructions.
- `README_DEPLOYMENT.md`: detailed deployment notes.
- `TESTING_GUIDE.md`: validation steps.

## Quick Install (from this repo)

```bash
git clone https://github.com/giovannicoppini/EasyMesh.git
cd EasyMesh
chmod +x deploy_easymesh.sh
```

## Quick Run (SHYFEM only)

Run on the SHYFEM host where image `surf_shyfem:x86_64-v2.0.4` exists:

```bash
bash deploy_easymesh.sh
```

Then enable EasyMesh in simulation config:

```json
{
	"meshing": {
		"use_easymesh": true
	}
}
```

## Notes

- This package is for **SURF SHYFEM** deployment, not NEMO.
- Rollback is immediate by setting `"use_easymesh": false`.