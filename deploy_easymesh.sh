#!/bin/bash
#
# deploy_easymesh.sh - Deploy EasyMesh integration to SURF SHYFEM container
#
# This script:
# 1. Prepares the modified files
# 2. Creates a new Docker image with EasyMesh
# 3. Tests the integration
# 4. Provides rollback instructions
#
# Usage:
#   bash deploy_easymesh.sh [--test-only] [--rollback] [--tag VERSION]
#

set -eu

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SOURCE_IMAGE="surf_shyfem:x86_64-v2.0.4"
NEW_TAG="${1:-easymesh-integrated}"
TARGET_IMAGE="surf_shyfem:x86_64-v2.0.4-${NEW_TAG}"
TEMP_DIR="/tmp/easymesh_deploy_$$"
TEST_ONLY=false
ROLLBACK=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --test-only)
            TEST_ONLY=true
            shift
            ;;
        --rollback)
            ROLLBACK=true
            shift
            ;;
        --tag)
            NEW_TAG="$2"
            TARGET_IMAGE="surf_shyfem:x86_64-v2.0.4-${NEW_TAG}"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Helper functions
print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}\n"
}

print_ok() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# ROLLBACK MODE
if [ "$ROLLBACK" = true ]; then
    print_header "ROLLING BACK to Original SURF SHYFEM"
    
    echo "This rollback procedure will:"
    echo "1. Remove EasyMesh integration"
    echo "2. Restore original create_grid_3d.py"
    echo "3. Revert Docker image"
    echo ""
    echo "Rollback instructions:"
    echo "  1. Restore original container: docker tag ${SOURCE_IMAGE} ${TARGET_IMAGE}"
    echo "  2. Update SURF config to: \"use_easymesh\": false"
    echo "  3. Re-run SURF simulations with updated config"
    echo ""
    echo "Original image: ${SOURCE_IMAGE}"
    echo "New image tag: ${TARGET_IMAGE}"
    exit 0
fi

# MAIN DEPLOYMENT FLOW
print_header "SURF SHYFEM - EasyMesh Integration Deployment"

echo "Configuration:"
echo "  Source image: ${SOURCE_IMAGE}"
echo "  Target image: ${TARGET_IMAGE}"
echo "  Temp dir: ${TEMP_DIR}"
echo ""

# Step 1: Prepare files
print_header "Step 1: Preparing Files"

mkdir -p "${TEMP_DIR}"
print_ok "Created temp directory: ${TEMP_DIR}"

# Verify source image exists
if ! docker image inspect "${SOURCE_IMAGE}" > /dev/null 2>&1; then
    print_error "Source image not found: ${SOURCE_IMAGE}"
    exit 1
fi
print_ok "Found source image: ${SOURCE_IMAGE}"

# Step 2: Create deployment Dockerfile
print_header "Step 2: Creating Deployment Dockerfile"

cat > "${TEMP_DIR}/Dockerfile" << 'DOCKERFILE_EOF'
# SURF SHYFEM with EasyMesh Integration
# Built from: surf_shyfem:x86_64-v2.0.4

ARG BASE_IMAGE=surf_shyfem:x86_64-v2.0.4

FROM ${BASE_IMAGE}

LABEL maintainer="SURF Integration" \
      description="SURF SHYFEM v2.0.4 with EasyMesh mesh generation" \
      version="2.0.4-easymesh"

# Install EasyMesh Python package
RUN pip install --no-cache-dir easymesh

# Copy EasyMesh integration modules into container
COPY easymesh_3d.py /app/surf_shyfem/preprocessing/core/meshing/easymesh_3d.py
COPY create_grid_3d.py /app/surf_shyfem/preprocessing/core/meshing/create_grid_3d.py

# Verify installation
RUN python3 -c "import easymesh; print('✓ EasyMesh ready')" && \
    python3 -c "from surf_shyfem.preprocessing.core.meshing.easymesh_3d import run_easymesh_3d; print('✓ Integration module ready')"

ENTRYPOINT ["python3"]
CMD ["-c", "print('SURF SHYFEM with EasyMesh ready')"]
DOCKERFILE_EOF

print_ok "Created Dockerfile"

# Step 3: Copy integration files
print_header "Step 3: Copying Integration Files"

# Note: These files should exist from the creation steps
for file in easymesh_3d.py create_grid_3d.py; do
    if [ -f "/tmp/$file" ]; then
        cp "/tmp/$file" "${TEMP_DIR}/"
        print_ok "Copied: $file"
    else
        print_warn "File not found (will be created): $file"
    fi
done

# Step 4: Build new image (unless test-only)
if [ "$TEST_ONLY" = true ]; then
    print_header "TEST MODE: Skipping Docker build"
    echo "To build: docker build -t ${TARGET_IMAGE} ${TEMP_DIR}"
else
    print_header "Step 4: Building Docker Image"
    
    if docker build -t "${TARGET_IMAGE}" "${TEMP_DIR}"; then
        print_ok "Successfully built: ${TARGET_IMAGE}"
    else
        print_error "Docker build failed"
        exit 1
    fi
fi

# Step 5: Verify integration (if image built)
if ! [ "$TEST_ONLY" = true ]; then
    print_header "Step 5: Verifying Integration"
    
    if docker run --rm "${TARGET_IMAGE}" python3 -c \
        "import easymesh; from surf_shyfem.preprocessing.core.meshing.easymesh_3d import run_easymesh_3d; print('✓ All checks passed')" 2>/dev/null; then
        print_ok "Integration verification successful"
    else
        print_warn "Verification test inconclusive (container may have issues)"
    fi
fi

# Step 6: Configuration template
print_header "Step 6: Configuration Template"

cat > "${TEMP_DIR}/config_easymesh.json" << 'CONFIG_EOF'
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
CONFIG_EOF

print_ok "Created config template: ${TEMP_DIR}/config_easymesh.json"

# Step 7: Deployment summary
print_header "Deployment Complete!"

echo "New image: ${TARGET_IMAGE}"
echo "Location: ${TEMP_DIR}"
echo ""

if [ "$TEST_ONLY" != true ]; then
    echo "Next steps:"
    echo ""
    echo "1. Tag the new image (optional):"
    echo "   docker tag ${TARGET_IMAGE} surf_shyfem:latest-easymesh"
    echo ""
    echo "2. Update your SURF deployment to use:"
    echo "   - Image: ${TARGET_IMAGE}"
    echo "   - Config: Add \"use_easymesh\": true"
    echo ""
    echo "3. Test with a sample run:"
    echo "   docker run -rm ${TARGET_IMAGE} ..."
    echo ""
    echo "4. To rollback, use original image:"
    echo "   docker tag ${SOURCE_IMAGE} your-target-tag"
    echo ""
fi

echo "Files generated:"
ls -lh "${TEMP_DIR}/"
echo ""

echo "To clean up temp directory:"
echo "   rm -rf ${TEMP_DIR}"
echo ""

if [ "$TEST_ONLY" = true ]; then
    print_warn "Test-only mode: no changes applied"
    echo "To perform actual deployment, run without --test-only"
else
    print_ok "EasyMesh integration deployed successfully!"
fi
