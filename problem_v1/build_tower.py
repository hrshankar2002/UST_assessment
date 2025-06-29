from __future__ import annotations
import json
from pathlib import Path
from typing import List

import numpy as np
import trimesh
from trimesh.creation import cylinder, box


# ───────────────────────────── Configurable constants ─────────────────────────
GAP_TOP_FACTOR = 0.6        # gap between the two top rings = GAP_TOP_FACTOR × antenna_height


# ────────────────────────────── Helper primitives ─────────────────────────────
def tube(a: np.ndarray, b: np.ndarray, r: float, sec: int = 24):
    v = b - a
    L = np.linalg.norm(v)
    if L < 1e-9:
        return None
    m = cylinder(radius=r, height=L, sections=sec)
    m.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], v / L))
    m.apply_translation(a + v / 2)
    return m


def box_beam(a: np.ndarray, b: np.ndarray,
             thk_z: float, thk_y: float) -> trimesh.Trimesh | None:
    v = b - a
    L = np.linalg.norm(v)
    if L < 1e-9:
        return None
    bm = box(extents=[L, thk_y, thk_z])            # long axis local +X
    bm.apply_translation([L / 2, 0, 0])
    bm.apply_transform(trimesh.geometry.align_vectors([1, 0, 0], v / L))
    bm.apply_translation(a)
    return bm


def tri_xy(r: float):
    ang = np.deg2rad([30, 150, 270])
    return np.column_stack((np.cos(ang), np.sin(ang))) * r


def make_half_cyl(r: float, h: float, sec: int = 32) -> trimesh.Trimesh:
    """Half-cylinder: axis +Z, curved face +X, flat face –X."""
    full = cylinder(radius=r, height=h, sections=sec)
    v, f = full.vertices, full.faces
    keep = f[np.any(v[f][:, :, 0] >= -1e-6, axis=1)]      # x ≥ 0
    mesh = trimesh.Trimesh(vertices=v.copy(), faces=keep, process=False)
    mesh.remove_unreferenced_vertices()
    return mesh


# ─────────────────────────────── Main builder ────────────────────────────────
def build(cfg_path: str | Path, out_path: str | Path = "tower.glb"):
    cfg = json.loads(Path(cfg_path).read_text())

    # —— JSON parameters ——
    pole_h  = float(cfg["pole_height"])
    pole_r  = float(cfg["pole_radius"])
    top_r   = float(cfg["antenna_distance_from_pole"])
    ant_h   = float(cfg["antenna_height"])
    counts  = {k.upper(): int(v) for k, v in cfg["antennas"].items()}
    levels  = int(cfg.get("num_levels", 4))

    # —— derived dimensions ——
    tube_r  = pole_r * 0.40
    beam_z  = pole_r * 0.70
    beam_y  = pole_r * 0.08
    ant_r   = pole_r * 0.15

    gap_top = GAP_TOP_FACTOR * ant_h        # distance between the two rings
    z_top   = pole_h                        # Ring 0
    z_mid   = z_top - gap_top               # Ring 1

    level_gap = pole_h * 0.15               # spacing to next tubular level
    inner_r0  = pole_r * 3.0

    parts: List[trimesh.Trimesh] = []

    # ── central pole ──
    pole = cylinder(radius=pole_r, height=pole_h)
    pole.apply_translation([0, 0, pole_h / 2])
    parts.append(pole)

    # ── build the TWO top rings (box beams) ──
    for z_ring in (z_top, z_mid):
        ring_xy  = tri_xy(top_r)
        ring_3d  = np.column_stack((ring_xy, np.full(3, z_ring)))
        for i in range(3):
            parts.append(box_beam(ring_3d[i], ring_3d[(i+1)%3], beam_z, beam_y))
            parts.append(tube(ring_3d[i], np.array([0,0,z_ring]), tube_r*0.8))

    # vertical tubes that tie Ring 0 ↔ Ring 1 at the vertices
    top_xy = tri_xy(top_r)
    ring0 = np.column_stack((top_xy, np.full(3, z_top)))
    ring1 = np.column_stack((top_xy, np.full(3, z_mid)))
    for i in range(3):
        parts.append(tube(ring0[i], ring1[i], tube_r*0.7))

    # ── lower tubular levels (start after the mid ring) ──
    for lvl in range(1, levels):                          # unchanged logic
        z = pole_h - lvl * level_gap
        if z >= z_mid - 1e-6:     # skip if would overlap mid ring
            continue
        r_in  = inner_r0 * (1 - 0.10 * lvl)
        r_out = top_r    * (1 - 0.05 * lvl)

        in_xy, out_xy = tri_xy(r_in), tri_xy(r_out)
        in_3d  = np.column_stack((in_xy,  np.full(3, z)))
        out_3d = np.column_stack((out_xy, np.full(3, z)))

        for i in range(3):
            parts.extend([tube(in_3d[i], in_3d[(i+1)%3], tube_r),
                          tube(out_3d[i], out_3d[(i+1)%3], tube_r),
                          tube(in_3d[i],  out_3d[i],        tube_r*0.8),
                          tube(in_3d[i],  np.array([0,0,z]), tube_r*0.8)])

    # ── antennas — stationed midway between Ring 0 & Ring 1 ──
    z_ant   = (z_top + z_mid) / 2                 # vertical centre
    mount_off = beam_y / 2 + ant_r                # move outward to clear beam
    placed = 0

    for edge_idx, side in enumerate(["A", "B", "C"]):
        n = counts.get(side, 0)
        if n <= 0:
            continue

        v0, v1 = ring0[edge_idx], ring0[(edge_idx+1)%3]
        edge_vec = v1 - v0
        edge_len = np.linalg.norm(edge_vec)
        edge_dir = edge_vec / edge_len

        # outward normal of beam side
        normal = np.cross(edge_dir, [0, 0, 1])
        normal /= np.linalg.norm(normal)

        # rotate: curved face (+X) → -normal (so curve hugs Ring 0)
        R_align = trimesh.geometry.align_vectors([1, 0, 0], -normal)

        for k in range(n):
            t = (k + 1) / (n + 1)
            anchor = v0 + edge_vec * t
            pos = anchor + normal * mount_off
            pos[2] = z_ant

            ant = make_half_cyl(ant_r, ant_h)
            ant.apply_transform(R_align)
            ant.apply_translation(pos)
            parts.append(ant)
            placed += 1

    # ── export ──
    parts = [p for p in parts if p is not None]
    scene = trimesh.util.concatenate(parts)
    scene.apply_transform(
        trimesh.transformations.rotation_matrix(np.radians(-90), [1, 0, 0]))
    scene.export(str(out_path))

    print(f"[✓] Tower exported → {out_path}")
    print(f"    Antennas placed: {placed} "
          f"(A={counts.get('A',0)}, B={counts.get('B',0)}, C={counts.get('C',0)})")


# ───────────────────────────── CLI entrypoint ────────────────────────────────
if __name__ == "__main__":
    import argparse, sys
    p = argparse.ArgumentParser(description="Build triangular-tower GLB")
    p.add_argument("config", help="Path to JSON configuration")
    p.add_argument("output", nargs="?", default="tower.glb",
                   help="Output GLB (default tower.glb)")
    args = p.parse_args()
    try:
        build(args.config, args.output)
    except Exception as err:
        print("[✗] Build failed:", err, file=sys.stderr)
        sys.exit(1)
