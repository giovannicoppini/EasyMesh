"""
MODIFIED: create_grid_3d.py - Integrated with EasyMesh support

This is the modified version with EasyMesh integration.
To use: Replace /app/surf_shyfem/preprocessing/core/meshing/create_grid_3d.py
"""

import logging
from typing import Dict, Any

from surf_shyfem.utils.execute import execute
from surf_shyfem.utils.tmp import tmpdir

logger = logging.getLogger(__name__)


def create_grid_3d(
    path_fembin,
    path_bin,
    src_bathymetry_path,
    src_bathymetry_filename,
    src_path_mesh,
    src_filename_mesh,
    dst_path_mesh,
    config: Dict[str, Any] = None,  # NEW: for EasyMesh config
):
    """
    Generate 3D grid with optional EasyMesh support.
    
    If config["meshing"]["use_easymesh"] = true: uses EasyMesh for 3D generation
    Otherwise: falls back to legacy shypre (backward compatible)
    """
    
    logger.info("\n\nGenerating 3D grid:")
    
    use_easymesh = False
    if config:
        use_easymesh = config.get("meshing", {}).get("use_easymesh", False)
    
    # Run shypre_grd (always needed - creates binary base file)
    run_shypre_grd(
        src_path=src_bathymetry_path,
        src_filename=src_bathymetry_filename,
        dst_path=dst_path_mesh,
        path_executable=path_fembin,
    )

    # Run shybas_grd (always needed - creates node/element indices)
    run_shybas_grd(
        src_path=dst_path_mesh,
        src_filename=src_bathymetry_filename.replace(".grd", ".bas"),
        dst_path=dst_path_mesh,
        path_executable=path_fembin,
    )

    # Generate 3D grid: use EasyMesh or shypre
    if use_easymesh:
        logger.info("Using EasyMesh for 3D grid generation (NEW)")
        run_easymesh(
            src_path=src_bathymetry_path,
            src_filename=src_bathymetry_filename,
            dst_path=dst_path_mesh,
            dst_filename=f"{src_filename_mesh.replace('2d', '3d')}.grd",
            config=config,
        )
    else:
        logger.info("Using legacy shypre for 3D grid generation")
        run_shypre(
            src_path=src_bathymetry_path,
            src_filename=src_bathymetry_filename,
            dst_path=dst_path_mesh,
            dst_filename=f"{src_filename_mesh.replace('2d', '3d')}.grd",
            path_executable=path_bin,
        )


@tmpdir
def run_shypre_grd(
        src_path, src_filename, dst_path, path_executable,
):
    """
    Use the bathymetry (already interpolated to the mesh) to create the 3D <bath
y_name>.bas file
    """

    logfile = "shypre_grd.log"
    command = f"./shypre_grd {src_filename}"

    input_files = [
        (path_executable, "shypre_grd"),
        (src_path, src_filename),
    ]
    output_files = [
        (logfile, dst_path),
        (src_filename.replace(".grd", ".bas"), dst_path),
    ]

    execute(
        input_files,
        output_files,
        logfile,
        command,
        shell=True
    )


@tmpdir
def run_shybas_grd(
        src_path, src_filename, dst_path, path_executable,
):
    """
    Create the in_ext_nodes.dat and in_ext_elements.dat using <bathy_name>.bas
    """

    logfile = "shybas_grd.log"
    command = f"./shybas_grd -grd {src_filename}"

    input_files = [
        (path_executable, "shybas_grd"),
        (src_path, src_filename),
    ]
    output_files = [
        (logfile, dst_path),
        ("in_ext_nodes.dat", dst_path),
        ("in_ext_elements.dat", dst_path),
    ]

    execute(
        input_files,
        output_files,
        logfile,
        command,
        shell=True
    )


@tmpdir
def run_easymesh(
        src_path, src_filename, dst_path, dst_filename, config,
):
    """
    Create 3D grid using EasyMesh mesh generator.
    Produces grid_3d.grd and grid_3d.bas compatible with SHYFEM.
    
    NEW: Modern mesh generation replacing legacy shypre.
    """
    
    try:
        from surf_shyfem.preprocessing.core.meshing.easymesh_3d import (
            run_easymesh_3d,
            validate_easymesh_output,
        )
    except ImportError as e:
        logger.error(
            f"Failed to import EasyMesh wrapper: {e}. "
            "Ensure easymesh_3d.py is in mesh generation module."
        )
        raise
    
    logger.info("Generating 3D mesh with EasyMesh...")
    
    run_easymesh_3d(
        src_path=src_path,
        src_filename=src_filename,
        dst_path=dst_path,
        dst_filename=dst_filename,
        config=config,
        logger_obj=logger,
    )
    
    # Validate output
    bas_filename = dst_filename.replace(".grd", ".bas")
    grd_file = f"{dst_path}/{dst_filename}"
    bas_file = f"{dst_path}/{bas_filename}"
    
    if not validate_easymesh_output(grd_file, bas_file, logger_obj=logger):
        raise RuntimeError(f"EasyMesh output validation failed")
    
    logger.info(f"EasyMesh mesh generation complete: {dst_filename}")


@tmpdir
def run_shypre(
        src_path, src_filename, dst_path, dst_filename, path_executable,
):
    """
    Create the 3D <grid_name>_3d.grd and <grid_name>_3d.bas files using <bathy_n
ame>.bas. The <grid_name>_3d.bas
    is the (binary) file that is actually passed to shyfem for the simulation (al
ongside the z-levels)
    
    LEGACY: Original shypre-based approach. Kept for backward compatibility.
    """

    logfile = "shypre.log"
    command = f"mpirun -np 1 ./shypre {src_filename}"

    input_files = [
        (path_executable, "shypre"),
        (src_path, src_filename),
    ]
    output_files = [
        (logfile, dst_path),
        (src_filename, dst_path, dst_filename),
        (src_filename.replace('.grd', '.bas'), dst_path, f"{dst_filename.replace
('.grd', '.bas')}"),                                                                ]

    execute(
        input_files,
        output_files,
        logfile,
        command,
        shell=True
    )
