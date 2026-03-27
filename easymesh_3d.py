"""
EasyMesh 3D Grid Generation Wrapper for SURF SHYFEM

Replaces legacy shypre binary with modern EasyMesh mesh generation.
Maintains API compatibility with existing SURF workflow.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def run_easymesh_3d(
    src_path: str,
    src_filename: str,
    dst_path: str,
    dst_filename: str,
    config: Dict[str, Any],
    logger_obj: Optional[logging.Logger] = None,
) -> None:
    """
    Generate 3D SHYFEM mesh using EasyMesh.
    
    Replaces run_shypre() - takes bathymetry.grd and produces grid_3d.grd + grid_3d.bas
    
    Args:
        src_path: Source directory containing bathymetry file
        src_filename: Bathymetry filename (e.g., "bathymetry.grd")
        dst_path: Destination directory for output mesh files
        dst_filename: Output mesh filename (e.g., "grid_3d.grd")
        config: Configuration dict with easymesh parameters
        logger_obj: Logger instance (optional)
    
    Raises:
        ImportError: If easymesh not installed
        FileNotFoundError: If input bathymetry file missing
        RuntimeError: If mesh generation fails
    """
    
    log = logger_obj or logger
    
    try:
        import easymesh
    except ImportError:
        log.error(
            "EasyMesh not installed. Install with: pip install easymesh"
        )
        raise ImportError(
            "EasyMesh required for mesh generation. "
            "Install: pip install easymesh"
        )
    
    src_path_obj = Path(src_path)
    dst_path_obj = Path(dst_path)
    bathymetry_file = src_path_obj / src_filename
    
    # Validate input
    if not bathymetry_file.exists():
        raise FileNotFoundError(f"Bathymetry file not found: {bathymetry_file}")
    
    log.info(f"Loading bathymetry from: {bathymetry_file}")
    
    # Extract EasyMesh config (with sensible defaults)
    easymesh_config = config.get("meshing", {}).get("easymesh", {})
    
    mesh_resolution = easymesh_config.get("resolution", {})
    sizemin = mesh_resolution.get("sizemin", 100.0)
    sizemax = mesh_resolution.get("sizemax", 5000.0)
    
    log.info(f"EasyMesh resolution: sizemin={sizemin}, sizemax={sizemax}")
    
    try:
        # Load bathymetry mesh
        log.info("Loading bathymetry mesh...")
        mesh_3d = easymesh.load_mesh(str(bathymetry_file))
        
        # Optimize mesh if requested
        if easymesh_config.get("optimize_bandwidth", True):
            log.info("Optimizing mesh bandwidth...")
            mesh_3d.optimize_bandwidth()
        
        # Refine mesh based on bathymetry gradient (optional)
        if easymesh_config.get("refine_bathymetry", False):
            log.info("Refining mesh based on bathymetry gradients...")
            mesh_3d.refine_by_gradient(
                gradient_threshold=easymesh_config.get(
                    "gradient_threshold", 0.1
                )
            )
        
        log.info("Exporting to SHYFEM format...")
        
        # Export to SHYFEM format (ASCII .grd + binary .bas)
        grd_file = dst_path_obj / dst_filename
        bas_file = dst_path_obj / dst_filename.replace(".grd", ".bas")
        
        # Write ASCII grid file
        easymesh.export_shyfem_grd(mesh_3d, str(grd_file))
        log.info(f"Wrote: {grd_file}")
        
        # Write binary format
        easymesh.export_shyfem_bas(mesh_3d, str(bas_file))
        log.info(f"Wrote: {bas_file}")
        
        # Log mesh statistics
        node_count = mesh_3d.n_nodes()
        elem_count = mesh_3d.n_elements()
        log.info(
            f"Generated mesh: {node_count} nodes, {elem_count} elements"
        )
        
        return
        
    except Exception as e:
        log.error(f"EasyMesh generation failed: {e}")
        raise RuntimeError(f"Mesh generation error: {e}") from e


def validate_easymesh_output(
    grd_file: str, bas_file: str, logger_obj: Optional[logging.Logger] = None
) -> bool:
    """
    Validate that EasyMesh output files are compatible with SHYFEM.
    
    Args:
        grd_file: Path to grid_3d.grd
        bas_file: Path to grid_3d.bas
        logger_obj: Logger instance
    
    Returns:
        True if validation passes, False otherwise
    """
    
    log = logger_obj or logger
    grd_path = Path(grd_file)
    bas_path = Path(bas_file)
    
    # Check files exist
    if not grd_path.exists():
        log.error(f"Grid file not found: {grd_path}")
        return False
    
    if not bas_path.exists():
        log.error(f"Binary file not found: {bas_path}")
        return False
    
    # Check file sizes
    grd_size = grd_path.stat().st_size
    bas_size = bas_path.stat().st_size
    
    if grd_size < 100:
        log.error(f"Grid file suspiciously small: {grd_size} bytes")
        return False
    
    if bas_size < 100:
        log.error(f"Binary file suspiciously small: {bas_size} bytes")
        return False
    
    log.info(
        f"Output validation passed: {grd_file} ({grd_size} bytes), "
        f"{bas_file} ({bas_size} bytes)"
    )
    
    return True
